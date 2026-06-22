"""Chrono24 source — uses their internal JSON search endpoint."""
import time

import requests

from watcharb.models import Listing
from watcharb.sources.base import Source

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.chrono24.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
}


class Chrono24Source(Source):
    """Scrapes Chrono24's internal JSON search API.
    No official API exists; this uses the same endpoint the website calls.
    """

    name = "chrono24"

    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        listings: list[Listing] = []
        session = requests.Session()
        # Warm up session with a browser-like GET first (helps avoid some bot checks)
        try:
            session.get("https://www.chrono24.com/", headers={**BROWSER_HEADERS, "Accept": "text/html"}, timeout=10)
        except Exception:
            pass

        for watch in watchlist:
            reference = watch["reference"]
            brand = watch.get("brand", "")
            model = watch.get("model", "")
            query = f"{brand} {model} {reference}".strip()
            url = (
                "https://www.chrono24.com/search/accessorieslist.json"
                f"?dosearch=true&query={requests.utils.quote(query)}"
                "&watchTypes=0&resultview=list&maxAgeInDays=0"
                "&priceFrom=0&priceTo=0&currencyId=USD&specials=0"
                "&accessoryCategory=0&country=0&showPage=1"
            )
            try:
                r = session.get(url, headers=BROWSER_HEADERS, timeout=15)
                r.raise_for_status()
                data = r.json()
            except Exception as exc:
                print(f"[chrono24] failed for {reference}: {exc}")
                time.sleep(2)
                continue

            for item in data.get("articles", []) or data.get("data", {}).get("articles", []):
                try:
                    price_raw = item.get("price") or item.get("priceFormatted", "")
                    price_str = "".join(c for c in str(price_raw) if c.isdigit() or c == ".")
                    price = float(price_str) if price_str else None
                    if price is None:
                        continue
                    seller = item.get("dealer", {}).get("name") or item.get("sellerName", "chrono24-seller")
                    listing_id = item.get("id") or item.get("articleId", "")
                    listing_url = (
                        item.get("detailUrl")
                        or f"https://www.chrono24.com/watches/ref_{reference}--{listing_id}.htm"
                    )
                    if listing_url and not listing_url.startswith("http"):
                        listing_url = "https://www.chrono24.com" + listing_url
                    listings.append(
                        Listing(
                            reference=reference,
                            brand=brand,
                            model=model,
                            price=price,
                            currency="USD",
                            seller=seller,
                            url=listing_url,
                            source="chrono24",
                            condition=item.get("condition", "pre-owned"),
                        )
                    )
                except Exception:
                    continue
            time.sleep(2)
        return listings
