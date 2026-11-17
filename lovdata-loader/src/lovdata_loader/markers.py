"""Footnote markers carried inside model text.

Lovdata prints a footnote reference as a superscript where it occurs, and the
note itself under the paragraph or chapter, each identified by a counter that
is unique within the document. The parser keeps both in place as tokens:

    <sup data-fn="15">1</sup>        a reference to note 15, printed as 1
    <sup data-fn-note="15">1</sup>   the label that opens note 15

The label is the text Lovdata prints; the counter is what links the two.
"""
import re

MARKER = re.compile(r'<sup data-fn(-note)?="(\d*)">([^<]*)</sup>')


def reference(counter: str, label: str) -> str:
    return f'<sup data-fn="{counter}">{label}</sup>'


def note(counter: str, label: str) -> str:
    return f'<sup data-fn-note="{counter}">{label}</sup>'


def plain_text(text: str) -> str:
    return MARKER.sub(lambda m: f" {m.group(3)} ", text or "")


def strip_references(text: str) -> str:
    return MARKER.sub(lambda m: "" if m.group(1) is None else m.group(0), text or "")


def strip_markers(text: str) -> str:
    return re.sub(r" {2,}", " ", MARKER.sub("", text or "")).strip()


def markers_in(text: str) -> list:
    return [("note" if m.group(1) else "reference", m.group(2), m.group(3)) for m in MARKER.finditer(text or "")]
