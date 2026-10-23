"""Swing engine, strategies, metrics and commands."""
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import numpy as np
import pandas as pd

from aptrade import cli
from aptrade.swing import metrics
from aptrade.swing.cli import ALL_SYMBOLS
from aptrade.swing.engine import BuyAndHold, run
from aptrade.swing.panel import Panel, build_panel
from aptrade.swing.strategies import (MeanReversion, TrendFollowing, WARMUP, grid, period_ends,
                                      rsi_wilder)
from aptrade.swing.validation import walk_forward

from .synthetic_daily import make_daily

NOISE = make_daily(ALL_SYMBOLS, days=1500, kind="noise", seed=1)
TREND = make_daily(ALL_SYMBOLS, days=1500, kind="trend", seed=2)


def panel(bars=NOISE):
    return build_panel(bars, ALL_SYMBOLS)


class TestPanel(unittest.TestCase):
    def test_aligned(self):
        p = panel()
        self.assertEqual(p.close.shape, (1500, len(ALL_SYMBOLS)))
        self.assertFalse(p.close.isna().any().any())

    def test_small_gap_is_filled_large_gap_refused(self):
        bars = {s: df.copy() for s, df in NOISE.items()}
        bars["GLD"] = bars["GLD"].drop(bars["GLD"].index[500:505])
        p = build_panel(bars, ALL_SYMBOLS)
        self.assertEqual(p.filled["GLD"], 5)
        self.assertEqual(p.open["GLD"].iloc[502], p.close["GLD"].iloc[499])   # no trading on a filled day
        bars["GLD"] = bars["GLD"].drop(bars["GLD"].index[600:700])
        with self.assertRaises(ValueError):
            build_panel(bars, ALL_SYMBOLS)

    def test_truncate(self):
        p = panel()
        cut = p.dates[1000]
        self.assertEqual(p.truncate(cut).dates[-1], p.dates[999])


class TestEngine(unittest.TestCase):
    def test_buy_and_hold_accounting(self):
        p = panel()
        res = run(p, BuyAndHold("SPY"), WARMUP, cost_bps=3.0)
        growth = float(np.prod(1 + res.returns))
        expected = p.close["SPY"].iloc[-1] / p.open["SPY"].iloc[WARMUP] * (1 - 2 * 3e-4)   # sell cash, buy SPY
        self.assertAlmostEqual(growth, expected, places=10)
        self.assertEqual(res.rebalances, 1)

    def test_no_cost_no_trade_is_cash(self):
        class Nothing:
            name = "nothing"
            def prepare(self, c): pass
            def reset(self): pass
            def on_close(self, i, w, s): return None
        p = panel()
        res = run(p, Nothing(), WARMUP, cost_bps=3.0)
        growth = float(np.prod(1 + res.returns))
        self.assertAlmostEqual(growth, p.close["BIL"].iloc[-1] / p.open["BIL"].iloc[WARMUP], places=10)

    def test_weights_never_exceed_100pct(self):
        class Greedy:
            name = "greedy"
            def prepare(self, c): pass
            def reset(self): pass
            def on_close(self, i, w, s): return {"SPY": 1.0, "QQQ": 1.0}
        res = run(panel(), Greedy(), WARMUP)
        self.assertTrue(np.allclose(res.weights.sum(axis=1), 1.0))
        self.assertLessEqual(res.weights.drop(columns="BIL").sum(axis=1).max(), 1.0 + 1e-9)

    def test_no_look_ahead(self):
        """Wreck every price after day t: nothing up to day t may change."""
        t = 900
        future = {s: df.copy() for s, df in TREND.items()}
        for s, df in future.items():
            if s != "SPY":
                df.iloc[t + 1:, :4] = df.iloc[t + 1:, :4].to_numpy() * np.linspace(0.3, 3.0, len(df) - t - 1)[:, None]
        for strat in grid("trend") + grid("meanrev"):
            a = run(build_panel(TREND, ALL_SYMBOLS), strat, WARMUP).returns
            b = run(build_panel(future, ALL_SYMBOLS), strat, WARMUP).returns
            day = a.index[t - WARMUP]
            pd.testing.assert_series_equal(a.loc[:day], b.loc[:day], check_names=False)


