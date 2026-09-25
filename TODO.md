# Norwegian laws: delivery backlog

Updated **2026-09-25** from source, workflow, live-source and browser audits.
**Current publishing repair is implemented locally; live deployment and consumer
readback remain pending.** A passing local run or green job does not close the
delivery work below.

Keep the existing personal repositories:
[norwegian-laws](https://github.com/sondreskarsten/norwegian-laws) for current
publication and [norwegian-laws-history](https://github.com/sondreskarsten/norwegian-laws-history)
for the new history product. Preserve the generated `gh-pages`, `law-history`
branches and existing tags. Automatic legacy-history regeneration is gated by
`ENABLE_LEGACY_HISTORY == 'true'`; leave it disabled during migration. Manual
legacy dispatch remains available.

## 1. Finish current-data delivery

Implemented locally: live-manifest archive selection, source identity and SHA256
cache checks, atomic downloads, a processed source receipt, snapshot validation,
and revised publication wiring. These changes await live delivery proof.

- [ ] Run the complete fresh-source pipeline and reconcile **document identities**
  through source, snapshot, generated corpus and deployed site. The audit found
  `forskrift/2026-09-18-1871` missing and `forskrift/2019-11-22-1547` retained even
  though both regulation sets counted 5,118. Handle the duplicate Constitution
  source explicitly; counts alone are insufficient.
- [ ] Publish the exact `snapshot/source-manifest.json` used by the successful
  build with its snapshot membership/integrity metadata and pinned source commit.
  Advance published state only after verified deployment. Confirm a failed
  publication is retried when the upstream manifest has not changed.
- [ ] Read the new regulation and published receipt from the live site; reconcile
  removed-document behavior, feeds and machine-readable consumers. Verify the
  next daily update before describing ongoing delivery as complete.
- [ ] Keep cloud mirroring optional. Publish only clean output; investigate and
  remove previously replicated `gha-creds-*.json` artifacts as authorized, then
  verify destination contents and access independently of upload logs.

## 2. Complete the shared data interface

- [ ] Preserve mixed text/list order in the canonical model and formatter, and
  resolve structured regulation amendment targets. The audit reproduced reordered
  text despite 100% token coverage and an empty regulation `target_law`.
- [ ] Finish a versioned producer/consumer contract: ordered content, source and
  output identities, parser/formatter versions, exact membership and explicit
  unresolved content. Verify deterministic replay through independently installed
  packages; declare the publisher's loader dependency or remove that coupling.
- [ ] Preserve the existing JSONL display API with documented limits, and provide
  a versioned lossless amendment interface for history. Current export drops
  unknown targets and truncates instructions/replacement text; it is not a
  canonical reconstruction input.

## 3. Deliver evidence-backed history

The new history repository was a README-only placeholder at audit time. The
legacy builder uses current text as a 2001 baseline and substitutes publication
dates for unknown commencement; its tags are not verified historical snapshots.

| Open issue | Remaining deliverable and acceptance evidence |
|---|---|
| [history #1: reusable pipeline and history implementation](https://github.com/sondreskarsten/norwegian-laws-history/issues/1) | Implement a small law-and-regulation pilot using the repaired interface, immutable source provenance and independently known historical checkpoints. Separate source publication, observation/knowledge time and legal valid time; retain unknown or partial commencement and unsupported intervals explicitly. Do not import the legacy graph, tags or generated text as authoritative evidence. |
| [#3: orphan v2000](https://github.com/sondreskarsten/norwegian-laws/issues/3) | Replace the hardcoded version range with an explicit supported-version catalog. Stop presenting the disconnected v2000 graph as a verified version; retain existing refs until an explicit migration decision. |
| [#4: future-year ordering](https://github.com/sondreskarsten/norwegian-laws/issues/4) | Prevent future or unsupported years from appearing as completed historical snapshots. Verify the order and provenance of selectable checkpoints; the audit confirmed v2028 was behind v2026. |
| [#5: inaccurate point-in-time claims](https://github.com/sondreskarsten/norwegian-laws/issues/5) | Correct version-page, diff and Git examples to describe the actual evidence and limitations. Display source basis, knowledge cutoff, legal-date certainty and reconstruction status for each supported result. |
| [#6: missing repealed documents](https://github.com/sondreskarsten/norwegian-laws/issues/6) | Retain terminal texts and source evidence for documents leaving the current corpus. Record observed exit separately from proven legal repeal; preserve unknown legal dates. Verify retrieval of a repealed example and provide recovery links for unavailable periods. |
| [#7: unstable history publication](https://github.com/sondreskarsten/norwegian-laws/issues/7) | Publish stable, citable identities with idempotent updates, explicit correction/version policy and checked remote/LFS readback. Preserve legacy references during consumer migration. Force rebuilding is confirmed; the claim that every SHA changes every day was not supported by the September 25 run. |

## 4. Finish the reader experience

- [ ] [#8: search payload](https://github.com/sondreskarsten/norwegian-laws/issues/8)
  — reduce or explicitly separate the full-text download from lightweight search.
  The audit measured 29,717,270 decoded bytes for `search.json`; verify actual
  transferred bytes and usable results on a constrained mobile connection.
- [ ] [#9: missing/repealed-page recovery](https://github.com/sondreskarsten/norwegian-laws/issues/9)
  — deploy a project 404 page with search, history and source links. Verify both
  an unknown URL and `lover/lov-1981-05-29-38.html` recover usefully.
- [ ] [#10: mobile comparison](https://github.com/sondreskarsten/norwegian-laws/issues/10)
  — wrap controls and contain diff scrolling. Verify the page at 390px width,
  and clear the previous result when equal or otherwise invalid versions are
  selected. Retest search, reading, crosslinks and paragraph deep links after
  deployment.

Close each item with its source/build identity, deployed receipt and relevant
consumer readback. Keep local implementation, publication and verified daily
operation as separate states.
