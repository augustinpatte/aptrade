"""The user-facing pieces: slider allocations, custom portfolios, the export, the CLI."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import numpy as np
import pandas as pd

from aptrade import cli
from aptrade.export import build
from aptrade.swing import metrics
from aptrade.swing.cli import ALL_SYMBOLS
from aptrade.swing.custom import evaluate
from aptrade.swing.engine import BuyAndHold, run
from aptrade.swing.panel import build_panel
from aptrade.swing.strategies import WARMUP, Allocation, CustomAllocation, StaticBlend

from .synthetic_daily import make_daily

BARS = make_daily(ALL_SYMBOLS, days=900, kind="noise", seed=8)


class TestAllocations(unittest.TestCase):
    def test_slider_ends(self):
        p = build_panel(BARS, ALL_SYMBOLS)
        all_spy = run(p, Allocation(1.0), WARMUP).returns
        spy = run(p, BuyAndHold("SPY"), WARMUP).returns
        self.assertLess(abs(float(np.prod(1 + all_spy)) - float(np.prod(1 + spy))), 1e-3)
        none = Allocation(0.0)
        none.prepare(p.close)
        i = next(j for j in range(WARMUP, 900) if none.ends[j])
        w = none.on_close(i, {}, [])
        self.assertLess(w["SPY"], 0.2)                           # only its sleeve share

    def test_static_is_alloc_50(self):
        p = build_panel(BARS, ALL_SYMBOLS)
        a = run(p, Allocation(0.5), WARMUP).returns
        b = run(p, StaticBlend(), WARMUP).returns
        pd.testing.assert_series_equal(a, b)

    def test_custom_validation(self):
        with self.assertRaises(ValueError):
            CustomAllocation({"SPY": 0.8, "TLT": 0.4})            # 120%: no leverage
        with self.assertRaises(ValueError):
            CustomAllocation({"SPY": 0})
        with self.assertRaises(ValueError):
            CustomAllocation({"SPY": 1}, rebalance="D")

    def test_custom_evaluate_and_young_etf(self):
        bars = dict(BARS)
        young = BARS["GLD"].iloc[300:].copy()                     # launched later than the rest
        bars["NEWETF"] = young
        out = evaluate(CustomAllocation({"SPY": 0.6, "NEWETF": 0.4}, "Q"), bars)
        self.assertGreaterEqual(out["growth"].index[0], pd.Timestamp(young.index[0].tz_convert("America/New_York").date()))
        self.assertIn("verdict", out["compare"])
        self.assertGreater(out["rebalances"], 2)

    def test_custom_cash_remainder(self):
        out = evaluate(CustomAllocation({"SPY": 0.5}, "M"), dict(BARS))
        self.assertAlmostEqual(float(out["weights"]["BIL"].iloc[5]), 0.5, delta=0.05)


class TestExport(unittest.TestCase):
    def test_no_prices_only_monthly_and_stats(self):
        p = build_panel(BARS, ALL_SYMBOLS)
        doc = build(p, str(p.dates[700].date()), progress=lambda m: None)
        text = json.dumps(doc)
        for banned in ('"open"', '"close"', '"high"', '"low"', '"volume"'):
            self.assertNotIn(banned, text)
        port = doc["portfolios"]["alloc_50"]
        months = [m for m, _ in port["monthly"]]
        self.assertEqual(len(months), len(set(months)))          # one value per month, no daily series
        self.assertLess(len(months), 60)
        self.assertEqual(set(port["stats"]), {"full", "3y", "research", "holdout"})
        self.assertIn("max_position_pct", port["activity"])
        self.assertIn("excess_sharpe", port["stats"]["holdout"]["portfolio"])
        self.assertEqual(len([k for k in doc["portfolios"] if k.startswith("alloc_")]), 11)


class TestTopLevelCli(unittest.TestCase):
    def test_groups(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit):
            cli.main(["--help"])
        for word in ("swing", "intraday", "export", "app", "runs"):
            self.assertIn(word, out.getvalue())

    def test_intraday_backtest_through_the_top_level(self):
        from aptrade.intraday import cli as icli
        from tests.test_cli import fake_load_bars
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict("os.environ", {"APTRADE_DATA_DIR": tmp}), \
                mock.patch.object(icli, "load_bars", fake_load_bars), redirect_stdout(io.StringIO()) as out, \
                redirect_stderr(io.StringIO()):
            self.assertEqual(cli.main(["intraday", "backtest", "--symbols", "TSLA", "--parity", "--no-save"]), 0)
        self.assertIn("avg R, gross      -0.0", out.getvalue())


if __name__ == "__main__":
    unittest.main()


class TestReadmeTables(unittest.TestCase):
    def test_fill_both_readmes(self):
        import shutil
        from pathlib import Path
        from aptrade.readme_tables import fill_readmes
        root = Path(__file__).resolve().parent.parent
        p = build_panel(BARS, ALL_SYMBOLS)
        doc = build(p, str(p.dates[700].date()), progress=lambda m: None)
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "results").mkdir()
            shutil.copy(root / "results" / "research.json", tmp / "results" / "research.json")
            for name in ("README.md", "README.fr.md"):
                shutil.copy(root / name, tmp / name)
            done = fill_readmes(doc, tmp)
            self.assertEqual(len(done), 2)
            en, fr = (tmp / "README.md").read_text(), (tmp / "README.fr.md").read_text()
            self.assertIn("| Diversified 50% SPY |", en)
            self.assertIn("| Diversifié 50 % SPY |", fr)
            self.assertIn("Day trading", en)
            self.assertNotIn("Run `aptrade export` to fill", en)
            self.assertNotIn("FAIL", en.split("<!-- results:start -->")[1].split("<!-- results:end -->")[0])
            again = fill_readmes(doc, tmp)                       # idempotent: markers survive
            self.assertEqual(len(again), 2)
