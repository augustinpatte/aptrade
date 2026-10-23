"""Managing a real account: everything that touches money is tested on a FakeBroker."""
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from aptrade import cli
from aptrade.live import plan as plan_mod
from aptrade.live import risk
from aptrade.live.alerts import check as alerts_check
from aptrade.live.broker import AlpacaBroker, BrokerError, FakeBroker
from aptrade.live.execute import ExecutionRefused, execute, human_confirms
from aptrade.live.target import Target, parse_weights

PRICES = {"SPY": 600.0, "IEF": 95.0, "GLD": 250.0, "QQQ": 520.0, "BRK.A": 700_000.0}


def fake(**kw):
    return FakeBroker(prices=dict(PRICES), **kw)


class TestTarget(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_weights("spy=60, ief=40"), {"SPY": 0.6, "IEF": 0.4})
        self.assertEqual(parse_weights("SPY=0.5"), {"SPY": 0.5})

    def test_no_leverage_and_valid(self):
        with self.assertRaises(ValueError):
            Target({"SPY": 0.8, "IEF": 0.3})
        with self.assertRaises(ValueError):
            Target({"SPY": 0.5}, rebalance="D")
        self.assertAlmostEqual(Target({"SPY": 0.7}).cash_weight, 0.3)


class TestPlan(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def test_first_deployment_from_cash(self):
        b = fake(cash=10_000)
        p = plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), b)
        self.assertEqual([(o["side"], o["symbol"], o["notional"]) for o in p["orders"]],
                         [("buy", "SPY", 6000.0), ("buy", "IEF", 4000.0)])
        self.assertNotIn("code", json.dumps(p))                  # nothing an agent could use to approve
        self.assertTrue(risk.check(p, self.data, True, 0)["ok"])

    def test_within_band_does_nothing(self):
        b = fake(cash=10_000)
        execute(plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), b), b, self.data, 0)
        p = plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), b)
        self.assertEqual(p["orders"], [])
        self.assertTrue(all("within band" in s["reason"] for s in p["skipped"]))

    def test_drift_sells_first_then_buys(self):
        b = fake(cash=10_000)
        execute(plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), b), b, self.data, 0)
        b.prices["SPY"] *= 1.5                                  # SPY rallies: now overweight
        p = plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), b)
        self.assertEqual([o["side"] for o in p["orders"]], ["sell", "buy"])
        res = execute(p, b, self.data, 0)
        self.assertTrue(res["complete"])
        pos = b.positions()
        total = sum(x["market_value"] for x in pos.values()) + b.cash
        self.assertAlmostEqual(pos["SPY"]["market_value"] / total, 0.6, delta=0.01)

    def test_unmanaged_positions_are_never_touched(self):
        b = fake(cash=5_000, holdings={"QQQ": 10})
        p = plan_mod.build(Target({"SPY": 1.0}), b)
        self.assertNotIn("QQQ", [o["symbol"] for o in p["orders"]])
        self.assertEqual(p["unmanaged"], ["QQQ"])
        self.assertLessEqual(p["totals"]["buy"], 5_000)          # only the cash, not the QQQ value
        self.assertTrue(any("left untouched" in w for w in risk.check(p, self.data, True, 0)["warnings"]))

    def test_max_capital(self):
        b = fake(cash=50_000)
        p = plan_mod.build(Target({"SPY": 1.0}, max_capital=1_000), b)
        self.assertEqual(p["totals"]["buy"], 1000.0)

    def test_whole_shares_when_not_fractionable(self):
        b = fake(cash=1_000, non_fractionable={"SPY"})
        p = plan_mod.build(Target({"SPY": 1.0}), b)
        self.assertEqual(p["orders"][0]["qty"], 1.0)              # 1,000 $ buys one 600 $ share
        b2 = fake(cash=500, non_fractionable={"SPY"})
        p2 = plan_mod.build(Target({"SPY": 1.0}), b2)
        self.assertEqual(p2["orders"], [])
        self.assertIn("whole share", p2["skipped"][0]["reason"])

    def test_buys_scaled_to_cash(self):
        # SPY slightly overweight but inside its band (not sold); GLD needs more than the cash
        b = fake(cash=5_000, holdings={"SPY": 8.5})              # 5,100 $ of SPY
        p = plan_mod.build(Target({"SPY": 0.5, "GLD": 0.5}), b)
        self.assertEqual([o["symbol"] for o in p["orders"]], ["GLD"])
        self.assertIsNotNone(p["buy_scale"])
        self.assertLessEqual(p["totals"]["buy"], 5_000)
        self.assertTrue(risk.check(p, Path(self.dir.name), True, 0)["ok"])

    def test_untradable_symbol_blocks(self):
        b = fake(cash=1_000, untradable={"GLD"})
        p = plan_mod.build(Target({"SPY": 0.5, "GLD": 0.5}), b)
        self.assertFalse(risk.check(p, self.data, True, 0)["ok"])


