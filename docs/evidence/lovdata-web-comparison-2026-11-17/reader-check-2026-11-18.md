# Reader page check, 18 November 2026

Pages: `lover/lov-1961-02-03.html` (bilansvarslova) and `lover/lov-1992-11-27-109.html` (EØS-loven) on https://sondreskarsten.github.io/norwegian-laws/, viewed at 1366 px and 375 px next to the same documents on lovdata.no. The live site was the build of run #268 (before #44); deploy #269 failed in `deploy-book`. The last column says whether the Markdown on `main` (`1bc20553`) still has the problem.

| # | Site | lovdata.no | `main` |
|---|---|---|---|
| 1 | Bilansvarslova § 2: items a–d run together in one paragraph | separate list items | still: lettered items are lines without a blank line; Markdown only makes lists of numbered items |
| 2 | Footnote markers as bare digits ("visste 1 at", "Etableringsrett. 1" in the contents, "1 Jf. EØS-avtalen …" inside the § 5 amendment note) | superscript markers; footnotes on their own line | fixed: `<sup data-fn>` and `<sup data-fn-note>` |
| 3 | Bilansvarslova Rettsområde shows a literal `\n` between areas | not shown | still: `rettsomrade` holds `\n` as text |
| 4 | Amendment notes italic in bilansvarslova, small grey in EØS-loven § 1, where the footnote text runs into the note | small type, footnotes on separate lines | partly changed; recheck after a deploy |
| 5 | Space before punctuation after links ("nr. 28 , 26 mai", "nr. 1054 )") | no space | unchanged (open decision) |
| 6 | No Rettet, EØS/EU/Schengen, ELI or "Overskriften endra …" note | shown | not published |
| 7 | Only some references are links | every law, provision and act linked | unchanged |
| 8 | Phone width: no element wider than the 375 px viewport | | |
