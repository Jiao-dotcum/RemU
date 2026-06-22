from collections import defaultdict

from watcharb.models import ArbitrageOpportunity, Listing


def group_by_reference(listings: list[Listing]) -> dict[str, list[Listing]]:
    groups: dict[str, list[Listing]] = defaultdict(list)
    for listing in listings:
        groups[listing.reference].append(listing)
    return groups


def find_arbitrage(
    listings: list[Listing],
    min_abs_diff: float = 0.0,
    min_pct_diff: float = 0.0,
) -> list[ArbitrageOpportunity]:
    """Exact-reference-number matching: for each reference, compare the
    cheapest and most expensive listing as long as they come from different
    sellers, and flag it if the spread clears either threshold."""
    opportunities = []
    for reference, group in group_by_reference(listings).items():
        if len(group) < 2:
            continue
        by_price = sorted(group, key=lambda l: l.price)
        cheap, expensive = by_price[0], by_price[-1]
        if cheap.seller == expensive.seller and cheap.source == expensive.source:
            continue
        if cheap.price <= 0:
            continue
        diff_abs = expensive.price - cheap.price
        diff_pct = (diff_abs / cheap.price) * 100
        if diff_abs >= min_abs_diff and diff_pct >= min_pct_diff:
            opportunities.append(
                ArbitrageOpportunity(
                    reference=reference,
                    brand=cheap.brand or expensive.brand,
                    model=cheap.model or expensive.model,
                    cheap=cheap,
                    expensive=expensive,
                    diff_abs=diff_abs,
                    diff_pct=diff_pct,
                    listing_count=len(group),
                )
            )
    opportunities.sort(key=lambda o: o.diff_abs, reverse=True)
    return opportunities
