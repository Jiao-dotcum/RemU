# Watch Arbitrage Scraper

Checks watch listings across sources by reference number and emails you when
the same watch is priced very differently in two places (buy low, sell high).

## A note on which sites this actually scrapes

Before building this, I checked `robots.txt` on Chrono24, Bob's Watches,
Crown & Caliber, and WatchCharts. All four returned **HTTP 403** to a plain,
unauthenticated request — they sit behind bot-protection that blocks
non-browser traffic outright. Building a scraper that defeats that
protection (headless-browser fingerprint spoofing, CAPTCHA solving, residential
proxies, etc.) means deliberately working around a site's explicit attempt to
block automated access, which this project intentionally does not do.

So the design is:

- **eBay** — fully automated via eBay's official [Browse API](https://developer.ebay.com/api-docs/buy/browse/overview.html).
  This is the one source that's both automatable and ToS-compliant out of the box.
- **Any other site** — via `manual_csv_path`: when you're browsing Chrono24,
  Bob's Watches, Crown & Caliber, etc. yourself, jot the price into
  `watches_manual.csv` (see `watches_manual.example.csv`). The matcher treats
  these exactly like a live source, so cross-site arbitrage detection still
  works — you're just the one fetching the page instead of a bot.
- **`html_sources` in config.yaml** — a generic scraper you can point at a
  site *you've personally confirmed* allows automated fetches of its search
  pages (permissive `robots.txt`, no 403/Cloudflare wall). It refuses to fetch
  any URL robots.txt disallows. Don't add a site here unless you've checked.

## Setup

```bash
cd watch-arbitrage-scraper
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml   # then edit your watchlist
cp watches_manual.example.csv watches_manual.csv   # optional
```

Environment variables (set these in your shell, never commit them):

```bash
# eBay Browse API — create a free app at https://developer.ebay.com
export EBAY_CLIENT_ID=...
export EBAY_CLIENT_SECRET=...

# Email alerts (Gmail example — use an App Password, not your real password:
# https://myaccount.google.com/apppasswords)
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

## Adding a new source

Implement `watcharb/sources/base.py`'s `Source` interface (one method,
`fetch(watchlist) -> list[Listing]`) and register it in
`watcharb/run.py:build_sources`. Look at `ebay.py` for an API-based example
or `html_source.py` for a robots.txt-respecting HTML example.

## Scheduling

This is built to run on demand. To run it automatically, put it on a host
you control (a cron job, or a small VM) — e.g. `0 * * * * cd /path/to/watch-arbitrage-scraper && .venv/bin/python -m watcharb.run`.
