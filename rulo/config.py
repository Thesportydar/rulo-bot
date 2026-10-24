from __future__ import annotations

import os
import tomllib
from pathlib import Path

from rulo.models import Venue

LEGS = ("buy", "convert", "sell")


def load_config(path: Path) -> dict:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    for leg in LEGS:
        cfg[leg] = [Venue(**v) for v in cfg.get(leg, [])]
        if not cfg[leg]:
            raise ValueError(f"config: no hay plataformas en [[{leg}]]")
    th = cfg["thresholds"]
    if th["close_pct"] > th["open_pct"]:
        raise ValueError("config: close_pct tiene que ser <= open_pct")
    return cfg


def load_dotenv(path: Path) -> None:
    """Carga KEY=VALUE en os.environ sin pisar variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
