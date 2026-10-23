"""Parity with Jakeschincariol/day-trader-skill: same data, same rule, same numbers.

The fixture is that repo's TSLA 5-minute bars (60 days to 2026-10-19), MIT licensed.
Its history replay reports 59 sessions, 33 trades: 13 targets, 15 stops, 5 open
at the close, average -0.062R. If aptrade reproduces that in parity mode, the
engine is right; the realistic mode then only changes the execution assumptions."""
import unittest
from datetime import date
from pathlib import Path

from aptrade.intraday.backtest import ExecConfig, run
from aptrade.data import load_yahoo_chart
from aptrade.intraday.sessions import split_sessions
from aptrade.intraday.stats import summarize
from aptrade.intraday.strategy import ORB

FIX = Path(__file__).parent / "fixtures" / "TSLA-60d5m.json.gz"


class TestParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = split_sessions(load_yahoo_chart(FIX), "TSLA", before=date(2026, 10, 19))

    def test_sessions(self):
        self.assertEqual(len(self.sessions), 59)
        self.assertEqual(str(self.sessions[0].day), "2026-07-27")
        self.assertEqual(str(self.sessions[-1].day), "2026-10-16")

    def test_original_numbers(self):
        trades, c = run(self.sessions, ORB(), ExecConfig.parity())
        self.assertEqual(c["trades"], 33)
        reasons = trades["exit_reason"].value_counts().to_dict()
        self.assertEqual(reasons, {"stop": 15, "target": 13, "flat": 5})
        self.assertAlmostEqual(round(trades["r_gross"].mean(), 3), -0.062)
        first = trades.iloc[0]
        self.assertEqual((str(first["day"]), first["signal_time"], first["ref_price"], first["stop"],
                          first["target"]), ("2026-07-28", "11:50", 307.97, 304.89, 311.05))

    def test_realistic_is_worse(self):
        par = summarize(run(self.sessions, ORB(), ExecConfig.parity())[0])
        real = summarize(run(self.sessions, ORB(), ExecConfig())[0])
        self.assertLess(real["avg_r_net"], par["avg_r_net"])


if __name__ == "__main__":
    unittest.main()
