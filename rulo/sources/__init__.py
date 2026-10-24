from __future__ import annotations

import json
import urllib.request
from typing import Protocol

from rulo.models import Quote

USER_AGENT = "rulo-monitor/0.1"


class QuoteSource(Protocol):
    name: str

    def fetch(self, pairs: set[str]) -> list[Quote]:
        """Devuelve las cotizaciones de todos los proveedores para los pares pedidos."""
        ...


def get_json(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def build_sources(cfg: dict) -> dict[str, QuoteSource]:
    from rulo.sources.comparadolar import ComparaDolar
    from rulo.sources.criptoya import CriptoYa

    return {
        "comparadolar": ComparaDolar(),
        "criptoya": CriptoYa(volume=cfg.get("amount_usdt", 1000)),
    }
