"""The laws.json catalog: document metadata, aliases, and lookup."""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from .errors import ResolveError

AMENDMENT_TITLE_RE = re.compile(
    r"^(endr\.|endringslov|endringsforskrift|forskrift om endring|lov om endring|"
    r"lov om endringer|forskrift om endringer|ikrafts|ikraftt|delvis ikraft|opphev)",
    re.I,
)


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip()


def tokens(s: str) -> list[str]:
    return [t for t in re.split(r"[^0-9a-zæøåäöüé]+", norm(s)) if t]


@dataclass
class Entry:
    refid: str
    kind: str
    path: str
    file: str
    tittel: str
    korttittel: str
    aliases: list[str]
    departement: list[str]
    ikrafttredelse: str
    sist_endret: str
    lovdata: str
    github: str
    amendments: int
    historie: str | None
    eli: str = ""
    names: list[str] = field(default_factory=list)
    alt_names: list[str] = field(default_factory=list)

    @property
    def is_amendment_act(self) -> bool:
        return bool(AMENDMENT_TITLE_RE.match(self.tittel or "")) or bool(
            AMENDMENT_TITLE_RE.match(self.korttittel or "")
        )

    @property
    def display_name(self) -> str:
        return self.korttittel or self.tittel or self.refid

    def historie_path(self) -> str | None:
        if self.historie:
            p = self.historie
            if p.endswith(".html"):
                p = p[: -len(".html")] + ".md"
            return p
        return None

    def summary(self) -> dict:
        return {
            "refid": self.refid,
            "kind": self.kind,
            "title": self.tittel,
            "short_title": self.korttittel,
            "aliases": self.aliases,
            "department": self.departement,
            "path": self.path,
            "in_force": self.ikrafttredelse,
            "last_amended_by": self.sist_endret,
            "amendment_records": self.amendments,
            "lovdata": self.lovdata,
        }


def _short_names(korttittel: str) -> list[str]:
    if not korttittel:
        return []
    parts = re.split(r"\s+[–—-]\s+", korttittel)
    return [norm(p) for p in parts if p.strip()]


def entry_from_json(raw: dict) -> Entry:
    aliases = [a for a in raw.get("aliases") or [] if a]
    dept = raw.get("departement") or []
    if isinstance(dept, str):
        dept = [dept]
    e = Entry(
        refid=raw.get("refid", ""),
        kind=raw.get("kind", ""),
        path=raw.get("path", ""),
        file=raw.get("file", ""),
        tittel=raw.get("tittel", "") or "",
        korttittel=raw.get("korttittel", "") or "",
        aliases=aliases,
        departement=list(dept),
        ikrafttredelse=raw.get("ikrafttredelse", "") or "",
        sist_endret=raw.get("sist_endret", "") or "",
        lovdata=raw.get("lovdata", "") or "",
        github=raw.get("github", "") or "",
        amendments=int(raw.get("amendments") or 0),
        historie=raw.get("historie"),
        eli=raw.get("eli", "") or "",
    )
    names = set(_short_names(e.korttittel))
    if e.korttittel:
        names.add(norm(e.korttittel))
    names.update(norm(a) for a in aliases)
    m = re.search(r"\(([^()]*(?:lov|forskrift)[^()]*)\)\s*$", e.tittel or "", re.I)
    if m and " " not in m.group(1).strip():
        names.add(norm(m.group(1)))
    e.names = sorted(n for n in names if n)
    alts = set()
    for n in e.names:
        stripped = re.sub(r"\s*\([^()]*\)", "", n).strip()
        for cand in (stripped, n.rstrip("."), stripped.rstrip(".")):
            if cand and cand not in names:
                alts.add(cand)
    e.alt_names = sorted(alts)
    return e


def normalize_refid(ref: str) -> str:
    """'LOV-2005-06-17-62', '/eli/lov/2005/06/17/62' -> 'lov/2005-06-17-62'; other strings unchanged."""
    key = norm(ref)
    key = re.sub(r"^https?://lovdata\.no/dokument/[a-z]+/", "", key)
    m = re.match(r"^(lov|forskrift)[-/ _](\d{4}-\d{2}-\d{2}(?:-\d+)?)$", key)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.match(r"^/?eli/(lov|forskrift)/(\d{4})/(\d{2})/(\d{2})(?:/(\d+))?$", key)
    if m:
        return f"{m.group(1)}/{m.group(2)}-{m.group(3)}-{m.group(4)}" + (f"-{m.group(5)}" if m.group(5) else "")
    return key


