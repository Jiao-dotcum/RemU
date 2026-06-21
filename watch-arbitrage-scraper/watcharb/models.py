from dataclasses import dataclass
from datetime import datetime, timezone


def normalize_reference(reference: str) -> str:
    return "".join(reference.split()).upper()


@dataclass
class Listing:
    reference: str
    brand: str
    model: str
    price: float
    currency: str
    seller: str
    url: str
    source: str
    condition: str = "unknown"
    scraped_at: str = ""

    def __post_init__(self):
        self.reference = normalize_reference(self.reference)
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "reference": self.reference,
            "brand": self.brand,
            "model": self.model,
            "price": self.price,
            "currency": self.currency,
            "seller": self.seller,
            "url": self.url,
            "source": self.source,
            "condition": self.condition,
            "scraped_at": self.scraped_at,
        }


@dataclass
class ArbitrageOpportunity:
    reference: str
    brand: str
    model: str
    cheap: Listing
    expensive: Listing
    diff_abs: float
    diff_pct: float
    listing_count: int

    def to_dict(self) -> dict:
        return {
            "reference": self.reference,
            "brand": self.brand,
            "model": self.model,
            "diff_abs": round(self.diff_abs, 2),
            "diff_pct": round(self.diff_pct, 2),
            "listing_count": self.listing_count,
            "cheap": self.cheap.to_dict(),
            "expensive": self.expensive.to_dict(),
        }
