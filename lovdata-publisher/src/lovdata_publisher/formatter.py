"""Format structured law data into Markdown with YAML frontmatter.

This module is the core of the publisher. It takes structured data (dicts
loaded from snapshot JSON files) and produces deterministic Markdown output.
Same input always produces byte-identical output.

No XML parsing, no BeautifulSoup, no network access.
"""
from __future__ import annotations
import html
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


def _list_contains_ordered_content(items: list) -> bool:
    return any(para.get("ordered_blocks")
               or _list_contains_ordered_content(para.get("list_items", []))
               for item in items for para in item.get("paragraphs", []))


def _paragraph_blocks(para: dict) -> list[dict]:
    """Use ordered content when present; retain legacy paragraph spacing."""
    if para.get("ordered_blocks"):
        return [dict(block, _semantic=True) for block in para["ordered_blocks"]]
    blocks = []
    if para.get("text"):
        blocks.append({"kind": "text", "text": para["text"]})
    if para.get("list_items"):
        blocks.append({"kind": "list", "list_items": para["list_items"],
                       "_semantic": _list_contains_ordered_content(para["list_items"])})
    if para.get("trailing_text"):
        blocks.append({"kind": "text", "text": para["trailing_text"]})
    return blocks


def _semantic_list_html(items: list) -> str:
    """Render legal labels literally; Markdown cannot express A./I./1. nesting.

    Only ordered-content subtrees use this renderer. Inline layout keeps the
    hierarchy readable in both the website and ordinary rendered Markdown.
    """
    lines = ['<ol class="legal-list" role="list" '
             'style="list-style:none;margin:.35em 0 .7em;padding:0">']
    for item in items:
        marker = html.escape(item.get("marker") or "-")
        lines.extend([
            '<li style="display:flex;align-items:baseline;gap:.5em;margin:.3em 0">',
            '<span class="legal-marker" style="flex:0 0 auto;min-width:2.25em">'
            + marker + '</span>',
            '<div class="legal-item-body" style="flex:1;min-width:0">',
        ])
        for para in item.get("paragraphs", []):
            for block in _paragraph_blocks(para):
                if block["kind"] == "text":
                    lines.append('<p style="margin:0 0 .3em">' + html.escape(block["text"]) + '</p>')
                elif block["kind"] == "list":
                    lines.append(_semantic_list_html(block["list_items"]))
                else:
                    raise ValueError(f"Unsupported paragraph block: {block['kind']}")
        lines.extend(['</div>', '</li>'])
    lines.append('</ol>')
    return "\n".join(lines)


def _render_paragraph_blocks(blocks: list, depth: int, lines: list, *, compact=False) -> None:
    for block in blocks:
        if block["kind"] == "text":
            lines.append(("  " * depth if compact else "") + block["text"])
        elif block["kind"] == "list":
            if block.get("_semantic"):
                lines.append(_semantic_list_html(block["list_items"]))
            else:
                _render_list_items(block["list_items"], depth, lines)
        else:
            raise ValueError(f"Unsupported paragraph block: {block['kind']}")
        if not compact:
            lines.append("")


def _render_list_items(items: list, depth: int, lines: list) -> None:
    indent = "  " * depth
    escape = _list_group_renumbered(items)
    for item in items:
        marker = item.get("marker") or "-"
        if escape:
            marker = "- " + marker.replace(".", "\\.")
        paras = item.get("paragraphs", [])
        first_blocks = _paragraph_blocks(paras[0]) if paras else []
        has_head = bool(first_blocks and first_blocks[0]["kind"] == "text"
                        and (paras[0].get("ordered_blocks") or paras[0].get("text")))
        head = first_blocks[0]["text"] if has_head else ""
        lines.append(f"{indent}{marker} {head}".rstrip())
        if paras:
            _render_paragraph_blocks(first_blocks[1:] if has_head else first_blocks,
                                     depth + 1, lines, compact=True)
            for para in paras[1:]:
                _render_paragraph_blocks(_paragraph_blocks(para), depth + 1, lines, compact=True)


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
        _render_paragraph_blocks(_paragraph_blocks(para), 0, lines)

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
        _render_paragraph_blocks(_paragraph_blocks(para), 0, lines)

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
    from .snapshot import validate_snapshot

    validate_snapshot(snapshot_dir)
    snapshot = Path(snapshot_dir)
    output = Path(output_dir)
    # Render every document before any writes or pruning. A malformed later
    # document must not leave a partially updated corpus behind.
    prepared = []
    for subdir in ["laws", "forskrifter"]:
        src = snapshot / subdir
        json_files = sorted(src.glob("*.json"))
        for path in json_files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                prepared.append((data["refid"], refid_to_filepath(data["refid"]), format_law_markdown(data)))
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                raise ValueError(f"Invalid snapshot document {path}: {exc}") from exc

    (output / "lover").mkdir(parents=True, exist_ok=True)
    (output / "forskrifter").mkdir(parents=True, exist_ok=True)
    results = {}
    for refid, filepath, markdown in prepared:
        (output / filepath).write_text(markdown, encoding="utf-8")
        results[refid] = filepath

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
