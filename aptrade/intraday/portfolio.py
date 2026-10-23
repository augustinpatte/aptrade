"""Chronological portfolio simulation on top of the per-trade results.

backtest.run() answers "what does each signal earn?". This answers "what would an
account have done?": signals compete for a limited number of slots and limited
cash, positions are sized from equity, and a daily loss limit stops new entries.
With 50 symbols and two slots, the account only ever takes the first signals of
the morning, which is not the same population as all signals.

Rules, in the order they are checked for each candidate:

  1. Positions closed before this entry release their cash and book their P&L.
     A position exiting during bar j frees its slot for an entry at the open of
     bar k only if j < k (the entry happens before anything inside bar k).
  2. Slots: no more than max_positions open at once.
  3. Frequency: no more than max_trades_per_day entries.
  4. Size: Q = floor(min(equity * risk_pct / risk_per_share, cash / price)).
     Whole shares only (bracket orders need them). Q = 0 is a rejection.
  5. Daily loss: refuse the entry if, should it and every open position hit their
     stops, the day's loss would exceed daily_loss_pct of start-of-day equity.
     This bounds the loss AT THE STOP PRICES; gaps and slippage can go past it.

Same-time candidates are taken in symbol order: deterministic, and documented as
a bias of its own."""
from __future__ import annotations

import math
from dataclasses import asdict

import numpy as np
import pandas as pd

from ..config import PortfolioConfig


def simulate_portfolio(trades: pd.DataFrame, pcfg: PortfolioConfig,
                       all_days=None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Returns (ledger: every candidate with taken/qty/pnl/reject, daily equity, counters).
    all_days: every trading day of the test, so days without a signal count as flat
    days in the returns (otherwise annualized figures would be inflated)."""
    equity = pcfg.capital
    ledger, days = [], []
    rejects: dict[str, int] = {}
    cash_capped = 0
    t = trades.sort_values(["day", "entry_bar", "symbol"]).reset_index(drop=True) if not trades.empty else trades
    groups = {d: g for d, g in t.groupby("day", sort=True)} if not t.empty else {}
    calendar = sorted(set(all_days or []) | set(groups))

    for day in calendar:
        cands = groups.get(day, t.iloc[0:0] if not t.empty else pd.DataFrame())
        start_equity = equity
        cash = start_equity
        limit = start_equity * pcfg.daily_loss_pct / 100
        realized, entries = 0.0, 0
        open_pos: list[dict] = []          # exit_bar, pnl, notional, risk
        hit_limit = False
        for _, c in cands.iterrows():
            still = []
            for p in open_pos:
                if p["exit_bar"] < c["entry_bar"]:
                    realized += p["pnl"]
                    cash += p["notional"] + p["pnl"]
                else:
                    still.append(p)
            open_pos = still

            reject, qty = None, 0
            if len(open_pos) >= pcfg.max_positions:
                reject = "max_positions"
            elif entries >= pcfg.max_trades_per_day:
                reject = "max_trades_per_day"
            else:
                by_risk = start_equity * pcfg.risk_pct / 100 / c["risk_ps"]
                by_cash = cash / c["fill"]
                qty = int(math.floor(min(by_risk, by_cash)))
                capped = by_cash < by_risk
                if qty < 1:
                    reject, qty = "size_zero", 0
                else:
                    risk_d = qty * c["risk_ps"]
                    open_risk = sum(p["risk"] for p in open_pos)
                    if realized - open_risk - risk_d < -limit:
                        reject, qty = "daily_loss", 0
                        hit_limit = True
            row = c.to_dict()
            if reject:
                rejects[reject] = rejects.get(reject, 0) + 1
                row.update(taken=False, qty=0, pnl=0.0, reject=reject)
            else:
                pnl = float(c["r_net"]) * float(c["risk_ps"]) * qty
                notional = qty * float(c["fill"])
                cash -= notional
                entries += 1
                cash_capped += int(capped)
                open_pos.append({"exit_bar": c["exit_bar"], "pnl": pnl, "notional": notional,
                                 "risk": qty * c["risk_ps"]})
                row.update(taken=True, qty=qty, pnl=pnl, reject=None)
            ledger.append(row)
        realized += sum(p["pnl"] for p in open_pos)     # everything is flat by the close
        equity = start_equity + realized
        days.append({"day": day, "start_equity": start_equity, "pnl": realized, "end_equity": equity,
                     "entries": entries, "hit_daily_limit": hit_limit})

    led = pd.DataFrame(ledger)
    if led.empty:
        led = pd.DataFrame(columns=list(trades.columns) + ["taken", "qty", "pnl", "reject"])
        led["taken"] = led["taken"].astype(bool)
    eq = pd.DataFrame(days)
    counters = {"candidates": len(led), "taken": int(led["taken"].sum()), "rejected": rejects,
                "sized_by_cash": cash_capped,
                "config": asdict(pcfg)}
    return led, eq, counters


def equity_stats(eq: pd.DataFrame, ledger: pd.DataFrame, capital: float) -> dict:
    """Account-level numbers, in dollars and percent. Equity is marked at each close
    only, so intraday drawdowns are not in these figures."""
    if eq.empty:
        return {}
    curve = np.concatenate([[capital], eq["end_equity"].to_numpy()])
    peak = np.maximum.accumulate(curve)
    dd = (peak - curve) / peak
    ret = eq["pnl"] / eq["start_equity"]
    taken = ledger[ledger["taken"]]
    years = max(len(eq) / 252, 1e-9)
    final = float(curve[-1])
    return {
        "start_equity": capital,
        "end_equity": final,
        "total_return_pct": 100 * (final / capital - 1),
        "annualized_return_pct": 100 * ((final / capital) ** (1 / years) - 1) if final > 0 else -100.0,
        "max_drawdown_pct": 100 * float(dd.max()),
        "max_drawdown_usd": float((peak - curve).max()),
        "worst_day_pct": 100 * float(ret.min()),
        "best_day_pct": 100 * float(ret.max()),
        "sharpe_daily_annualized": float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else float("nan"),
        "trading_days": int(len(eq)),
        "days_with_trades": int((eq["entries"] > 0).sum()),
        "days_daily_limit_hit": int(eq["hit_daily_limit"].sum()),
        "trades_taken": int(len(taken)),
        "avg_qty": float(taken["qty"].mean()) if len(taken) else 0.0,
        "avg_notional_pct": float((taken["qty"] * taken["fill"]).mean() / capital * 100) if len(taken) else 0.0,
    }
