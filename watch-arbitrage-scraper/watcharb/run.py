import argparse
import json
import os
from datetime import datetime, timezone

import yaml

from watcharb.alerter import build_alerter
from watcharb.matcher import find_arbitrage
from watcharb.models import Listing
from watcharb.sources.csv_source import CsvSource
from watcharb.sources.ebay import EbaySource
from watcharb.sources.html_source import GenericHtmlSource


def build_sources(config: dict) -> list:
    sources = []
    if config.get("sources", {}).get("ebay", False):
        sources.append(EbaySource())
    csv_path = config.get("sources", {}).get("manual_csv_path")
    if csv_path and os.path.exists(csv_path):
        sources.append(CsvSource(csv_path))
    for site_config in config.get("html_sources", []):
        sources.append(GenericHtmlSource(site_config))
    return sources


def collect_listings(sources: list, watchlist: list[dict]) -> list[Listing]:
    listings = []
    for source in sources:
        found = source.fetch(watchlist)
        print(f"[{getattr(source, 'name', source)}] found {len(found)} listing(s)")
        listings.extend(found)
    return listings


def main():
    parser = argparse.ArgumentParser(description="Check watch listings across sources for arbitrage.")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Skip sending alert, just print/save report")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    watchlist = config["watchlist"]
    thresholds = config.get("thresholds", {})
    sources = build_sources(config)

    listings = collect_listings(sources, watchlist)
    opportunities = find_arbitrage(
        listings,
        min_abs_diff=thresholds.get("min_abs_diff", 100),
        min_pct_diff=thresholds.get("min_pct_diff", 10),
    )

    print(f"\n{len(opportunities)} arbitrage opportunity(ies) found\n")
    for opp in opportunities:
        print(
            f"  {opp.brand} {opp.model} ({opp.reference}): "
            f"buy ${opp.cheap.price:,.2f} @ {opp.cheap.source}/{opp.cheap.seller} -> "
            f"sell ${opp.expensive.price:,.2f} @ {opp.expensive.source}/{opp.expensive.seller} "
            f"= ${opp.diff_abs:,.2f} ({opp.diff_pct:.1f}%)"
        )

    os.makedirs("reports", exist_ok=True)
    report_path = os.path.join(
        "reports", f"report_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    with open(report_path, "w") as f:
        json.dump([o.to_dict() for o in opportunities], f, indent=2)
    print(f"\nReport written to {report_path}")

    if opportunities and not args.dry_run:
        alerter = build_alerter(config)
        if alerter:
            alerter.send(opportunities)


if __name__ == "__main__":
    main()