class TestTrend(unittest.TestCase):
    def test_holds_uptrends_only_inverse_vol(self):
        p = panel()
        s = TrendFollowing(63, "M")
        s.prepare(p.close)
        i = next(j for j in range(WARMUP, len(p.dates)) if s.ends[j])
        w = s.on_close(i, {}, list(p.close.columns))
        held = [k for k, v in w.items() if v > 0]
        mom = (p.close[s.universe].iloc[i] / p.close[s.universe].iloc[i - 63] - 1)
        self.assertEqual(sorted(held), sorted(mom[mom > 0].index))
        inv = 1 / p.close[s.universe].pct_change().rolling(60).std().iloc[i]
        self.assertAlmostEqual(w[held[0]], (inv / inv.sum())[held[0]])
        self.assertLessEqual(sum(w.values()), 1.0 + 1e-12)

    def test_only_trades_on_period_ends(self):
        p = panel()
        s = TrendFollowing(126, "W")
        s.prepare(p.close)
        self.assertIsNone(s.on_close(next(j for j in range(WARMUP, 1400) if not s.ends[j]), {}, []))

    def test_period_ends(self):
        d = pd.bdate_range("2026-01-26", "2026-02-06")
        m = period_ends(d, "M")
        self.assertEqual([str(x.date()) for x in d[m]], ["2026-01-30", "2026-02-06"])
        w = period_ends(d, "W")
        self.assertEqual([str(x.date()) for x in d[w]], ["2026-01-30", "2026-02-06"])

    def test_grid_is_closed(self):
        with self.assertRaises(ValueError):
            TrendFollowing(200, "M")


class TestMeanReversion(unittest.TestCase):
    def series(self):
        """One ETF in a steady uptrend with a sharp 2-day dip at day 300, then a rebound."""
        days = 400
        c = 100 * np.cumprod(np.full(days, 1.001))
        c[300], c[301] = c[299] * 0.97, c[299] * 0.94
        c[302:] = c[301] * np.cumprod(np.full(days - 302, 1.01))
        idx = pd.bdate_range("2020-01-01", periods=days)
        return pd.DataFrame({"XLK": c}, index=idx)

    def test_entry_on_washout_exit_above_sma5(self):
        closes = self.series()
        s = MeanReversion(10, 10, universe=["XLK"])
        s.prepare(closes)
        s.reset()
        self.assertIsNone(s.on_close(299, {}, ["XLK"]))
        self.assertLess(s.rsi[301, 0], 10)
        self.assertEqual(s.on_close(301, {}, ["XLK"]), {"XLK": 0.2})
        exits = [i for i in range(302, 320) if s.on_close(i, {"XLK": 0.2}, ["XLK"]) == {}]
        self.assertTrue(exits)
        self.assertGreater(closes["XLK"].iloc[exits[0]], closes["XLK"].rolling(5).mean().iloc[exits[0]])

    def test_max_hold(self):
        closes = self.series()
        closes.iloc[302:, 0] = closes.iloc[301, 0] * np.cumprod(np.full(98, 0.999))   # no rebound
        s = MeanReversion(10, 5, universe=["XLK"])
        s.prepare(closes)
        s.reset()
        s.on_close(301, {}, ["XLK"])
        out = [s.on_close(i, {"XLK": 0.2}, ["XLK"]) for i in range(302, 307)]
        self.assertEqual(out[:-1], [None] * 4)
        self.assertEqual(out[-1], {})                     # day 306 = entry + 5, no same-close re-entry
        self.assertEqual(s.on_close(307, {}, ["XLK"]), {"XLK": 0.2})   # eligible again the next close

    def test_no_entry_below_sma200(self):
        closes = self.series()
        closes.iloc[:, 0] = closes.iloc[::-1, 0].to_numpy()      # downtrend
        s = MeanReversion(20, 10, universe=["XLK"])
        s.prepare(closes)
        s.reset()
        self.assertTrue(all(s.on_close(i, {}, ["XLK"]) is None for i in range(200, 399)))

    def test_rsi_extremes(self):
        up = pd.DataFrame({"A": np.arange(1, 30, dtype=float)})
        self.assertEqual(rsi_wilder(up).iloc[-1, 0], 100.0)
        down = pd.DataFrame({"A": np.arange(30, 1, -1, dtype=float)})
        self.assertAlmostEqual(rsi_wilder(down).iloc[-1, 0], 0.0)


class TestMetrics(unittest.TestCase):
    def test_drawdown(self):
        self.assertAlmostEqual(metrics.max_drawdown(np.array([0.1, -0.5, 0.2])), 0.5)

    def test_verdicts(self):
        s = {"max_drawdown_pct": 10}
        b = {"max_drawdown_pct": 20}
        self.assertTrue(metrics.verdict(s, b, {"diff": 0.3, "ci90_low": 0.05}).startswith("PASS"))
        self.assertTrue(metrics.verdict(s, b, {"diff": 0.3, "ci90_low": -0.1}).startswith("WEAK"))
        self.assertTrue(metrics.verdict(b, s, {"diff": 0.3, "ci90_low": 0.1}).startswith("FAIL"))
        self.assertTrue(metrics.verdict(s, b, {"diff": -0.1, "ci90_low": -0.4}).startswith("FAIL"))

    def test_bootstrap_identical_series(self):
        r = pd.Series(np.random.default_rng(0).normal(0, 0.01, 500), index=pd.bdate_range("2020-01-01", periods=500))
        d = metrics.sharpe_difference(r, r, n_boot=200)
        self.assertAlmostEqual(d["diff"], 0.0)
        self.assertAlmostEqual(d["ci90_low"], 0.0)


