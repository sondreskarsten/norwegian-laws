# lovdata-publisher

Validate a [lovdata-loader snapshot](../lovdata-loader/README.md) and build
the current-law reader: Markdown under `lover/` and `forskrifter/`, Quarto
chapters, parsed amendment pages, Atom feeds, display JSONL with schemas,
search indexes, and a sitemap. Amendment timelines and display dates do
not establish past legal states or operation-level commencement.

From the repository root, use Python 3.11+ and install Quarto separately:

```bash
pip install -e lovdata-loader/ -e lovdata-publisher/
lovdata-load --download --output snapshot
lovdata-publish --snapshot snapshot --output . --quarto
quarto render
cp laws.json _site/laws.json
mkdir -p _site/assets
cp -R assets/. _site/assets/
python -m lovdata_publisher.feed snapshot _site/feed.xml
python -m lovdata_publisher.search_index _site laws.json
lovdata-publish --snapshot snapshot --post-render --output . --site-dir _site
```

Post-render builds reader pages, feeds, manifests, the Pagefind index, and
checks internal links. Default search uses document metadata. The reader's
**Hele lovteksten** option loads search chunks only when requested; it
indexes the full rendered body without the former 8,000-character cap.
Pagefind's binary is included in the Python dependency installation.
`laws.json` and the existing display exports retain their public formats.

Production uses `--source-evidence-links` with `--quarto` and supplies
`_site/evidence.json` plus `_site/snapshot-manifest.json` before post-render
validation. These link to the verified source release and snapshot checksums.
The flag is off by default so local builds and older supported snapshots do
not require release files. See [publication status](../README.md#source-evidence-and-publication-status)
and the [deployment workflow](../.github/workflows/deploy.yml).

The `--build-history` exporter is retained for legacy reconstruction work.
Its synthetic baseline and inferred dates are unverified; it does not create
authoritative historical legal text. Automatic regeneration is gated by
`ENABLE_LEGACY_HISTORY`. Existing branches and yearly tags remain available.
The separate [observed-source history consumer](https://github.com/sondreskarsten/norwegian-laws-history)
uses retained evidence rather than those legacy outputs.

MIT licensed; Lovdata data is NLOD 2.0.
