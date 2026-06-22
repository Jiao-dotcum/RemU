from abc import ABC, abstractmethod

from watcharb.models import Listing


class Source(ABC):
    """A pluggable listing provider. Implementations must only collect data
    in ways that respect the target site's terms of service and robots.txt."""

    name: str = "unnamed-source"

    @abstractmethod
    def fetch(self, watchlist: list[dict]) -> list[Listing]:
        """watchlist items look like {"brand": ..., "model": ..., "reference": ...}.
        Returns Listing objects found for those references."""
        raise NotImplementedError
