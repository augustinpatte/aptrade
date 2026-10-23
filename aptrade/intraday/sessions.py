"""Cut a bar series into regular trading sessions (09:30 to 16:00 New York)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from ..config import BAR_MINUTES, NY, OPEN_MIN, SESSION_BARS


@dataclass(frozen=True)
class Session:
    symbol: str
    day: date
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray
    c: np.ndarray

    def __len__(self) -> int:
        return len(self.c)

    @staticmethod
    def clock(i: int) -> str:
        """Start time of bar i, New York, 24h."""
        m = OPEN_MIN + BAR_MINUTES * i
        return f"{m // 60:02d}:{m % 60:02d}"


def split_sessions(df: pd.DataFrame, symbol: str, before: date | None = None) -> list[Session]:
    """Full regular sessions only: exactly 78 five-minute bars, 09:30 to 15:55 starts.
    Half days (early closes) and sessions with a missing bar are dropped, because a
    hole in the bars would silently skip a stop or a target."""
    if df.empty:
        return []
    local = df.tz_convert(NY)
    minutes = local.index.hour * 60 + local.index.minute
    local = local[(minutes >= OPEN_MIN) & (minutes < OPEN_MIN + SESSION_BARS * BAR_MINUTES)]
    out = []
    for day, part in local.groupby(local.index.date):
        if before is not None and day >= before:
            continue
        if len(part) != SESSION_BARS:
            continue
        slots = (part.index.hour * 60 + part.index.minute - OPEN_MIN) // BAR_MINUTES
        if not np.array_equal(np.asarray(slots), np.arange(SESSION_BARS)):
            continue
        out.append(Session(symbol, day,
                           part["open"].to_numpy(float), part["high"].to_numpy(float),
                           part["low"].to_numpy(float), part["close"].to_numpy(float)))
    return out


MIN_COVERAGE = 0.90


def coverage(sessions_by_symbol: dict[str, list[Session]], min_coverage: float = MIN_COVERAGE):
    """Share of the market's full sessions that each symbol actually has.

    The reference calendar is every day on which at least half the symbols have a
    full session: that drops weekends, holidays and half days without needing an
    exchange calendar. A symbol below min_coverage is excluded, because the days it
    is missing are not random (thin trading, halts, data outages) and keeping it
    would quietly select market conditions.

    Returns (table per symbol, kept symbols, reference calendar)."""
    counts: dict = {}
    for sessions in sessions_by_symbol.values():
        for s in sessions:
            counts[s.day] = counts.get(s.day, 0) + 1
    need = max(1, len(sessions_by_symbol) / 2)
    calendar = sorted(d for d, n in counts.items() if n >= need)
    cal = set(calendar)
    rows = []
    for sym, sessions in sessions_by_symbol.items():
        have = sum(1 for s in sessions if s.day in cal)
        cov = have / len(calendar) if calendar else 0.0
        rows.append({"symbol": sym, "full_sessions": have, "expected": len(calendar),
                     "coverage": cov, "kept": cov >= min_coverage})
    table = pd.DataFrame(rows, columns=["symbol", "full_sessions", "expected", "coverage", "kept"])
    kept = table.loc[table["kept"], "symbol"].tolist()
    return table, kept, calendar
