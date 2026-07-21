"""CLI entry point for lovdata-publisher."""
from __future__ import annotations
import argparse

from .formatter import format_all_laws
from .git_export import build_history
from .quarto import generate_quarto_config


def main():
    parser = argparse.ArgumentParser(
        description="Read a snapshot and produce formatted law outputs"
    )
    parser.add_argument(
        "--snapshot",
        default="snapshot",
        help="Snapshot directory to read (default: snapshot/)",
    )
    parser.add_argument(
        "--output",
        default=".",
        help="Output directory for Markdown files (default: .)",
    )
    parser.add_argument(
        "--format-only",
        action="store_true",
        help="Write Markdown files only, skip git operations",
    )
    parser.add_argument(
        "--build-history",
        action="store_true",
        help="Build the law-history branch with backdated commits",
    )
    parser.add_argument(
        "--history-mode",
        choices=["year", "act"],
        default="year",
        help="Commit granularity for law-history: 'year' (one commit per year-end snapshot) or 'act' (one commit per amendment act, tens of thousands; use --use-lfs)",
    )
    parser.add_argument(
        "--use-lfs",
        action="store_true",
        help="Configure git-lfs for lover/*.md (recommended for --history-mode=act)",
    )
    parser.add_argument(
        "--quarto",
        action="store_true",
        help="Generate Quarto book chapters and config",
    )
    parser.add_argument(
        "--feeds-only",
        action="store_true",
        help="Regenerate Atom feeds only (skip formatting, Quarto, post-render)",
    )
    parser.add_argument(
        "--post-render",
        action="store_true",
        help="After `quarto render`, generate per-law HTML pages and merge full-text search index",
    )
    parser.add_argument(
        "--site-dir",
        default="_site",
        help="Quarto output directory (default: _site)",
    )
    parser.add_argument(
        "--repo-path",
        default=None,
        help="Git repo path for history operations (default: temp dir)",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to amendments.db (default: snapshot/amendments.db)",
    )
    args = parser.parse_args()

    db_path = args.db
    if db_path is None:
        import os
        candidate = os.path.join(args.snapshot, "amendments.db")
        if os.path.exists(candidate):
            db_path = candidate

    # Always format laws when producing any output that depends on lover/*.md.
    # --quarto and default (no flags) both need formatted Markdown to exist.
    # --feeds-only and --post-render skip formatting because lover/*.md already exists.
    if (not args.build_history and not args.feeds_only and not args.post_render) or args.format_only or args.quarto:
        print("=" * 60)
        print("Formatting laws to Markdown")
        print("=" * 60)
        results = format_all_laws(args.snapshot, args.output)
        print(f"  Wrote {len(results)} law files to {args.output}/lover/")

        if db_path:
            from .historie import generate_historie
            import os
            historie_dir = os.path.join(args.output, "historie")
            count = generate_historie(db_path, historie_dir)
            print(f"  Wrote {count} historie files to {historie_dir}/")

    if args.quarto:
        print()
        print("=" * 60)
        print("Generating Quarto book chapters")
        print("=" * 60)
        generate_quarto_config(args.output, db_path=db_path)

    if args.feeds_only:
        from .feeds import generate_per_law_feeds
        import os
        print()
        print("=" * 60)
        print("Generating per-law, per-topic, and per-ministry Atom feeds")
        print("=" * 60)
        generate_per_law_feeds(
            snapshot_dir=args.snapshot,
            lover_dir=os.path.join(args.output, "lover"),
            forskrifter_dir=os.path.join(args.output, "forskrifter"),
            output_dir=os.path.join(args.site_dir, "feeds"),
        )

    if args.post_render:
        from .per_law_pages import generate_per_law_pages, merge_full_text_into_search
        from .feeds import generate_per_law_feeds
        from .historie_pages import generate_historie_pages
        from .paragraph_history import generate_paragraph_history_pages
        from .site_index import SiteIndex
        import os

        db_path = os.path.join(args.snapshot, "amendments.db")

        # One source of truth for every cross-generator link. Built from the
        # corpus on disk, enriched with each producer's manifest as it runs,
        # consumed by every emitter, and enforced by verify_links at the end.
        site_index = SiteIndex.build(args.output)
        from .historie_pages import scan_historie_slugs
        site_index.attach_historie(scan_historie_slugs(os.path.join(args.output, "historie")))
        site_index.attach_book_chapters(args.site_dir)
        print(f"  Site index: {len(site_index.corpus)} corpus documents, "
              f"{len(site_index.historie)} historie pages")

        # Build paragraph-history pages first so we can link to them from
        # the per-law pages (each amended paragraph gets a "⧉ historikk"
        # link next to its heading).
        print()
        print("=" * 60)
        print("Generating per-paragraph history pages")
        print("=" * 60)
        if os.path.exists(db_path):
            _, amended_paragraphs_map = generate_paragraph_history_pages(
                db_path=db_path,
                output_dir=os.path.join(args.site_dir, "historikk"),
                site_index=site_index,
            )
            site_index.attach_paragraphs(amended_paragraphs_map)
        else:
            print(f"  {db_path} not found, skipping paragraph history")
            amended_paragraphs_map = {}


        print()
        print("=" * 60)
        print("Generating per-law, per-topic, and per-ministry Atom feeds")
        print("=" * 60)
        feeds_manifest = generate_per_law_feeds(
            snapshot_dir=args.snapshot,
            lover_dir=os.path.join(args.output, "lover"),
            forskrifter_dir=os.path.join(args.output, "forskrifter"),
            output_dir=os.path.join(args.site_dir, "feeds"),
        )
        site_index.attach_feeds(feeds_manifest)
        print()
        print("=" * 60)
        print("Generating per-law HTML pages and full-text search index")
        print("=" * 60)
        historie_map = generate_historie_pages(
            historie_dir=os.path.join(args.output, "historie"),
            site_dir=args.site_dir,
            site_index=site_index,
        )
        site_index.attach_historie(historie_map)
        generate_per_law_pages(
            repo_root=args.output,
            site_dir=args.site_dir,
            historie_map=historie_map,
            amended_paragraphs_map=amended_paragraphs_map,
            site_index=site_index,
        )
        merge_full_text_into_search(repo_root=args.output, site_dir=args.site_dir)


        print()
        print("=" * 60)
        print("Generating JSONL manifests (amendment-acts, amendments)")
        print("=" * 60)
        from .manifests import generate_manifests
        if os.path.exists(db_path):
            generate_manifests(db_path=db_path, output_dir=args.site_dir)
        else:
            print(f"  {db_path} not found, skipping manifests")

        print()
        print("=" * 60)
        print("Generating aktivitet leaderboard page")
        print("=" * 60)
        from .stats_page import generate_stats_page
        generate_stats_page(
            db_path=db_path,
            output_path=os.path.join(args.site_dir, "aktivitet.html"),
            lover_dir=os.path.join(args.output, "lover"),
            forskrifter_dir=os.path.join(args.output, "forskrifter"),
            site_index=site_index,
        )

        # Sitemap must run LAST since it indexes everything in _site/
        print()
        print("=" * 60)
        print("Generating sitemap.xml + robots.txt")
        print("=" * 60)
        from .sitemap import generate_sitemap
        generate_sitemap(
            repo_root=args.output,
            site_dir=args.site_dir,
            historikk_dir=os.path.join(args.site_dir, "historikk"),
        )

        # Deploy-time enforcement of the whole dead-link class: every internal
        # reference in the built site must resolve, or the run fails here
        # instead of a user finding it later.
        print()
        print("=" * 60)
        print("Verifying internal link integrity")
        print("=" * 60)
        from .verify_links import verify_site, summarize
        broken = verify_site(args.site_dir)
        if broken:
            print(f"  {len(broken)} broken internal references in "
                  f"{len(summarize(broken))} classes:")
            for cls, count, samples in summarize(broken)[:30]:
                print(f"    [{count:>6}] {cls}")
                for s in samples:
                    print(f"             e.g. {s}")
            raise SystemExit(1)
        print("  All internal references resolve")

    if args.build_history:
        repo_path = args.repo_path
        if repo_path is None:
            import tempfile
            repo_path = tempfile.mkdtemp(prefix="law-repo-")
        print()
        print("=" * 60)
        print(f"Building git history (mode={args.history_mode}, lfs={args.use_lfs})")
        print("=" * 60)
        build_history(args.snapshot, repo_path, mode=args.history_mode, use_lfs=args.use_lfs)
        print(f"  Repository at: {repo_path}")


if __name__ == "__main__":
    main()
