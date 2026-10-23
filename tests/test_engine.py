"""Execution, strategy and stats on hand-built sessions where the answer is known."""
import unittest
from datetime import date, timedelta

import numpy as np
import pandas as pd

from aptrade.intraday.backtest import ExecConfig, run, simulate
from aptrade.config import SESSION_BARS
from aptrade.intraday.sessions import Session, split_sessions
from aptrade.intraday.stats import day_bootstrap_ci, longest_losing_streak, max_drawdown, summarize
from aptrade.intraday.strategy import ORB, Signal

NO_COST = ExecConfig(cost_bps=0.0)


def flat_session(price=100.0, day=date(2026, 1, 5), symbol="TEST"):
    """78 bars at a constant price, range +-0.10 except the first three bars."""
    o = np.full(SESSION_BARS, price)
    h, l, c = o + 0.10, o - 0.10, o.copy()
    h[:3], l[:3] = price + 1.0, price - 1.0          # opening range 99..101, mid 100
    return Session(symbol, day, o.copy(), h, l, c)


def set_bar(s, i, o, h, l, c):
    s.o[i], s.h[i], s.l[i], s.c[i] = o, h, l, c


class TestORB(unittest.TestCase):
    def test_signal_on_first_close_above_range(self):
        s = flat_session()
        set_bar(s, 5, 100.0, 102.2, 99.9, 102.0)
        sig = ORB().signals(s)
        self.assertEqual(len(sig), 1)
        self.assertEqual((sig[0].bar, sig[0].ref_price, sig[0].stop, sig[0].target), (5, 102.0, 100.0, 104.0))

    def test_no_signal_inside_range(self):
        self.assertEqual(ORB().signals(flat_session()), [])

    def test_last_entry_cutoff(self):
        s = flat_session()
        set_bar(s, 40, 100.0, 102.2, 99.9, 102.0)
        self.assertEqual(ORB(last_entry_bar=20).signals(s), [])

    def test_short_side(self):
        s = flat_session()
        set_bar(s, 5, 100.0, 100.1, 97.8, 98.0)
        sig = ORB(side="short").signals(s)[0]
        self.assertEqual((sig.side, sig.stop, sig.target), ("short", 100.0, 96.0))


class TestExecution(unittest.TestCase):
    def sig(self, bar=5):
        return Signal("long", bar, 102.0, 100.0, 104.0)

    def test_target(self):
        s = flat_session(102.0)
        set_bar(s, 8, 102.0, 104.5, 101.9, 104.2)
        t = simulate(self.sig(), s, NO_COST)
        self.assertEqual((t["exit_reason"], t["exit"]), ("target", 104.0))
        self.assertAlmostEqual(t["r_net"], 1.0)

    def test_both_levels_in_one_bar_is_a_stop(self):
        s = flat_session(102.0)
        set_bar(s, 8, 102.0, 104.5, 99.5, 102.0)
        self.assertEqual(simulate(self.sig(), s, NO_COST)["exit_reason"], "stop")

    def test_gap_through_stop_exits_at_open(self):
        s = flat_session(102.0)
        set_bar(s, 8, 98.0, 98.5, 97.5, 98.0)
        t = simulate(self.sig(), s, NO_COST)
        self.assertEqual((t["exit_reason"], t["exit"]), ("stop_gap", 98.0))
        self.assertAlmostEqual(t["r_net"], -2.0)

    def test_open_past_the_stop_fills_then_exits_at_that_open(self):
        """The market order is already sent: a skip would be optimistic."""
        s = flat_session(102.0)
        s.o[6] = 99.0
        t = simulate(self.sig(), s, ExecConfig(cost_bps=10.0))
        self.assertEqual((t["exit_reason"], t["fill"], t["exit"], t["entry_bar"], t["exit_bar"]),
                         ("stop_at_entry", 99.0, 99.0, 6, 6))
        self.assertAlmostEqual(t["r_gross"], 0.0)
        self.assertLess(t["r_net"], 0.0)                    # the round trip still costs

    def test_open_past_the_target_exits_at_that_open(self):
        s = flat_session(102.0)
        s.o[6] = 104.5
        self.assertEqual(simulate(self.sig(), s, NO_COST)["exit_reason"], "target_at_entry")

    def test_flat_at_the_close(self):
        s = flat_session(102.0)
        s.c[SESSION_BARS - 1] = 103.0
        t = simulate(self.sig(), s, NO_COST)
        self.assertEqual(t["exit_reason"], "flat")
        self.assertAlmostEqual(t["r_net"], 0.5)

    def test_slippage_measured_against_planned_risk(self):
        s = flat_session(102.0)
        s.o[6] = 102.5                                  # fills 0.50 worse than planned
        s.c[SESSION_BARS - 1] = 102.5
        t = simulate(self.sig(), s, NO_COST)
        self.assertAlmostEqual(t["r_net"], 0.0)          # flat on the fill...
        self.assertAlmostEqual(t["fill"] - 102.0, 0.5)   # ...but the plan was 102

    def test_costs(self):
        s = flat_session(102.0)
        s.c[SESSION_BARS - 1] = 102.0
        t = simulate(self.sig(), s, ExecConfig(cost_bps=10.0))
        # 10 bps a side on ~102 = about 0.204 per share round trip, on a 2.00 risk
        self.assertAlmostEqual(t["r_net"], -(102 * 0.001 * 2) / 2.0, places=3)

    def test_short_is_symmetric(self):
        s = flat_session(98.0)
        set_bar(s, 8, 98.0, 98.1, 95.5, 96.0)
        t = simulate(Signal("short", 5, 98.0, 100.0, 96.0), s, NO_COST)
        self.assertEqual(t["exit_reason"], "target")
        self.assertAlmostEqual(t["r_net"], 1.0)


