"""Public navigation to immutable, provenance-checked prior reader copies."""
from __future__ import annotations

import html
from pathlib import Path
import subprocess

from .reader_exits import load_capture_records


def _git(repository, *args):
    result = subprocess.run(["git", "--no-optional-locks", "-C", str(repository), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=60)
    if result.returncode:
        raise ValueError("Reader archive requires complete committed provenance: " +
                         result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def published_captures(repository) -> dict[str, list[dict]]:
    root = Path(repository)
    if not (root / "reader-exits").exists(): return {}
    rows = load_capture_records(root)
    if not rows: return {}
    if _git(root, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ValueError("Reader archive links require full Git history")
    commits = _git(root, "rev-list", "HEAD", "--", "reader-exits/records").decode().splitlines()
    rank = {commit: i for i, commit in enumerate(commits)}
    result = {}
    for row in rows:
        path = f"reader-exits/records/{row['capture_id']}.json"
        created = _git(root, "log", "--format=%H", "--diff-filter=A", "HEAD", "--", path).decode().splitlines()
        if len(created) != 1 or created[0] not in rank:
            raise ValueError("Reader capture has no unique committed publication")
        commit = created[0]
        parent = _git(root, "show", "-s", "--format=%P", commit).decode().strip()
        if parent != row["source_git_commit"]:
            raise ValueError("Reader capture was not published from its recorded source parent")
        if _git(root, "ls-tree", "-z", commit, "--", row["source_path"]):
            raise ValueError("Reader capture publication did not remove the recorded current path")
        content = (root / row["object_path"]).read_bytes()
        if (_git(root, "show", f"{commit}:{path}") != (root / path).read_bytes()
                or _git(root, "show", f"{commit}:{row['object_path']}") != content
                or _git(root, "show", f"{parent}:{row['source_path']}") != content):
            raise ValueError("Reader copy or provenance differs from its committed source")
        base = f"https://github.com/{row['source_repository']}/blob/{commit}/"
        result.setdefault(row["refid"], []).append({"title": row["title"], "sha256": row["sha256"],
            "copy": base + row["object_path"], "provenance": base + path,
            "download": f"https://raw.githubusercontent.com/{row['source_repository']}/{commit}/{row['object_path']}",
            "captureId": row["capture_id"], "creationCommit": commit,
            "observedAbsentAt": row["observed_absent_at"], "rank": rank[commit]})
    for entries in result.values():
        entries.sort(key=lambda row: (row["rank"], row["captureId"]))
        for row in entries: row.pop("rank")
    return result


def write_archive_page(site, prior, captured, base_path):
    """A browseable index; it never promotes reader Markdown into legal history."""
    items = []
    for refid in sorted(set(prior) | set(captured)):
        versions = list(captured.get(refid, []))
        if refid in prior: versions.append(prior[refid])
        title = html.escape(versions[0]["title"])
        links = []
        for version in versions:
            label = "Bevart ved observert uttreden" if "captureId" in version else "Gjenfunnet tidligere lesekopi"
            provenance = (f' · <a href="{html.escape(version["provenance"], quote=True)}">Opphav</a>'
                          if version.get("provenance") else "")
            download = (f' · <a href="{html.escape(version["download"], quote=True)}">Last ned</a>'
                        if version.get("download") else "")
            links.append(f'<li><a href="{html.escape(version["copy"], quote=True)}">{label}</a>{provenance}{download}</li>')
        items.append(f'<article><h2>{title}</h2><p class="refid">{html.escape(refid)}</p><ul>{"".join(links)}</ul></article>')
    count = len(items)
    page = f'''<!DOCTYPE html><html lang="nb"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Bevarte lesekopier</title>
<style>*{{box-sizing:border-box}}body{{max-width:960px;margin:auto;padding:1rem;font:16px/1.6 system-ui,sans-serif;color:#212529}}
a{{color:#1864ab}}h1,h2,.refid{{overflow-wrap:anywhere}}h1{{font-size:2rem}}h2{{font-size:1.1rem;margin:0}}
article{{border-top:1px solid #dee2e6;padding:1.1rem 0}}article p{{margin:.2rem 0;color:#495057}}
ul{{padding-left:1.3rem}}.note{{padding:1rem;background:#f1f7fd;border-left:3px solid #2780e3}}</style></head>
<body><nav><a href="{html.escape(base_path, quote=True)}">Norges Lover og Forskrifter</a></nav>
<main><h1>Bevarte lesekopier</h1><p>{count} dokumenter med tidligere lesekopier.</p>
<p class="note">Dette er avledede lesekopier, ikke bekreftede rettslige versjoner. Hver kopi har lenke til sitt opphav.
At et dokument ikke lenger finnes i den valgte kildesamlingen, fastslår ikke om eller når det ble opphevet.</p>
{"".join(items)}</main></body></html>'''
    path = Path(site) / "reader-archive.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(page, encoding="utf-8")
    return path
