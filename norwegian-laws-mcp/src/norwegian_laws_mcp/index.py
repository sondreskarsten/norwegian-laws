"""The queryable corpus index (docs/NODE-HISTORY-DESIGN.md) as seen by the server.

The deploy workflow builds ``laws-index.sqlite`` from the same parser output as
the committed Markdown, stamps it with the source manifest digest, the parser
identity and the publication commit, and publishes it gzipped as an asset of
that publication's observation release. The server locates the asset through
``.github/state/publication.json`` on ``main`` (so index and checkout belong to
the same publication), caches it next to the clone, and builds the full-text
table locally on first open. ``NORWEGIAN_LAWS_INDEX=/path/laws-index.sqlite``
points at an index built locally with ``python -m lovdata_publisher.index_build``.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sqlite3
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .errors import LawsError

ENV_INDEX = "NORWEGIAN_LAWS_INDEX"
ASSET_NAME = "laws-index.sqlite.gz"
STATE_FILE = ".github/state/publication.json"
FTS_SQL = "CREATE VIRTUAL TABLE node_fts USING fts5(text, content='node_text', content_rowid='node_id', tokenize='unicode61')"
SQL_ROW_LIMIT = 200
SQL_TIME_LIMIT_S = 20.0
WRITE_ACTIONS = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE,
                 sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA,
                 sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX,
                 sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
                 sqlite3.SQLITE_CREATE_VTABLE, sqlite3.SQLITE_DROP_VTABLE, sqlite3.SQLITE_TRANSACTION,
                 sqlite3.SQLITE_SAVEPOINT, sqlite3.SQLITE_REINDEX, sqlite3.SQLITE_ANALYZE}


class IndexUnavailable(LawsError):
    pass


def normalize_section_ref(spec: str) -> str:
    s = spec.replace("§", "").replace("\xa0", " ").strip().rstrip(".")
    m = re.match(r"^(\d+(?:-\d+)*)\s*([a-zA-Z])?$", s)
    if not m:
        return s.lower().replace(" ", "")
    return m.group(1) + (m.group(2).lower() if m.group(2) else "")


def _read_only_authorizer(action, arg1, arg2, db_name, trigger):
    if action in WRITE_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION and arg2 in ("load_extension", "writefile", "edit", "fts5_rebuild"):
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


@dataclass
class IndexStatus:
    path: str | None
    source: str
    meta: dict
    counts: dict
    publication_source_sha: str | None
    matches_publication: bool | None
    note: str | None = None


class Index:
    """Locate, fetch, prepare and query the corpus index."""

    def __init__(self, repo, cache_dir: Path | None = None) -> None:
        self.repo = repo
        self.cache_dir = cache_dir or (Path(repo.path).parent / "index")
        self._lock = threading.Lock()
        self._path: Path | None = None
        self._note: str | None = None

    # -- location ----------------------------------------------------------

    def publication(self) -> dict:
        try:
            return json.loads(self.repo.read(STATE_FILE))
        except Exception:  # noqa: BLE001 - absent file or unreadable state means no publication
            return {}

    def repository_slug(self) -> str:
        remote = str(getattr(self.repo, "remote", "") or "")
        m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote)
        return m.group(1) if m else "sondreskarsten/norwegian-laws"

    def asset_url(self, publication: dict | None = None) -> str | None:
        pub = publication if publication is not None else self.publication()
        observation = ((pub.get("evidence") or {}).get("observation_id")) or ""
        if not observation:
            return None
        return f"https://github.com/{self.repository_slug()}/releases/download/observation-{observation}/{ASSET_NAME}"

    def path(self) -> Path:
        """The index file, downloading the publication's asset when needed."""
        with self._lock:
            override = os.environ.get(ENV_INDEX)
            if override:
                p = Path(override).expanduser()
                if not p.exists():
                    raise IndexUnavailable(f"{ENV_INDEX} points at {p}, which does not exist")
                if self._path != p:
                    self._path = self._prepare(p)
                return self._path
            if self._path and self._path.exists() and self._path.parent == self.cache_dir:
                return self._path
            pub = self.publication()
            url = self.asset_url(pub)
            if not url:
                raise IndexUnavailable("No published index: the checkout has no acknowledged publication "
                                       "(.github/state/publication.json). Set NORWEGIAN_LAWS_INDEX to a local index.")
            observation = pub["evidence"]["observation_id"]
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            target = self.cache_dir / f"laws-index-{observation[:16]}.sqlite"
            if not target.exists():
                self._download(url, target)
                for old in self.cache_dir.glob("laws-index-*.sqlite"):
                    if old != target:
                        old.unlink(missing_ok=True)
            self._path = self._prepare(target)
            return self._path

    def _download(self, url: str, target: Path) -> None:
        tmp = target.with_suffix(".part")
        try:
            with urllib.request.urlopen(url, timeout=120) as response, gzip.GzipFile(fileobj=response) as stream, \
                    tmp.open("wb") as out:
                shutil.copyfileobj(stream, out, length=1 << 20)
        except Exception as exc:  # noqa: BLE001
            tmp.unlink(missing_ok=True)
            raise IndexUnavailable(f"Could not download the index from {url}: {exc}") from exc
        tmp.replace(target)

    def _prepare(self, path: Path) -> Path:
        """Build the full-text table once; the published asset ships without it."""
        conn = sqlite3.connect(path)
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'node_fts'").fetchone():
                try:
                    conn.execute(FTS_SQL)
                    conn.execute("INSERT INTO node_fts(node_fts) VALUES ('rebuild')")
                    conn.commit()
                except sqlite3.OperationalError as exc:
                    self._note = f"Full-text table not built ({exc}); laws_index_search is unavailable"
        finally:
            conn.close()
        return path

    def connect(self) -> sqlite3.Connection:
        path = self.path()
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # -- queries -----------------------------------------------------------

    def meta(self) -> dict:
        conn = self.connect()
        try:
            return dict(conn.execute("SELECT key, value FROM meta").fetchall())
        finally:
            conn.close()

    def status(self) -> IndexStatus:
        pub = self.publication()
        pub_sha = pub.get("source_sha")
        try:
            path = self.path()
        except IndexUnavailable as exc:
            return IndexStatus(None, "unavailable", {}, {}, pub_sha, None, str(exc))
        conn = self.connect()
        try:
            meta = dict(conn.execute("SELECT key, value FROM meta").fetchall())
            counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                      for t in ("documents", "nodes", "node_text", "amendments", "refs", "definitions")}
            counts["fts"] = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'node_fts'").fetchone())
        finally:
            conn.close()
        source = "env" if os.environ.get(ENV_INDEX) else "release-asset"
        matches = (meta.get("source_sha") == pub_sha) if (pub_sha and meta.get("source_sha")) else None
        return IndexStatus(str(path), source, meta, counts, pub_sha, matches, self._note)

    def document(self, refid: str) -> dict | None:
        conn = self.connect()
        try:
            row = conn.execute("SELECT * FROM documents WHERE refid = ?", (refid,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def outline(self, refid: str) -> list[dict]:
        conn = self.connect()
        try:
            rows = conn.execute(
                "SELECT id, address, kind, heading, parent_id, line_start, line_end FROM nodes "
                "WHERE refid = ? AND kind IN ('chapter', 'section') ORDER BY line_start", (refid,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def provision(self, refid: str, section: str) -> dict | None:
        key = normalize_section_ref(section)
        conn = self.connect()
        try:
            sec = conn.execute("SELECT * FROM nodes WHERE refid = ? AND kind = 'section' AND section_key = ? "
                               "ORDER BY line_start LIMIT 1", (refid, key)).fetchone()
            if not sec:
                return None
            ledd = conn.execute("SELECT n.id, n.address, n.ordinal, t.text FROM nodes n LEFT JOIN node_text t ON t.node_id = n.id "
                                "WHERE n.parent_id = ? AND n.kind = 'ledd' ORDER BY n.ordinal", (sec["id"],)).fetchall()
            items = conn.execute("SELECT n.id, n.address, n.parent_id FROM nodes n WHERE n.kind = 'item' AND n.parent_id IN "
                                 "(SELECT id FROM nodes WHERE parent_id = ?) ORDER BY n.line_start", (sec["id"],)).fetchall()
            return {"section": dict(sec), "ledd": [dict(r) for r in ledd], "items": [dict(r) for r in items]}
        finally:
            conn.close()

    def history(self, refid: str, section: str | None, until: str | None = None, limit: int = 100) -> list[dict]:
        conn = self.connect()
        try:
            sql = ("SELECT a.id, a.act_refid, a.target, a.target_section, a.change_type, a.instruction, a.new_text, "
                   "a.operations, a.date_in_force, a.date_published, ac.title AS act_title, ac.short_title AS act_short_title "
                   "FROM amendments a LEFT JOIN acts ac ON ac.refid = a.act_refid WHERE a.target_law = ?")
            params: list = [refid]
            if section:
                sql += " AND a.target_section = ?"
                params.append(normalize_section_ref(section))
            if until:
                sql += " AND a.date_in_force <= ?"
                params.append(until)
            sql += " ORDER BY a.date_in_force, a.id LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def search(self, query: str, kind: str | None, limit: int) -> list[dict]:
        conn = self.connect()
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'node_fts'").fetchone():
                raise IndexUnavailable("The full-text table is not built in this index")
            sql = ("SELECT n.refid, n.address, d.kind, d.title, d.short_title, bm25(node_fts) AS score, "
                   "snippet(node_fts, 0, '[', ']', '…', 24) AS snippet "
                   "FROM node_fts JOIN nodes n ON n.id = node_fts.rowid JOIN documents d ON d.refid = n.refid "
                   "WHERE node_fts MATCH ?")
            params: list = [query]
            if kind:
                sql += " AND d.kind = ?"
                params.append(kind)
            sql += " ORDER BY score LIMIT ?"
            params.append(limit)
            try:
                return [dict(r) for r in conn.execute(sql, params).fetchall()]
            except sqlite3.OperationalError as exc:
                raise LawsError(f"Full-text query rejected: {exc}. Use words, quoted phrases, AND/OR/NOT, prefix*.") from exc
        finally:
            conn.close()

    def references_to(self, refid: str, section: str | None, limit: int) -> list[dict]:
        conn = self.connect()
        try:
            sql = ("SELECT r.from_refid, n.address AS from_address, d.short_title, d.title, d.kind, r.to_section, r.kind AS ref_kind, r.text "
                   "FROM refs r JOIN nodes n ON n.id = r.from_node_id JOIN documents d ON d.refid = r.from_refid WHERE r.to_refid = ?")
            params: list = [refid]
            if section:
                sql += " AND r.to_section = ?"
                params.append(normalize_section_ref(section))
            sql += " AND r.from_refid != r.to_refid ORDER BY r.from_refid, n.line_start LIMIT ?"
            params.append(limit)
            return [dict(r) for r in conn.execute(sql, params).fetchall()]
        finally:
            conn.close()

    def definitions(self, term: str, limit: int) -> list[dict]:
        conn = self.connect()
        try:
            like = f"%{term.lower()}%"
            rows = conn.execute(
                "SELECT de.term, de.definition, de.refid, n.address, d.short_title, d.title, d.kind FROM definitions de "
                "JOIN nodes n ON n.id = de.node_id JOIN documents d ON d.refid = de.refid "
                "WHERE lower(de.term) LIKE ? ORDER BY (lower(de.term) = ?) DESC, length(de.term), de.refid LIMIT ?",
                (like, term.lower(), limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def sql(self, query: str, limit: int = SQL_ROW_LIMIT) -> dict:
        """Run one read-only SELECT with a row cap and a time limit."""
        stripped = query.strip().rstrip(";").strip()
        if not re.match(r"^(select|with)\b", stripped, re.I):
            raise LawsError("Only a single SELECT (or WITH ... SELECT) statement is allowed")
        if ";" in stripped:
            raise LawsError("One statement at a time")
        conn = self.connect()
        conn.set_authorizer(_read_only_authorizer)
        started = time.monotonic()
        conn.set_progress_handler(lambda: 1 if time.monotonic() - started > SQL_TIME_LIMIT_S else 0, 10000)
        try:
            cursor = conn.execute(stripped)
            columns = [c[0] for c in cursor.description or []]
            rows = cursor.fetchmany(limit + 1)
            truncated = len(rows) > limit
            return {"columns": columns, "rows": [list(r) for r in rows[:limit]], "truncated": truncated,
                    "seconds": round(time.monotonic() - started, 3)}
        except sqlite3.OperationalError as exc:
            if "interrupted" in str(exc).lower():
                raise LawsError(f"Query stopped after {SQL_TIME_LIMIT_S:.0f} s; add a WHERE clause or a LIMIT") from exc
            raise LawsError(f"SQL error: {exc}") from exc
        except sqlite3.DatabaseError as exc:
            raise LawsError(f"SQL rejected: {exc}") from exc
        finally:
            conn.close()