class TestSessions(unittest.TestCase):
    def bars(self, day, n=SESSION_BARS, tz_offset_h=5):
        start = pd.Timestamp(f"{day} 09:30") + pd.Timedelta(hours=tz_offset_h)
        idx = pd.date_range(start, periods=n, freq="5min", tz="UTC")
        return pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1}, index=idx)

    def test_full_and_partial_days(self):
        df = pd.concat([self.bars("2026-01-05"), self.bars("2026-01-06", n=42),     # half day
                        self.bars("2026-01-07").drop(self.bars("2026-01-07").index[10])])  # hole
        self.assertEqual([str(s.day) for s in split_sessions(df, "X")], ["2026-01-05"])

    def test_coverage_excludes_patchy_symbols(self):
        from aptrade.intraday.sessions import coverage
        days = [date(2026, 2, 2) + timedelta(days=i) for i in range(20)]
        full = [flat_session(day=d) for d in days]
        by_sym = {"A": full, "B": full, "C": full[:15], "D": []}
        table, kept, cal = coverage(by_sym)
        self.assertEqual(len(cal), 20)
        self.assertEqual(kept, ["A", "B"])
        self.assertAlmostEqual(table.set_index("symbol").loc["C", "coverage"], 0.75)

    def test_daylight_saving(self):
        df = pd.concat([self.bars("2026-01-05", tz_offset_h=5), self.bars("2026-07-06", tz_offset_h=4)])
        self.assertEqual(len(split_sessions(df, "X")), 2)


class TestStats(unittest.TestCase):
    def test_drawdown_and_streak(self):
        r = np.array([1, -1, -1, -1, 1, 1, -1])
        self.assertEqual(max_drawdown(r), 3.0)
        self.assertEqual(longest_losing_streak(r), 3)

    def test_bootstrap_ci_brackets_the_mean(self):
        rng = np.random.default_rng(0)
        days = [date(2025, 1, 1) + timedelta(days=i) for i in range(200)]
        t = pd.DataFrame({"day": np.repeat(days, 3), "r_net": rng.normal(0.2, 1.0, 600)})
        lo, hi = day_bootstrap_ci(t)
        self.assertLess(lo, t["r_net"].mean())
        self.assertGreater(hi, t["r_net"].mean())

    def test_correlated_days_widen_the_interval(self):
        """Ten identical trades per day are one observation, not ten."""
        rng = np.random.default_rng(1)
        days = [date(2025, 1, 1) + timedelta(days=i) for i in range(100)]
        daily = rng.normal(0, 1.0, 100)
        t = pd.DataFrame({"day": np.repeat(days, 10), "r_net": np.repeat(daily, 10)})
        lo, hi = day_bootstrap_ci(t)
        naive = 2 * 1.96 * t["r_net"].std() / np.sqrt(len(t))
        self.assertGreater(hi - lo, 2 * naive)

    def test_verdict_needs_enough_trades(self):
        t = pd.DataFrame({"symbol": "X", "day": [date(2025, 1, i + 1) for i in range(20)], "r_net": 1.0,
                          "r_gross": 1.0, "risk_pct": 1.0, "exit_reason": "target"})
        self.assertTrue(summarize(t)["verdict"].startswith("INCONCLUSIVE"))


class TestRun(unittest.TestCase):
    def test_counts_skips(self):
        s = flat_session()
        set_bar(s, SESSION_BARS - 1, 100.0, 102.2, 99.9, 102.0)   # signal on the last bar
        trades, c = run([s], ORB(), NO_COST)
        self.assertEqual((c["signals"], c["trades"], c.get("skipped_no_bar_left")), (1, 0, 1))


if __name__ == "__main__":
    unittest.main()
