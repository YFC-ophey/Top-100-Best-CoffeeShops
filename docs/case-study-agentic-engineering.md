# Case Study: ROAST as Agentic Engineering Discipline

How a solo builder shipped and operates a self-updating public data product by
coordinating AI coding agents through isolated branches and verification gates.
Every claim below is verifiable in this repo's history, CI logs, or tests.

## The product

ROAST maps *The World's 100 Best Coffee Shops*: 200 ranked shops across 56
countries on an interactive world map with country-density bubbles, filters,
and one-tap Google Maps directions. It costs $0 to run and needs no API key
from visitors: GitHub Actions scrapes and rebuilds, GitHub Pages hosts, and the
dataset is flat JSON committed to the repo (~$3.40/year of owner-side geocoding,
inside Google's free tier).

## The agentic workflow

**Plan first, in a separate repo.** A planning repository holds the PRD,
implementation plan, and four phased prompt specs (`claude_prompts/phase1-4.md`)
written before implementation started. Agents executed against specs, not vibes.

**Isolated branches per task.** 18+ `codex/*` remote branches, each scoped to
one concern: `mobile-chrome-layout-fix`, `map-ui-polish-no-ghost-pins`,
`rank71-ottawa-fix`, `security-key-remediation`, `ui-banner-cleanup`. Risky
syncs got timestamped backup branches first
(`codex/backup-local-main-20260222-165402`). Local work happens in gitignored
`.worktrees/`, so parallel agents never collide on a working tree.

**Verification gates, not trust.** CI runs the full pytest suite (81 tests
across 14 files) before the pipeline may touch data. Two data guards sit
between scrape and commit: a scrape-collapse guard (any category shrinking
below 80% of the previous run aborts the save) and a geocode-wipe guard
(place_id/coord counts dropping to zero aborts the commit). Human-owned steps
are automated into visibility instead of hoped for: when shops lack place_ids,
CI opens a GitHub issue naming the exact recovery command.

**Operations as code.** The pipeline self-updates weekly and daily during the
annual February release window, committing as `github-actions[bot]`. A runbook
(`docs/RUNBOOK.md`) documents every guard and a playbook for each failure mode.

## A real incident, and what it proves

On 2026-06-08 a scheduled run failed: `! [rejected] main -> main (fetch first)`.
Root cause: two byte-identical workflow files (`update.yml` + `update_map.yml`)
had double-fired every schedule since creation, and the second run raced the
first's push. The July 2026 reliability pass found it by auditing CI history,
deleted the duplicate, and added a `concurrency` group so overlapping runs
serialize. The same pass added fetch retries with User-Agent + backoff, the
scrape-collapse guard, and dataset provenance (`data/metadata.json` + a
"Data updated" stamp in the site footer) — each landed with tests (47 → 55).

## Reusable bullets

- Shipped a zero-cost, self-updating data product: scraper → guarded data
  pipeline → static site, on GitHub Actions/Pages, serving 200 geocoded shops
  across 56 countries with no visitor API keys.
- Coordinated AI coding agents through 18+ single-concern branches with backup
  branches before risky merges and gitignored worktrees for parallel work.
- Put verification between agents and production: 55-test CI gate plus two
  data-regression guards that abort before bad data can be committed.
- Diagnosed a CI race condition from run logs (duplicate workflow double-fire),
  fixed it with workflow dedup + concurrency groups, and wrote the runbook so
  the failure mode stays fixed.
- Treated operations as part of the product: auto-filed geocode-refresh issues,
  dataset provenance metadata, and a user-visible freshness stamp.
