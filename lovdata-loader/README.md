# lovdata-loader

Download and parse Lovdata's public-data archives into the snapshot
directory this repo's publishing pipeline consumes: one JSON per law or
forskrift under `snapshot/laws/`, plus `snapshot/amendments.db` built
from Norsk Lovtidend avd. 1.

The CLI defaults to snapshot version 4. The production workflow explicitly uses
`--capture-source-bodies` for snapshot version 5. Publishers must validate the entire
snapshot before using it; older readers must reject unsupported versions. Direct
`write_snapshot()` callers without source evidence retain the version 2/3
contract. The existing display JSONL exports and SQLite date behavior are
unchanged; they are not the complete amendment interface described below.

```bash
pip install -e "lovdata-loader/[test]"
lovdata-load --download --output snapshot
# Retain ordered source bodies under the explicit v5 contract:
lovdata-load --download --capture-source-bodies --output snapshot-v5
python -m pytest lovdata-loader/tests/
```

## Ordered document content

Snapshots declare an exact content/formatter pair. The v4 container pair,
`ordered-law-containers-v1` / `law-markdown-ordered-containers-v1`, preserves
interleaved paragraphs, articles, sections, notes and remaining text. Optional
`content_order` references on a law or section point into its existing child
arrays; every child must occur exactly once. Empty or absent references retain
the earlier grouped traversal. Older content contracts reject populated
ordering references rather than silently changing the reader's interpretation.

This repairs observed ordering defects, including a closing provision previously
displayed before the law's first paragraph. It does not certify complete source
fidelity: unsupported or flattened structures still require independent review.
The v4 evidence envelope and unresolved legal-time declarations are unchanged.

## Ordered source-body capture

Snapshot v5 requires `ordered-source-document-body-v1` /
`law-markdown-convenience-with-source-body-v1`. It retains an additional
`source_body` for every selected law and regulation: ordered text/element children,
all body-tree attributes, exact inherited html/head/body attributes, base URL,
language, refid and raw-member/body/context hashes. Unknown forms are preserved.
The current Markdown reader continues to use the existing typed convenience
projection; the new field does not certify that projection's fidelity.

Capture and rendering have separate boundaries. ElementTree creates the body
model; a standalone Expat gate independently compares raw source events and
context. A closed rendering grammar then admits only supported structures.
Unsupported lists, images, formulas, row spans, inherited attributes and other
forms retain their exact raw/body evidence but cannot receive qualified HTML.
The initial renderer supports selected headings, provisions, HTTP(S) links,
footnotes and regular tables with column spans, with a reverse rendering check.
It does not establish legal effect or whole-document completeness.

Use `EvidenceBundle(capture_source_bodies=True)` or
`parse_law(raw, capture_source_body=True)` for explicit programmatic capture.
`LawData.to_dict()` preserves the new field when present and omits it for legacy
objects. V4 and earlier reject the field, and snapshot creation rejects mixed
captured/uncaptured models. The v5 parser identity adds `source_body.py` to the
original three source files. Non-selected duplicates keep their exact raw member
and model identity; only selected body models are persisted in document JSON.

## Source evidence and parsed amendments

`manifest.json` contains `evidence.version: lovdata-source-evidence-v1`, named
artifact paths, counts, and SHA-256 hashes for every generated artifact. The
new files are:

| Artifact | Contents |
| --- | --- |
| `source-observations.json` | Original archive names and scope, retained paths and hashes, source URL/lastModified, retrieval and local observation times, parser source fingerprint and Python/dependency versions. |
| `source-members.jsonl` | Every tar member in archive order, including excluded and unresolved members: original path, zero-based archive/member ordinals, byte hash/size, parse status, parsed model hash and occurrence identity. |
| `parsed-amendment-acts.v1.jsonl` | Every parsed amendment act occurrence, including overwritten duplicates. `record` contains every `AmendmentActData` field and each full `Amendment`, with raw date text, `changes_to`, unknown operations/targets, instructions and untruncated `new_text`. |
| `raw/<archive_sha256>.tar.bz2` | A separate copy of the exact source archive bytes, retained for independent replay; tar paths are inventoried without extracting them. |

The observation identity is
`manifest.artifact_hashes[manifest.evidence.observations]`. The `archives`
array in that file exposes each `raw_path`, `archive_sha256` and `size_bytes`.
The parser fingerprint hashes `parser.py`, `models.py`, and `evidence.py`;
`parser_runtime` separately records Python, Beautiful Soup, soupsieve and lxml
versions and the actual `html.parser` backend. An unavailable dependency
version is explicitly `null`.

All occurrence ordinals are zero-based. Parsed occurrence ordinals follow the
existing CLI selection order: original archive order, and laws (`nl-`) before
regulations (`sf-`) within each Lovtidend archive. Physical member ordinals
disambiguate duplicate paths. `source_occurrence_id` is the canonical-JSON
SHA-256 of `[archive_ordinal, archive_sha256, member_ordinal, member_path,
member_sha256, role]`. `parsed_model_sha256` hashes the full dataclass object
as sorted, compact UTF-8 JSON (`ensure_ascii=False`).

The selected occurrence remains the last occurrence of a refid for the role.
Each selected member binds its output artifact path and SHA-256; non-selected
occurrences remain in the inventory and amendment export. For an amendment
act that output artifact is the complete `amendments.db`. The export's
`amendment_occurrences` retains the original per-act ordinal and separately
marks unresolved target/operation recognition. Skipped source prefixes and
members missing a refid are recorded, not silently counted as parsed.

The amendment interface is **lossless relative to the parsed model**, captured
before SQLite date normalization. It does not claim lossless XML structure:
the existing parser flattens some amendment bodies, and
`source_structure_status` / `structural_coverage_status` remain `not_verified`.
Raw archives preserve the source bytes independently. History consumers must
pass their own structural coverage gate before constructing canonical text.

`legal_valid_time` is always `{ "status": "unresolved", "date": null }` in
this interface. Publication dates and source `lastModified` are retained as
source fields and never establish legal effect or historical knowledge.
`knowledge_cutoff` means the latest **local archive observation**, with
`knowledge_cutoff_basis: local_archive_observation`; historical knowledge time
remains unknown. Downloads made by this loader record `retrieved_at` in their
verified receipt. Imported archives or older receipts without a retrieval
timestamp explicitly record it as unknown.

`lovdata_publisher.snapshot.validate_snapshot()` checks all artifact hashes,
raw archive/member membership and hashes, selected output bindings, complete
parsed model membership, occurrence ordinals and counts. It does not rerun the
parser or prove legal semantics. Replaying the same archives in the same role
and scope order with the same parser/runtime reproduces the parsed-amendment
file and source/model member identities. Selected output hashes also depend
on materialization bytes (including the SQLite build); they bind those bytes
without claiming cross-runtime database binary equivalence. Local observation
timestamps are intentionally fresh.
The separately generated release receipt is allowed at the snapshot root and
is not part of its own hashed evidence bundle.

Part of [norwegian-laws](https://github.com/sondreskarsten/norwegian-laws).
MIT licensed; the parsed data itself is NLOD 2.0 (Lovdata).
