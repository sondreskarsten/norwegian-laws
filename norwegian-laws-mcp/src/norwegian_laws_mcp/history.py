"""Git history, diffs, blame, and parsed amendment records."""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .catalog import Catalog, Entry
from .markdown import Document, get_section, parse_document
from .repo import DOC_DIRS, HISTORIE_DIR, Repo

LOG_FORMAT = "%x1e%H%x1f%ad%x1f%an%x1f%s"


@dataclass
class FileChange:
    path: str
    status: str
    sha: str
    date: str
    subject: str
    old_path: str | None = None


@dataclass
class DocumentChange:
    path: str
    entry: Entry | None
    changes: list[FileChange] = field(default_factory=list)

    @property
    def first_date(self) -> str:
        return min(c.date for c in self.changes)

    @property
    def last_date(self) -> str:
        return max(c.date for c in self.changes)

    @property
    def statuses(self) -> str:
        order = []
        for c in self.changes:
            if c.status not in order:
                order.append(c.status)
        return "".join(order)


STATUS_WORDS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied", "T": "type-changed"}


def parse_name_status_log(out: str) -> list[FileChange]:
    changes: list[FileChange] = []
    for block in out.split("\x1e"):
        block = block.strip("\n")
        if not block:
            continue
        header, _, body = block.partition("\n")
        parts = header.split("\x1f")
        if len(parts) < 4:
            continue
        sha, date, _author, subject = parts[0], parts[1], parts[2], parts[3]
        for line in body.split("\n"):
            if not line.strip():
                continue
            cols = line.split("\t")
            status = cols[0][0]
            if status in ("R", "C") and len(cols) >= 3:
                changes.append(FileChange(cols[2], status, sha, date, subject, old_path=cols[1]))
            elif len(cols) >= 2:
                changes.append(FileChange(cols[1], status, sha, date, subject))
    return changes


