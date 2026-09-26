# Older primary-source acquisition

Checked 26 September 2026. Acquisition evidence only; no legal reconstruction qualified.

## Local deliverables

- `manifest.json`: original/final URLs, retrieval times, response types, sizes and SHA-256. Failed attempts retained.
- `uio-volume-links.json`: 200 exact NB volume links from UiO's 1877–1973 index.
- `government-pdf-links.json`: 49 government-hosted PDF links.
- Four full PDFs: 1965 building-law print, 1983 amendment and commencement order, 1985 law.
- NB IIIF manifests plus exact full-resolution page and ALTO OCR samples for 1877, 1965, 1973 and 1975.
- `coverage-implications.json`: measured counts and limitations.

## Verified official archive route

UiO index: https://www.ub.uio.no/fag/rettshistorie/norsk-lovtidend/

PowerShell Invoke-WebRequest obtained this index with normal TLS checks. Python urllib's certificate-chain failure was local; it does not prove source unavailability.

Follow index URNs to `https://api.nb.no/catalog/v1/iiif/{URN}/manifest`. Exact image and ALTO URLs are supplied by each manifest. Four sampled manifests and their page-image/OCR bytes returned HTTP 200 without credentials. Metadata identifies public-domain, unrestricted access. Preserve scans and OCR separately; OCR is not qualified legal text.

The 1975 volume came from the NB catalog API's own presentation link. A date-filtered catalog search works, but matches unrelated full text too. Filter exact title/series metadata. Its 10,808 results are not a gazette-volume count, and only the first result page was retained.

UiO index gaps: 1888/I, 1891/I+II, 1892/II, 1949/I+II, 1950/II, 1958/I. These are missing index links, not proven missing NB holdings. Split issues/registers explain why 200 links exceed the number of year/division pairs.

## Government source route

Index: https://www.regjeringen.no/no/tema/plan-bygg-og-eiendom/plan_bygningsloven/bygg/bygningsregelverket-fra-1965--20172/bygningsloven/id2590707/

The 1965 PDF is a contemporaneous printed-law scan, 55 pages. The other acquired PDFs are government-hosted 2017 Lovdata printouts of older enactments/orders. Preserve that provenance; do not describe those as original gazette scans. NB provides a separate route to original gazette corroboration.

Visual inspection confirmed 1965 page 2 identity/start; 1985 page 1 identity; 1983 amendment pages 1 and 6; and commencement order page 3.

Real timing conflict: amendment 1983-05-27-32 page 1 metadata gives 10 July 1983. Its operative section II delegates commencement to the King and allows provision-specific dates. Linked order 1983-07-08-1244 page 3 says the law enters force 1 August 1983. Retain both claims and exact locations; resolve against the original gazette and corrections before an eligible temporal interpretation. Do not silently trust the header.

The amendment PDF returned 403 with urllib's default user agent, then HTTP 200 with an ordinary browser user-agent string. No credentials or TLS override were used.

## Coverage implications

Pre-2001 evidence is demonstrably obtainable. Missing producer ingestion, source segmentation, scan qualification and interval completeness are implementation work, not established external access limitations. No repo changes or publication were performed here. Pre-1877 holdings and complete 1974–2000 enumeration remain outside this bounded result.
