# Norwegian laws product completion scope

Confirmed 25 September 2026. This records the user's product overview and subsequent direction: **do all work in this task; no cloud session or handoff**. The original overview remains a dated evidence snapshot, not a statement that unfinished capabilities work.

## Intended product

A reader can find current Norwegian laws and central regulations, read their structure faithfully, follow published amendment records, retrieve earlier observations and removed-document copies, and request historical legal text with an explicit evidence basis. A data consumer can retrieve exact source evidence and reproduce published results. A maintainer can operate both personal GitHub repositories reliably with ordinary repository credentials.

The observed-history pilot is an intermediate delivery. It does not replace the requested historical-date functionality.

## Delivery constraints

- Both repositories remain under `github.com/sondreskarsten`.
- Reuse `fix/reliable-laws-delivery` and `fix/reliable-history-delivery`; minimize new branches.
- Preserve generated `gh-pages`/`law-history` branches, existing tags, source releases and accepted observations.
- All implementation, integration and coordination continue in this task. No cloud coding setup, new task or handoff.
- Delivery is the focus. Checks must establish real published behavior or prevent a demonstrated defect; test volume is not progress by itself.
- Existing documentation and green workflows are not sufficient evidence of working functionality.
- Source observation time, publication time, Git time and legal validity are separate.
- Do not turn today's consolidated text into an invented historic baseline; do not infer repeal from source disappearance.
- Raw source bytes remain retrievable when a derived representation cannot be qualified.
- The initial source population is the current selected public corpus plus recorded prior documents and amendment evidence. Historical coverage expands through explicit source acquisition; no universal earliest legal date is assumed.
- A missing source, unsupported operation or unresolved commencement remains an explicit gap. It is not grounds for claiming the requested historical coverage complete.

## User stories and ownership

| ID | User outcome | Owning work packages |
|---|---|---|
| U01 | Read the latest selected laws and regulations with accurate membership | D1, D10 |
| U02 | Find a document by title, abbreviation, number or body text | D2 |
| U03 | Read faithful hierarchy, paragraphs, lists, tables, footnotes and references | D1, D6 |
| U04 | Browse topics and ministries and follow working links | D2 |
| U05 | Find, copy and consume available feeds; understand unavailable feeds | D2 |
| U06 | Run amendment notifications without duplicate alerts | D2, D10 |
| U07 | Inspect document/paragraph amendment history and activity with honest date labels | D2, D7, D9 |
| U08 | Compare legacy output while understanding its limits | D2, D9 |
| U09 | Recover a missing document and retrieve retained prior copies | D3 |
| U10 | Download correctly described metadata, display records and full evidence | D2, D4, D7 |
| U11 | Verify publication identity and retrieve exact raw XML | D1, D4, D10 |
| U12 | Reproduce stable, citable observed-text versions across multiple observations | D4, D5 |
| U13 | Preserve duplicate language/source occurrences and identify the displayed variant | D4, D6 |
| U14 | Understand operation targets and commencement uncertainty without invented dates | D7 |
| U15 | Ask what text applied on a legal date, and optionally what evidence was known by a cutoff | D8, D9 |
| U16 | Get an explicit incomplete/unavailable answer when historical evidence cannot support an answer | D8, D9 |
| U17 | Install, clone and operate on Linux/Windows with ordinary repository credentials | D4, D5, D10 |
| U18 | Rely on scheduled publication, catch-up and recovery after interrupted runs | D5, D10 |
| U19 | Use the existing optional mirror without stray runtime files or unclear retention/access | D10 |
| U20 | Distinguish a legal change from a parser/formatter representation change | D4, D7, D8, D9 |

## Current evidence baseline

- Last complete consumer readback before this plan: source `2d90a466a8ca3954494f82041409b39242c5c1f5`; 756 laws + 5,118 regulations.
- Public observation: `ccdbf3e45098076118bf9362b60d31b7a80dc1aab1dcc2e226a4aee58c92b596`; independent intake and raw retrieval verified.
- Main PR14 is merged as `c8fba0a6bfe131883dee63d6ab702a1dc1f248aa`. Production run `36171176807` has completed successfully. The public receipt now names source `7971606f7683612779e17cea1ef53d8531ba0fa3` and observation `ca32e6b7b13b3435683c450f81cfc1ea0ae4c0a95694a0cde0d7cf2bc20e5f4c`; the five repaired examples and new independent history intake still need final consumer readback.
- History PR10 is merged as `b9a0d9aa37a8447f5e4d79780d48dbf78e6c097c`; Windows byte-preserving checkout verified.
- Local unshipped work: strict document-body qualification, derived-output generation/CLI, exact 105-document reader archive, subscription/count repairs.
- Main issues #8–#10 and history #1/#3 are closed. Main #3–#7 and history #4–#8 remain open.
- Global/per-document feed readback and display exports passed. Topic/ministry navigation, subscription UX, activity pages, broader history journeys and external notification delivery are not thereby proved.
- One observation and same-day repeats do not establish subsequent daily operation.

## Product distinctions

1. **Current reader:** a source-derived publication; document membership and structural fidelity are distinct.
2. **Observed source history:** what exact bytes were retrieved and when.
3. **Qualified observed text:** a versioned readable projection whose declared structure matches its source.
4. **Legal history:** a reconstruction justified by a prior-state basis, applicable operations and commencement evidence.
5. **Prior reader archive:** exact old generated Markdown copies with Git provenance, outside the raw-observation/canonical authority.
6. **Legacy annual comparison:** preserved unverified output, never a legal reconstruction input.

## Completion standard

For each story, record the deployed identity, representative consumer result, limitations and remaining coverage. Required corpus-wide properties need corpus-wide evidence; a three-document pilot cannot establish them. Mark the overall work complete only when the requested outcomes and historical coverage are demonstrated, or the user explicitly changes scope after a concrete source/access limitation has been established.

