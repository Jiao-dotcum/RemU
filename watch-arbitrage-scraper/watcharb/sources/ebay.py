import base64
import os

import requests

from watcharb.models import Listing
from watcharb.sources.base import Source

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
WATCHES_CATEGORY_ID = "31387"  # eBay "Wristwatches" category


class EbaySource(Source):
    """Uses eBay's official Browse API (requires a free developer app).
    This is the only fully-automated, ToS-compliant source in this project:
    eBay publishes and supports this API for exactly this kind of use.

    Sign up at https://developer.ebay.com → My Account → Application Keysets → Production.
    Set EBAY_CLIENT_ID and EBAY_CLIENT_SECRET environment variables.
    """

    name = "ebay"

    def __init__(self, marketplace_id: str = "EBAY_US"):
        self.client_id = os.environ.get("EBAY_CLIENT_ID")
        self.client_secret = os.environ.get("EBAY_CLIENT_SECRET")
        self.marketplace_id = marketplace_id
        self._token: str | None = None

    def _get_token(self) -> str:
        if self._token:
            return self._token
        if not self.client_id or not self.client_secret:
            raise RuntimeError(
                "EBAY_CLIENT_ID and EBAY_CLIENT_SECRET env vars are required for the eBay source. "
                "Get a free key at https://developer.ebay.com"
            )
        creds = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        r = requests.post(
            TOKEN_URL,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials&scope=https%3A%2F%2Fapi.ebay.com%2Foauth%2Fapi_scope",
            timeout=15,
        )
        r.raise_for_status()
        self._token = r.json()["access_token"]
        return self._token

    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        listings: list[Listing] = []
        try:
            token = self._get_token()
        except Exception as exc:
            print(f"[ebay] auth failed: {exc}")
            return listings

        for watch in watchlist:
            reference = watch["reference"]
            brand = watch.get("brand", "")
            model = watch.get("model", "")
            query = f"{brand} {model} {reference}".strip()
            try:
                r = requests.get(
                    SEARCH_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "X-EBAY-C-MARKETPLACE-ID": self.marketplace_id,
                        "X-EBAY-C-ENDUSERCTX": "affiliateCampaignId=<ePNCampaignId>,affiliateReferenceId=<referenceId>",
                    },
                    params={
                        "q": query,
                        "category_ids": WATCHES_CATEGORY_ID,
                        "filter": "conditions:{USED}",
                        "limit": 50,
                    },
                    timeout=15,
                )
                r.raise_for_status()
            except requests.RequestException as exc:
                print(f"[ebay] search failed for {reference}: {exc}")
                continue

            for item in r.json().get("itemSummaries", []):
                price_info = item.get("price", {})
                price_str = price_info.get("value")
                if not price_str:
                    continue
                try:
                    price = float(price_str)
                except ValueError:
                    continue
                listings.append(
                    Listing(
                        reference=reference,
                        brand=brand,
                        model=model,
                        price=price,
                        currency=price_info.get("currency", "USD"),
                        seller=item.get("seller", {}).get("username", "ebay-seller"),
                        url=item.get("itemWebUrl", ""),
                        source="ebay",
                        condition=item.get("condition", "USED"),
                    )
                )
        return listings
