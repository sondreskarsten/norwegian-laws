# Observed-history reader delivery

This implements the observed-history part of D9 in the accepted product-completion plan. Work remains in the two personal repositories and existing implementation branches. A legal-date selector remains dependent on D8 evidence coverage.

## Reader outcome

From a current law or regulation, open its retained observed versions, choose an exact version, read qualified text, compare two qualified copies side by side, inspect the source basis and copy a stable citation. Unsupported versions explain their availability and link to evidence without substituting current text. A previously qualified version remains explicitly selectable when a later observation is rejected. Observation time and legal effective time are different; this product only supplies the former.

## Data boundary

The history repository exports only committed complete-body receipts and exact Git publication proofs at a recorded checkout. It verifies immutable bundle/artifact hashes and selected payload bindings. This is retrieval of the recorded qualification, not requalification under the current renderer. All earlier representations remain available.

`history-reader-export-v1` supplies a compact index, per-document version metadata and deduplicated exact HTML files. The index binds each metadata file by SHA-256; each qualified version binds its HTML bytes. Rejected versions have no HTML. Source receipt/bundle URLs, member identities and pinned product/publication URLs accompany each version. Export writes a new directory atomically and does not change accepted evidence.

The current-law publisher consumes a separately checked-out history repository and records its commit in the exported index. It copies the exact export and generates pages under `observasjoner/`. Site links are registered through the existing SiteIndex. The default version is the latest source observation, with append order breaking ties; reprocessing an older source must not become the apparent latest observation.

## Page behavior

- Current-title breadcrumb and return link when that current document exists.
- Clear observed-source scope and version selector with observation date, qualification and representation-change status.
- Exact qualified HTML in a same-origin sandbox without script permission. Rejected versions display their reason and source download instead.
- Optional side-by-side comparison of qualified versions, retaining source structure; no inferred legal differences.
- Stable `?product=<full identity>` citation, original HTML download and source/publication links. Unknown product selections show an explicit unavailable result and clear stale content.
- Searchable observed-history directory, including retained entries no longer in the current corpus.

## Delivery evidence

Use real two-product fixtures to check exact HTML, rejected no-payload behavior, version ordering, committed proof requirements and failure on tampering. Exercise the generated pages in a browser at desktop and 390px, including selection, comparison, citation, unavailable product and keyboard navigation. Publish and read back the pinned index, representative exact HTML and complete current-to-observed journeys before marking D9's observed-reader slice delivered.

Raw XML remains retrievable with the history CLI and its exact source bundle. The first reader slice links that bundle and identifies the original member; it does not claim individual browser XML extraction. Legacy reconstructed versions retain separate labels and references.
