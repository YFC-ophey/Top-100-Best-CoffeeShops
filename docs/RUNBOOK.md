# ROAST Operations Runbook

How the automated pipeline works, what its guards do, and what to do when
something fires. Live site: GitHub Pages for this repo. One workflow:
`.github/workflows/update_map.yml` ("Update Map and Deploy Site").

## Schedule

| Trigger | When | Why |
|---------|------|-----|
| `cron: 0 9 * * 1` | Mondays 09:00 UTC | Weekly freshness sync |
| `cron: 0 9 10-20 2 *` | Daily, Feb 10-20 | Catch the annual list release (~Feb 16) |
| `workflow_dispatch` | Manual | Recovery / ad-hoc refresh |

A `concurrency` group serializes runs. History note: until July 2026 a
byte-identical duplicate (`update.yml`) double-fired every schedule; the
2026-06-08 run failed on the resulting push race. Do not add a second
workflow that pushes to main.

## Pipeline stages and guards

1. **pytest** — full suite must pass before anything touches data.
2. **Scrape** (`python src/main.py scrape-only`) — stdlib fetch with
   User-Agent + 3 retries and linear backoff (`src/scraper.py:fetch_html`).
3. **Scrape-collapse guard** (`src/main.py`) — aborts before saving if any
   category shrinks below 80% of the previous run (source redesign, partial
   fetch, WAF block). Committed data stays intact. Deliberate override:
   `SCRAPE_ALLOW_SHRINK=1 python src/main.py scrape-only`.
4. **Geocode-wipe guard** (workflow step) — aborts before commit if
   place_id/coord counts drop to zero.
5. **Provenance** — every save writes `data/metadata.json` (UTC timestamp,
   counts, sources, geocoded count); the site footer shows "Data updated".
6. **Commit + Pages deploy** — bot commits `data/`, `output/`, `site/`; a
   browser-key rebuild runs only when the `GOOGLE_MAPS_JS_API_KEY` secret exists.
7. **Auto-issue** — if shops are missing `place_id`, the workflow opens
   "Owner geocode refresh needed (N shops missing place_id)".

## Playbooks

**Run failed on "Scrape collapse"** — the source layout probably changed.
Check the two list URLs in a browser. If the site is fine and the list really
shrank, re-run with `SCRAPE_ALLOW_SHRINK=1` locally, inspect the diff, push.
If the layout changed, fix the parsers in `src/scraper.py` (legacy `<li>`
parser first, Elementor loop-card parser second) against saved HTML.

**Geocode reminder issue opened** — run locally with the owner key
(never commit it; it lives in `.env`):
`python src/main.py owner-geocode --api-key "$GOOGLE_MAPS_API_KEY"`,
then commit `data/current_list.json`. Annual cost ~$3.40, inside free tier.

**Bad data got committed** — revert the bot commit
(`git revert <sha>`), push, then `workflow_dispatch` a fresh run.

**Pages deploy failed but data committed** — re-run the workflow via
`workflow_dispatch`; it is idempotent (scrape diff will be empty).

## Annual February release (~Feb 16)

The daily Feb 10-20 cron catches the new list automatically. After it lands:
1. Check the run log: both categories near 100 shops.
2. Expect the geocode reminder issue (new shops lack place_ids) — run
   owner-geocode the same week.
3. Spot-check the live map: #1 shop, a Peru shop, one South America shop.
See `docs/release-timeline-2026.md` for the full timeline.

## Local development

```bash
python3.11 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
./.venv/bin/python -m pytest            # 55 tests
./.venv/bin/python src/main.py scrape-only
./.venv/bin/python src/main.py build-site   # writes site/index.html
```
Branch discipline: work in `.worktrees/<name>` (gitignored) on isolated
branches; never commit directly to main — CI owns main's data commits.
