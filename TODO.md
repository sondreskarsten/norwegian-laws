# Norwegian laws: open items

Updated **2 November 2026**. The 29–30 October stress test ([log](docs/STRESS-TEST-2026-10-29.md)) replaced the September delivery plan; that plan and its status records are archived under [docs/archive/](docs/archive/).

## Delivered and running

- Daily publication of current laws and central regulations with provenance-bound commits, observation releases, the corpus index and public-site readback (`.github/workflows/deploy.yml`, `poll-lovdata.yml`).
- Nightly `law-history` reconstruction with yearly and dated build tags, removed documents kept until their dated deletion, `reconstruction-manifest.json` (`.github/workflows/law-history.yml`).
- The MCP server (`norwegian-laws-mcp/`, 21 tools) installable with `uvx`; the instruction wording catalogue with its watchdog issue.
- `norwegian-laws-history` continues as the evidence ledger.

## Open by decision

- 626 multi-target amendment acts (mostly new forskrifter whose change instructions do not name a provision) still produce no records, and 858 records carry an instruction without recoverable wording.
- Node ids in the corpus index do not follow a provision across renumbering.
- Documents repealed before publication began (2026-02-18) are not reconstructed; legal-date reconstruction of past texts is not delivered and not planned here.
- The optional GCS mirror's retained object versions and IAM have not been audited separately.

## Open checks

- Reader pages for bilansvarslova and EØS-loven viewed in a browser on 18 November 2026 (desktop 1366 px, phone 375 px) next to lovdata.no. The live site was still the build of run #268, since deploy #269 failed. Findings: [reader check](docs/evidence/lovdata-web-comparison-2026-11-17/reader-check-2026-11-18.md). Recheck footnote markers and amendment-note styling once a deploy after #44 has run.

## Housekeeping

- The remote branch `fix/reliable-laws-delivery` is merged (0 commits ahead of `main`) and can be deleted.
