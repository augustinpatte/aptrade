"""The broker APtrade manages an account at. Today: Alpaca (US), paper and live.

Adding a broker means one adapter with the surface described in base.py, tested on a
real paper account before it is published: the planner, the risk checks and the
executor do not change."""
from __future__ import annotations

import os

from .base import BrokerError

NAMES = ("alpaca",)


def name() -> str:
    n = (os.environ.get("APTRADE_BROKER") or "alpaca").strip().lower()
    if n not in NAMES:
        raise BrokerError(f"APTRADE_BROKER must be one of {', '.join(NAMES)}, not {n!r}")
    return n


def get_broker(live: bool, symbols=(), data_dir="data"):
    name()
    from .alpaca import AlpacaBroker
    return AlpacaBroker(live=live)
