from __future__ import annotations

from datetime import datetime, timezone

from rulo.models import Quote
from rulo.sources import get_json

BASE_URL = "https://api.comparadolar.ar"

# par -> endpoint
ENDPOINTS = {
    "USD/ARS": "/usd",
    "USDT/ARS": "/usdt",
    "USDC/ARS": "/usdc",
}


def _parse_ts(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        # la spec dice "segundos o ms según origen"
        return datetime.fromtimestamp(value / 1000 if value > 1e11 else value, timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class ComparaDolar:
    name = "comparadolar"

    def fetch(self, pairs: set[str]) -> list[Quote]:
        quotes = []
        for pair in pairs:
            endpoint = ENDPOINTS.get(pair)
            if endpoint is None:
                raise ValueError(f"comparadolar no soporta el par {pair}")
            for item in get_json(BASE_URL + endpoint):
                quotes.append(
                    Quote(
                        source=self.name,
                        slug=item["slug"],
                        pair=pair,
                        bid=item.get("totalBid", item.get("bid")),
                        ask=item.get("totalAsk", item.get("ask")),
                        ts=_parse_ts(item.get("time")),
                    )
                )
        return quotes
