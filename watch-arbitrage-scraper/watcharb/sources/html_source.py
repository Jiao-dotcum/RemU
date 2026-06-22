import time
import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from watcharb.models import Listing
from watcharb.sources.base import Source

USER_AGENT = "watch-arbitrage-bot/1.0 (+respects robots.txt; manual personal use)"


class GenericHtmlSource(Source):
    """Configurable scraper for a site YOU have checked allows automated
    access to its search/listing pages. It refuses to fetch any URL that the
    site's robots.txt disallows for our user agent, and rate-limits requests.

    Do not point this at a site whose robots.txt disallows the path, and
    do not point it at a site that blocks requests outright (HTTP 403/
    Cloudflare challenge etc.) -- that means the operator does not want
    automated traffic, and working around it is out of scope for this tool.

    Config (one entry per site) lives in config.yaml under html_sources, e.g.:

      html_sources:
        - name: example-dealer
          search_url_template: "https://example-dealer.com/search?q={reference}"
          listing_selector: "div.result-item"
          price_selector: ".price"
          seller_selector: ".seller-name"
          url_selector: "a.result-link"
          delay_seconds: 2
    """

    def __init__(self, site_config: dict):
        self.site_name = site_config["name"]
        self.name = f"html:{self.site_name}"
        self.search_url_template = site_config["search_url_template"]
        self.listing_selector = site_config["listing_selector"]
        self.price_selector = site_config["price_selector"]
        self.seller_selector = site_config.get("seller_selector")
        self.url_selector = site_config.get("url_selector")
        self.delay_seconds = site_config.get("delay_seconds", 2)
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def _allowed(self, url: str) -> bool:
        origin = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        if origin not in self._robots_cache:
            rp = urllib.robotparser.RobotFileParser()
            rp.set_url(urljoin(origin, "/robots.txt"))
            try:
                rp.read()
            except Exception:
                print(f"[{self.name}] could not read robots.txt, refusing to fetch")
                return False
            self._robots_cache[origin] = rp
        return self._robots_cache[origin].can_fetch(USER_AGENT, url)

    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        listings: list[Listing] = []
        for watch in watchlist:
            reference = watch["reference"]
            url = self.search_url_template.format(reference=reference)
            if not self._allowed(url):
                print(f"[{self.name}] robots.txt disallows {url}, skipping")
                continue
            try:
                resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"[{self.name}] request failed for {reference}: {exc}")
                time.sleep(self.delay_seconds)
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for node in soup.select(self.listing_selector):
                price_node = node.select_one(self.price_selector)
                if not price_node:
                    continue
                price_text = "".join(c for c in price_node.get_text() if c.isdigit() or c == ".")
                if not price_text:
                    continue
                seller_node = node.select_one(self.seller_selector) if self.seller_selector else None
                link_node = node.select_one(self.url_selector) if self.url_selector else None
                listings.append(
                    Listing(
                        reference=reference,
                        brand=watch.get("brand", ""),
                        model=watch.get("model", ""),
                        price=float(price_text),
                        currency=watch.get("currency", "USD"),
                        seller=seller_node.get_text(strip=True) if seller_node else self.site_name,
                        url=urljoin(url, link_node["href"]) if link_node and link_node.has_attr("href") else url,
                        source=self.name,
                    )
                )
            time.sleep(self.delay_seconds)
        return listings
