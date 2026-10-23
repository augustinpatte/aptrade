"""An in-memory account for tests and demos."""
from __future__ import annotations

from dataclasses import dataclass, field

from .base import BrokerError


@dataclass
class FakeBroker:
    """An in-memory account: market orders fill at once at the given prices."""
    prices: dict
    cash: float = 10_000.0
    holdings: dict = field(default_factory=dict)          # symbol -> qty
    open_: bool = True
    non_fractionable: set = field(default_factory=set)
    untradable: set = field(default_factory=set)
    history: list = field(default_factory=list)
    orders: dict = field(default_factory=dict)
    fail_on: set = field(default_factory=set)              # symbols whose orders are rejected
    stuck: set = field(default_factory=set)                # symbols whose orders stay open (not filled yet)
    mode: str = "paper"
    name: str = "fake"

    def account(self) -> dict:
        return {"equity": self.cash + sum(q * self.prices[s] for s, q in self.holdings.items()), "cash": self.cash,
                "currency": "USD", "trading_blocked": False, "account_blocked": False, "status": "ACTIVE"}

    def positions(self) -> dict:
        return {s: {"qty": q, "market_value": q * self.prices[s], "price": self.prices[s]}
                for s, q in self.holdings.items() if q}

    def is_open(self, symbols=None) -> bool:
        return self.open_

    def describe(self, symbol: str) -> str:
        return symbol

    def asset(self, symbol: str) -> dict:
        if symbol not in self.prices or symbol in self.untradable:
            return {"tradable": False, "fractionable": False}
        return {"tradable": True, "fractionable": symbol not in self.non_fractionable}

    def last_price(self, symbol: str) -> float:
        return self.prices[symbol]

    def submit(self, symbol, side, client_id, notional=None, qty=None) -> dict:
        if client_id in self.orders:
            raise BrokerError(f"duplicate client_order_id {client_id}")
        if symbol in self.fail_on:
            o = {"id": f"o{len(self.orders)}", "client_id": client_id, "symbol": symbol, "side": side,
                 "status": "rejected", "filled_qty": 0.0, "filled_avg_price": None}
            self.orders[client_id] = o
            return o
        if symbol in self.stuck:
            o = {"id": f"o{len(self.orders)}", "client_id": client_id, "symbol": symbol, "side": side,
                 "status": "accepted", "filled_qty": 0.0, "filled_avg_price": None}
            self.orders[client_id] = o
            return o
        price = self.prices[symbol]
        q = qty if qty is not None else notional / price
        if side == "buy":
            if q * price > self.cash + 1e-6:
                raise BrokerError("insufficient buying power")
            self.cash -= q * price
            self.holdings[symbol] = self.holdings.get(symbol, 0.0) + q
        else:
            have = self.holdings.get(symbol, 0.0)
            if q > have + 1e-9:
                raise BrokerError("cannot sell more than held (no shorting)")
            self.holdings[symbol] = have - q
            self.cash += q * price
        o = {"id": f"o{len(self.orders)}", "client_id": client_id, "symbol": symbol, "side": side,
             "status": "filled", "filled_qty": q, "filled_avg_price": price}
        self.orders[client_id] = o
        return o

    def find(self, client_id: str) -> dict | None:
        return self.orders.get(client_id)

    def order(self, order_id: str) -> dict:
        return next(o for o in self.orders.values() if o["id"] == order_id)

    def open_orders(self) -> list:
        return [o for o in self.orders.values() if o["status"] not in ("filled", "rejected", "canceled", "expired")]

    def equity_history(self) -> list:
        return list(self.history) or [self.account()["equity"]]
