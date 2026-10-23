"""The command line end to end, on the offline fixture instead of Alpaca."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from aptrade.intraday import cli
from aptrade.data import load_yahoo_chart

FIX = Path(__file__).parent / "fixtures" / "TSLA-60d5m.json.gz"


def fake_load_bars(symbols, start, end, settings, feed="sip", refresh=False, timeframe="5m"):
    return {"TSLA": load_yahoo_chart(FIX)}, "fixture"


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict("os.environ", {"APTRADE_DATA_DIR": self.tmp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def call(self, *argv):
        buf = io.StringIO()
        with mock.patch.object(cli, "load_bars", fake_load_bars), redirect_stdout(buf):
            self.assertEqual(cli.main(list(argv)), 0)
        return buf.getvalue()

    def test_backtest_saves_and_shows(self):
        out = self.call("backtest", "--symbols", "TSLA", "--end", "2026-10-19")
        self.assertIn("VERDICT  INCONCLUSIVE", out)
        self.assertIn("saved as run 1", out)
        self.assertIn("backtest", self.call("runs"))
        self.assertIn("RESULT", self.call("show", "1"))

    def test_parity_flag(self):
        out = self.call("backtest", "--symbols", "TSLA", "--parity", "--no-save")
        self.assertIn("avg R, gross      -0.0", out)

    def test_last_entry_parsing(self):
        self.assertEqual(cli._last_entry_bar("09:45"), 2)    # the 09:40 bar closes at 09:45
        self.assertIsNone(cli._last_entry_bar(None))


if __name__ == "__main__":
    unittest.main()
