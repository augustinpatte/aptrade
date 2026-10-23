"""Bar-by-bar simulator. Turns signals into trades under an explicit execution model.

Two execution models:

  next_open (default, realistic)
      You see the signal bar close and send a market order with a bracket (stop
      and target attached). It fills at the NEXT bar's open, plus costs. If that
      open is already past the stop or the target, the order is already in the
      market: you are filled, the bracket leg triggers at once and you are out at
      the same open, paying the round trip. A bar that opens past the stop later
      exits at that open, not at the stop: gaps hurt.

  close (parity with the original repo)
      Fill at the signal bar's close, exits exactly at the stop and target levels,
      no costs. Optimistic: nobody fills at the close of the bar that told them to buy.

In both models, a bar that touches the stop and the target counts as the stop
(the bars cannot tell which came first, so assume the worst).

R is measured in the PLANNED risk per share (signal price to stop), because that is
what the position is sized on. Slippage therefore shows up as a worse R."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import pandas as pd

from ..config import SESSION_BARS
from .sessions import Session
from .strategy import Signal, Strategy


@dataclass(frozen=True)
class ExecConfig:
    fill: str = "next_open"          # "next_open" or "close"
    cost_bps: float = 3.0            # per side: half the spread plus slippage, in basis points
    commission_per_share: float = 0.0
    flat_bar: int = SESSION_BARS - 1  # exit at this bar's close if still open (77 = 16:00)
    gap_fills: bool = True           # a bar opening past a level fills at the open
    round_r: int | None = None       # parity mode rounds R like the original (2 decimals)

    @classmethod
    def parity(cls) -> "ExecConfig":
        return cls(fill="close", cost_bps=0.0, gap_fills=False, round_r=2)


def simulate(sig: Signal, s: Session, cfg: ExecConfig) -> dict | None | str:
    """One signal on one session. Returns a trade dict, or a skip reason (str)."""
    long = sig.side == "long"
    sign = 1.0 if long else -1.0
    risk = sig.risk

    if cfg.fill == "close":
        fill, start = sig.ref_price, sig.bar + 1
    else:
        k = sig.bar + 1
        if k > cfg.flat_bar:
            return "no_bar_left"
        fill = float(s.o[k])
        start = k

    exit_px, reason, exit_bar = None, "flat", cfg.flat_bar
    if cfg.fill == "next_open":
        # the bracket is live from the fill: an open already past a level exits right there
        if (long and fill <= sig.stop) or (not long and fill >= sig.stop):
            exit_px, reason, exit_bar = fill, "stop_at_entry", start
        elif (long and fill >= sig.target) or (not long and fill <= sig.target):
            exit_px, reason, exit_bar = fill, "target_at_entry", start
    for j in range(start, cfg.flat_bar + 1):
        if exit_px is not None:
            break
        o, h, l = float(s.o[j]), float(s.h[j]), float(s.l[j])
        fresh_bar = not (cfg.fill == "next_open" and j == start)   # fill bar's open is the fill
        if cfg.gap_fills and fresh_bar:
            if (long and o <= sig.stop) or (not long and o >= sig.stop):
                exit_px, reason, exit_bar = o, "stop_gap", j
                break
            if (long and o >= sig.target) or (not long and o <= sig.target):
                exit_px, reason, exit_bar = o, "target_gap", j
                break
        if (long and l <= sig.stop) or (not long and h >= sig.stop):
            exit_px, reason, exit_bar = sig.stop, "stop", j
            break
        if (long and h >= sig.target) or (not long and l <= sig.target):
            exit_px, reason, exit_bar = sig.target, "target", j
            break
    if exit_px is None:
        exit_px = float(s.c[cfg.flat_bar])

    bps = cfg.cost_bps / 10_000
    paid = fill * (1 + sign * bps)          # buying costs more, selling short gets less
    got = exit_px * (1 - sign * bps)
    r_gross = sign * (exit_px - fill) / risk
    r_net = sign * (got - paid) / risk - 2 * cfg.commission_per_share / risk
    if cfg.round_r is not None:
        r_gross = round(r_gross, cfg.round_r)
        r_net = round(r_net, cfg.round_r)
    return {
        "symbol": s.symbol, "day": s.day, "side": sig.side,
        "entry_bar": start, "exit_bar": exit_bar,
        "signal_time": Session.clock(sig.bar + 1),   # the signal bar's close
        "ref_price": sig.ref_price, "fill": round(fill, 4), "stop": sig.stop, "target": sig.target,
        "exit": round(exit_px, 4), "exit_reason": reason, "exit_time": Session.clock(exit_bar + 1),
        "risk_ps": round(risk, 4), "risk_pct": round(100 * risk / sig.ref_price, 3),
        "r_gross": r_gross, "r_net": r_net,
    }


def run(sessions: list[Session], strategy: Strategy, cfg: ExecConfig) -> tuple[pd.DataFrame, dict]:
    """Every signal of the strategy on every session. Returns (trades, counters)."""
    rows, counters = [], {"sessions": len(sessions), "signals": 0}
    for s in sessions:
        for sig in strategy.signals(s):
            counters["signals"] += 1
            out = simulate(sig, s, cfg)
            if isinstance(out, str):
                counters[f"skipped_{out}"] = counters.get(f"skipped_{out}", 0) + 1
            else:
                rows.append(out)
    trades = pd.DataFrame(rows)
    if not trades.empty:
        trades = trades.sort_values(["day", "signal_time", "symbol"]).reset_index(drop=True)
    counters["trades"] = len(trades)
    counters["exec"] = asdict(cfg)
    return trades, counters
