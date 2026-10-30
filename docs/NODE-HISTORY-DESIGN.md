# Node-level history: design rules

Status 30 October 2026. This note fixes two rules before any queryable index
(SQLite/parquet data releases, node ids, cross-reference graph) is built on top
of the parser output. Both rules close weaknesses named in the data-release
brainstorm of the same day.

## 1. One source of truth: every derived artifact is a function of the same run

The Markdown in `lover/`, `forskrifter/` and `historie/` on `main` is already a
pure function of (source archives, parser code), bound by the commit trailers
`Kildemanifest` and `Parser` and the reproducibility gate in
`.github/scripts/provenance.py`. An index must not become a second source of
truth next to it. Rules:

- The index is built **in the same workflow job, from the same snapshot** that
  produced the committed Markdown. It is never rebuilt from the Markdown, from
  git, or on a schedule of its own.
- The index carries the same `Kildemanifest` digest and the same `Parser` tree
  hashes in a metadata table, plus the commit SHA it was published with. A
  server that loads the index reports those three values and refuses an index
  whose digest differs from the commit trailer it claims to belong to.
- The index is published only on a `kilde` or `parser` publication, as an asset
  of that publication, never on a no-change day.
- Reproducibility is verified on a **logical dump** (sorted rows of every table
  hashed with SHA-256), not on the file, because SQLite and DuckDB files are not
  byte-deterministic. The dump hash is written to the commit trailer
  `Indeks` so the gate in `provenance.py verify-reproducible` can compare the
  second pass to it exactly as it compares `lover/` and `forskrifter/`.
- Schema changes are parser changes: they bump the index schema version, run as
  a `parser` publication and regenerate the previous sources first, exactly as
  a change to `lovdata-loader` does today.

## 2. Stable node ids: renumbering is an operation, not a new node

A node is a provision-level unit the parser already walks: document, chapter,
§, ledd, punktum, nr., bokstav, strekpunkt. Its *current* address
(`lov/1998-07-17-56 § 1-2 (1) nr. 4`) is not its identity, because amendment
acts renumber ("Nåværende § 4 blir ny § 5", "Nåværende tredje og fjerde ledd
blir fjerde og nytt femte ledd"). Rules:

- A node id is minted the first time a provision is seen and never changes.
  Renumbering writes a new *address* row with the act and in-force date; the
  id stays. Reads by address resolve through the address history for the
  `at` date.
- Renumbering can only be applied when the wording that expresses it is
  understood. That is what `lovdata-loader/src/lovdata_loader/instruction_catalog.json`
  is for: a catalogue of every operation wording found in the 2001–2026
  Lovtidend archives (13 operation kinds, both written languages, glued-word
  variants), with the effect each has on the target.
- The catalogue is a **contract**: a text that looks like an amendment
  instruction but matches no catalogued operation is an *unknown form*. The
  deploy workflow classifies every instruction on every run
  (`python -m lovdata_loader.instruction_catalog`) and opens or updates the issue
  "Ukjente endringsinstruksjoner i Lovtidend" (label `parser`) with the form,
  its count and example acts (`.github/scripts/instruction_forms_issue.py`).
  The publication continues: the text is kept as an `unknown` record, as
  before. The wording is added to the catalogue by a pull request, after which
  the parser can learn to apply it.
- Until a node-id layer exists, `historie/` records stay keyed by the address
  printed in the act, as today.

## Catalogue measurements (30 October 2026, full archives, 39,241 acts)

| Measure | Value |
|---|---|
| Instructions classified | 109,031 |
| Operation kinds | 13 (`replace_text`, `new_provision`, `repeal`, `renumber`, `move`, `word_substitution`, `insert`, `commencement`, `preamble`, `structural_title`, `delegation`, `decision_text`, `target_list`) |
| Instruction-like texts with no catalogued operation | 0 |
| Texts that are not instruction-like (prose bodies kept as `unknown` records) | 431 |
| `replace_text` | 88,271 |
| `new_provision` | 20,487 |
| `renumber` | 7,081 |
| `repeal` | 7,484 |
| `word_substitution` | 940 |
| `insert` | 204 |
| `move` | 67 |

Two caveats. The catalogue classifies by wording and is many-valued (one
instruction can be `replace_text` and `new_provision`); it does not yet apply
the operations. And a free-text decision published as a forskrift with a new
turn of phrase will open the issue; that is intended, the review decides
whether it is an operation or belongs under `reviewed_non_instructions`.
