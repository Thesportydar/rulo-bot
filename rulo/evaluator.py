from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import product

from rulo.models import Quote, Route, Venue

# Rango razonable para USD por USDT; fuera de esto asumimos dato roto.
RATE_BOUNDS = (0.9, 1.3)


def index_quotes(quotes: list[Quote]) -> dict[tuple[str, str, str], Quote]:
    return {(q.source, q.pair, q.slug): q for q in quotes}


def _price(
    index: dict, venue: Venue, side: str, now: datetime, max_age: timedelta, problems: list[str]
) -> float | None:
    q = index.get((venue.source, venue.pair, venue.slug))
    if q is None:
        problems.append(f"{venue.name}: sin cotización en {venue.source} {venue.pair}")
        return None
    value = getattr(q, side)
    if not value or value <= 0:
        problems.append(f"{venue.name}: {side} inválido ({value})")
        return None
    if q.ts is not None and now - q.ts > max_age:
        problems.append(f"{venue.name}: dato viejo ({q.ts:%Y-%m-%d %H:%M} UTC)")
        return None
    return value


def evaluate(
    cfg: dict, quotes: list[Quote], now: datetime | None = None
) -> tuple[list[Route], list[str]]:
    """Arma todas las rutas válidas, ordenadas de mejor a peor, y la lista de problemas de datos."""
    now = now or datetime.now(timezone.utc)
    max_age = timedelta(minutes=cfg.get("freshness", {}).get("max_age_minutes", 30))
    index = index_quotes(quotes)
    problems: list[str] = []

    buys = [(v, _price(index, v, "ask", now, max_age, problems)) for v in cfg["buy"]]
    converts = [(v, _price(index, v, "ask", now, max_age, problems)) for v in cfg["convert"]]
    sells = [(v, _price(index, v, "bid", now, max_age, problems)) for v in cfg["sell"]]

    for venue, rate in converts:
        if rate is not None and not RATE_BOUNDS[0] <= rate <= RATE_BOUNDS[1]:
            problems.append(f"{venue.name}: tasa fuera de rango ({rate})")
    converts = [(v, r) for v, r in converts if r is not None and RATE_BOUNDS[0] <= r <= RATE_BOUNDS[1]]

    routes = [
        Route(buy=b, convert=c, sell=s, mep_ask=bp, rate=cp, sell_bid=sp)
        for (b, bp), (c, cp), (s, sp) in product(buys, converts, sells)
        if bp is not None and sp is not None
    ]
    routes.sort(key=lambda r: r.pct, reverse=True)
    return routes, problems
