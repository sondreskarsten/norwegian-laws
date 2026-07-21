"""Format structured law data into Markdown with YAML frontmatter.

This module is the core of the publisher. It takes structured data (dicts
loaded from snapshot JSON files) and produces deterministic Markdown output.
Same input always produces byte-identical output.

No XML parsing, no BeautifulSoup, no network access.
"""
from __future__ import annotations
import json
import re
from pathlib import Path


def refid_to_filepath(refid: str) -> str:
    """Convert a refid to a Markdown file path.

    - lov/* → lover/lov-*.md
    - forskrift/* → forskrifter/forskrift-*.md
    """
    if refid.startswith("forskrift/"):
        return f"forskrifter/{refid.replace('/', '-')}.md"
    return f"lover/{refid.replace('/', '-')}.md"


def _list_group_renumbered(items: list) -> bool:
    nums = []
    for item in items:
        m = re.fullmatch(r"(\d+)\.", item.get("marker") or "")
        if not m:
            return False
        nums.append(int(m.group(1)))
    return len(nums) >= 2 and nums != list(range(nums[0], nums[0] + len(nums)))


def _render_list_items(items: list, depth: int, lines: list) -> None:
    indent = "  " * depth
    escape = _list_group_renumbered(items)
    for item in items:
        marker = item.get("marker") or "-"
        if escape:
            marker = "- " + marker.replace(".", "\\.")
        paras = item.get("paragraphs", [])
        head = paras[0].get("text", "") if paras else ""
        lines.append(f"{indent}{marker} {head}".rstrip())
        if paras:
            first = paras[0]
            if first.get("list_items"):
                _render_list_items(first["list_items"], depth + 1, lines)
            if first.get("trailing_text"):
                lines.append(f"{indent}  {first['trailing_text']}")
            for para in paras[1:]:
                if para.get("text"):
                    lines.append(f"{indent}  {para['text']}")
                if para.get("list_items"):
                    _render_list_items(para["list_items"], depth + 1, lines)
                if para.get("trailing_text"):
                    lines.append(f"{indent}  {para['trailing_text']}")


def format_article(article: dict, depth: int = 0) -> str:
    """Format an article (§/paragraf) as Markdown.

    Args:
        article: Dict with keys 'name', 'header_text', 'paragraphs'.
        depth: Nesting depth for heading level (0=top-level, 1=inside section,
               2=inside subsection, etc.).
    """
    lines = []

    if article.get("header_text"):
        lines.append(f"{'#' * min(depth + 3, 6)} {article['header_text']}")
        lines.append("")

    for para in article.get("paragraphs", []):
        if para.get("text"):
            lines.append(para["text"])
            lines.append("")
        if para.get("list_items"):
            _render_list_items(para["list_items"], 0, lines)
            lines.append("")
        if para.get("trailing_text"):
            lines.append(para["trailing_text"])
            lines.append("")

    if article.get("trailing_text"):
        lines.append(f"*{article['trailing_text']}*")
        lines.append("")

    return "\n".join(lines)