class TestNoiseVsTrend(unittest.TestCase):
    def test_noise_does_not_pass(self):
        for strategy in ("trend", "meanrev"):
            wf = walk_forward(panel(NOISE), strategy)
            self.assertFalse(wf["oos"]["verdict"].startswith("PASS"), (strategy, wf["oos"]["verdict"]))

    def test_planted_trend_is_found(self):
        wf = walk_forward(panel(TREND), "trend")
        self.assertTrue(wf["oos"]["verdict"].startswith("PASS"), wf["oos"]["verdict"])


class TestSwingCommands(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict("os.environ", {"APTRADE_DATA_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        fake = lambda syms, start, end, settings, feed="sip", refresh=False, timeframe="5m": (NOISE, "synthetic")
        with mock.patch("aptrade.swing.cli.load_bars", fake), redirect_stdout(out), redirect_stderr(err):
            try:
                cli.main(list(argv))
            except SystemExit as exc:
                return out.getvalue() + err.getvalue() + str(exc)
        return out.getvalue() + err.getvalue()

    def test_full_cycle(self):
        out = self.call("swing", "fetch")
        self.assertIn("swing holdout locked", out)
        out = self.call("swing", "backtest", "--strategy", "trend")
        self.assertIn("VERDICT", out)
        self.assertIn("RESEARCH DATA only", out)
        out = self.call("swing", "sweep", "--strategy", "meanrev")
        self.assertIn("OUT OF SAMPLE", out)
        self.assertIn("CANDIDATE FOR THE HOLDOUT", out)
        self.assertIn("SWING HOLDOUT LOOK #1", self.call("swing", "holdout", "--strategy", "trend"))
        self.assertIn("already been looked at 1", self.call("swing", "holdout", "--strategy", "trend"))

    def test_off_grid_parameters_refused(self):
        self.assertIn("pre-registered grid", self.call("swing", "backtest", "--strategy", "trend", "--lookback", "200"))


if __name__ == "__main__":
    unittest.main()


class TestBlend(unittest.TestCase):
    def test_weights_half_spy_half_trend(self):
        from aptrade.swing.strategies import Blend
        p = panel()
        b, t = Blend(), TrendFollowing(63, "M")
        b.prepare(p.close)
        t.prepare(p.close)
        i = next(j for j in range(WARMUP, len(p.dates)) if t.ends[j])
        wb, wt = b.on_close(i, {}, []), t.on_close(i, {}, [])
        self.assertAlmostEqual(wb["SPY"], 0.5 + 0.5 * wt.get("SPY", 0.0))
        for s, w in wt.items():
            if s != "SPY":
                self.assertAlmostEqual(wb[s], 0.5 * w)
        self.assertLessEqual(sum(wb.values()), 1.0 + 1e-12)
        self.assertIsNone(b.on_close(i + 1, {}, []))          # only at month-ends

    def test_blend_cuts_the_drawdown_in_a_trending_market(self):
        from aptrade.swing.strategies import Blend
        p = panel(TREND)
        r = run(p, Blend(), WARMUP).returns
        spy = run(p, BuyAndHold("SPY"), WARMUP).returns
        self.assertLess(metrics.max_drawdown(r.to_numpy()), metrics.max_drawdown(spy.to_numpy()))

    def test_verdict(self):
        spy = {"max_drawdown_pct": 30.0, "excess_sharpe": 0.8, "cagr_pct": 12.0}
        ok = {"max_drawdown_pct": 15.0, "excess_sharpe": 0.75, "cagr_pct": 7.0}
        self.assertTrue(metrics.verdict_blend(ok, spy).startswith("PASS"))
        self.assertIn("MISS  max drawdown", metrics.verdict_blend({**ok, "max_drawdown_pct": 19.0}, spy))
        self.assertIn("MISS  excess Sharpe", metrics.verdict_blend({**ok, "excess_sharpe": 0.6}, spy))
        self.assertIn("MISS  CAGR", metrics.verdict_blend({**ok, "cagr_pct": 5.0}, spy))
        self.assertTrue(metrics.verdict_blend({**ok, "cagr_pct": -3.0}, {**spy, "cagr_pct": -8.0}).startswith("PASS"))

    def test_excess_sharpe_penalises_cash(self):
        idx = pd.bdate_range("2020-01-01", periods=500)
        cash = pd.Series(0.0002, index=idx)
        r = cash + pd.Series(np.random.default_rng(3).normal(0, 0.0005, 500), index=idx)
        c = metrics.compare(r, r * 0 + 0.0003 + np.random.default_rng(4).normal(0, 0.01, 500), cash)
        self.assertLess(abs(c["strategy"]["excess_sharpe"]), c["strategy"]["sharpe"])

    def test_blend_commands(self):
        tc = TestSwingCommands()
        tc.setUp()
        try:
            out = tc.call("swing", "backtest", "--strategy", "blend")
            self.assertIn("excess Sharpe", out)
            self.assertIn("conditions missed", out) if "FAIL" in out else self.assertIn("PASS", out)
            self.assertIn("SWING HOLDOUT LOOK #1", tc.call("swing", "holdout", "--strategy", "blend"))
        finally:
            tc.tearDown()


class TestStaticAndRotation(unittest.TestCase):
    def test_static_is_blend_without_the_signal(self):
        from aptrade.swing.strategies import StaticBlend
        p = panel()
        s = StaticBlend()
        s.prepare(p.close)
        i = next(j for j in range(WARMUP, len(p.dates)) if s.ends[j])
        w = s.on_close(i, {}, [])
        self.assertEqual(len(w), 15)                                  # every ETF, whatever its trend
        self.assertAlmostEqual(sum(w.values()), 1.0)
        inv = 1 / p.close[s.universe].pct_change().rolling(60).std().iloc[i]
        self.assertAlmostEqual(w["GLD"], 0.5 * (inv / inv.sum())["GLD"])

    def test_rotation_top3_above_cash(self):
        from aptrade.swing.strategies import Rotation
        p = panel(TREND)
        r = Rotation()
        r.prepare(p.close)
        for i in [j for j in range(WARMUP, len(p.dates)) if r.ends[j]][:12]:
            w = r.on_close(i, {}, [])
            mom = p.close[r.universe].iloc[i] / p.close[r.universe].iloc[i - 252] - 1
            cash = p.close["BIL"].iloc[i] / p.close["BIL"].iloc[i - 252] - 1
            top = list(mom.sort_values(ascending=False).index[:3])
            self.assertEqual(set(w), {s for s in top if mom[s] > cash})
            self.assertTrue(all(abs(v - 1 / 3) < 1e-12 for v in w.values()))

    def test_rotation_all_cash_when_nothing_beats_cash(self):
        from aptrade.swing.strategies import Rotation
        idx = pd.bdate_range("2018-01-01", periods=400)
        closes = pd.DataFrame({s: np.linspace(100, 90, 400) for s in Rotation().universe}, index=idx)
        closes["BIL"] = np.linspace(100, 101, 400)
        r = Rotation()
        r.prepare(closes)
        i = next(j for j in range(300, 400) if r.ends[j])
        self.assertEqual(r.on_close(i, {}, []), {})

    def test_rotation_uses_98pct_interval(self):
        tc = TestSwingCommands()
        tc.setUp()
        try:
            out = tc.call("swing", "backtest", "--strategy", "rotation")
            self.assertIn("Excess Sharpe difference", out)
            self.assertIn("98% interval", out)
        finally:
            tc.tearDown()

    def test_holdout_counted_per_strategy(self):
        tc = TestSwingCommands()
        tc.setUp()
        try:
            self.assertIn("LOOK #1", tc.call("swing", "holdout", "--strategy", "blend"))
            self.assertIn("LOOK #1", tc.call("swing", "holdout", "--strategy", "static"))
            self.assertIn("LOOK #1", tc.call("swing", "holdout", "--strategy", "rotation"))
            self.assertIn("already been looked at 1", tc.call("swing", "holdout", "--strategy", "static"))
        finally:
            tc.tearDown()

    def test_no_look_ahead_new_strategies(self):
        from aptrade.swing.strategies import Rotation, StaticBlend
        t = 900
        future = {s: df.copy() for s, df in TREND.items()}
        for s, df in future.items():
            if s != "SPY":
                df.iloc[t + 1:, :4] = df.iloc[t + 1:, :4].to_numpy() * 2.5
        for strat in (StaticBlend(), Rotation()):
            a = run(build_panel(TREND, ALL_SYMBOLS), strat, WARMUP).returns
            b = run(build_panel(future, ALL_SYMBOLS), strat, WARMUP).returns
            day = a.index[t - WARMUP]
            pd.testing.assert_series_equal(a.loc[:day], b.loc[:day], check_names=False)
