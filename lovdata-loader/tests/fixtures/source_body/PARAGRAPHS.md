# Paragraph qualification source fixtures

The four `paragraph-*.xml` files preserve exact source members from the retained v5 snapshot. `paragraph-source-members.json` records their archive/member hashes, occurrence identities and selected model bindings. The inputs include Grunnloven, Barneloven, Instruks for Regjeringen and the 2000 delegation regulation.

Qualification independently compares raw XML with the ordered model and reverses the rendered HTML back to source structure. Paragraph numbering must already occur as visible source text and match `data-numerator`; the renderer creates no numbering. Continuation paragraphs retain their nesting. Centred source paragraphs/headings and small ordinary paragraphs keep declared layout. `data-legalArea` is retained source classification metadata and supplies no legal validity claim.

Unknown forms, attributes, text sizes, conflicting centring and mismatched numbered labels remain explicit rejections. Existing qualified forms retain their old stylesheet bytes. Source classification codes are preserved verbatim, not interpreted.
