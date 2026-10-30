from __future__ import annotations

import html

from rulo.models import Route


def decide(best_pct: float, state: dict, th: dict) -> str | None:
    """Devuelve 'open', 'improve', 'close' o None, y actualiza state en el lugar.

    Para abrir, la ruta tiene que superar el umbral en `confirm_runs` corridas seguidas: un pico
    de una sola corrida suele ser un dato roto de la fuente.
    """
    if not state["open"]:
        if best_pct < th["open_pct"]:
            state["pending"] = 0
            return None
        state["pending"] += 1
        if state["pending"] < th.get("confirm_runs", 1):
            return None
        state.update(open=True, last_pct=best_pct, pending=0)
        return "open"
    if best_pct < th["close_pct"]:
        state.update(open=False, last_pct=None)
        return "close"
    if best_pct >= state["last_pct"] + th["improve_pct"]:
        state["last_pct"] = best_pct
        return "improve"
    return None


def _fmt(n: float, decimals: int = 2) -> str:
    # formato argentino: 1.637,00
    return f"{n:,.{decimals}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def collapse(routes: list[Route], tolerance_pct: float = 0.05) -> list[tuple[Route, list[str]]]:
    """Agrupa por (compra, conversión) y junta las ventas que rinden casi lo mismo que la mejor.

    Espera las rutas ordenadas de mejor a peor, así la primera de cada grupo es su mejor ruta.
    """
    groups: dict[tuple[str, str], tuple[Route, list[str]]] = {}
    for r in routes:
        key = (r.buy.name, r.convert.name)
        if key not in groups:
            groups[key] = (r, [r.sell.name])
        elif r.pct >= groups[key][0].pct - tolerance_pct:
            groups[key][1].append(r.sell.name)
    return list(groups.values())


def format_route(r: Route, sells: list[str] | None = None) -> str:
    def e(s: str) -> str:
        return html.escape(s, quote=False)

    transfer = " (sin transferir)" if r.same_broker else ""
    sell_names = " / ".join(e(s) for s in (sells or [r.sell.name]))
    return (
        f"<b>{_fmt(r.pct)}%</b> · MEP {e(r.buy.name)} {_fmt(r.mep_ask)} → "
        f"convertir en {e(r.convert.name)}{transfer} {_fmt(r.rate, 4)} → "
        f"vender en {sell_names} {_fmt(r.sell_bid)}"
    )


def format_message(event: str, routes: list[Route], th: dict) -> str:
    best = routes[0]
    if event == "close":
        return f"⚪ Rulo cerrado. Mejor ruta ahora: {_fmt(best.pct)}%\n{format_route(best)}"
    icon = "🔥" if best.pct >= th["strong_pct"] else "🟢"
    title = "Rulo abierto" if event == "open" else "Rulo mejoró"
    lines = [f"{icon} <b>{title}</b>", ""]
    top = collapse(routes)[: th["top_routes"]]
    lines += [f"{i}. {format_route(r, sells)}" for i, (r, sells) in enumerate(top, 1)]
    lines += ["", f"Costo por USDT: {_fmt(best.cost_per_usdt)} ARS"]
    return "\n".join(lines)


def format_summary(state: dict, day: str) -> str:
    dd, mm = day[8:10], day[5:7]
    if not state["runs"]:
        return f"⚠️ <b>Resumen {dd}/{mm}</b>: no hubo corridas hoy. Revisar la Lambda o el schedule."
    lines = [f"📊 <b>Resumen {dd}/{mm}</b>", ""]
    best = state["best"]
    if best:
        lines.append(f"Mejor ruta del día ({best['at']}): {best['route']}")
    else:
        lines.append("Sin rutas válidas en todo el día.")
    failed = f" ({state['fail_runs']} sin datos)" if state["fail_runs"] else ""
    lines.append(f"Corridas: {state['runs']}{failed} · Avisos: {state['alerts']}")
    return "\n".join(lines)
