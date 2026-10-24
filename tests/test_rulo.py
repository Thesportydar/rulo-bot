import unittest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from rulo.alerts import collapse, decide, format_message
from rulo.evaluator import evaluate
from rulo.market import is_market_open
from rulo.models import Quote, Venue
from rulo.state import EMPTY_STATE

NOW = datetime(2026, 10, 26, 15, 0, tzinfo=timezone.utc)
TH = {"open_pct": 1.0, "strong_pct": 1.5, "improve_pct": 0.3, "close_pct": 0.8, "top_routes": 5}


def venue(name, pair, source="test"):
    return Venue(name=name, platform=name.lower(), source=source, slug=name.lower(), pair=pair)


def quote(name, pair, bid=None, ask=None, ts=NOW):
    return Quote(source="test", slug=name.lower(), pair=pair, bid=bid, ask=ask, ts=ts)


CFG = {
    "buy": [venue("Cocos", "USD/ARS"), venue("Fiwind", "USD/ARS")],
    "convert": [venue("Fiwind", "USDT/USD"), venue("Belo", "USDT/USD")],
    "sell": [venue("Belo", "USDT/ARS"), venue("Lemon", "USDT/ARS")],
    "freshness": {"max_age_minutes": 30},
    "market": {"timezone": "America/Argentina/Buenos_Aires", "days": [0, 1, 2, 3, 4], "open": "11:00", "close": "17:00"},
}

QUOTES = [
    quote("Cocos", "USD/ARS", ask=1550),
    quote("Fiwind", "USD/ARS", ask=1560),
    quote("Fiwind", "USDT/USD", ask=1.04),
    quote("Belo", "USDT/USD", ask=1.065),
    quote("Belo", "USDT/ARS", bid=1637),
    quote("Lemon", "USDT/ARS", bid=1600),
]


class EvaluateTest(unittest.TestCase):
    def test_best_route_matches_manual_math(self):
        routes, problems = evaluate(CFG, QUOTES, now=NOW)
        self.assertEqual(problems, [])
        self.assertEqual(len(routes), 8)
        best = routes[0]
        self.assertEqual(best.id, "Cocos>Fiwind>Belo")
        self.assertAlmostEqual(best.pct, (1637 / (1550 * 1.04) - 1) * 100)

    def test_same_broker_detected(self):
        routes, _ = evaluate(CFG, QUOTES, now=NOW)
        r = next(r for r in routes if r.id == "Fiwind>Fiwind>Belo")
        self.assertTrue(r.same_broker)

    def test_stale_missing_and_broken_quotes_are_dropped(self):
        quotes = [q for q in QUOTES if q.slug != "lemon"]
        quotes = [q if q.slug != "belo" or q.pair != "USDT/USD" else quote("Belo", "USDT/USD", ask=1.04, ts=NOW - timedelta(hours=2)) for q in quotes]
        quotes = [q if q.pair != "USDT/USD" or q.slug != "fiwind" else quote("Fiwind", "USDT/USD", ask=1600) for q in quotes]
        routes, problems = evaluate(CFG, quotes, now=NOW)
        self.assertEqual(routes, [])
        self.assertEqual(len(problems), 3)


class DecideTest(unittest.TestCase):
    def test_lifecycle(self):
        state = dict(EMPTY_STATE)
        self.assertIsNone(decide(0.5, state, TH))
        self.assertEqual(decide(1.1, state, TH), "open")
        self.assertIsNone(decide(1.2, state, TH))
        self.assertEqual(decide(1.45, state, TH), "improve")
        self.assertIsNone(decide(0.9, state, TH))  # histéresis: sigue abierto
        self.assertEqual(decide(0.7, state, TH), "close")
        self.assertFalse(state["open"])


class FormatTest(unittest.TestCase):
    def test_collapse_and_message(self):
        quotes = QUOTES + [quote("Lemon", "USDT/ARS", bid=1637)]
        routes, _ = evaluate(CFG, [q for q in quotes if not (q.slug == "lemon" and q.bid == 1600)], now=NOW)
        groups = collapse(routes)
        self.assertEqual(groups[0][1], ["Belo", "Lemon"])
        msg = format_message("open", routes, TH)
        self.assertIn("🔥", msg)
        self.assertIn("vender en Belo / Lemon", msg)


class MarketTest(unittest.TestCase):
    tz = ZoneInfo("America/Argentina/Buenos_Aires")

    def test_hours(self):
        self.assertTrue(is_market_open(CFG, datetime(2026, 10, 26, 11, 0, tzinfo=self.tz)))  # lunes
        self.assertFalse(is_market_open(CFG, datetime(2026, 10, 26, 17, 0, tzinfo=self.tz)))
        self.assertFalse(is_market_open(CFG, datetime(2026, 10, 24, 12, 0, tzinfo=self.tz)))  # sábado


if __name__ == "__main__":
    unittest.main()