def changes_between(
    repo: Repo,
    *,
    since: str | None,
    until: str | None,
    paths: list[str],
    max_commits: int | None = None,
) -> list[FileChange]:
    args = ["log", "--date=iso-strict", f"--format={LOG_FORMAT}", "--name-status", "--no-renames"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    if max_commits:
        args.append(f"-n{max_commits}")
    args += ["HEAD", "--", *paths]
    return parse_name_status_log(repo.git(*args))


def group_by_document(changes: list[FileChange], catalog: Catalog) -> list[DocumentChange]:
    grouped: dict[str, DocumentChange] = {}
    for c in changes:
        dc = grouped.get(c.path)
        if dc is None:
            dc = DocumentChange(c.path, catalog.by_path.get(c.path))
            grouped[c.path] = dc
        dc.changes.append(c)
    return sorted(grouped.values(), key=lambda d: (-len(d.changes), d.path))


def doc_paths_from_entries(entries: list[Entry], include_historie: bool) -> list[str]:
    paths = [e.path for e in entries]
    if include_historie:
        paths += [p for p in (e.historie_path() for e in entries) if p]
        paths += [f"{HISTORIE_DIR}/{e.file}" for e in entries]
    return sorted(set(paths))


def document_log(repo: Repo, path: str, *, since: str | None, until: str | None, limit: int) -> list[dict]:
    args = ["log", "--date=iso-strict", f"--format={LOG_FORMAT}", "--numstat", f"-n{limit}"]
    if since:
        args.append(f"--since={since}")
    if until:
        args.append(f"--until={until}")
    args += ["HEAD", "--", path]
    out = repo.git(*args)
    commits: list[dict] = []
    for block in out.split("\x1e"):
        block = block.strip("\n")
        if not block:
            continue
        header, _, body = block.partition("\n")
        parts = header.split("\x1f")
        if len(parts) < 4:
            continue
        added = deleted = 0
        for line in body.split("\n"):
            cols = line.split("\t")
            if len(cols) >= 3 and cols[0].isdigit() and cols[1].isdigit():
                added += int(cols[0])
                deleted += int(cols[1])
        commits.append({"sha": parts[0], "date": parts[1], "subject": parts[3], "added": added, "deleted": deleted})
    return commits


@dataclass
class DiffResult:
    path: str
    from_sha: str
    to_sha: str
    from_date: str
    to_date: str
    diff: str
    section: str | None = None
    existed_before: bool = True
    existed_after: bool = True


def commit_date(repo: Repo, sha: str) -> str:
    return repo.git("log", "-1", "--date=iso-strict", "--format=%ad", sha).strip()


def diff_document(
    repo: Repo,
    path: str,
    *,
    from_rev: str,
    to_rev: str = "HEAD",
    section: str | None = None,
    context: int = 3,
) -> DiffResult:
    a = repo.resolve_rev(from_rev)
    b = repo.resolve_rev(to_rev)
    res = DiffResult(path, a, b, commit_date(repo, a), commit_date(repo, b), "", section)
    old = repo.show(a, path)
    new = repo.show(b, path)
    res.existed_before = old is not None
    res.existed_after = new is not None
    if section:
        old_s = get_section(parse_document(old), section) if old is not None else None
        new_s = get_section(parse_document(new), section) if new is not None else None
        old_lines = old_s.lines if old_s else []
        new_lines = new_s.lines if new_s else []
        res.diff = "\n".join(
            difflib.unified_diff(
                old_lines, new_lines,
                fromfile=f"{path}@{a[:10]} {section}", tofile=f"{path}@{b[:10]} {section}",
                n=context, lineterm="",
            )
        )
        if old_s is None and new_s is None:
            res.diff = ""
        return res
    if old is None and new is None:
        return res
    res.diff = repo.git("diff", f"--unified={context}", "--no-color", a, b, "--", path, check=False)
    return res


@dataclass
class BlameRun:
    sha: str
    date: str
    subject: str
    start: int
    end: int
    first_line: str


def blame_lines(repo: Repo, path: str, start: int, end: int) -> list[BlameRun]:
    out = repo.git("blame", "--line-porcelain", "-L", f"{start},{end}", "HEAD", "--", path)
    runs: list[BlameRun] = []
    cur_sha = None
    cur_meta: dict[str, str] = {}
    line_no = start
    for line in out.split("\n"):
        if re.match(r"^[0-9a-f]{40} \d+ \d+", line):
            cur_sha = line.split()[0]
            cur_meta = {}
        elif line.startswith("\t"):
            content = line[1:]
            date = cur_meta.get("author-time", "")
            if date.isdigit():
                import datetime as _dt
                date = _dt.datetime.fromtimestamp(int(date), tz=_dt.timezone.utc).strftime("%Y-%m-%d")
            subject = cur_meta.get("summary", "")
            if runs and runs[-1].sha == cur_sha and runs[-1].end == line_no - 1:
                runs[-1].end = line_no
            else:
                runs.append(BlameRun(cur_sha or "", date, subject, line_no, line_no, content.strip()[:120]))
            line_no += 1
        elif " " in line:
            k, _, v = line.partition(" ")
            cur_meta[k] = v
    return runs


# -- parsed amendment records (historie/) ----------------------------------


@dataclass
class AmendmentRecord:
    paragraph: str
    date: str
    act: str
    instruction: str
    text: str


RECORD_RE = re.compile(r"^###\s+(\d{4}-\d{2}-\d{2}|[^\s]+)\s+[—–-]+\s+(.+?)\s*$")


def parse_historie(text: str) -> tuple[dict, list[AmendmentRecord]]:
    doc = parse_document(text)
    records: list[AmendmentRecord] = []
    para = ""
    i = 0
    lines = doc.lines
    while i < len(lines):
        line = lines[i]
        if line.startswith("## "):
            para = line[3:].strip()
            i += 1
            continue
        m = RECORD_RE.match(line) if line.startswith("### ") else None
        if m:
            date, act = m.group(1), m.group(2)
            i += 1
            instruction = ""
            body: list[str] = []
            while i < len(lines) and not lines[i].startswith("### ") and not lines[i].startswith("## "):
                l = lines[i]
                if not instruction and l.startswith("*") and l.endswith("*") and len(l) > 2:
                    instruction = l.strip("*").strip()
                elif l.startswith(">"):
                    body.append(l[1:].strip())
                elif l.strip() and not instruction:
                    instruction = l.strip()
                i += 1
            while body and not body[-1]:
                body.pop()
            records.append(AmendmentRecord(para, date, act, instruction, "\n".join(body)))
            continue
        i += 1
    return doc.meta, records


def historie_path_for(repo: Repo, entry: Entry) -> str | None:
    for cand in (entry.historie_path(), f"{HISTORIE_DIR}/{entry.file}"):
        if cand and repo.exists(cand):
            return cand
    return None


def related_paths(entries: list[Entry]) -> list[str]:
    return [e.path for e in entries] or list(DOC_DIRS)
