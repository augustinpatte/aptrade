"""Daily bars of many ETFs aligned on one calendar."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import NY

BENCHMARK = "SPY"
CASH = "BIL"


@dataclass
class Panel:
    open: pd.DataFrame       # index: trading dates (datetime64, New York), columns: symbols
    close: pd.DataFrame
    filled: dict             # symbol -> number of days forward-filled (missing bars)

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.close.index

    def truncate(self, before_date) -> "Panel":
        """Only dates strictly before `before_date`: research never sees the holdout."""
        keep = self.close.index < pd.Timestamp(before_date)
        return Panel(self.open[keep], self.close[keep], self.filled)


def build_panel(bars: dict[str, pd.DataFrame], symbols: list[str], max_fill_pct: float = 1.0,
                trim_start: bool = False) -> Panel:
    """Align daily bars on the benchmark's calendar. A missing day is forward-filled
    (no trade possible: open = previous close). A symbol missing more than
    max_fill_pct % of days is an error, not something to paper over.
    trim_start: start the calendar at the youngest symbol's first day instead of
    refusing (for user portfolios with recently launched ETFs)."""
    if BENCHMARK not in bars:
        raise ValueError(f"{BENCHMARK} is required: it defines the calendar and the benchmark")
    def local_dates(df):
        idx = df.index.tz_convert(NY) if df.index.tz is not None else df.index
        return pd.DatetimeIndex(idx.date)
    cal = pd.DatetimeIndex(sorted(set(local_dates(bars[BENCHMARK]))))
    if trim_start:
        missing = [s for s in symbols if s not in bars or bars[s].empty]
        if missing:
            raise ValueError(f"no daily bars for {', '.join(missing)}")
        first = max(local_dates(bars[s]).min() for s in symbols)
        cal = cal[cal >= first]
    opens, closes, filled = {}, {}, {}
    for s in symbols:
        if s not in bars or bars[s].empty:
            raise ValueError(f"no daily bars for {s}")
        df = bars[s].copy()
        df.index = local_dates(df)
        df = df[~df.index.duplicated(keep="last")].reindex(cal)
        first = df["close"].first_valid_index()
        if first is None or first > cal[0]:
            raise ValueError(f"{s} starts on {first}, after the first day {cal[0].date()}")
        missing = int(df["close"].isna().sum())
        if 100 * missing / len(cal) > max_fill_pct:
            raise ValueError(f"{s} is missing {missing} of {len(cal)} days")
        filled[s] = missing
        c = df["close"].ffill()
        o = df["open"].where(df["open"].notna(), c)
        opens[s], closes[s] = o, c
    return Panel(pd.DataFrame(opens), pd.DataFrame(closes), filled)
