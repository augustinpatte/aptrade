"""`aptrade target ...`, `aptrade live ...` and `aptrade test-portfolio`.

Every command takes --json so an AI agent can read the result reliably."""
from __future__ import annotations

import json
import sys

from .. import store
from . import alerts as alerts_mod
from . import plan as plan_mod
from . import risk
from . import target as target_mod
from ..brokers import get_broker
from ..brokers.base import BrokerError
from .execute import ExecutionRefused, execute


def _out(a, payload: dict, text: str):
    print(json.dumps(payload, indent=1, default=str) if getattr(a, "json", False) else text)


def _broker(a, settings):
    t = target_mod.load(settings.data_dir)
    try:
        return get_broker(a.live, list(t.weights) if t else [], settings.data_dir)
    except BrokerError as exc:
        raise SystemExit(f"error: {exc}")


def _target(settings) -> target_mod.Target:
    t = target_mod.load(settings.data_dir)
    if t is None:
        raise SystemExit("no target yet: aptrade target set --weights SPY=60,IEF=30,GLD=10 (or --alloc 50)")
    return t


def alloc_weights(spy_share: float, settings) -> dict:
    """The app's slider, today: spy_share in SPY, the rest in the 15 ETFs at inverse volatility."""
    from ..swing.custom import load_daily
    from ..swing.panel import build_panel
    from ..swing.strategies import TREND_UNIVERSE, VOL_WINDOW
    bars, _ = load_daily(TREND_UNIVERSE, settings)
    panel = build_panel(bars, sorted(set(TREND_UNIVERSE) | {"SPY", "BIL"}))
    vol = panel.close[TREND_UNIVERSE].pct_change().rolling(VOL_WINDOW).std().iloc[-1]
    inv = 1 / vol
    w = {s: (1 - spy_share) * float(v) for s, v in (inv / inv.sum()).items()}
    w["SPY"] = w.get("SPY", 0.0) + spy_share
    return {s: round(v, 4) for s, v in w.items() if v >= 0.0005}


# ------------------------------------------------------------------ target

def cmd_target_set(a, settings):
    try:
        if a.alloc is not None:
            if not 0 <= a.alloc <= 100:
                raise ValueError("--alloc is the % in SPY, between 0 and 100")
            weights, source = alloc_weights(a.alloc / 100, settings), {"kind": "alloc", "spy_pct": a.alloc}
        elif a.weights:
            weights, source = target_mod.parse_weights(a.weights), {"kind": "custom"}
        else:
            raise ValueError("give --weights SPY=60,IEF=30,GLD=10 or --alloc 50")
        t = target_mod.Target(weights=weights, rebalance=a.rebalance, drift_pts=a.drift, max_capital=a.max_capital,
                              alert_drawdown_pct=a.alert_drawdown, source=source)
    except ValueError as exc:
        raise SystemExit(f"error: {exc}")
    p = target_mod.save(t, settings.data_dir)
    lines = "\n".join(f"  {s:6s} {100 * w:6.2f}%" for s, w in t.weights.items())
    cash = f"\n  cash   {100 * t.cash_weight:6.2f}%" if t.cash_weight > 0.0005 else ""
    cap = f"{t.max_capital:,.0f} $" if t.max_capital else "all of it"
    _out(a, {"saved": str(p), "target": t.to_dict()},
         f"target saved to {p}\n{lines}{cash}\nrebalance {t.rebalance}, band +-{t.drift_pts} pts, "
         f"capital managed: {cap}\nNext: aptrade test-portfolio --weights ... to see its history, "
         f"then aptrade live plan.")


def cmd_target_show(a, settings):
    t = _target(settings)
    lines = [f"  {s:6s} {100 * w:6.2f}%" for s, w in t.weights.items()]
    cap = f"{t.max_capital:,.0f} $" if t.max_capital is not None else "whole account"
    lines.append(f"rebalance {t.rebalance}, band +-{t.drift_pts} pts, capital managed: {cap}, "
                 f"alert at -{t.alert_drawdown_pct}%")
    _out(a, t.to_dict(), "\n".join(lines))