def format_section(section: dict, depth: int = 0) -> str:
    """Format a section (kapittel/del) as Markdown."""
    lines = []

    if section.get("heading"):
        level = min(depth + 2, 6)
        lines.append(f"{'#' * level} {section['heading']}")
        lines.append("")

    for text in section.get("preamble", []):
        lines.append(text)
        lines.append("")

    for article in section.get("articles", []):
        lines.append(format_article(article, depth=depth + 1))

    for subsection in section.get("subsections", []):
        lines.append(format_section(subsection, depth=depth + 1))

    for text in section.get("footnotes", []):
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def format_law_markdown(law: dict) -> str:
    """Convert a structured law dict (from snapshot JSON) to Markdown.

    This is the primary formatting function. It produces Markdown with
    YAML frontmatter from a law data dict.

    The function is deterministic: same input always produces same output.

    Args:
        law: Dict matching the LawData JSON schema from the snapshot.
    """
    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"tittel: \"{law['title']}\"")
    if law.get("short_title"):
        lines.append(f"korttittel: \"{law['short_title']}\"")
    lines.append(f"refid: \"{law['refid']}\"")
    eli = "/eli/" + law["refid"].replace("-", "/", 3)
    lines.append(f"eli: \"{eli}\"")
    lines.append(f"departement: \"{law.get('ministry', '')}\"")
    if law.get("legal_area"):
        # YAML double-quoted scalars need literal "\n" escape for embedded newlines
        legal_area = law["legal_area"].replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        lines.append(f"rettsomrade: \"{legal_area}\"")
    lines.append(f"ikrafttredelse: \"{law.get('date_in_force', '')}\"")
    if law.get("last_amended"):
        lines.append(f"sist-endret: \"{law['last_amended']}\"")
    if law.get("last_amended_in_force"):
        lines.append(f"sist-endret-ikrafttredelse: \"{law['last_amended_in_force']}\"")
    lines.append("---")
    lines.append("")
    lines.append(f"# {law['title']}")
    lines.append("")

    for para in law.get("top_level_paragraphs", []):
        if para.get("text"):
            lines.append(para["text"])
            lines.append("")
        if para.get("list_items"):
            _render_list_items(para["list_items"], 0, lines)
            lines.append("")
        if para.get("trailing_text"):
            lines.append(para["trailing_text"])
            lines.append("")

    for rem in law.get("remainders", []):
        lines.append(rem)
        lines.append("")

    for section in law.get("sections", []):
        lines.append(format_section(section))

    for article in law.get("top_level_articles", []):
        lines.append(format_article(article, depth=0))

    return "\n".join(lines)


def format_all_laws(snapshot_dir: str, output_dir: str) -> dict[str, str]:
    """Read all law and forskrift JSONs from a snapshot and write Markdown files.

    Args:
        snapshot_dir: Path to the snapshot directory.
        output_dir: Path to write lover/*.md and forskrifter/*.md files.

    Returns:
        Dict mapping refid → relative filepath of the written Markdown file.
    """
    snapshot = Path(snapshot_dir)
    output = Path(output_dir)
    (output / "lover").mkdir(parents=True, exist_ok=True)
    (output / "forskrifter").mkdir(parents=True, exist_ok=True)

    results = {}

    for subdir in ["laws", "forskrifter"]:
        src = snapshot / subdir
        if not src.exists():
            continue
        json_files = sorted(src.glob("*.json"))
        for i, path in enumerate(json_files):
            data = json.loads(path.read_text(encoding="utf-8"))
            refid = data.get("refid", "")
            if not refid:
                continue

            md = format_law_markdown(data)
            filepath = refid_to_filepath(refid)
            full_path = output / filepath
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(md, encoding="utf-8")
            results[refid] = filepath

            if (i + 1) % 200 == 0:
                print(f"  Formatted {i + 1}/{len(json_files)} {subdir}...")

    # Prune Markdown for documents the snapshot no longer contains (repealed
    # laws, withdrawn forskrifter). Without this the corpus is add-only and
    # ships repealed documents as gjeldende. Each output subdir is pruned
    # only when this run wrote at least one file into it, so a partial
    # snapshot cannot wipe an entire corpus directory.
    written = set(results.values())
    written_dirs = {fp.split("/", 1)[0] for fp in written}
    pruned = 0
    for out_subdir, prefix in [("lover", "lov-"), ("forskrifter", "forskrift-")]:
        if out_subdir not in written_dirs:
            continue
        for stale in (output / out_subdir).glob(f"{prefix}*.md"):
            if f"{out_subdir}/{stale.name}" not in written:
                stale.unlink()
                pruned += 1
    if pruned:
        print(f"  Pruned {pruned} Markdown files for documents absent from the snapshot")

    return results
