from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

EMPTY_STATE = {
    "open": False,
    "last_pct": None,
    "fail_streak": 0,
    "pending": 0,  # corridas seguidas sobre open_pct sin confirmar todavía
    "day": None,
    # métricas del día para el resumen de cierre
    "runs": 0,
    "fail_runs": 0,
    "alerts": 0,
    "best": None,  # {"pct", "route" (HTML), "at" (HH:MM)}
}


def roll_day(state: dict, today: str) -> None:
    """Al cambiar de día se descarta todo: una ruta abierta de ayer ya no vale y las métricas arrancan de cero."""
    if state["day"] != today:
        state.update({**EMPTY_STATE, "day": today})


class StateStore(Protocol):
    def load(self) -> dict: ...

    def save(self, state: dict) -> None: ...


class FileStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> dict:
        try:
            return {**EMPTY_STATE, **json.loads(self.path.read_text())}
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(EMPTY_STATE)

    def save(self, state: dict) -> None:
        self.path.write_text(json.dumps(state, indent=2))


class DynamoStore:
    """Un único ítem con el estado serializado. Solo escribe si cambió."""

    def __init__(self, table: str, key: str = "monitor"):
        import boto3  # disponible en el runtime de Lambda; local solo hace falta si se usa

        self.table = boto3.resource("dynamodb").Table(table)
        self.key = key
        self._loaded: dict | None = None

    def load(self) -> dict:
        item = self.table.get_item(Key={"pk": self.key}).get("Item")
        state = {**EMPTY_STATE, **json.loads(item["state"])} if item else dict(EMPTY_STATE)
        self._loaded = dict(state)
        return state

    def save(self, state: dict) -> None:
        if state == self._loaded:
            return
        self.table.put_item(Item={"pk": self.key, "state": json.dumps(state)})
        self._loaded = dict(state)


def build_store(default_path: Path) -> StateStore:
    table = os.environ.get("RULO_STATE_TABLE")
    return DynamoStore(table) if table else FileStore(default_path)
