# Watch Arbitrage Scraper

Checks watch listings across sellers/marketplaces by reference number and
emails you when the same watch is priced very differently in two places
(buy low, sell high).

## Why there's no automated scraper for any marketplace

I checked `robots.txt` on every marketplace considered for this project —
Bezel, Chrono24, Bob's Watches, Crown & Caliber, WatchBox, Jomashop,
ChronExt, and WatchCharts. **All eight returned HTTP 403** to a plain,
unauthenticated request: they sit behind bot-protection that blocks
non-browser traffic outright. (eBay was the one exception with a usable
official API, but it's intentionally not used here per your request to drop
it — its listings are mostly unauthenticated individual sellers anyway,
which doesn't fit the "verified/paperwork" bar the rest of this project
targets.)

Building a scraper that defeats that protection (headless-browser
fingerprint spoofing, CAPTCHA solving, residential proxies, etc.) means
deliberately working around a site's explicit attempt to block automated
access, which this project intentionally does not do.

So the design is:

- **`manual_csv_path` (primary source)** — when you're browsing Bezel,
  Chrono24, Bob's Watches, WatchBox, Jomashop, etc. yourself, jot the price
  into `watches_manual.csv` (see `watches_manual.example.csv`, which has
  example rows across all of these). The matcher treats every row exactly
  like a live source, so cross-marketplace arbitrage detection works fully —
  you're just the one fetching the page instead of a bot.
- **`html_sources` in config.yaml** — a generic scraper you can point at a
  site *you've personally confirmed* allows automated fetches of its search
  pages (permissive `robots.txt`, no 403/Cloudflare wall). It refuses to
  fetch any URL robots.txt disallows. None of the marketplaces above qualify
  today — this is here for if you find/get access to one that does (e.g. a
  smaller dealer site, or a marketplace you have a data-access agreement
  with).

## Setup

```bash
cd watch-arbitrage-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml          # then edit your watchlist
cp watches_manual.example.csv watches_manual.csv
```

Environment variables for email alerts (set in your shell, never commit them):

```bash
# Gmail example — use an App Password, not your real password:
# https://myaccount.google.com/apppasswords
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASS=your-16-char-app-password
export ALERT_EMAIL_TO=you@gmail.com
```

## Run it

```bash
python -m watcharb.run --config config.yaml
```

Each run prints a summary, writes a JSON report to `reports/`, and — if any
opportunity clears the thresholds in `config.yaml` — emails you. Use
`--dry-run` to skip the email while testing.

## How matching works

Listings are grouped by exact reference number (e.g. `126610LN`), normalized
by stripping whitespace and uppercasing. For each reference with listings
from 2+ different sellers, the cheapest and most expensive are compared; it's
flagged as arbitrage if the spread clears **both** `min_abs_diff` (USD) and
`min_pct_diff` (%) in `config.yaml`. Exact-reference matching avoids false
positives from comparing different conditions/box-and-papers under a fuzzy
brand/model match.

## Day-to-day workflow

1. Browse Bezel, Chrono24, Bob's Watches, etc. for the references in your
   `config.yaml` watchlist.
2. Append a row to `watches_manual.csv` for each listing you see (reference,
   brand, model, price, currency, seller, url, source, condition).
3. Run `python -m watcharb.run --config config.yaml`.
4. If a real spread shows up, you'll get the alert email; the JSON report in
   `reports/` keeps a history of every run.

## Adding a new source

Implement `watcharb/sources/base.py`'s `Source` interface (one method,
`fetch(watchlist) -> list[Listing]`) and register it in
`watcharb/run.py:build_sources`. Look at `html_source.py` for a
robots.txt-respecting HTML example, or `csv_source.py` for the manual-entry
example.

## Scheduling

This is built to run on demand. To run it automatically, put it on a host
you control (a cron job, or a small VM) — e.g. `0 * * * * cd /path/to/watch-arbitrage-scraper && .venv/bin/python -m watcharb.run`.
Since the data entry into `watches_manual.csv` is manual, scheduling mostly
just automates the matching/alerting step on whatever you've logged so far.
