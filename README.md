# Norges Lover (norwegian-laws)

Norwegian law texts as git history, with a [Quarto book](https://sondreskarsten.github.io/norwegian-laws/) for browsing.

## What this is

Every current Norwegian formal law (`gjeldende formelle lover`) parsed from [Lovdata's public API](https://api.lovdata.no/) into Markdown files, committed to git with amendment history. Each amendment act from [Norsk Lovtidend](https://lovdata.no/register/lovtidend) becomes a backdated git commit, so `git log -- lover/lov-1998-07-17-56.md` shows the legislative history of regnskapsloven.

The [Quarto book](https://sondreskarsten.github.io/norwegian-laws/) organizes all 774 laws by responsible ministry and is rebuilt weekly via GitHub Actions.

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Pipeline code, law files, Quarto source. Updated weekly. |
| `gh-pages` | Rendered Quarto book. Auto-deployed from `main`. |
| `law-history` | Orphan branch with backdated git commits per amendment act. Rebuilt weekly. |

Browse the `law-history` branch to see `git log` with real legislative dates:

```bash
git clone -b law-history https://github.com/sondreskarsten/norwegian-laws.git
git log --oneline -- lover/lov-1998-07-17-56.md
```

## Quick start

```bash
pip install -e ./lovdata-loader -e ./lovdata-publisher
lovdata-load --download --output snapshot/
lovdata-publish --snapshot snapshot/ --output . --quarto
```

Loader flags:
- `--download`: fetch archives from Lovdata API
- `--output`: snapshot output directory
- `--skip-amendments`: skip Lovtidend parsing (faster, laws only)

Publisher flags:
- `--snapshot`: path to snapshot directory
- `--output`: output directory for Markdown files
- `--quarto`: generate Quarto book chapters and config
- `--build-history`: build the law-history branch with backdated commits
- `--repo-path`: git repo path for history operations

## Repository structure

```
lover/                    # 774 Markdown law files (one per law)
lovdata-loader/           # Download and parse Lovdata XML archives
  src/lovdata_loader/     #   Python package
lovdata-publisher/        # Format and publish law data
  src/lovdata_publisher/  #   Python package
book/                     # Quarto chapter files (auto-generated per department)
_quarto.yml               # Quarto book config
.github/workflows/
  deploy.yml              # Weekly: update laws + deploy Quarto book
  law-history.yml         # Weekly: rebuild backdated commit history
  release.yml             # On tag: create GitHub release
```

## How it works

1. **Download** `gjeldende-lover.tar.bz2` and `lovtidend-avd1-*.tar.bz2` from Lovdata API
2. **Parse** consolidated law XML → structured JSON snapshot
3. **Parse** Lovtidend amendment XML → structured amendment records (SQLite)
4. **Format** JSON snapshot → Markdown with YAML frontmatter
5. **Commit** each amendment act as a backdated git commit via `git fast-import`
6. **Generate** Quarto book chapters grouped by ministry
7. **Deploy** rendered book to GitHub Pages

## Data source and license

Contains data under the [Norwegian Licence for Open Government Data (NLOD) 2.0](https://data.norge.no/nlod/no/2.0) distributed by [Lovdata](https://lovdata.no).

Source code is [MIT licensed](LICENSE).

**This is an unofficial project.** For authoritative legal text, see [lovdata.no](https://lovdata.no).
