"""Extra data sources (Yahoo, Tiingo), broker selection and the .env helper. No network:
the HTTP function is replaced by canned answers in the documented format."""
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS
from unittest import mock

import pandas as pd

from aptrade import sources
from aptrade.brokers import base, get_broker


class TestBrokerChoice(unittest.TestCase):
    def test_unknown_broker_is_refused(self):
        with mock.patch.dict(os.environ, {"APTRADE_BROKER": "ibkr"}):
            with self.assertRaises(base.BrokerError):
                get_broker(False)


# ------------------------------------------------------------------ data sources
def _yahoo_doc():
    ts = [int(pd.Timestamp("2026-10-20 13:30", tz="UTC").timestamp()),
          int(pd.Timestamp("2026-10-21 13:30", tz="UTC").timestamp())]
    return {"chart": {"result": [{"meta": {"currency": "USD", "regularMarketPrice": 101.0}, "timestamp": ts,
                                  "indicators": {"quote": [{"open": [99, 100], "high": [101, 102], "low": [98, 99],
                                                            "close": [100, 101], "volume": [10, 20]}],
                                                 "adjclose": [{"adjclose": [50, 101]}]}}], "error": None}}


class TestSources(unittest.TestCase):
    def test_yahoo_bars_are_adjusted_and_dated_right(self):
        with mock.patch.object(sources, "http_json", lambda url, **k: _yahoo_doc()):
            df = sources.yahoo_daily("SPY", "2026-10-19", "2026-10-22")
        self.assertAlmostEqual(df["close"].iloc[0], 50.0)
        self.assertAlmostEqual(df["open"].iloc[0], 99 * 0.5)
        ny = df.index.tz_convert("America/New_York")
        self.assertEqual([d.day for d in ny], [20, 21])                 # same calendar day in New York

    def test_yahoo_last(self):
        with mock.patch.object(sources, "http_json", lambda url, **k: _yahoo_doc()):
            self.assertEqual(sources.yahoo_last("SPY"), (101.0, "USD"))

    def test_tiingo_bars(self):
        rows = [{"date": "2026-10-20T00:00:00.000Z", "adjOpen": 1, "adjHigh": 2, "adjLow": 0.5, "adjClose": 1.5,
                 "adjVolume": 9}]
        seen = {}

        def fake(url, headers=None, **k):
            seen["auth"] = headers["Authorization"]
            return rows
        with mock.patch.object(sources, "http_json", fake):
            df = sources.tiingo_daily("SPY", "2026-10-19", "2026-10-21", "tok")
        self.assertEqual(seen["auth"], "Token tok")
        self.assertEqual(df.index.tz_convert("America/New_York")[0].day, 20)
        with self.assertRaises(sources.SourceError):
            sources.tiingo_daily("SPY", "2026-10-19", "2026-10-21", "")

    def test_auto_source(self):
        from aptrade.data import daily_source
        keys = NS(api_key="a", secret_key="b")
        none = NS(api_key="", secret_key="")
        with mock.patch.dict(os.environ, {"APTRADE_DATA": "auto", "TIINGO_API_KEY": ""}):
            self.assertEqual(daily_source(keys), "alpaca")
            self.assertEqual(daily_source(none), "yahoo")
        with mock.patch.dict(os.environ, {"APTRADE_DATA": "auto", "TIINGO_API_KEY": "t"}):
            self.assertEqual(daily_source(none), "tiingo")
        with mock.patch.dict(os.environ, {"APTRADE_DATA": "yahoo"}):
            self.assertEqual(daily_source(keys), "yahoo")

    def test_load_bars_through_yahoo_uses_its_own_cache(self):
        from aptrade.data import load_bars
        calls = []

        def fake(url, **k):
            calls.append(url)
            return _yahoo_doc()
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"APTRADE_DATA": "yahoo"}), \
                mock.patch.object(sources, "http_json", fake):
            s = NS(api_key="", secret_key="", data_dir=Path(d))
            bars, used = load_bars(["SPY"], datetime(2026, 10, 20), datetime(2026, 10, 22), s, timeframe="1d")
            self.assertEqual(used, "yahoo")
            self.assertEqual(len(bars["SPY"]), 2)
            self.assertTrue((Path(d) / "cache" / "yahoo" / "SPY_1d.csv.gz").is_file())
            load_bars(["SPY"], datetime(2026, 10, 20), datetime(2026, 10, 22), s, timeframe="1d")
        self.assertEqual(len(calls), 1)                                  # second read from cache


class TestEnvFile(unittest.TestCase):
    def test_saving_keys_keeps_the_rest_of_env(self):
        from aptrade.config import set_env_values
        with tempfile.TemporaryDirectory() as d:
            env = Path(d) / ".env"
            env.write_text("# mine\nAPTRADE_DATA=yahoo\nALPACA_API_KEY=old\nAPTRADE_ALLOW_LIVE=1\n")
            set_env_values(env, {"ALPACA_API_KEY": "new", "ALPACA_SECRET_KEY": "sec"})
            txt = env.read_text()
        self.assertIn("APTRADE_DATA=yahoo", txt)
        self.assertIn("APTRADE_ALLOW_LIVE=1", txt)
        self.assertIn("ALPACA_API_KEY=new", txt)
        self.assertNotIn("old", txt)
        self.assertIn("ALPACA_SECRET_KEY=sec", txt)


class TestNoSecretsInFiles(unittest.TestCase):
    def test_example_env_has_placeholders_only(self):
        txt = (Path(__file__).resolve().parents[1] / ".env.example").read_text()
        for name in ("ALPACA_API_KEY", "TIINGO_API_KEY", "APTRADE_DATA", "APTRADE_ALLOW_LIVE"):
            self.assertIn(name, txt)
        for line in txt.splitlines():
            if "KEY=" in line or "SECRET=" in line:
                self.assertTrue(line.split("=", 1)[1].strip() in ("", "your-key-here", "your-secret-here"), line)


if __name__ == "__main__":
    unittest.main()