class Catalog:
    def __init__(self, entries: list[Entry]) -> None:
        self.entries = entries
        self.by_refid: dict[str, Entry] = {}
        self.by_path: dict[str, Entry] = {}
        self.by_name: dict[str, list[Entry]] = {}
        self.by_alt_name: dict[str, list[Entry]] = {}
        for e in entries:
            self.by_refid[norm(e.refid)] = e
            self.by_path[e.path] = e
            self.by_path[e.file] = e
            for n in e.names:
                self.by_name.setdefault(n, []).append(e)
            for n in e.alt_names:
                self.by_alt_name.setdefault(n, []).append(e)

    @classmethod
    def from_json_text(cls, text: str) -> "Catalog":
        raw = json.loads(text)
        return cls([entry_from_json(r) for r in raw])

    def __len__(self) -> int:
        return len(self.entries)

    # -- lookup ------------------------------------------------------------

    def resolve(self, ref: str) -> Entry:
        """Resolve a refid, file path, alias, short title, or title to one entry."""
        if not ref or not ref.strip():
            raise ResolveError("Empty document reference.")
        key = normalize_refid(ref)
        if key in self.by_refid:
            return self.by_refid[key]
        path_key = ref.strip().lstrip("/")
        for cand in (path_key, path_key + ".md"):
            if cand in self.by_path:
                return self.by_path[cand]
            base = cand.rsplit("/", 1)[-1]
            if base in self.by_path:
                return self.by_path[base]
        for table in (self.by_name, self.by_alt_name):
            if key in table:
                hits = sorted(table[key], key=lambda e: (e.kind != "lov", e.is_amendment_act, e.refid))
                return hits[0]
        results = self.search(ref, limit=5)
        if results and results[0][0] >= 80 and (len(results) == 1 or results[1][0] <= results[0][0] - 10):
            return results[0][1]
        suggestions = ", ".join(f"{e.refid} ({e.display_name})" for _, e in results)
        raise ResolveError(
            f"No document matches '{ref}'. "
            + (f"Closest: {suggestions}. " if suggestions else "")
            + "Use laws_search_documents to find the refid."
        )

    def search(
        self,
        query: str,
        kind: str | None = None,
        limit: int = 20,
        include_amendment_acts: bool = True,
    ) -> list[tuple[float, Entry]]:
        q = normalize_refid(query)
        q_tokens = tokens(query)
        if not q:
            return []
        scored: list[tuple[float, Entry]] = []
        for e in self.entries:
            if kind and e.kind != kind:
                continue
            if not include_amendment_acts and e.is_amendment_act:
                continue
            score = self._score(e, q, q_tokens)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda t: (-t[0], t[1].kind != "lov", t[1].is_amendment_act, t[1].refid))
        return scored[:limit]

    @staticmethod
    def _score(e: Entry, q: str, q_tokens: list[str]) -> float:
        refid = norm(e.refid)
        if q == refid:
            return 100
        score = 0.0
        for n in e.names:
            if q == n:
                score = max(score, 95)
            elif n.startswith(q):
                score = max(score, 80)
            elif re.search(r"(?<![0-9a-zæøå])" + re.escape(q), n):
                score = max(score, 70)
            elif len(q) >= 5 and q in n:
                score = max(score, 60)
        for n in e.alt_names:
            if q == n:
                score = max(score, 93)
        title = norm(e.tittel)
        if q and q in title:
            score = max(score, 60 if len(q) > 3 else 30)
        if q_tokens:
            hay = title + " " + " ".join(e.names) + " " + refid
            hay_tokens = set(tokens(hay))
            matched = 0
            for t in q_tokens:
                if t in hay_tokens:
                    matched += 1
                elif len(t) >= 5 and any(ht.startswith(t) or t.startswith(ht) and len(ht) >= 5 for ht in hay_tokens):
                    matched += 0.7
            frac = matched / len(q_tokens)
            if frac == 1 and score < 55:
                score = max(score, 55 if len(q_tokens) > 1 else 50)
            elif frac > 0:
                score = max(score, 40 * frac)
        if score and e.is_amendment_act:
            score -= 5
        return score