# ------------------------------------------------------------------ live

def cmd_status(a, settings):
    b = _broker(a, settings)
    t = target_mod.load(settings.data_dir)
    acct, pos = b.account(), b.positions()
    _snap(settings, b, acct["equity"])
    payload = {"mode": b.mode, "market_open": b.is_open(), "account": acct, "positions": pos,
               "target": t.to_dict() if t else None, "kill_switch": risk.kill_file(settings.data_dir).exists()}
    c = _ccy(acct)
    payload["broker"] = getattr(b, "name", "alpaca")
    rows = "\n".join(f"  {s:12s} {p['qty']:>12.4f} sh  {p['market_value']:>12,.2f} {c}" for s, p in pos.items())
    _out(a, payload, f"{b.mode.upper()} account ({payload['broker']}): equity {acct['equity']:,.2f} {c}, "
                     f"cash {acct['cash']:,.2f} {c}, "
                     f"market {'open' if payload['market_open'] else 'closed'}\n{rows or '  no positions'}")


def _snap(settings, b, equity: float) -> None:
    try:
        store.record_equity(settings.db_path, getattr(b, "name", "alpaca"), b.mode, equity)
    except Exception:          # bookkeeping only: never block a command on it
        pass


def _ccy(d: dict) -> str:
    return {"USD": "$", "EUR": "EUR", "GBP": "GBP"}.get(str(d.get("currency", "USD")), str(d.get("currency", "")))


def _plan_text(p: dict, chk: dict, hint: bool = True) -> str:
    c = _ccy(p["account"])
    out = [f"PLAN {p['id']} ({p['mode'].upper()}, {p.get('broker', 'alpaca')}), managed capital {p['capital']:,.2f} {c}"]
    for o in p["orders"]:
        amt = f"{o['qty']} sh" if o["qty"] is not None else f"{o['notional']:,.2f} {c}"
        via = f"   via {o['instrument']}" if o.get("instrument") and o["instrument"] != o["symbol"] else ""
        out.append(f"  {o['side'].upper():4s} {o['symbol']:6s} {amt:>14s}  ~{o['notional_est']:>10,.2f} {c}   "
                   f"{o['current_weight_pct']:5.1f}% -> {o['target_weight_pct']:5.1f}%{via}")
    for s in p["skipped"]:
        out.append(f"  skip {s['symbol']:6s} {s['reason']}")
    out.append(f"  totals: sell {p['totals']['sell']:,.2f} {c}, buy {p['totals']['buy']:,.2f} {c}")
    if p.get("buy_scale"):
        out.append(f"  buys scaled to {100 * p['buy_scale']:.1f}% to fit the cash available")
    out += [f"  BLOCK {b}" for b in chk["blocks"]] + [f"  note  {w}" for w in chk["warnings"]]
    if hint and chk["ok"] and p["orders"]:
        cmd = f"aptrade live execute {p['id']}" + (" --live" if p["mode"] == "live" else "")
        out.append(f"Ready. To execute: {cmd}" + ("  (you will type a code shown in your terminal)"
                                                    if p["mode"] == "live" else ""))
    return "\n".join(out)


def cmd_plan(a, settings):
    t = _target(settings)
    b = _broker(a, settings)
    p = plan_mod.build(t, b)
    chk = risk.check(p, settings.data_dir, b.is_open([o["symbol"] for o in p["orders"]] or None), store.executed_today(settings.db_path, b.mode))
    p["risk"] = chk
    store.save_plan(settings.db_path, p)
    _out(a, p, _plan_text(p, chk))


