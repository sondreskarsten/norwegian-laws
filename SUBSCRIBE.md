# How to subscribe to regulatory changes

This repo publishes Atom feeds for parsed amendment records by document, topic, and ministry. Use the feed catalog to check availability; feeds do not establish complete historical coverage or when each legal change took effect.

## Interactive: paste a law name, get the feed URL

[**Try the subscribe page →**](https://sondreskarsten.github.io/norwegian-laws/book/abonner.html) — type any law name or abbreviation (regnskapsloven, aml, pbl, …) and instantly see the feed URL with a copy button.

## Finding your feed URL

Available document feeds use this URL pattern:

```
https://sondreskarsten.github.io/norwegian-laws/feeds/lov-{YYYY-MM-DD-NN}.xml
https://sondreskarsten.github.io/norwegian-laws/feeds/forskrift-{YYYY-MM-DD-NN}.xml
```

Common laws:

| Law | Feed URL |
|---|---|
| Regnskapsloven (rskl) | `feeds/lov-1998-07-17-56.xml` |
| Aksjeloven (asl) | `feeds/lov-1997-06-13-44.xml` |
| Allmennaksjeloven (asal) | `feeds/lov-1997-06-13-45.xml` |
| Arbeidsmiljøloven (aml) | `feeds/lov-2005-06-17-62.xml` |
| Skatteloven (sktl) | `feeds/lov-1999-03-26-14.xml` |
| Konkursloven (kkl) | `feeds/lov-1984-06-08-58.xml` |
| Verdipapirhandelloven | `feeds/lov-2007-06-29-75.xml` |
| Finansforetaksloven | `feeds/lov-2015-04-10-17.xml` |
| Hvitvaskingsloven | `feeds/lov-2018-06-01-23.xml` |
| Personopplysningsloven (popplyl) | `feeds/lov-2018-06-15-38.xml` |

For other laws, browse the [feed index](https://sondreskarsten.github.io/norwegian-laws/feeds/) or use [`laws.json`](https://sondreskarsten.github.io/norwegian-laws/laws.json) to look up a `refid` programmatically.

You can also subscribe by topic or ministry:

```
feeds/topic-skatte--og-avgiftsrett.xml
feeds/topic-bank-finans-og-regnskapsrett.xml
feeds/topic-arbeidsrett.xml
feeds/dept-finansdepartementet.xml
feeds/dept-justis--og-beredskapsdepartementet.xml
```

## RSS / Atom readers

Most modern feed readers accept Atom 1.0. Paste the feed URL into:

- **Feedly** — Add Content → enter URL
- **Inoreader** — Add Subscription → Feed URL
- **NetNewsWire** (macOS/iOS, free) — File → New Feed
- **Thunderbird** — Account Settings → Add → Feeds
- **Microsoft Outlook** — RSS Feeds → Add a new RSS Feed
- **NewsBlur** — Add a Site

## GitHub Actions

React to law changes from inside your own GitHub repository.

**The easiest path: copy the [reusable workflow template](https://github.com/sondreskarsten/norwegian-laws/blob/main/examples/github-action-watcher/.github/workflows/watch-norwegian-laws.yml)** and edit the `feeds:` matrix. It polls Atom feeds every weekday morning, opens a GitHub Issue when amendments are found (with affected paragraphs broken out as `<category>` elements), and persists state so it never refires for the same amendment.

```yaml
matrix:
  feed:
    - name: "Regnskapsloven"
      url: "https://sondreskarsten.github.io/norwegian-laws/feeds/lov-1998-07-17-56.xml"
    - name: "Skatteloven"
      url: "https://sondreskarsten.github.io/norwegian-laws/feeds/lov-1999-03-26-14.xml"
    # … as many as you like
```

See [examples/github-action-watcher/](https://github.com/sondreskarsten/norwegian-laws/tree/main/examples/github-action-watcher) for the full workflow file and per-feed setup guide.

## Repository notifications

GitHub repository notifications concern repository activity rather than one law. Use an Atom feed or the watcher template above for document-specific amendment notifications.

## Python — poll and dedupe

```python
import feedparser
import json
import pathlib

URL = "https://sondreskarsten.github.io/norwegian-laws/feeds/lov-1998-07-17-56.xml"
state_file = pathlib.Path(".seen_amendments.json")
seen = json.loads(state_file.read_text()) if state_file.exists() else []

feed = feedparser.parse(URL)
new = [e for e in feed.entries if e.id not in seen]

for entry in new:
    print(f"New amendment: {entry.title}")
    print(f"  Date: {entry.updated}")
    print(f"  Link: {entry.link}")
    print(f"  Summary: {entry.summary}")
    seen.append(entry.id)

state_file.write_text(json.dumps(seen))
```

## Raw curl

```bash
curl -s https://sondreskarsten.github.io/norwegian-laws/feeds/lov-1998-07-17-56.xml | xmllint --format -
```

## API for batch lookup

To find the feed URL for any law programmatically:

```bash
curl -s https://sondreskarsten.github.io/norwegian-laws/laws.json | \
  jq '.[] | select(.korttittel | test("Regnskapsloven")) | "feeds/\(.path | sub("\\.md$"; ".xml") | sub("^lover/"; "") | sub("^forskrifter/"; ""))"'
```

Or use the feed manifest at `feeds/index.json`:

```bash
curl -s https://sondreskarsten.github.io/norwegian-laws/feeds/index.json | jq '.laws | keys' | head
```

## Feed format

Each feed is Atom 1.0. Each `<entry>` represents one amendment act:

```xml
<entry>
  <id>https://sondreskarsten.github.io/norwegian-laws/feeds/lov/1998-07-17-56/lov/2024-06-21-42</id>
  <title>Endringer i regnskapsloven (bærekraftsrapportering)</title>
  <link href="https://sondreskarsten.github.io/norwegian-laws/lover/lov-1998-07-17-56.html"/>
  <updated>2024-06-21T00:00:00Z</updated>
  <category term="§ 1-2a" label="§ 1-2a"/>
  <category term="§ 2-3" label="§ 2-3"/>
  <summary>Ikrafttredelse: 2024-11-01
Departement: Finansdepartementet
Endrer: lov/1998-07-17-56
Lovtidend: 2024-0042
Berørte paragrafer: § 1-2a, § 2-3</summary>
</entry>
```

The `<id>` includes both the *target* law refid and the *amendment act* refid, so consumers can deduplicate cleanly across multiple feeds.

The `<category>` elements list the specific paragraphs the amendment modifies. Feed readers and automation tools can filter on these — so a tax-advisor subscribed to regnskapsloven who only cares about § 7-25 (egenkapital) can ignore amendments that don't touch it. Filtering syntax depends on the reader:

- **Feedly**: rule-based filters on `category`
- **Inoreader**: built-in tag/category filters
- **Python feedparser**: `entry.tags[i].term`
- **xmllint**: `xpath '//atom:entry[atom:category/@term="§ 7-25"]'`

## Update cadence

The daily source poll requests a build when Lovdata's selected archive list differs from the last acknowledged publication. Feeds are regenerated during publication. Check the site's [publication receipt](https://sondreskarsten.github.io/norwegian-laws/publication.json) for the served source generation; the schedule alone does not confirm delivery.

## Limits

- 50 most recent entries per feed.
- For paragraph-level "what changed" view (the actual amendment instruction and new text), there are two granularities:
  - **Per-law endringshistorikk pages** — parsed amendment records associated with the law, [example](https://sondreskarsten.github.io/norwegian-laws/historie/regnskapsloven.html).
  - **Per-paragraph history pages** — records with a recognized paragraph target, [example](https://sondreskarsten.github.io/norwegian-laws/historikk/lov-1998-07-17-56/para-7-25.html). Look for ⧉ historikk on the law page.
  - Or filter feed entries by their `<category>` tags as shown above.

## Bulk download: JSONL manifests for programmatic consumption

For batch queries over the parsed display records, download the JSON Lines manifests:

- **[amendment-acts.jsonl.gz](https://sondreskarsten.github.io/norwegian-laws/amendment-acts.jsonl.gz)** — selected amendment-act records from the display database.
- **[amendments.jsonl.gz](https://sondreskarsten.github.io/norwegian-laws/amendments.jsonl.gz)** — recognized target/paragraph records for finer-grained queries; `new_text` is truncated to 4,000 characters.

Both are regenerated during publication. Uncompressed `.jsonl` versions are also available at the same paths (drop `.gz`). Dates include source metadata and best-effort resolution, not verified legal effect. These exports can omit unresolved targets and duplicate source occurrences. For complete parsed occurrences and exact original bytes, use the [version-4 source evidence](lovdata-loader/README.md#source-evidence-and-parsed-amendments); see [publication status](README.md#source-evidence-and-publication-status) for its rollout.

JSON Schema 2020-12 definitions for both manifests are published alongside the data:

- **[schemas/amendment-acts.schema.json](https://sondreskarsten.github.io/norwegian-laws/schemas/amendment-acts.schema.json)**
- **[schemas/amendments.schema.json](https://sondreskarsten.github.io/norwegian-laws/schemas/amendments.schema.json)**

Each schema documents every field's type, format, and allowed values (e.g. `change_type` ∈ {`change`, `add`, `remove`, `repeal`, `renumber`, `move`, `unknown`}). Use them with `jsonschema` (Python), `ajv` (JS), or any Draft 2020-12 validator to catch schema drift in your ingestion pipeline.

```bash
# Download both manifests
curl -sL https://sondreskarsten.github.io/norwegian-laws/amendments.jsonl.gz | gunzip > amendments.jsonl

# Find displayed amendment records for regnskapsloven § 7-25 since 2024
jq -c 'select(.target_law == "lov/1998-07-17-56"
            and .paragraph == "§ 7-25"
            and .date_published >= "2024-01-01")' amendments.jsonl

# Same but only show the replacement paragraph wording (new_text)
jq -r 'select(.target_law == "lov/1998-07-17-56" and .paragraph == "§ 7-25")
       | .date_published + " — " + (.new_text // "(no text)")' amendments.jsonl

# Group amendments by ministry, 2026 only
jq -c 'select(.date_published >= "2026-01-01") | .ministry' amendments.jsonl | sort | uniq -c | sort -rn
```

Polars / DuckDB / pandas can read either file directly:

```python
import duckdb
duckdb.sql("""
    SELECT target_law, paragraph, COUNT(*) AS n
    FROM read_json_auto('amendments.jsonl')
    WHERE date_published >= '2024-01-01'
    GROUP BY 1, 2 ORDER BY n DESC LIMIT 20
""").show()
```
