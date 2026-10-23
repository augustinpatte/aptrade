"""End to end on synthetic markets: the tool must say NO on noise and find a planted edge."""
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

from aptrade.intraday import cli
from aptrade.intraday.backtest import ExecConfig, run
from aptrade.intraday.sessions import split_sessions
from aptrade.intraday.stats import summarize
from aptrade.intraday.strategy import ORB
from aptrade.intraday.validation import walk_forward

from .synthetic import universe

NOISE = universe(8, days=260)
EDGE = universe(8, days=260, drift_after_breakout=0.0006)


def sessions(bars):
    return [s for sym, df in bars.items() for s in split_sessions(df, sym)]


class TestNoiseVsEdge(unittest.TestCase):
    def test_noise_has_no_edge(self):
        s = summarize(run(sessions(NOISE), ORB(), ExecConfig())[0])
        self.assertLess(s["ci95_low"], 0.0)                  # cannot claim an edge
        self.assertLess(s["avg_r_net"], 0.1)
        self.assertFalse(s["verdict"].startswith("CANDIDATE"))

    def test_planted_edge_is_found(self):
        s = summarize(run(sessions(EDGE), ORB(), ExecConfig())[0])
        self.assertGreater(s["ci95_low"], 0.0)
        self.assertTrue(s["verdict"].startswith(("CANDIDATE", "WEAK")), s["verdict"])

    def test_walk_forward_out_of_sample(self):
        noise = walk_forward(sessions(NOISE), ExecConfig())
        edge = walk_forward(sessions(EDGE), ExecConfig())
        self.assertLess(noise["oos_summary"]["ci95_low"], 0.0)
        self.assertGreater(edge["oos_summary"]["avg_r_net"], 0.0)
        self.assertEqual(len(noise["folds"]), 4)
        self.assertIsNotNone(edge["final"])


class TestCommandsEndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict("os.environ", {"APTRADE_DATA_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def call(self, *argv, code=0):
        out, err = io.StringIO(), io.StringIO()
        fake = lambda syms, start, end, settings, feed="sip", refresh=False, timeframe="5m": (NOISE, "synthetic")
        argv = list(argv) + (["--symbols", ",".join(NOISE)] if argv[0] in ("backtest", "sweep", "holdout") else [])
        with mock.patch.object(cli, "load_bars", fake), redirect_stdout(out), redirect_stderr(err):
            try:
                self.assertEqual(cli.main(argv), code)
            except SystemExit as exc:
                return out.getvalue() + str(exc)
        return out.getvalue() + err.getvalue()

    def test_backtest_sweep_holdout(self):
        out = self.call("backtest")
        self.assertIn("holdout locked", out)
        self.assertIn("PORTFOLIO", out)
        self.assertIn("RESEARCH DATA", out)
        out = self.call("sweep")
        self.assertIn("WALK-FORWARD", out)
        self.assertIn("OUT OF SAMPLE", out)
        out = self.call("holdout")
        self.assertIn("HOLDOUT LOOK #1", out)
        self.assertIn("HOLDOUT DATA", out)
        refused = self.call("holdout")
        self.assertIn("already been looked at 1 time", refused)
        self.assertIn("HOLDOUT LOOK #2", self.call("holdout", "--again"))

    def test_research_never_touches_the_holdout(self):
        self.call("backtest", "--no-save")
        from aptrade import store
        from aptrade.config import Settings
        hold = store.get_meta(Settings.from_env().db_path, cli.HOLDOUT_KEY)
        out = self.call("backtest", "--csv", f"{self.tmp.name}/t.csv")
        import pandas as pd
        days = pd.read_csv(f"{self.tmp.name}/t.csv")["day"]
        self.assertLess(days.max(), hold)

    def test_hard_limit_refused(self):
        self.assertIn("hard limit", self.call("backtest", "--risk-pct", "5"))


if __name__ == "__main__":
    unittest.main()
