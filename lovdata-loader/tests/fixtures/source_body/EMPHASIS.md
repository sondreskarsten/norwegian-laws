# Source emphasis and paragraph-table fixtures

These three files retain exact Lovdata XML member bytes from the complete source bundle used for the structural inventory. `emphasis-source-members.json` records archive/member hashes, occurrence IDs and the selected model binding. XML is excluded from Git newline conversion.

The Bankenes sikringsfond law and 2017 delegation retain actual `<strong>` text. Their original source semantics and markup must survive independent source/model/render checking; no new formatting or legal date is inferred.

The 1995 Heidrun regulation reproduces the published v4 rejection for a table inside `article.defaultP`. The v4 grammar allowed this parent, but the reverse-render verifier incorrectly accepted only `article.legalP`. The corrected verifier accepts the three declared table-bearing paragraph forms while preserving the exact scroll wrapper, keyboard focus and source table. Previously accepted bodies require no HTML or stylesheet change.

The local generated law was visually inspected on desktop. The real regulation was inspected at 390 by 844: the document stays 390 pixels wide and the keyboard-focusable table region stays within it. See `docs/evidence/source-emphasis-tables-local.json`. These fixture results are not a whole-corpus or public v5 delivery claim.
