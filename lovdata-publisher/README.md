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

To install the published v0.5.0 wheels outside a checkout, supply both release assets together. The publisher declares its loader dependency, but the loader is not published to the package registry:

```bash
uv pip install \
  https://github.com/sondreskarsten/norwegian-laws/releases/download/v0.5.0/lovdata_loader-0.5.0-py3-none-any.whl \
  https://github.com/sondreskarsten/norwegian-laws/releases/download/v0.5.0/lovdata_publisher-0.5.0-py3-none-any.whl
```

The equivalent source installation supplies both release `.tar.gz` assets together. Markdown formatting works without a checkout. Building the complete reader also requires the repository's `assets/` directory and Quarto, as shown above; those site resources are not bundled in the Python distributions.

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

`--build-history` builds the `law-history` branch: one commit per amendment
act since 2001, replayed from the current consolidated text with the parsed
Lovtidend records, with a baseline commit that is today's text (not the law
in 2001) and a final reset to the current text for documents whose replay
diverged. Documents that left the current corpus are kept until a dated
deletion commit (the legal repeal date where Lovtidend carries a
whole-document repeal, otherwise the detected exit), and
`reconstruction-manifest.json` lists replay counts, divergence and removal
dates per document. The [nightly workflow](../.github/workflows/law-history.yml)
runs it and pushes yearly tags and a `history-YYYY-MM-DD` build tag. The
result is an unverified reconstruction with inferred dates, not
authoritative historical text; the reader and the MCP server label it so.

`python -m lovdata_publisher.index_build` derives `laws-index.sqlite` from
the committed Markdown and `amendments.db`: documents, nodes (chapter, §,
ledd, item), ledd text, amendment records classified by the instruction
catalogue, cross-references and defined terms, stamped with the source
manifest digest and parser identity. The deploy workflow builds it, the
reproducibility gate rebuilds it and compares the logical digest, and the
index is attached to the publication's observation release; see
[docs/NODE-HISTORY-DESIGN.md](../docs/NODE-HISTORY-DESIGN.md).

`.github/scripts/provenance.py` decides whether a run is a source update or a
parser regeneration, restores the previous publication's archives for a
regeneration, writes the commit trailers and refuses output that a second
formatting pass does not reproduce byte for byte.

MIT licensed; Lovdata data is NLOD 2.0.
