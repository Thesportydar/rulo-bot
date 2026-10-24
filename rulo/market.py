from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo


def is_market_open(cfg: dict, now: datetime | None = None) -> bool:
    m = cfg["market"]
    local = (now or datetime.now(ZoneInfo(m["timezone"]))).astimezone(ZoneInfo(m["timezone"]))
    if local.weekday() not in m["days"]:
        return False
    return time.fromisoformat(m["open"]) <= local.time() < time.fromisoformat(m["close"])


def local_today(cfg: dict) -> str:
    return datetime.now(ZoneInfo(cfg["market"]["timezone"])).date().isoformat()