class TestRiskAndExecution(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name)
        self.b = fake(cash=10_000)
        self.p = plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), self.b)

    def tearDown(self):
        self.dir.cleanup()

    def test_market_closed_blocks(self):
        self.b.open_ = False
        with self.assertRaises(ExecutionRefused):
            execute(self.p, self.b, self.data, 0)
        self.assertEqual(self.b.orders, {})

    def test_kill_switch_blocks(self):
        risk.kill_file(self.data).write_text("x")
        with self.assertRaises(ExecutionRefused):
            execute(self.p, self.b, self.data, 0)
        self.assertEqual(self.b.orders, {})

    def test_stale_plan_blocks(self):
        later = datetime.now(timezone.utc) + timedelta(minutes=20)
        self.assertIn("rebuild", " ".join(risk.check(self.p, self.data, True, 0, now=later)["blocks"]))

    def test_paper_needs_no_human(self):
        res = execute(self.p, self.b, self.data, 0, confirm=lambda p: self.fail("asked for paper"))
        self.assertTrue(res["complete"])

    def test_live_refused_without_the_human_code(self):
        self.b.mode = "live"
        p = plan_mod.build(Target({"SPY": 0.6, "IEF": 0.4}), self.b)
        with self.assertRaises(ExecutionRefused):
            execute(p, self.b, self.data, 0, confirm=lambda plan: False)
        self.assertEqual(self.b.orders, {})                      # nothing sent

    def test_live_without_a_terminal_is_refused(self):
        self.b.mode = "live"
        p = plan_mod.build(Target({"SPY": 1.0}), self.b)
        with self.assertRaises(ExecutionRefused) as ctx:
            human_confirms(p, tty_path="/nonexistent/tty")
        self.assertIn("human", str(ctx.exception))

    def test_live_code_must_match(self):
        self.b.mode = "live"
        p = plan_mod.build(Target({"SPY": 1.0}), self.b)
        with tempfile.NamedTemporaryFile("w+") as f:              # a fake terminal that types a wrong code
            f.write("000000\n")
            f.flush()
            with mock.patch("aptrade.live.execute.secrets.randbelow", return_value=123456), \
                    mock.patch("builtins.open", lambda *a, **k: open_real(f.name, "r+")):
                self.assertFalse(human_confirms(p))

    def test_live_daily_limit(self):
        self.b.mode = "live"
        p = plan_mod.build(Target({"SPY": 1.0}), self.b)
        self.assertFalse(risk.check(p, self.data, True, risk.LIMITS["max_live_plans_per_day"])["ok"])

    def test_idempotent_after_a_crash(self):
        first = self.p["orders"][0]
        self.b.submit(first["symbol"], first["side"], f"apt-{self.p['id']}-00", notional=first["notional"])
        res = execute(self.p, self.b, self.data, 0)
        self.assertEqual(res["results"][0]["note"], "already submitted")
        self.assertEqual(len(self.b.orders), 2)                  # SPY once, IEF once

    def test_rejection_stops_the_plan(self):
        self.b.fail_on = {"SPY"}
        res = execute(self.p, self.b, self.data, 0)
        self.assertFalse(res["complete"])
        self.assertEqual([r["symbol"] for r in res["results"]], ["SPY"])     # IEF never sent

    def test_no_short_no_leverage_in_the_fake_broker(self):
        with self.assertRaises(BrokerError):
            self.b.submit("SPY", "sell", "x1", qty=1)
        with self.assertRaises(BrokerError):
            self.b.submit("SPY", "buy", "x2", notional=50_000)


