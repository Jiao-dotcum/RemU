"""Generic best-effort HTML scraper — no robots.txt gate, browser-like headers."""
import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from watcharb.models import Listing
from watcharb.sources.base import Source

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

PRICE_RE = re.compile(r"[\$\£\€]?\s*([\d,]+(?:\.\d{1,2})?)")


def extract_price(text: str) -> float | None:
    text = text.replace(",", "")
    m = PRICE_RE.search(text)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


class GenericHtmlSource(Source):
    """Best-effort scraper: uses browser-like headers, no robots.txt check.
    If a site returns a Cloudflare challenge or 403, it logs and moves on.

    Config lives in config.yaml under html_sources, e.g.:

      html_sources:
        - name: jomashop
          search_url_template: "https://www.jomashop.com/watches.html?name={reference}"
          listing_selector: "div.product-item"
          price_selector: ".price-box .price"
          seller_name: "Jomashop"
          url_selector: "a.product-item-link"
          delay_seconds: 3
    """

    def __init__(self, site_config: dict):
        self.site_name = site_config["name"]
        self.name = f"html:{self.site_name}"
        self.search_url_template = site_config["search_url_template"]
        self.listing_selector = site_config["listing_selector"]
        self.price_selector = site_config["price_selector"]
        self.seller_name = site_config.get("seller_name", self.site_name)
        self.seller_selector = site_config.get("seller_selector")
        self.url_selector = site_config.get("url_selector")
        self.delay_seconds = site_config.get("delay_seconds", 3)

    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        listings: list[Listing] = []
        session = requests.Session()

        for watch in watchlist:
            reference = watch["reference"]
            url = self.search_url_template.format(
                reference=reference,
                brand=watch.get("brand", ""),
                model=watch.get("model", ""),
            )
            try:
                r = session.get(url, headers=BROWSER_HEADERS, timeout=20)
                if r.status_code in (403, 429, 503):
                    print(f"[{self.name}] blocked ({r.status_code}) for {reference} — skipping")
                    time.sleep(self.delay_seconds)
                    continue
                r.raise_for_status()
            except requests.RequestException as exc:
                print(f"[{self.name}] request failed for {reference}: {exc}")
                time.sleep(self.delay_seconds)
                continue

            # Quick Cloudflare check
            if "cf-mitigated" in r.headers or "just a moment" in r.text.lower():
                print(f"[{self.name}] Cloudflare challenge for {reference} — skipping")
                time.sleep(self.delay_seconds)
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            for node in soup.select(self.listing_selector):
                price_node = node.select_one(self.price_selector)
                if not price_node:
                    continue
                price = extract_price(price_node.get_text())
                if price is None:
                    continue
                seller_node = node.select_one(self.seller_selector) if self.seller_selector else None
                link_node = node.select_one(self.url_selector) if self.url_selector else None
                listings.append(
                    Listing(
                        reference=reference,
                        brand=watch.get("brand", ""),
                        model=watch.get("model", ""),
                        price=price,
                        currency="USD",
                        seller=seller_node.get_text(strip=True) if seller_node else self.seller_name,
                        url=urljoin(url, link_node["href"]) if link_node and link_node.has_attr("href") else url,
                        source=self.name,
                    )
                )
            time.sleep(self.delay_seconds)
        return listings
