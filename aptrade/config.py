"""Settings, defaults and the test universe."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

NY = "America/New_York"
BAR_MINUTES = 5
OPEN_MIN = 9 * 60 + 30            # 09:30 New York
SESSION_BARS = 78                 # 09:30 to 16:00 in 5-minute bars

# 50 liquid US names and ETFs. This is today's list of winners, so a backtest on it
# carries survivorship bias: the stocks that collapsed over the period are not here.
DEFAULT_UNIVERSE = [
    "SPY", "QQQ", "IWM", "DIA",
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX",
    "ORCL", "CRM", "ADBE", "INTC", "QCOM", "MU", "PLTR", "UBER", "SHOP", "COIN",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "V", "MA",
    "XOM", "CVX", "COP",
    "UNH", "LLY", "JNJ", "PFE", "ABBV", "MRK",
    "WMT", "COST", "HD", "NKE", "MCD", "DIS", "BA", "CAT", "GE",
]


# Hard ceilings. Configuration may set anything BELOW these, never above. They live in
# code, not in a config file, so that raising them takes a commit you can see.
HARD_LIMITS = {
    "risk_pct": 1.0,            # max % of equity at risk per trade
    "daily_loss_pct": 3.0,      # max % of equity lost per day before entries stop
    "max_positions": 5,         # simultaneous positions
    "max_trades_per_day": 10,
}


@dataclass(frozen=True)
class PortfolioConfig:
    capital: float = 5000.0
    risk_pct: float = 0.25           # % of start-of-day equity risked per trade
    daily_loss_pct: float = 1.0      # entries stop once a new loss could exceed this
    max_positions: int = 2
    max_trades_per_day: int = 4

    def __post_init__(self):
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        for key, ceiling in HARD_LIMITS.items():
            value = getattr(self, key)
            if not 0 < value <= ceiling:
                raise ValueError(f"{key}={value} is outside (0, {ceiling}], the hard limit in config.py")


def load_dotenv(path: str | Path = ".env") -> None:
    """Minimal .env reader: KEY=VALUE lines, existing environment variables win."""
    p = Path(path)
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def set_env_values(path: str | Path, values: dict) -> None:
    """Set KEY=VALUE lines in a .env file, keeping every other line as it is."""
    p = Path(path)
    lines = p.read_text().splitlines() if p.is_file() else []
    todo = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in todo:
            lines[i] = f"{key}={todo.pop(key)}"
    lines += [f"{k}={v}" for k, v in todo.items()]
    p.write_text("\n".join(lines) + "\n")
    p.chmod(0o600)


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    secret_key: str | None
    data_dir: Path
    db_path: Path

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        data_dir = Path(os.environ.get("APTRADE_DATA_DIR", "data"))
        return cls(
            api_key=os.environ.get("ALPACA_API_KEY"),
            secret_key=os.environ.get("ALPACA_SECRET_KEY"),
            data_dir=data_dir,
            db_path=Path(os.environ.get("APTRADE_DB", data_dir / "aptrade.db")),
        )