open_real = open


class TestAlerts(unittest.TestCase):
    def test_drift_drawdown_due(self):
        b = fake(cash=0, holdings={"SPY": 10, "IEF": 10}, history=[20_000, 12_000])
        r = alerts_check(Target({"SPY": 0.5, "IEF": 0.5}), b, None)
        kinds = {a["kind"] for a in r["alerts"]}
        self.assertEqual(kinds, {"drift", "drawdown", "rebalance_due"})


class TestLiveCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"APTRADE_DATA_DIR": self.dir.name, "APTRADE_ALLOW_LIVE": "0"})
        self.env.start()
        self.b = fake(cash=10_000)

    def tearDown(self):
        self.env.stop()
        self.dir.cleanup()

    def call(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with mock.patch("aptrade.live.cli.get_broker", lambda live=False, *a, **k: self.b), \
                redirect_stdout(out), redirect_stderr(err):
            try:
                cli.main(list(argv))
            except SystemExit as exc:
                return out.getvalue() + str(exc)
        return out.getvalue()

    def test_paper_cycle_for_an_agent(self):
        self.call("target", "set", "--weights", "SPY=60,IEF=30,GLD=10")
        plan = json.loads(self.call("live", "plan", "--json"))
        self.assertEqual(len(plan["orders"]), 3)
        self.assertTrue(plan["risk"]["ok"])
        res = json.loads(self.call("live", "execute", plan["id"], "--json"))
        self.assertEqual(res["status"], "executed")
        self.assertIn("already executed", self.call("live", "execute", plan["id"]))   # never twice
        alerts = json.loads(self.call("live", "alerts", "--json"))
        self.assertEqual([a for a in alerts["alerts"] if a["kind"] == "drift"], [])

    def test_run_does_everything_on_paper(self):
        self.call("target", "set", "--weights", "SPY=50,IEF=50")
        res = json.loads(self.call("live", "run", "--json"))
        self.assertEqual(res["status"], "executed")
        self.assertEqual(sorted(self.b.holdings), ["IEF", "SPY"])
        again = json.loads(self.call("live", "run", "--json"))
        self.assertEqual(again["status"], "nothing to do")          # within band: no churn

    def test_run_refuses_when_blocked(self):
        self.call("target", "set", "--weights", "SPY=100")
        self.b.open_ = False
        out = self.call("live", "run")
        self.assertIn("Refused", out)
        self.assertEqual(self.b.orders, {})

    def test_run_live_needs_the_human(self):
        self.call("target", "set", "--weights", "SPY=100")
        self.b.mode = "live"
        from aptrade.live.execute import ExecutionRefused

        def refuse(*_a, **_k):
            raise ExecutionRefused("wrong code")
        with mock.patch("aptrade.live.cli.execute", refuse):
            out = self.call("live", "run", "--live")
        self.assertIn("refused", out)
        self.assertEqual(self.b.orders, {})

    def test_unfilled_orders_block_the_next_plan(self):
        """A run interrupted (or sent near the close) leaves orders open: never buy twice."""
        self.call("target", "set", "--weights", "SPY=50,IEF=50")
        self.b.stuck = {"IEF"}
        first = json.loads(self.call("live", "run", "--json"))
        self.assertEqual(first["status"], "executed")
        sent = len(self.b.orders)
        out = self.call("live", "run")
        self.assertIn("still accepted", out)
        self.assertEqual(len(self.b.orders), sent)          # nothing new was sent

    def test_kill_switch_from_the_cli(self):
        self.call("target", "set", "--weights", "SPY=100")
        self.call("live", "kill")
        plan = json.loads(self.call("live", "plan", "--json"))
        self.assertFalse(plan["risk"]["ok"])
        self.assertIn("refused", self.call("live", "execute", plan["id"]))
        self.assertEqual(self.b.orders, {})

    def test_mode_mismatch_refused(self):
        self.call("target", "set", "--weights", "SPY=100")
        plan = json.loads(self.call("live", "plan", "--json"))
        self.assertIn("paper plan", self.call("live", "execute", plan["id"], "--live"))

    def test_live_is_off_by_default(self):
        with mock.patch.dict(os.environ, {"ALPACA_LIVE_API_KEY": "k", "ALPACA_LIVE_SECRET_KEY": "s",
                                          "APTRADE_ALLOW_LIVE": "0"}):
            with self.assertRaises(BrokerError) as ctx:
                AlpacaBroker(live=True)
        self.assertIn("APTRADE_ALLOW_LIVE", str(ctx.exception))

    def test_paper_keys_never_trade_live(self):
        with mock.patch.dict(os.environ, {"ALPACA_API_KEY": "k", "ALPACA_SECRET_KEY": "s", "APTRADE_ALLOW_LIVE": "1",
                                          "ALPACA_LIVE_API_KEY": "", "ALPACA_LIVE_SECRET_KEY": ""}):
            with self.assertRaises(BrokerError):
                AlpacaBroker(live=True)


if __name__ == "__main__":
    unittest.main()


class TestAlpacaAdapter(unittest.TestCase):
    """The Alpaca adapter's mapping, with the SDK client replaced by a stub (no network)."""

    def adapter(self):
        from types import SimpleNamespace as NS
        sent = []

        def order(req):
            sent.append(req)
            return NS(id="1", client_order_id=req.client_order_id, symbol=req.symbol, side=req.side,
                      status=NS(value="accepted"), filled_qty="0", filled_avg_price=None)
        trading = NS(
            get_account=lambda: NS(equity="10500.5", cash="500.25", currency="USD", trading_blocked=False,
                                   account_blocked=False, status="ACTIVE"),
            get_all_positions=lambda: [NS(symbol="SPY", qty="16.5", market_value="9900", current_price="600")],
            get_clock=lambda: NS(is_open=True),
            get_asset=lambda s: NS(tradable=True, fractionable=s != "BRK.A"),
            submit_order=order,
            get_order_by_client_id=lambda cid: (_ for _ in ()).throw(Exception("404")),
        )
        b = object.__new__(AlpacaBroker)
        b.live, b.trading = False, trading
        return b, sent

    def test_mapping(self):
        b, sent = self.adapter()
        self.assertEqual(b.account()["equity"], 10500.5)
        self.assertEqual(b.positions()["SPY"]["qty"], 16.5)
        self.assertTrue(b.is_open())
        self.assertFalse(b.asset("BRK.A")["fractionable"])
        self.assertIsNone(b.find("apt-x-00"))                   # 404 means "never sent"
        r = b.submit("SPY", "buy", "apt-x-00", notional=123.456)
        self.assertEqual((r["status"], r["side"], r["client_id"]), ("accepted", "buy", "apt-x-00"))
        self.assertEqual((sent[0].notional, sent[0].qty, sent[0].time_in_force.value), (123.46, None, "day"))
        b.submit("SPY", "sell", "apt-x-01", qty=1.5)
        self.assertEqual((sent[1].qty, sent[1].notional, sent[1].side.value), (1.5, None, "sell"))
