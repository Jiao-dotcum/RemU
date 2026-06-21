import base64
import os

import requests

from watcharb.models import Listing
from watcharb.sources.base import Source

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
WATCHES_CATEGORY_ID = "31387"  # eBay "Wristwatches" category


class EbaySource(Source):
    """Uses eBay's official Browse API (requires a developer app).
    This is the only fully-automated, ToS-compliant source in this project:
    eBay publishes and supports this API for exactly this kind of use."""

    name = "ebay"

    def __init__(self, marketplace_id: str = "EBAY_US"):
        self.client_id = os.environ.get("EBAY_CLIENT_ID")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET")
        self.marketplace_id = marketplace_id
        self._token = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "EBAY_CLIENT_ID / EBAY_CLIENT_SECRET env vars are not set. "
                "Create a developer app at https://developer.ebay.com to use this source."
            )
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        resp = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "client_credentials",
                "scope": "https://api.ebay.com/oauth/api_scope",
            },
            timeout=15,
        )
        resp.raise_for_status()
        self._token = resp.json()["access_token"]
        return self._token

    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        listings: list[Listing] = []
        try:
            token = self._get_token()
        except (RuntimeError, requests.RequestException) as exc:
            print(f"[ebay] skipping source: {exc}")
            return listings

        headers = {
            "Authorization": f"Bearer {token}",
            "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
        }
        for watch in watchlist:
            reference = watch["reference"]
            params = {
                "q": f"{watch.get('brand', '')} {reference}".strip(),
                "category_ids": WATCHES_CATEGORY_ID,
                "limit": 25,
            }
            try:
                resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as exc:
                print(f"[ebay] search failed for {reference}: {exc}")
                continue

            for item in resp.json().get("itemSummaries", []):
                if reference.lower() not in item.get("title", "").lower():
                    continue
                price = item.get("price", {})
                seller = item.get("seller", {})
                listings.append(
                    Listing(
                        reference=reference,
                        brand=watch.get("brand", ""),
                        model=watch.get("model", ""),
                        price=float(price.get("value", 0)),
                        currency=price.get("currency", "USD"),
                        seller=seller.get("username", "unknown"),
                        url=item.get("itemWebUrl", ""),
                        source=self.name,
                        condition=item.get("condition", "unknown"),
                    )
                )
        return listings
