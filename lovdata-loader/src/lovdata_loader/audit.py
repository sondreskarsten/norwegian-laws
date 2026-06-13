"""Structural audit of parsed list content.

Surfaces the failure mode where an ordered list yields items with no
resolvable marker — the signature of a source-schema drift that would
otherwise degrade silently to bullets.
"""
from dataclasses import dataclass


@dataclass
class ListAnomaly:
    refid: str
    article: str
    detail: str


def _walk_paragraphs(paragraphs, refid, article_name, metrics, anomalies):
    for para in paragraphs:
        ordered = bool(para.get("list_style"))
        for item in para.get("list_items", []):
            metrics["items"] += 1
            if item.get("marker"):
                metrics["with_marker"] += 1
            else:
                metrics["bullets"] += 1
                if ordered:
                    anomalies.append(ListAnomaly(
                        refid=refid,
                        article=article_name,
                        detail=f"ordered list (type={para.get('list_style')!r}) item without marker",
                    ))
            _walk_paragraphs(item.get("paragraphs", []), refid, article_name, metrics, anomalies)


def audit_law_lists(law: dict) -> dict:
    refid = law.get("refid", "")
    metrics = {"items": 0, "with_marker": 0, "bullets": 0}
    anomalies = []

    def walk_articles(articles):
        for a in articles:
            _walk_paragraphs(a.get("paragraphs", []), refid, a.get("name", ""), metrics, anomalies)

    def walk_sections(sections):
        for s in sections:
            walk_articles(s.get("articles", []))
            walk_sections(s.get("subsections", []))

    walk_sections(law.get("sections", []))
    walk_articles(law.get("top_level_articles", []))
    metrics["anomalies"] = anomalies
    return metrics
