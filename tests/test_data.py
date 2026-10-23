"""The data layer with Alpaca mocked: first call downloads and caches, second call
reads the cache. The second path crashed in v0.2 on tz-aware datetimes, which is
exactly what the CLI passes; these tests use the CLI's own _period() to build them."""
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from aptrade import data
from aptrade.intraday import cli
from aptrade.config import Settings

from .synthetic import make_bars


def settings(tmp):
    return Settings(api_key="k", secret_key="s", data_dir=Path(tmp), db_path=Path(tmp) / "db.sqlite")


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bars = {"AAA": make_bars(1, days=40, start="2026-01-02"),
                     "BBB": make_bars(2, days=40, start="2026-01-02")}
        a = Namespace(start="2026-01-02", end="2026-02-26")
        self.start, self.end = cli._period(a)            # tz-aware, as in real runs

    def tearDown(self):
        self.tmp.cleanup()

    def fake_fetch(self, symbols, start, end, feed, key, secret, timeframe="5m"):
        self.calls.append(list(symbols))
        return {s: self.bars[s] for s in symbols}

    def test_download_then_cache(self):
        self.calls = []
        st = settings(self.tmp.name)
        with mock.patch.object(data, "_alpaca_fetch", self.fake_fetch):
            first, feed = data.load_bars(["AAA", "BBB"], self.start, self.end, st)
            second, _ = data.load_bars(["AAA", "BBB"], self.start, self.end, st)
        self.assertEqual(self.calls, [["AAA", "BBB"]])          # one download only
        self.assertEqual(feed, "sip")
        for s in ("AAA", "BBB"):
            self.assertEqual(len(second[s]), len(first[s]))
            self.assertEqual(str(second[s].index.tz), "UTC")
            # CSV round trip: equal to 12 significant digits (real prices have at most 4 decimals)
            self.assertTrue(np.allclose(second[s]["close"].to_numpy(), first[s]["close"].to_numpy(),
                                        rtol=1e-12, atol=0))

    def test_partial_cache_fetches_only_the_missing(self):
        self.calls = []
        st = settings(self.tmp.name)
        with mock.patch.object(data, "_alpaca_fetch", self.fake_fetch):
            data.load_bars(["AAA"], self.start, self.end, st)
            data.load_bars(["AAA", "BBB"], self.start, self.end, st)
        self.assertEqual(self.calls, [["AAA"], ["BBB"]])

    def test_naive_and_aware_dates_agree(self):
        idx = pd.date_range("2026-01-05", periods=3, freq="D", tz="UTC")
        df = pd.DataFrame({"close": [1, 2, 3]}, index=idx)
        self.assertTrue(data._covers(df, self.start.replace(tzinfo=None), self.end.replace(tzinfo=None))
                        == data._covers(df, self.start, self.end))

    def test_sip_refused_falls_back_to_iex(self):
        self.calls = []
        st = settings(self.tmp.name)

        def fetch(symbols, start, end, feed, key, secret, timeframe="5m"):
            if feed == "sip":
                raise RuntimeError("subscription does not permit querying recent SIP data")
            return self.fake_fetch(symbols, start, end, feed, key, secret, timeframe)
        with mock.patch.object(data, "_alpaca_fetch", fetch), mock.patch("sys.stderr"):
            _, feed = data.load_bars(["AAA"], self.start, self.end, st)
        self.assertEqual(feed, "iex")

    def test_cli_backtest_on_cached_data(self):
        """The exact sequence that crashed: fetch, then backtest reading the cache."""
        self.calls = []
        with mock.patch.dict("os.environ", {"APTRADE_DATA_DIR": self.tmp.name, "ALPACA_API_KEY": "k",
                                            "ALPACA_SECRET_KEY": "s"}), \
                mock.patch.object(data, "_alpaca_fetch", self.fake_fetch), \
                mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            args = ["--symbols", "AAA,BBB", "--start", "2026-01-02", "--end", "2026-02-26"]
            self.assertEqual(cli.main(["fetch"] + args), 0)
            self.assertEqual(cli.main(["backtest", "--no-save"] + args), 0)
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
