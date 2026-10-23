"""Portfolio rules on hand-built candidate trades."""
import unittest
from datetime import date

import pandas as pd

from aptrade.config import PortfolioConfig
from aptrade.intraday.portfolio import equity_stats, simulate_portfolio

D1, D2 = date(2026, 1, 5), date(2026, 1, 6)


def cand(symbol, entry_bar, exit_bar, r_net, risk_ps=1.0, fill=100.0, day=D1):
    return {"symbol": symbol, "day": day, "side": "long", "entry_bar": entry_bar, "exit_bar": exit_bar,
            "fill": fill, "risk_ps": risk_ps, "r_net": r_net, "r_gross": r_net}


def sim(rows, **kw):
    return simulate_portfolio(pd.DataFrame(rows), PortfolioConfig(**kw))


class TestSizing(unittest.TestCase):
    def test_risk_based_size(self):
        led, _, _ = sim([cand("A", 4, 10, 1.0, risk_ps=2.0)], capital=10_000, risk_pct=0.5)
        self.assertEqual(led.iloc[0]["qty"], 25)                 # 50 $ at risk / 2 $ per share
        self.assertAlmostEqual(led.iloc[0]["pnl"], 50.0)         # +1R

    def test_cash_caps_the_size(self):
        led, _, _ = sim([cand("A", 4, 10, 1.0, risk_ps=0.01, fill=100.0)], capital=1_000, risk_pct=1.0)
        led, _, c = sim([cand("A", 4, 10, 1.0, risk_ps=0.01, fill=100.0)], capital=1_000, risk_pct=1.0)
        self.assertEqual(led.iloc[0]["qty"], 10)                 # 1,000 $ buys 10 shares, not 1,000
        self.assertEqual(c["sized_by_cash"], 1)

    def test_tiny_account_cannot_trade(self):
        led, _, c = sim([cand("A", 4, 10, 1.0, risk_ps=5.0)], capital=50, risk_pct=1.0)
        self.assertFalse(led.iloc[0]["taken"])
        self.assertEqual(c["rejected"], {"size_zero": 1})


class TestSlots(unittest.TestCase):
    def test_max_positions(self):
        rows = [cand("A", 4, 30, 1.0), cand("B", 5, 30, 1.0), cand("C", 6, 30, 1.0)]
        led, _, c = sim(rows, capital=100_000, max_positions=2)
        self.assertEqual(list(led["taken"]), [True, True, False])
        self.assertEqual(c["rejected"], {"max_positions": 1})

    def test_exit_frees_the_slot_only_before_the_entry_bar(self):
        rows = [cand("A", 4, 10, 1.0), cand("B", 10, 30, 1.0), cand("C", 11, 30, 1.0)]
        led, _, _ = sim(rows, capital=100_000, max_positions=1)
        self.assertEqual(list(led["taken"]), [True, False, True])   # B enters in A's exit bar: no

    def test_same_bar_ties_go_by_symbol(self):
        led, _, _ = sim([cand("B", 4, 30, 1.0), cand("A", 4, 30, 1.0)], capital=100_000, max_positions=1)
        self.assertEqual(led[led["taken"]]["symbol"].tolist(), ["A"])

    def test_max_trades_per_day(self):
        rows = [cand(s, i, i + 1, 1.0) for i, s in zip(range(4, 20, 3), "ABCDEF")]
        led, _, _ = sim(rows, capital=100_000, max_trades_per_day=3)
        self.assertEqual(int(led["taken"].sum()), 3)


class TestDailyLoss(unittest.TestCase):
    def test_stops_entries_before_the_limit_can_be_breached(self):
        # 10,000 $, 0.5% risk = 50 $ per trade, daily limit 1% = 100 $
        rows = [cand("A", 4, 5, -1.0), cand("B", 6, 7, -1.0), cand("C", 8, 9, 1.0)]
        led, eq, c = sim(rows, capital=10_000, risk_pct=0.5, daily_loss_pct=1.0)
        self.assertEqual(list(led["taken"]), [True, True, False])
        self.assertEqual(c["rejected"], {"daily_loss": 1})
        self.assertAlmostEqual(eq.iloc[0]["pnl"], -100.0)
        self.assertTrue(eq.iloc[0]["hit_daily_limit"])

    def test_open_risk_counts(self):
        # two positions open at once: the second is sized, then the third would breach
        rows = [cand("A", 4, 30, 1.0), cand("B", 5, 30, 1.0), cand("C", 6, 30, 1.0)]
        led, _, _ = sim(rows, capital=10_000, risk_pct=0.5, daily_loss_pct=1.0, max_positions=5)
        self.assertEqual(list(led["taken"]), [True, True, False])

    def test_resets_the_next_day(self):
        rows = [cand("A", 4, 5, -1.0), cand("B", 6, 7, -1.0), cand("C", 4, 5, 1.0, day=D2)]
        led, eq, _ = sim(rows, capital=10_000, risk_pct=0.5, daily_loss_pct=1.0)
        self.assertTrue(led.iloc[2]["taken"])
        self.assertEqual(len(eq), 2)


class TestEquity(unittest.TestCase):
    def test_compounding_and_drawdown(self):
        rows = [cand("A", 4, 5, 2.0), cand("A", 4, 5, -1.0, day=D2)]
        led, eq, _ = sim(rows, capital=10_000, risk_pct=1.0, daily_loss_pct=3.0)
        self.assertAlmostEqual(eq.iloc[0]["end_equity"], 10_200.0)
        self.assertEqual(led.iloc[1]["qty"], 102)               # sized on the new equity
        st = equity_stats(eq, led, 10_000)
        self.assertAlmostEqual(st["end_equity"], 10_098.0)
        self.assertAlmostEqual(st["max_drawdown_pct"], 100 * 102 / 10_200)

    def test_signal_free_days_count(self):
        led, eq, _ = simulate_portfolio(pd.DataFrame([cand("A", 4, 5, 1.0)]), PortfolioConfig(),
                                        all_days=[D1, D2, date(2026, 1, 7)])
        self.assertEqual(len(eq), 3)


class TestHardLimits(unittest.TestCase):
    def test_cannot_exceed(self):
        with self.assertRaises(ValueError):
            PortfolioConfig(risk_pct=2.0)
        with self.assertRaises(ValueError):
            PortfolioConfig(max_positions=50)


if __name__ == "__main__":
    unittest.main()
