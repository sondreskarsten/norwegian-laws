"""Completeness harness: verify that the parsed model represents the source.

For every law, source body tokens must be represented in the model. A
coverage shortfall is the universal signal of silent loss — it fires for
dropped lists, dropped sections, archaic-law bodies, change-act bodies,
and any future structural drift, with no per-element special-casing.
"""
import re
import tarfile
from collections import Counter
from dataclasses import asdict

from bs4 import BeautifulSoup

from .parser import parse_law, _text

_WORD = re.compile(r"\w+", re.UNICODE)


def _tokens(s: str) -> Counter:
    return Counter(w.lower() for w in _WORD.findall(s or ""))


def model_tokens(law: dict) -> Counter:
    bag = Counter()

    def para(p):
        bag.update(_tokens(p.get("text", "")))
        bag.update(_tokens(p.get("trailing_text", "")))
        for it in p.get("list_items", []):
            bag.update(_tokens(it.get("marker", "")))
            for q in it.get("paragraphs", []):
                para(q)

    def article(a):
        bag.update(_tokens(a.get("header_text", "")))
        bag.update(_tokens(a.get("trailing_text", "")))
        for p in a.get("paragraphs", []):
            para(p)
        for r in a.get("remainders", []):
            bag.update(_tokens(r))

    def section(s):
        bag.update(_tokens(s.get("heading", "")))
        for t in s.get("preamble", []):
            bag.update(_tokens(t))
        for t in s.get("footnotes", []):
            bag.update(_tokens(t))
        for t in s.get("remainders", []):
            bag.update(_tokens(t))
        for a in s.get("articles", []):
            article(a)
        for sub in s.get("subsections", []):
            section(sub)

    bag.update(_tokens(law.get("title", "")))
    bag.update(_tokens(law.get("short_title", "")))
    for s in law.get("sections", []):
        section(s)
    for a in law.get("top_level_articles", []):
        article(a)
    for p in law.get("top_level_paragraphs", []):
        para(p)
    for r in law.get("remainders", []):
        bag.update(_tokens(r))
    return bag


def source_tokens(content: bytes) -> Counter:
    soup = BeautifulSoup(content, "lxml")
    body = soup.find("main", class_="documentBody") or soup.find("body")
    if body is None:
        return Counter()
    for chrome in body.find_all(["nav", "footer", "header"]):
        chrome.extract()
    return _tokens(_text(body))


def law_coverage(content: bytes, law: dict) -> dict:
    src = source_tokens(content)
    mdl = model_tokens(law)
    total = sum(src.values())
    captured = sum(min(c, mdl.get(w, 0)) for w, c in src.items())
    return {
        "coverage": captured / total if total else 1.0,
        "source_total": total,
        "captured": captured,
        "missing": src - mdl,
    }


def corpus_report(archive_path: str, threshold: float = 0.999) -> dict:
    rows = []
    remainder_laws = 0
    with tarfile.open(archive_path, "r:bz2") as tar:
        for member in tar.getmembers():
            if not member.name.endswith(".xml"):
                continue
            f = tar.extractfile(member)
            if not f:
                continue
            content = f.read()
            law = parse_law(content)
            if law is None:
                continue
            d = asdict(law)
            if d.get("remainders"):
                remainder_laws += 1
            cov = law_coverage(content, d)
            if cov["source_total"] == 0:
                continue
            rows.append((cov["coverage"], d["refid"], cov["source_total"], cov["missing"]))
    rows.sort()
    n = len(rows)
    mean = sum(c for c, _, _, _ in rows) / n if n else 1.0
    failures = [(c, rid, total, miss) for c, rid, total, miss in rows if c < threshold]
    return {
        "n": n,
        "mean": mean,
        "min": rows[0][0] if rows else 1.0,
        "threshold": threshold,
        "failures": failures,
        "remainder_laws": remainder_laws,
    }


def main():
    import argparse
    import sys
    ap = argparse.ArgumentParser(description="Completeness gate over consolidated archives")
    ap.add_argument("archives", nargs="+")
    ap.add_argument("--mean", type=float, default=0.999)
    ap.add_argument("--min", type=float, default=0.90)
    ap.add_argument("--max-failures", type=int, default=25)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    ok = True
    for arch in args.archives:
        r = corpus_report(arch, threshold=0.999)
        print(f"{arch}: laws={r['n']} mean={r['mean']*100:.3f}% "
              f"min={r['min']*100:.2f}% below-99.9%={len(r['failures'])} "
              f"remainder_laws={r['remainder_laws']}")
        for c, rid, total, miss in r["failures"][:12]:
            print(f"    {c*100:6.2f}%  {rid}  ({', '.join(w for w, _ in miss.most_common(5))})")
        if r["mean"] < args.mean:
            print(f"  FAIL: mean {r['mean']:.5f} < {args.mean}")
            ok = False
        if r["min"] < args.min:
            print(f"  FAIL: min {r['min']:.5f} < {args.min}")
            ok = False
        if len(r["failures"]) > args.max_failures:
            print(f"  FAIL: {len(r['failures'])} laws below 99.9% > {args.max_failures}")
            ok = False

    if not ok and not args.report_only:
        sys.exit(1)


if __name__ == "__main__":
    main()
