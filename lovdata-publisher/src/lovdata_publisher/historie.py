"""Generate per-law amendment timeline files from amendments.db."""
from __future__ import annotations
import re
import sqlite3
from collections import defaultdict
from pathlib import Path


def _normalize_paragraph(instruction: str) -> str:
    from lovdata_loader.reconstruct import parse_instruction
    spec = parse_instruction(instruction)
    return spec.paragraph if spec.paragraph else ""


def _law_filename(refid: str, short_title: str, used_names: dict) -> str:
    if short_title:
        name = re.sub(r"\s*–\s*.*$", "", short_title).strip()
        name = re.sub(r"^Lov om\s+", "", name, flags=re.I)
        name = re.sub(r"^Lov\s+", "", name, flags=re.I)
        name = name.lower()
    else:
        name = refid
    name = re.sub(r"[^a-zæøå0-9]+", "-", name).strip("-")
    if not name or len(name) < 3:
        name = refid.replace("/", "-")
    if name in used_names and used_names[name] != refid:
        m = re.search(r"(\d{4})", refid)
        year = m.group(1) if m else ""
        name = f"{name}-{year}"
    used_names[name] = refid
    return name + ".md"


def _sort_key(para: str) -> tuple:
    m = re.match(r"§\s*(\d+)-(\d+)\s*([a-z])?", para)
    if m:
        return (int(m.group(1)), int(m.group(2)), m.group(3) or "")
    return (999, 999, para)


def generate_historie(db_path: str, output_dir: str, laws_dir: str = "") -> int:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT a.date_in_force_resolved AS date, a.refid AS act_refid,
               a.title AS act_title,
               am.change_type, am.target_law, am.instruction, am.new_text
        FROM amendments am
        JOIN amendment_acts a ON am.act_refid = a.refid
        WHERE am.target_law != ''
        ORDER BY am.target_law, a.date_in_force_resolved
    """).fetchall()
    conn.close()

    # Load law metadata for short titles
    import json
    law_titles = {}
    if laws_dir:
        laws_path = Path(laws_dir)
    else:
        laws_path = Path(db_path).parent / "laws"
    if laws_path.exists():
        for path in laws_path.glob("*.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            refid = data.get("refid", "")
            if refid:
                law_titles[refid] = {
                    "short_title": data.get("short_title", ""),
                    "title": data.get("title", ""),
                }

    laws = defaultdict(lambda: defaultdict(list))
    for row in rows:
        para = _normalize_paragraph(row["instruction"])
        if not para:
            para = "(annet)"
        laws[row["target_law"]][para].append({
            "date": row["date"],
            "act": row["act_refid"],
            "act_title": row["act_title"],
            "type": row["change_type"],
            "instruction": row["instruction"],
            "text": row["new_text"],
        })

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    count = 0
    used_names = {}

    for law_refid, paragraphs in sorted(laws.items()):
        meta = law_titles.get(law_refid, {})
        short = meta.get("short_title", "")
        title = meta.get("title", law_refid)
        display = short if short else title

        lines = []
        lines.append("---")
        lines.append(f"tittel: \"{display}\"")
        lines.append(f"refid: \"{law_refid}\"")
        lines.append("---")
        lines.append("")
        lines.append(f"# Endringshistorikk: {display}")
        lines.append("")

        for para in sorted(paragraphs.keys(), key=_sort_key):
            entries = paragraphs[para]
            lines.append(f"## {para}")
            lines.append("")

            for entry in entries:
                date = entry["date"] or "ukjent"
                act = entry["act"]
                lines.append(f"### {date} — {act}")
                lines.append("")
                lines.append(f"*{entry['instruction']}*")
                lines.append("")
                if entry["text"]:
                    for text_line in entry["text"].split("\n"):
                        text_line = text_line.strip()
                        if text_line:
                            lines.append(f"> {text_line}")
                            lines.append(">")
                    lines.append("")

        filename = _law_filename(law_refid, short, used_names)
        filepath = out / filename
        filepath.write_text("\n".join(lines), encoding="utf-8")
        count += 1

    return count