def cmd_execute(a, settings):
    got = store.get_plan(settings.db_path, a.plan_id)
    if got is None:
        raise SystemExit(f"no plan {a.plan_id}: run aptrade live plan first")
    p, status = got
    if status != "planned":
        raise SystemExit(f"plan {a.plan_id} is already {status}: build a new one")
    if p["mode"] != ("live" if a.live else "paper"):
        raise SystemExit(f"plan {a.plan_id} is a {p['mode']} plan: add or remove --live to match")
    b = _broker(a, settings)
    try:
        res = execute(p, b, settings.data_dir, store.executed_today(settings.db_path, b.mode))
    except ExecutionRefused as exc:
        store.set_plan_result(settings.db_path, p["id"], "refused", {"reason": str(exc)})
        raise SystemExit(f"refused: {exc}")
    status = "executed" if res.get("complete") or not res["results"] else "partial"
    store.set_plan_result(settings.db_path, p["id"], status, res)
    rows = "\n".join(f"  {r.get('side', ''):4s} {r.get('symbol', ''):6s} {r.get('status', '')}"
                     + (f"  {r['filled_qty']:.4f} @ {r['filled_avg_price']}" if r.get("filled_avg_price") else "")
                     + (f"  {r['error']}" if r.get("error") else "") for r in res["results"])
    _out(a, {**res, "status": status}, f"{status.upper()} plan {p['id']} ({p['mode']})\n{rows or res.get('note', '')}")


def cmd_run(a, settings):
    """The whole loop in one command: plan, risk check, execution.
    Paper: executes directly (an agent or a schedule may run it).
    Live: shows the plan and asks for a code on the terminal; run it yourself, once a month."""
    t = _target(settings)
    b = _broker(a, settings)
    p = plan_mod.build(t, b)
    chk = risk.check(p, settings.data_dir, b.is_open([o["symbol"] for o in p["orders"]] or None), store.executed_today(settings.db_path, b.mode))
    p["risk"] = chk
    store.save_plan(settings.db_path, p)
    if not a.json:
        print(_plan_text(p, chk, hint=False))
    if not p["orders"]:
        store.set_plan_result(settings.db_path, p["id"], "nothing", {"note": "nothing to do"})
        _out(a, {"plan": public_plan(p), "status": "nothing to do"}, "Nothing to do: every line is within its band.")
        return
    if not chk["ok"]:
        store.set_plan_result(settings.db_path, p["id"], "refused", {"reason": chk["blocks"]})
        _out(a, {"plan": public_plan(p), "status": "refused", "blocks": chk["blocks"]}, "Refused: nothing was sent.")
        raise SystemExit(1)
    a.plan_id = p["id"]
    cmd_execute(a, settings)


def public_plan(p: dict) -> dict:
    return {k: v for k, v in p.items() if k != "account"} | {"equity": p["account"]["equity"]}


def cmd_kill(a, settings):
    f = risk.kill_file(settings.data_dir)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("kill switch: no plan is executed while this file exists\n")
    _out(a, {"kill_switch": True}, f"kill switch ON ({f}). No order will be sent. aptrade live unkill to resume.")


def cmd_unkill(a, settings):
    risk.kill_file(settings.data_dir).unlink(missing_ok=True)
    _out(a, {"kill_switch": False}, "kill switch OFF.")


def cmd_alerts(a, settings):
    t = _target(settings)
    b = _broker(a, settings)
    _snap(settings, b, b.account()["equity"])
    r = alerts_mod.check(t, b, store.last_executed(settings.db_path, b.mode),
                         store.equity_history(settings.db_path, getattr(b, "name", "alpaca"), b.mode))
    lines = "\n".join(f"  {l['symbol']:6s} {l['current_pct']:6.2f}% vs {l['target_pct']:6.2f}%  ({l['drift_pts']:+.2f})"
                      for l in r["lines"])
    msgs = "\n".join(f"  ! {x['message']}" for x in r["alerts"]) or "  no alert"
    _out(a, r, f"{r['mode'].upper()} equity {r['equity']:,.2f}, drawdown {r['drawdown_pct']}%\n{lines}\n{msgs}")


# ------------------------------------------------------------------ research for agents

