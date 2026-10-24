from __future__ import annotations

from datetime import datetime, timezone

from rulo.models import Quote
from rulo.sources import get_json

BASE_URL = "https://criptoya.com/api"


class CriptoYa:
    """Ojo: `time` es el momento en que CriptoYa consultó al exchange, no la última
    actualización del precio, así que no detecta datos congelados (ej. mantenimiento)."""

    name = "criptoya"

    def __init__(self, volume: float = 1000):
        self.volume = volume

    def fetch(self, pairs: set[str]) -> list[Quote]:
        quotes = []
        for pair in pairs:
            coin, fiat = pair.split("/")
            data = get_json(f"{BASE_URL}/{coin}/{fiat}/{self.volume}")
            if "error" in data:
                raise ValueError(f"criptoya {pair}: {data['error']}")
            for slug, item in data.items():
                quotes.append(
                    Quote(
                        source=self.name,
                        slug=slug,
                        pair=pair,
                        bid=item.get("totalBid", item.get("bid")),
                        ask=item.get("totalAsk", item.get("ask")),
                        ts=datetime.fromtimestamp(item["time"], timezone.utc) if item.get("time") else None,
                    )
                )
        return quotes
