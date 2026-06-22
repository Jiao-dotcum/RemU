import csv
import os

from watcharb.models import Listing
from watcharb.sources.base import Source


class CsvSource(Source):
    """Reads listings you've logged by hand from sites that block automated
    access (Chrono24, Bob's Watches, Crown & Caliber, WatchCharts, etc. all
    returned HTTP 403 to a plain request when this project was built, meaning
    they actively block non-browser traffic). This is how those sites get
    included in arbitrage checks without scraping them against their wishes."""

    name = "manual-csv"

    def __init__(self, path: str):
        self.path = path

    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        if not self.path or not os.path.exists(self.path):
            return []
        wanted_refs = {w["reference"].strip().upper() for w in watchlist}
        listings = []
        with open(self.path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                reference = row.get("reference", "").strip()
                if reference.upper() not in wanted_refs:
                    continue
                listings.append(
                    Listing(
                        reference=reference,
                        brand=row.get("brand", ""),
                        model=row.get("model", ""),
                        price=float(row["price"]),
                        currency=row.get("currency", "USD"),
                        seller=row.get("seller", "unknown"),
                        url=row.get("url", ""),
                        source=row.get("source", "manual"),
                        condition=row.get("condition", "unknown"),
                    )
                )
        return listings
