# Norwegian law watcher — GitHub Action template

Drop the [workflow file](.github/workflows/watch-norwegian-laws.yml) into your repo and it will open a GitHub Issue whenever a watched Norwegian law or forskrift is amended.

## Setup

1. Copy `.github/workflows/watch-norwegian-laws.yml` into your repo
2. Edit the `feeds:` matrix — paste any Atom feed URL from the [feed catalog](https://sondreskarsten.github.io/norwegian-laws/feeds/) or use the [interactive subscribe page](https://sondreskarsten.github.io/norwegian-laws/book/abonner.html) to find URLs by law name
3. Commit and push. The workflow runs every weekday at 09:00 UTC by default. **First run is silent** — it registers existing amendments as already-seen so you do not get a flood of historical issues; you start receiving notifications from the next amendment forward
4. Trigger it once with **Actions → Watch Norwegian law changes → Run workflow** to initialize state

## What you get

When Lovdata publishes an amendment touching one of your watched laws, the action files a GitHub Issue like:

> **Regnskapsloven: 2 new amendments**
>
> ### Endringer i regnskapsloven (bærekraftsrapportering)
> - **Published**: 2024-06-21
> - **Link**: https://sondreskarsten.github.io/norwegian-laws/lover/lov-1998-07-17-56.html
> - **Affected paragraphs**: § 1-2a, § 2-3

The issue is labeled `law-change` so you can route it to whichever team handles compliance, audit, or product.

## State

State (which amendments have already been seen) is committed to `.watcher-state/` in your repo so the workflow never fires twice for the same amendment. The state file is hashed by feed URL, so you can add and remove feeds without affecting siblings.

## Alternatives

For feed-reader subscriptions and local polling examples, see [SUBSCRIBE.md](https://github.com/sondreskarsten/norwegian-laws/blob/main/SUBSCRIBE.md).
