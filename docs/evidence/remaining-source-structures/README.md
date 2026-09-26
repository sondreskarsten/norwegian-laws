# Remaining asset, formula and table inventory (v8)

Scope: all 523 rejected documents in retained observation be688fe828a9bfa712680a2531fc619186b8b472ba60359bb12c6c2bf9df3f6b. Inventory includes structures hidden behind another first rejection. Source bundle SHA256: 83e946e4ef03576b3e9b235b5c041a54adf25bbf00a8c1094133ddb51b5f523f.

## Images

1,141 image occurrences refer to 943 distinct URLs: 487 GIF, 331 PNG (including two uppercase .PNG), 125 JPEG. Eleven figure containers also carry captions. Source attributes include literal src, alt, width and height. Image alt is absent on some real source images; do not invent descriptions and label any generated accessibility descriptions separately.

The retained member ledger contains 45,089 XML members and 31 directories, and zero image binaries. Missing retained image payloads are an acquisition/interface gap, not evidence that the referenced public files do not exist.

Actual unauthenticated range retrieval returned 300 HTTP 206 image prefixes with expected PNG/GIF/JPEG signatures, then 643 HTTP 403 responses. The exact transition after 300 successes is consistent with a request cap; it does not prove the remaining files are unavailable or absent. Further requests stopped. No alternate identity or access mechanism was attempted. Full payload identity remains unverified even for the 300 accessible prefixes. See asset-access.json for each URL, timestamp, response headers and signature. No complete image binaries were retained because the server honoured byte ranges.

Required next acquisition: producer-controlled, rate-limited full downloads with retry/backoff at the supported access limit; retain final bytes inside the existing evidence-publication path. Record source occurrence, exact model path and original src, resolved/final URL, retrieval timestamp, response metadata, byte count, SHA256 and media validation. Multiple source uses of one content hash remain separate provenance references. Offline independent regeneration must resolve only the asset manifest bound to that observation and verify all bytes. Do not use live hotlinks to qualify historical bodies.

Smallest source fixture: forskrift/2022-06-17-1114, image at /main[1]/section[1]/article[1]/img[1], static/SF/sf-20220617-1114-01.png, 216x217, source alt describes the standardized retouched-advertising label. Figure fixture: forskrift/2021-06-20-2086.

## Formulas

261 div.latexBlock and 94 span.latexInline nodes. TeX is present as exact text in retained XML, not an absent external asset. One inline formula also carries lang=en. Preserve literal source TeX and its path/hash before rendering; do not silently repair backslashes, formulas or unsupported commands. Use a pinned offline math renderer with all required fonts/styles included in product provenance, safe rendering settings and explicit rejected-command reporting. The independent consumer must verify source binding and deterministic output.

Smallest block fixture: forskrift/2023-10-30-1734, /main[1]/article[8]/article[2]/div[1]. Smallest inline fixture: forskrift/2017-01-06-10, /main[1]/article[3]/article[2]/ul[1]/li[1]/article[1]/article[1]/span[1].

## Tables

The rejected subset contains 3,642 tables, all with explicit tbody; 2,299 also have thead. No tfoot/colgroup/col source forms were found. There are 4,610 td and 47 th with rowspan, across 39 td-bearing documents and 7 th-bearing documents (these sets can overlap). Actual positive rowspan values range from 2 to 33. There are 1,663 tr.startGroup rows across 40 documents. The rowspan attributes and grouping rows are implementable structures, not source-access limitations.

Implement a slot-based grid that accounts for carried spans, column spans, complete row coverage and row-group boundaries. Retain grouping classes, captions, source order, header cells and exact row/column span values. Reject actual overlaps, holes or spans extending outside their source row group instead of silently correcting the table. Keep the bounded horizontally scrollable table presentation.

Smallest td rowspan fixture: forskrift/2025-12-09-2503 (Trøndelag fylke cell). Smallest th rowspan fixture: forskrift/2025-12-19-2784 (combined colspan=2 and rowspan=4 header).

## Scratch evidence

- inventory.json: exact source references, node paths, form/attribute counts and smallest nodes.
- retained-members.json: retained member inventory showing no image binaries.
- table-inventory.json: table forms, parent edges and exact attribute values.
- asset-access.json: actual public URL probe results and access limitation.
- asset-structure-fixtures-v8/source-members.json and adjacent XML: independently hash-checked retained primary-source fixtures.

This report is inventory and acquisition evidence only. It does not declare image, formula or complex-table delivery complete.

The subsequent v9 table batch supports 24 additional bodies locally; its qualification evidence is retained in `../source-body-table-spans-v9-local.json`. Asset/formula acquisition remains unfinished.
