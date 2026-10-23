"""The portfolio you want: weights, rebalancing rule, caps. Stored in data/target.json."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

REBALANCE = ("M", "Q", "Y")


@dataclass
class Target:
    weights: dict                      # symbol -> fraction of the managed capital; the rest stays in cash
    rebalance: str = "M"               # how often a rebalance is due: monthly, quarterly, yearly
    drift_pts: float = 2.0             # leave a line alone while it is within +-2 points of its target
    max_capital: float | None = None   # never manage more than this many dollars (None: all managed value)
    min_order_usd: float = 5.0         # no order smaller than this
    alert_drawdown_pct: float = 10.0   # alert when the account is this far below its peak
    note: str = ""
    source: dict = field(default_factory=dict)   # how the weights were chosen (alloc slider, custom...)

    def __post_init__(self):
        w = {str(s).upper().strip(): float(v) for s, v in self.weights.items() if float(v) > 0}
        if not w:
            raise ValueError("the target needs at least one symbol with a positive weight")
        total = sum(w.values())
        if total > 1 + 1e-9:
            raise ValueError(f"weights add up to {100 * total:.1f}%: at most 100% (no leverage)")
        if self.rebalance not in REBALANCE:
            raise ValueError(f"rebalance must be one of {REBALANCE}")
        if not 0.5 <= self.drift_pts <= 20:
            raise ValueError("drift_pts must be between 0.5 and 20 percentage points")
        if self.max_capital is not None and self.max_capital <= 0:
            raise ValueError("max_capital must be positive")
        self.weights = dict(sorted(w.items(), key=lambda kv: -kv[1]))

    @property
    def cash_weight(self) -> float:
        return max(0.0, 1.0 - sum(self.weights.values()))

    def to_dict(self) -> dict:
        return asdict(self)


def path(data_dir: Path) -> Path:
    return Path(data_dir) / "target.json"


def save(target: Target, data_dir: Path) -> Path:
    p = path(data_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(target.to_dict(), indent=1))
    return p


def load(data_dir: Path) -> Target | None:
    p = path(data_dir)
    return Target(**json.loads(p.read_text())) if p.is_file() else None


def parse_weights(text: str) -> dict:
    """'SPY=60,IEF=30,GLD=10' or 'SPY=0.6,IEF=0.3' -> {'SPY': 0.6, ...}. Percentages if any value > 1."""
    pairs = [p.split("=") for p in text.replace(" ", "").split(",") if p]
    try:
        raw = {s.upper(): float(v) for s, v in pairs}
    except ValueError:
        raise ValueError("weights look like SPY=60,IEF=30,GLD=10") from None
    if any(v > 1 for v in raw.values()):
        raw = {s: v / 100 for s, v in raw.items()}
    return raw