def cmd_test_portfolio(a, settings):
    from ..swing import metrics
    from ..swing.custom import run_custom
    try:
        w = target_mod.parse_weights(a.weights)
        out = run_custom(w, a.rebalance, settings, a.cost_bps)
    except (ValueError, SystemExit) as exc:
        raise SystemExit(f"error: {exc}")
    r = out["growth"].pct_change().dropna()
    spy = out["spy_growth"].pct_change().dropna()
    windows = {"full": slice(None), "3y": r.index[-min(756, len(r))]}
    res = {}
    for name, w_ in windows.items():
        rr = r if name == "full" else r[r.index >= w_]
        ss = spy if name == "full" else spy[spy.index >= w_]
        res[name] = {"portfolio": metrics.summary(rr), "spy": metrics.summary(ss)}
    payload = {"label": out["label"], "rebalance": a.rebalance, "cost_bps": a.cost_bps, "results": res,
               "costs_pct_per_year": out["cost_pct_year"],
               "warning": "Weights chosen knowing the past look better than they are. Past results do not "
                          "predict future ones."}
    def row(k, s):
        return (f"  {k:10s} {s['total_return_pct']:+8.1f}% total  {s['cagr_pct']:+6.1f}%/yr  "
                f"max drop {s['max_drawdown_pct']:5.1f}%  vol {s['vol_pct']:5.1f}%  Sharpe {s['sharpe']:.2f}")
    text = [out["label"]]
    for name in ("3y", "full"):
        x = res[name]
        text += [f"{'last 3 years' if name == '3y' else 'whole period'} ({x['portfolio']['start']} to {x['portfolio']['end']})",
                 row("portfolio", x["portfolio"]), row("SPY", x["spy"])]
    text.append(payload["warning"])
    _out(a, payload, "\n".join(text))


def add_parsers(sub):
    def j(q):
        q.add_argument("--json", action="store_true", help="machine-readable output for agents")

    def lv(q):
        q.add_argument("--live", action="store_true", help="real money (needs live keys and APTRADE_ALLOW_LIVE=1)")
        j(q)

    t = sub.add_parser("target", help="the portfolio you want APtrade to maintain")
    ts = t.add_subparsers(dest="target_cmd", required=True)
    q = ts.add_parser("set", help="set the target weights")
    q.add_argument("--weights", help="SPY=60,IEF=30,GLD=10 (percent or fractions); the rest stays in cash")
    q.add_argument("--alloc", type=float, help="the app's slider: %% in SPY, the rest diversified (needs data)")
    q.add_argument("--rebalance", choices=["M", "Q", "Y"], default="M")
    q.add_argument("--drift", type=float, default=2.0, help="band in percentage points (default 2)")
    q.add_argument("--max-capital", type=float, help="never manage more than this many dollars")
    q.add_argument("--alert-drawdown", type=float, default=10.0)
    j(q)
    q.set_defaults(func=cmd_target_set)
    q = ts.add_parser("show")
    j(q)
    q.set_defaults(func=cmd_target_show)

    l = sub.add_parser("live", help="manage a real or paper account at Alpaca")
    ls = l.add_subparsers(dest="live_cmd", required=True)
    for name, func, text in (("status", cmd_status, "account, positions, market clock"),
                             ("plan", cmd_plan, "build a rebalancing plan and check its risk"),
                             ("alerts", cmd_alerts, "drift, drawdown, rebalance due")):
        q = ls.add_parser(name, help=text)
        lv(q)
        q.set_defaults(func=func)
    q = ls.add_parser("run", help="plan + risk check + execute in one go (live: you type a code)")
    lv(q)
    q.set_defaults(func=cmd_run)
    q = ls.add_parser("execute", help="execute a plan (live: a human types a code in the terminal)")
    q.add_argument("plan_id")
    lv(q)
    q.set_defaults(func=cmd_execute)
    for name, func in (("kill", cmd_kill), ("unkill", cmd_unkill)):
        q = ls.add_parser(name, help="stop / allow all order sending")
        j(q)
        q.set_defaults(func=func)

    q = sub.add_parser("test-portfolio", help="any weights vs SPY, last 3 years and since 2016")
    q.add_argument("--weights", required=True)
    q.add_argument("--rebalance", choices=["M", "Q", "Y", "none"], default="Q")
    q.add_argument("--cost-bps", type=float, default=3.0)
    j(q)
    q.set_defaults(func=cmd_test_portfolio)
