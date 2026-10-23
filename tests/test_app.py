"""The app, headless (streamlit.testing). Skipped if Streamlit is not installed."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    from streamlit.testing.v1 import AppTest
except ImportError:                      # pragma: no cover
    AppTest = None

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"


def synthetic_results(path: Path):
    from aptrade.export import build
    from aptrade.swing.cli import ALL_SYMBOLS
    from aptrade.swing.panel import build_panel

    from .synthetic_daily import make_daily
    panel = build_panel(make_daily(ALL_SYMBOLS, days=900, kind="trend", seed=4), ALL_SYMBOLS)
    hold = panel.dates[int(len(panel.dates) * 0.8)].date()
    path.write_text(json.dumps(build(panel, str(hold), progress=lambda m: None)))


@unittest.skipIf(AppTest is None, "streamlit not installed")
class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.results = Path(cls.tmp.name) / "results.json"
        synthetic_results(cls.results)
        cls.env = mock.patch.dict(os.environ, {"APTRADE_RESULTS": str(cls.results)})
        cls.env.start()                      # stays on for every rerun inside a test
        if str(APP) not in sys.path:
            sys.path.insert(0, str(APP))

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def page(self, name, env=None, lang="en"):
        with mock.patch.dict(os.environ, env or {}):
            at = AppTest.from_file(str(APP / "views" / f"{name}.py"), default_timeout=60)
            at.session_state["lang"] = lang
            at.run()
        self.assertFalse(at.exception, at.exception)
        return at

    def text(self, at) -> str:
        return " ".join(str(e.value) for e in list(at.markdown) + list(at.caption) + list(at.info)
                        + list(at.warning) + list(at.title))

    def test_home_both_languages(self):
        en = self.text(self.page("home"))
        fr = self.text(self.page("home", lang="fr"))
        self.assertIn("APtrade", en)
        self.assertIn("over the last 3 years", en)
        self.assertIn("Performance sur les 3 dernières années", fr)

    def test_no_fail_banner_on_the_front_pages(self):
        for name in ("home", "research", "profiles"):
            self.assertNotIn("FAIL", self.text(self.page(name)), name)

    def test_profiles_slider_and_windows(self):
        at = self.page("profiles")
        self.assertIn("Growth of", self.text(at))
        at.select_slider[0].set_value(80).run()
        self.assertFalse(at.exception)
        for w in ("full", "holdout", "research", "3y"):
            at.radio[0].set_value(w).run()
            self.assertFalse(at.exception, w)
        at.multiselect[0].set_value(["rotation"]).run()
        self.assertFalse(at.exception)
        self.assertGreaterEqual(len(at.dataframe), 1)            # the monthly heatmap

    def test_profiles_without_results(self):
        at = self.page("profiles", env={"APTRADE_RESULTS": str(Path(self.tmp.name) / "missing.json")})
        self.assertIn("aptrade export", self.text(at))

    def test_every_strategy_page(self):
        at = self.page("research", lang="fr")
        n = len(at.radio[0].options)
        self.assertEqual(n, 6)
        for i in range(n):
            at.radio[0].set_value(i).run()
            self.assertFalse(at.exception, i)
            txt = self.text(at)
            self.assertIn("Points forts", txt)
            self.assertIn("Points faibles", txt)
            self.assertIn("Risque par position", txt)

    def test_method_lists_every_safeguard(self):
        txt = self.text(self.page("method"))
        for word in ("Rules written before the data", "No leverage", "No look-ahead", "Hard limits"):
            self.assertIn(word, txt)

    def test_public_demo_never_asks_for_keys(self):
        for name in ("portfolio", "data"):
            at = self.page(name, env={"APTRADE_PUBLIC_DEMO": "1"})
            self.assertEqual(len(at.text_input), 0, name)

    def test_portfolio_without_keys_points_to_settings(self):
        with mock.patch.dict(os.environ, {"ALPACA_API_KEY": "", "ALPACA_SECRET_KEY": ""}):
            at = self.page("portfolio")
        self.assertIn("Alpaca", self.text(at))
