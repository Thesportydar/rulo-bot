from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Quote:
    """Cotización normalizada. bid/ask ya incluyen comisiones cuando la fuente las informa."""

    source: str
    slug: str
    pair: str  # "BASE/QUOTE", ej. "USDT/ARS"
    bid: float | None
    ask: float | None
    ts: datetime | None  # None si la fuente no informa timestamp


@dataclass(frozen=True)
class Venue:
    """Una plataforma en un paso del rulo, tal como se define en config.toml."""

    name: str
    platform: str  # identificador propio de la plataforma, para reconocerla entre pasos
    source: str
    slug: str
    pair: str


@dataclass(frozen=True)
class Route:
    buy: Venue
    convert: Venue
    sell: Venue
    mep_ask: float  # ARS por USD
    rate: float  # USD por USDT
    sell_bid: float  # ARS por USDT

    @property
    def cost_per_usdt(self) -> float:
        return self.mep_ask * self.rate

    @property
    def pct(self) -> float:
        return (self.sell_bid / self.cost_per_usdt - 1) * 100

    @property
    def id(self) -> str:
        return f"{self.buy.name}>{self.convert.name}>{self.sell.name}"

    @property
    def same_broker(self) -> bool:
        """Compra MEP y conversión en la misma plataforma: no hay transferencia de USD."""
        return self.buy.platform == self.convert.platform
