# lovdata.no web comparison, 17 November 2026

Every published document (5,906) compared with its page on lovdata.no, fetched from a laptop at one request per 3 seconds. Published output compared: `1bc20553` (`main` after PR #44). Source data for the list measurements: observation `e25331b1…`.

## Files

- `compare_lovdata_web.py <repo> <out> <delay>`: fetches `https://lovdata.no/<refid>` (the catalog address if the redirect lands on another document, the full document if lovdata.no serves a front page only), caches pages under `<out>/pages/` and writes `result.json`. The cached pages are not committed.
- `summarise_lovdata_web.py result.json summary.md`: the tables in `summary.md`.
- `result.json`: per document the missing and extra words, the opening-paragraph word count, both sets of header fields and both addresses.
- `measure_source_lists.py`, `measure_source_list_words.py <observation dir>`: lists in the source XML by where they sit.

The comparison is a per-document word multiset: it does not see reordering.

## Last amended (3 documents)

| Document | lovdata.no | Lovdata open data | Ours | Cause |
|---|---|---|---|---|
| lov/1973-03-09-14 | LOV-2018-06-22-77 from 30.03.2026, LOV-2025-06-20-70 from 01.01.2026 | `<a href=""/> fra 2026-03-30, <a href="lov/2025-06-20-70">` | empty | empty link in Lovdata's data; we read only the first link and drop lov/2025-06-20-70 |
| forskrift/1988-12-23-1073 | FOR-1993-12-29-1354 | `<a href=""/>` | empty | empty link in Lovdata's data |
| forskrift/2017-04-18-480 | FOR-2026-11-11-2360 | forskrift/2026-10-09-2041 | forskrift/2026-10-09-2041 | regulations dataset behind the web; the act is in the Lovtidend 2026 archive |

Empty links: 2 of 2,991 documents with the field. 57 documents name several amending acts; ours keeps the first, which matches lovdata.no in all of them.

## List numbers and letters (41,303 missing words)

The marker is only in attributes (`<li data-name="1." value="1">`). `_parse_list` reads it, but is only called from `_parse_ledd`. A list that is a direct child of a section, chapter or the document body goes to the `else` branch of `parse_article`, `parse_section` or the body loop, and `_text` flattens it into `trailing_text`.

| List sits directly under | Lists | Items | Items with marker | Words | Documents |
|---|---|---|---|---|---|
| a paragraph (handled) | 141,179 | 587,000 | 548,971 | | |
| `legalArticle` | 4,202 | 18,664 | 17,573 | 721,621 | 821 |
| `section` | 3,218 | 17,696 | 14,521 | 699,637 | 1,111 |
| document body | 568 | 1,926 | 1,918 | 61,835 | 419 |
| other (`marginIdArticle`, `futureLegalArticle`, `change`, …) | 1,976 | 6,761 | 6,024 | 243,844 | 547 |

Effects:

1. Markers and item boundaries are lost; `nr. 2` or `bokstav b` cannot be addressed.
2. `trailing_text` is placed after all paragraphs of the section, so the list can move (forskrift/1999-03-11-301 § 1-4).
3. The formatter prints a section's `trailing_text` in italics, the style of editorial notes (forskrift/1991-10-15-713 § 10).
4. `reconstruct.strip_trailing_text` empties it on `law-history`: forskrift/1991-10-15-713 § 10 there has only its heading.
5. The second stream compares text content, so neither stream saw the markers.

## Other observations

- 2,998 documents have an opening paragraph on lovdata.no (`Hjemmel: Fastsatt …`, `Jf. tidligere …`, 141,463 words) that is not in our body text; the source carries it in the header field `miscInformation`.
- 1,701 catalog `lovdata` links return 404: the documents are under `DEL` (1,430), `INS` (187) or `STV` (84), not `NL`/`SF`. `https://lovdata.no/<refid>` redirects correctly, except `lov/1814-05-17`, which lands on the nynorsk text.
- 4,628 missing words are footnote digits fused to the preceding word on the web page (`tid1`).
- ELI differs only for lov/1814-05-17-nn: lovdata.no `/eli/lov/1814/05/17/nno`, ours `/0`.
- 7 regulation titles differ: lovdata.no shows an abbreviated title, or `§ 20 –` where ours has `§ 20–`.
