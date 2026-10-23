"""What every broker adapter must provide. The planner, the risk checks and the executor
only use this surface, so the safety logic is written and tested once.

  mode ("paper" | "live"), name
  account()                        -> {equity, cash, currency, trading_blocked, account_blocked, status}
  asset(symbol)                    -> {tradable, fractionable}
  positions()                      -> {symbol: {qty, market_value, price}}
  is_open(symbols=None)            -> True only during regular hours for those symbols
  last_price(symbol)               -> float, in the account currency
  submit(symbol, side, client_id, notional=None, qty=None) -> order
  find(client_id) / order(id)      -> order or None
  open_orders()                    -> [order]
  equity_history()                 -> [float] (may be empty)
  describe(symbol)                 -> what is actually traded for that symbol
An order is {id, client_id, symbol, side, status, filled_qty, filled_avg_price},
with status normalised to: pending_new, new, accepted, partially_filled, filled,
canceled, rejected, expired."""
from __future__ import annotations

import os

TERMINAL = ("filled", "canceled", "rejected", "expired")


class BrokerError(RuntimeError):
    pass


def live_allowed() -> bool:
    return os.environ.get("APTRADE_ALLOW_LIVE") == "1"


def require_live_switch():
    if not live_allowed():
        raise BrokerError("live trading is off. Set APTRADE_ALLOW_LIVE=1 in .env to allow it.")


def need(*names: str) -> list[str]:
    vals = [os.environ.get(n) for n in names]
    if not all(vals):
        raise BrokerError(f"{' and '.join(names)} must be set in .env")
    return vals
