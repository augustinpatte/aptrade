"""Opening-range breakout.

The opening range is the high and low of the first N minutes. The signal is the
first 5-minute bar that CLOSES beyond it. Stop at the range's midpoint (or its far
side), target at a multiple of the risk. At most one trade per symbol per day.

With the defaults this is the exact rule of Jakeschincariol/day-trader-skill's
history replay (or_minutes=15, stop_rule="or_mid", target_r=1, long only)."""
from __future__ import annotations

import math

from ..sessions import Session
from .base import Signal, Strategy

STOP_RULES = ("or_mid", "or_far")


def cents_away(x: float, long: bool) -> float:
    """Round a stop to the cent, away from the entry: down for a long, up for a short."""
    c = round(x * 100, 4)
    return (math.floor(c) if long else math.ceil(c)) / 100.0


class ORB(Strategy):
    name = "orb"

    def __init__(self, or_minutes: int = 15, stop_rule: str = "or_mid", target_r: float = 1.0,
                 side: str = "long", last_entry_bar: int | None = None):
        if or_minutes % 5 or not 5 <= or_minutes <= 120:
            raise ValueError("or_minutes must be a multiple of 5 between 5 and 120")
        if stop_rule not in STOP_RULES:
            raise ValueError(f"stop_rule must be one of {STOP_RULES}")
        if side not in ("long", "short", "both"):
            raise ValueError("side must be long, short or both")
        if target_r <= 0:
            raise ValueError("target_r must be positive")
        self.or_minutes, self.stop_rule, self.target_r = or_minutes, stop_rule, target_r
        self.side, self.last_entry_bar = side, last_entry_bar

    def params(self) -> dict:
        return {"or_minutes": self.or_minutes, "stop_rule": self.stop_rule,
                "target_r": self.target_r, "side": self.side, "last_entry_bar": self.last_entry_bar}

    def signals(self, s: Session) -> list[Signal]:
        n = self.or_minutes // 5
        oh, ol = float(s.h[:n].max()), float(s.l[:n].min())
        last = len(s) - 1 if self.last_entry_bar is None else min(self.last_entry_bar, len(s) - 1)
        for i in range(n, last + 1):
            c = s.c[i]
            for side in (("long", "short") if self.side == "both" else (self.side,)):
                if (side == "long" and c > oh) or (side == "short" and c < ol):
                    sig = self._build(side, i, round(float(c), 2), oh, ol)
                    return [sig] if sig else []
        return []

    def _build(self, side: str, i: int, e: float, oh: float, ol: float) -> Signal | None:
        long = side == "long"
        if self.stop_rule == "or_mid":
            stop = cents_away((oh + ol) / 2, long)
        else:
            stop = cents_away(ol if long else oh, long)
        risk = (e - stop) if long else (stop - e)
        if risk <= 0:
            return None
        target = round(e + self.target_r * risk, 2) if long else round(e - self.target_r * risk, 2)
        return Signal(side, i, e, stop, target, {"or_high": oh, "or_low": ol})
