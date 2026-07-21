# lovdata-publisher

Turn a lovdata-loader snapshot into the published outputs of
[norwegian-laws](https://github.com/sondreskarsten/norwegian-laws):
formatted Markdown under `lover/` and `forskrifter/`, Quarto book
chapters, per-law and per-paragraph history pages, Atom feeds (per law,
rettsområde, and ministry), JSONL manifests with schemas, full-text
search index, sitemap, README count refresh, and the backdated
`law-history` branch via `git fast-import`.

```bash
pip install -e "lovdata-publisher/[test]"
lovdata-publish --snapshot snapshot --output . --quarto
quarto render
lovdata-publish --post-render --output . --site-dir _site
python -m pytest lovdata-publisher/tests/
```

MIT licensed.
