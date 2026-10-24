from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from rulo.alerts import collapse, decide, format_message, format_route
from rulo.config import LEGS, load_config, load_dotenv
from rulo.evaluator import evaluate
from rulo.market import is_market_open, local_today
from rulo.notifier import build_notifier
from rulo.sources import build_sources
from rulo.state import build_store

ROOT = Path(__file__).resolve().parent.parent
FAIL_STREAK_ALERT = 5


def fetch_all(cfg: dict) -> tuple[list, list[str]]:
    sources = build_sources(cfg)
    pairs_by_source: dict[str, set[str]] = defaultdict(set)
    for leg in LEGS:
        for venue in cfg[leg]:
            pairs_by_source[venue.source].add(venue.pair)

    quotes, errors = [], []
    for name, pairs in pairs_by_source.items():
        try:
            quotes += sources[name].fetch(pairs)
        except Exception as e:  # noqa: BLE001 - si una fuente cae seguimos con las demás
            errors.append(f"{name}: {e}")
    return quotes, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rulo", description="Monitor del rulo MEP → USDT → ARS")
    parser.add_argument("--config", type=Path, default=ROOT / "config.toml")
    parser.add_argument("--state", type=Path, default=ROOT / "state.json")
    parser.add_argument("--dry-run", action="store_true", help="muestra la tabla de rutas sin notificar ni guardar estado")
    parser.add_argument("--force", action="store_true", help="ignora el horario de mercado")
    parser.add_argument("--test-notify", action="store_true", help="envía un mensaje de prueba y sale")
    parser.add_argument("--top", type=int, default=15, help="rutas a mostrar en --dry-run")
    args = parser.parse_args(argv)

    load_dotenv(ROOT / ".env")
    cfg = load_config(args.config)
    stamp = datetime.now(ZoneInfo(cfg["market"]["timezone"])).strftime("%Y-%m-%d %H:%M:%S")

    if args.test_notify:
        ok = build_notifier(cfg).send("✅ Rulo monitor: prueba de notificación")
        return 0 if ok else 1

    store = build_store(args.state)
    state = store.load()
    today = local_today(cfg)
    if state["open"] and state["day"] != today:
        # una ruta abierta de otro día ya no vale: el próximo aviso tiene que ser de apertura
        state.update(open=False, last_pct=None)
    state["day"] = today
    if not (args.dry_run or args.force or is_market_open(cfg)):
        if state["open"]:
            # fuera de horario no se puede operar: se resetea sin avisar
            state.update(open=False, last_pct=None)
            store.save(state)
        print(f"{stamp} mercado cerrado")
        return 0

    quotes, errors = fetch_all(cfg)
    routes, problems = evaluate(cfg, quotes)
    for msg in errors:
        print(f"{stamp} error fuente {msg}", file=sys.stderr)

    if args.dry_run:
        for p in problems:
            print(f"  ! {p}")
        for r, sells in collapse(routes)[: args.top]:
            print(format_route(r, sells).replace("<b>", "").replace("</b>", ""))
        return 0 if routes else 1

    notifier = build_notifier(cfg)
    if not routes:
        state["fail_streak"] += 1
        print(f"{stamp} sin rutas ({'; '.join(errors + problems)[:500]})", file=sys.stderr)
        if state["fail_streak"] == FAIL_STREAK_ALERT:
            notifier.send(f"⚠️ Rulo monitor: {FAIL_STREAK_ALERT} corridas seguidas sin datos.\n" + "\n".join(errors[:3]))
        store.save(state)
        return 1

    state["fail_streak"] = 0
    best = routes[0]
    event = decide(best.pct, state, cfg["thresholds"])
    print(f"{stamp} mejor {best.pct:+.2f}% {best.id} evento={event}")
    if event:
        notifier.send(format_message(event, routes, cfg["thresholds"]))
    store.save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
