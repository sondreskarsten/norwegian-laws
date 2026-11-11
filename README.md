# Norwegian laws

**Read Norwegian laws and central regulations, follow published amendments, and inspect recorded source changes.** This project formats Lovdata's public data into a searchable reader, Markdown files, Atom feeds, and data exports.

**[Browse the site →](https://sondreskarsten.github.io/norwegian-laws/)** · **[Atom feeds →](https://sondreskarsten.github.io/norwegian-laws/feeds/)** · **[Observed-source history →](https://github.com/sondreskarsten/norwegian-laws-history)**

The current reader reflects the consolidated sources selected for its last successful publication. Amendment pages and feeds are parsed views of Norsk Lovtidend. Neither those views nor Git dates establish the complete law in force at a past date.

## Recent amendments

Recent parsed amendment acts, ordered by their source publication date and refreshed by the publishing workflow:

<!-- AI_SUMMARY_START -->
*Oppsummering av endringene, generert fra publiseringens diff · 2026-11-11*

4 endrede dokumenter i denne publiseringen.

Endrede dokumenter etter endringskilde:
- forskrift/2026-11-05-2276 endrer 1 dokument: forskrift/2021-05-05-1407 Dyresykdomsnødtiltaksforskriften
- forskrift/2026-11-04-2275 endrer 1 dokument: forskrift/2008-05-30-516 REACH-forskriften
- forskrift/2026-10-22-2231 endrer 1 dokument: forskrift/2024-10-21-2545 Forskrift om delvis allmenngjøring av tariffavtale for renholdsbedrifter
- forskrift/2026-10-19-2274 endrer 1 dokument: forskrift/2000-12-08-1281 Forskrift om fag underlagt mesterbrevloven
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
| 2026-11-06 | Endr. i dyresykdomsnødtiltaksforskriften | [`forskrift/2021-05-05-1407`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2021-05-05-1407.html) |
| 2026-11-06 | Endr. i REACH-forskriften | [`forskrift/2008-05-30-516`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2008-05-30-516.html) |
| 2026-11-06 | Forskrift om endring i forskrift om hvilke fag som er lagt under lo… | [`forskrift/2000-12-08-1281`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2000-12-08-1281.html) |
| 2026-11-06 | Forskrift om endring i forskrift om hvilke fag som er lagt under lo… | [`forskrift/2000-12-08-1281`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2000-12-08-1281.html) |
| 2026-11-05 | Endr. i HPAI-soneforskrift | [`forskrift/2026-11-03-2258`](https://sondreskarsten.github.io/norwegian-laws/forskrifter/forskrift-2026-11-03-2258.html) |
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

## Ask an AI assistant

[`norwegian-laws-mcp/`](norwegian-laws-mcp/) is an MCP server that answers questions such as "where is underenheter defined", "what changed last week" or "how has § 13-14 of aksjeloven changed" directly from this repository: the catalog, `git grep`, `git log`, `git diff`, `git blame`, the parsed amendment records, the last text of repealed acts and the yearly reconstructions. Every history answer states its data coverage and limits.

```bash
claude mcp add norwegian-laws -- uvx --from "git+https://github.com/sondreskarsten/norwegian-laws.git#subdirectory=norwegian-laws-mcp" norwegian-laws-mcp
```

See the [server README](norwegian-laws-mcp/README.md) for other clients and the tool list.

Each publication also produces a queryable **corpus index** (`laws-index.sqlite.gz` on the publication's observation release): every chapter, §, ledd and item of every current document, the parsed amendment records classified by the instruction catalogue, cross-references and defined terms, stamped with the source manifest digest and parser identity and verified by the reproducibility gate (the `Indeks` trailer on each publication commit). The MCP server uses it for outlines, provision-level history, ranked search, incoming references, definitions and read-only SQL; see [docs/NODE-HISTORY-DESIGN.md](docs/NODE-HISTORY-DESIGN.md).

## Source evidence and publication status

[`publication.json`](https://sondreskarsten.github.io/norwegian-laws/publication.json) identifies the source commit and the Lovdata manifest actually served by the site. A publication is acknowledged only after that receipt is read back from the public site; a failed deploy is not recorded as delivered.

Every publication also creates an `observation-*` [GitHub Release](https://github.com/sondreskarsten/norwegian-laws/releases) named after the SHA-256 of its source observation. It holds `snapshot.tar.gz` (the raw Lovdata archives, every archive member's identity, the complete parsed amendment occurrences and checksums), `evidence.json` and the gzipped corpus index, each verified by an unauthenticated download before the release is published. The reader links to the release of the publication it serves:

| Download | Purpose |
| --- | --- |
| `evidence.json` | Observation identity, source commit, bundle checksum, and permanent release download URL. |
| `snapshot-manifest.json` | Exact snapshot artifact membership and checksums. |

Observation releases have been published for every daily publication since 25 September 2026 (the first: [observation-ccdbf3e45098](https://github.com/sondreskarsten/norwegian-laws/releases/tag/observation-ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596)). The restore step of a parser regeneration reads the previous publication's archives from its release, so these releases are not pruned. See the [loader contract](lovdata-loader/README.md) for the snapshot fields. Checksums establish consistency with the captured bytes; they do not prove lossless parsing, historical legal validity, or permanent availability.

## Releases and versions

Three kinds of tag live in this repository and mean different things:

- **Package releases** `vX.Y.Z` carry the wheels of `lovdata-loader`, `lovdata-publisher` and `norwegian-laws-mcp`, built by the [release workflow](.github/workflows/release.yml) from the tag with the notes in `.github/release-notes/`. The three packages and [`CITATION.cff`](CITATION.cff) share the version number. Releases before v0.5.0 shipped the pre-split `lovdata_pipeline` package and no longer describe the repository.
- **Observation releases** `observation-<sha256>` are the source evidence of one publication, described above. They are never "latest".
- **History tags** `v2001`…`v<current year>` and `history-YYYY-MM-DD` point into the `law-history` branch, described below. A yearly tag is not a verified legal snapshot.

[`RELEASES.md`](RELEASES.md) is the publication log: one entry per source update, listing the documents the run added and changed, grouped by the amending act and generated from the run's diff.

## Observed history and legacy reconstructions

The separate [norwegian-laws-history](https://github.com/sondreskarsten/norwegian-laws-history) repository is the evidence ledger: it verifies each published observation release, records observed document membership without replacing earlier observations, and retrieves exact archived XML, daily since 25 September 2026. Observation time means when this collector inspected the source, not when the law took effect. Commencement, repeal, and canonical historical text remain unresolved unless separately established.

The [`law-history` branch](https://github.com/sondreskarsten/norwegian-laws/tree/law-history) is an **unverified reconstruction**: one commit per amendment act since 2001, built from the current consolidated text by applying parsed Lovtidend instructions, with some dates inferred. It cannot answer “what was the law on this date?” reliably, and the [comparison tool](https://sondreskarsten.github.io/norwegian-laws/book/diff.html) labels it as such; a textual difference is not proof of a legal change.

The [nightly workflow](.github/workflows/law-history.yml) rebuilds the branch at 05:30 UTC, moves the yearly tags `v2001`…`v<current year>`, and pushes a permanent build tag `history-YYYY-MM-DD` so a build can be cited after later rebuilds have replaced the branch. Acts with a commencement after the build date are not applied. Build tags older than 35 days are pruned except the first build of each month. The reconstruction is separate from the observed-source history product above.

The baseline commit ("Utgangspunkt: gjeldende tekst …", dated 2001-01-01) is today's text, not the law as it stood in 2001; the final commit ("Tilbakestilling til gjeldende tekst …") snaps every document whose replay did not round-trip back to the current text. `reconstruction-manifest.json` on the branch lists, per document, how many acts were replayed and whether it diverged, and the comparison tool shows that note. Documents that left the Lovdata corpus since publication began (2026-02-18) stay in the branch with their last published text until a dated deletion commit: on the legal repeal date when Lovtidend carries a whole-document repeal, otherwise on the day the publication detected the exit; both dates are in the commit. Documents repealed before publication began are not reconstructed.

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

Every commit the pipeline makes on `main` is a pure function of two inputs and says which one moved. `Oppdater lover og forskrifter fra Lovdata API …` commits carry new source archives through unchanged parser code; `Regenerer lover og forskrifter med endret parser …` commits carry changed parser code over the archives of the previous publication, restored from its public observation bundle, so a formatting change never appears as a legal change. When both moved, the regeneration is committed first. Each message ends with trailers naming the source manifest digest, every archive with its upstream timestamp, and the Git tree hashes of `lovdata-loader/` and `lovdata-publisher/`; `.github/scripts/provenance.py` produces them and refuses to commit output that a second formatting pass of the same snapshot does not reproduce byte for byte.

The [daily poll](.github/workflows/poll-lovdata.yml) compares the source list with the last acknowledged publication and requests a new build when they differ. Failed publication is not recorded as delivered.

Earlier plans and status records (the package-split design, the September 2026 delivery status and wind-down) are kept under [docs/archive/](docs/archive/) and are not current specifications. [docs/STRESS-TEST-2026-10-29.md](docs/STRESS-TEST-2026-10-29.md) is the running log of defects found and fixed since 29 October 2026; [TODO.md](TODO.md) lists what is open.

## Data format and limits

Each document is Markdown with YAML metadata such as `refid`, `tittel`, `departement`, `ikrafttredelse`, and `sist-endret`. Source date fields are retained as metadata; some display exports also use normalized or fallback dates. Do not interpret them as verified effective dates for every amendment operation.

The reader preserves supported source structures and links recognized references. Parsing and rendering can still lose or misinterpret content. Token coverage checks do not establish complete structural or legal correctness. Use [Lovdata](https://lovdata.no) to check the source text and legal status. This is an unofficial project, unaffiliated with Lovdata or the Norwegian government.

`historie/` records are keyed by the instruction wording printed in each amendment act. Every wording found in the 2001–2026 Lovtidend archives is catalogued in `lovdata-loader/src/lovdata_loader/instruction_catalog.json` (13 operation kinds: replace, new provision, repeal, renumber, move, word substitution, insert, commencement, preamble, structural title, delegation, decision text, target list). The daily run classifies every instruction against it; a wording that matches no catalogued operation opens or updates the issue "Ukjente endringsinstruksjoner i Lovtidend" (label `parser`), and the wording is added by a pull request. Design rules for node ids and derived indexes: [docs/NODE-HISTORY-DESIGN.md](docs/NODE-HISTORY-DESIGN.md).

## License

- **Law data:** Lovdata, [Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/no/2.0).
- **Source code:** [MIT](LICENSE).
