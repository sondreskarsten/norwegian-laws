# Norwegian laws

**Read Norwegian laws and central regulations, follow published amendments, and inspect recorded source changes.** This project formats Lovdata's public data into a searchable reader, Markdown files, Atom feeds, and data exports.

**[Browse the site →](https://sondreskarsten.github.io/norwegian-laws/)** · **[Atom feeds →](https://sondreskarsten.github.io/norwegian-laws/feeds/)** · **[Observed-source history →](https://github.com/sondreskarsten/norwegian-laws-history)**

The current reader reflects the consolidated sources selected for its last successful publication. Amendment pages and feeds are parsed views of Norsk Lovtidend. Neither those views nor Git dates establish the complete law in force at a past date.

## Recent amendments

Recent parsed amendment acts, ordered by their source publication date and refreshed by the publishing workflow:

<!-- AI_SUMMARY_START -->
<!-- AI_SUMMARY_END -->

<!-- RECENT_AMENDMENTS_START -->
**Lover (endringslover):**

| Date | Amendment | Targets |
|---|---|---|
| 2026-06-23 | Endringslov til endringslov til merverdiavgiftsloven | [`lov/2009-06-19-58`](https://sondreskarsten.github.io/norwegian-laws/lover/lov-2009-06-19-58.html) [`lov/2025-12-22-121`](https://lovdata.no/dokument/NLO/lov/2025-12-22-121) |
| 2026-06-23 | Endringslov til utleveringsloven | [`lov/1975-06-13-39`](https://sondreskarsten.github.io/norwegian-laws/lover/lov-1975-06-13-39.html) |
| 2026-06-23 | Endringslov til folketrygdloven | [`lov/1997-02-28-19`](https://sondreskarsten.github.io/norwegian-laws/lover/lov-1997-02-28-19.html) |
| 2026-06-23 | Endringslov til folketrygdloven | [`lov/1997-02-28-19`](https://sondreskarsten.github.io/norwegian-laws/lover/lov-1997-02-28-19.html) |
| 2026-06-23 | Endringslov til skatteloven | [`lov/1999-03-26-14`](https://sondreskarsten.github.io/norwegian-laws/lover/lov-1999-03-26-14.html) |

**Forskrifter:**

| Date | Amendment | Targets |
|---|---|---|
| 2026-09-25 | Forskrift om endring i forskrift om fartsskriververksteder | [`forskrift/2018-09-26-1467`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2018-09-26-1467.html) |
| 2026-09-25 | Endr. i fastlegeforskriften | [`forskrift/2025-12-02-2405`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2025-12-02-2405.html) |
| 2026-09-25 | Forskrift om endring i dagpengeforskriften og oppheving av forskrif… | [`forskrift/1998-09-16-890`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-1998-09-16-890.html) [`forskrift/2022-12-21-2456`](https://lovdata.no/dokument/SFO/forskrift/2022-12-21-2456) |
| 2026-09-25 | Endr. i EU-gjødselvareforskriften | [`forskrift/2024-03-06-538`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2024-03-06-538.html) |
| 2026-09-23 | Forskrift om endring i forskrift om regulering av fisket etter bris… | [`forskrift/2026-06-22-1211`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2026-06-22-1211.html) |
<!-- RECENT_AMENDMENTS_END -->

## Read, search, and subscribe

- **Find a document:** [search by title, abbreviation, or refid](https://sondreskarsten.github.io/norwegian-laws/book/sok.html), such as `aml` or `lov/1998-07-17-56`. The search update in [PR #13](https://github.com/sondreskarsten/norwegian-laws/pull/13) uses a small metadata catalog by default; selecting **Hele lovteksten** loads the relevant full-text index chunks on demand.
- **Follow amendments:** use the [feed catalog](https://sondreskarsten.github.io/norwegian-laws/feeds/) to find available document, topic, and ministry feeds. For example, [Regnskapsloven's feed](https://sondreskarsten.github.io/norwegian-laws/feeds/lov-1998-07-17-56.xml) works in an Atom reader. See [subscription instructions](SUBSCRIBE.md) and the [GitHub Action watcher](examples/github-action-watcher/).
- **Inspect parsed amendment records:** open a law's amendment timeline or paragraph history. These expose recognized source instructions and display dates; they are not a verified reconstruction of legal effect.
- **Use the data:** [`laws.json`](https://sondreskarsten.github.io/norwegian-laws/laws.json) provides document metadata, aliases, links, and amendment counts. The [JSONL examples](examples/python-consumer/) query the display exports; complete parsed amendment occurrences and original source bytes belong to the evidence snapshot described below.

To inspect changes recorded in this repository:

```bash
git clone https://github.com/sondreskarsten/norwegian-laws.git
cd norwegian-laws
git log -p -- lover/lov-1998-07-17-56.md
```

These diffs may reflect updated sources, parser repairs, or formatting changes. A repository commit date is not a commencement date.

## Source evidence and publication status

[`publication.json`](https://sondreskarsten.github.io/norwegian-laws/publication.json) identifies the source commit and selected Lovdata manifest actually served by the site. Publication is acknowledged only after this receipt is read back from the public site.

The merged [PR #13](https://github.com/sondreskarsten/norwegian-laws/pull/13) adds a version-4 snapshot retaining raw archives, every archive member's identity, parser/runtime provenance, complete parsed amendment occurrences, and checksums. Its publication workflow creates an `observation-*` GitHub Release containing `snapshot.tar.gz` and `evidence.json`, verifies the downloads, then supplies these reader downloads:

| Download | Purpose |
| --- | --- |
| `evidence.json` | Observation identity, source commit, bundle checksum, and permanent release download URL. |
| `snapshot-manifest.json` | Exact snapshot artifact membership and checksums. |

**Verified 25 September 2026:** the first [public evidence release](https://github.com/sondreskarsten/norwegian-laws/releases/tag/observation-ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596), reader evidence links and on-demand full-text search are live through [run 36167592215](https://github.com/sondreskarsten/norwegian-laws/actions/runs/36167592215), source `2d90a466a8ca3954494f82041409b39242c5c1f5`. The site's receipt agrees with the release; the history repository accepted it and a fresh consumer retrieved exact source XML. See [delivery evidence](docs/evidence/live-v4-readback.json). Subsequent daily operation still needs verification.

See the [loader contract](lovdata-loader/README.md) for the snapshot fields. Checksums establish consistency with the captured bytes; they do not prove lossless parsing, historical legal validity, or permanent availability.

## Observed history and legacy reconstructions

The separate [norwegian-laws-history](https://github.com/sondreskarsten/norwegian-laws-history) product verifies published evidence bundles, records observed document membership without replacing earlier observations, and retrieves exact archived XML. Its first [public intake](https://github.com/sondreskarsten/norwegian-laws-history/actions/runs/36169832648) committed 45,114 source archive members on 25 September 2026. Observation time means when this collector inspected the source, not when the law took effect. Commencement, repeal, and canonical historical text remain unresolved unless separately established.

The old [`law-history` branch](https://github.com/sondreskarsten/norwegian-laws/tree/law-history) and yearly tags are preserved as **unverified legacy reconstructions**. They began from a synthetic baseline using then-current consolidated text, and some dates were inferred. They cannot answer “what was the law on this date?” reliably. The [comparison tool](https://sondreskarsten.github.io/norwegian-laws/book/diff.html) labels these outputs and uses a catalog of pinned legacy commits; a textual difference is not proof of a legal change.

Automatic legacy regeneration requires `ENABLE_LEGACY_HISTORY=true`; the separate manual workflow remains available. It is not part of the new observed-source history product.

## Build the current reader

Use Python 3.11+ and install Quarto separately. From this checkout, install both packages together so the publisher reads the loader's snapshot contract:

```bash
pip install -e lovdata-loader/ -e lovdata-publisher/

lovdata-load --download --output snapshot
lovdata-publish --snapshot snapshot --output . --quarto
quarto render

# Supply the static data and assets before post-render link validation.
cp laws.json _site/laws.json
mkdir -p _site/assets
cp -R assets/. _site/assets/
python -m lovdata_publisher.feed snapshot _site/feed.xml
python -m lovdata_publisher.search_index _site laws.json
lovdata-publish --snapshot snapshot --post-render --output . --site-dir _site
```

The loader selects archives from the live Lovdata list and verifies cached bytes against their receipt. The publisher validates the snapshot, writes Markdown and Quarto chapters, and generates reader pages, feeds, display JSONL, and the search indexes. Pagefind's binary is installed with the publisher; full-text search requires no search server. See the [publisher guide](lovdata-publisher/README.md) for deployment-specific evidence links.

The [daily poll](.github/workflows/poll-lovdata.yml) compares the source list with the last acknowledged publication and requests a new build when they differ. Failed publication is not recorded as delivered. Software package releases, `observation-*` evidence releases, and legacy yearly tags serve different purposes; a yearly tag is not a verified legal snapshot.

[MIGRATION.md](MIGRATION.md) is an archived design plan, not the current installation or snapshot specification.

## Data format and limits

Each document is Markdown with YAML metadata such as `refid`, `tittel`, `departement`, `ikrafttredelse`, and `sist-endret`. Source date fields are retained as metadata; some display exports also use normalized or fallback dates. Do not interpret them as verified effective dates for every amendment operation.

The reader preserves supported source structures and links recognized references. Parsing and rendering can still lose or misinterpret content. Token coverage checks do not establish complete structural or legal correctness. Use [Lovdata](https://lovdata.no) to check the source text and legal status. This is an unofficial project, unaffiliated with Lovdata or the Norwegian government.

## License

- **Law data:** Lovdata, [Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/no/2.0).
- **Source code:** [MIT](LICENSE).
