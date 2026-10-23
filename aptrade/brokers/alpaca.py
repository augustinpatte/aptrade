"""Alpaca (US). Fractional shares, dollar orders, paper and live accounts with separate keys."""
from __future__ import annotations

import os

from .base import BrokerError, live_allowed


class AlpacaBroker:
    """Paper uses ALPACA_API_KEY / ALPACA_SECRET_KEY. Live uses its own pair,
    ALPACA_LIVE_API_KEY / ALPACA_LIVE_SECRET_KEY, AND needs APTRADE_ALLOW_LIVE=1:
    a paper key can never place a real order, and a live key is never used by accident."""

    name = "alpaca"

    def __init__(self, live: bool = False):
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.trading.client import TradingClient

        self.live = live
        if live:
            if not live_allowed():
                raise BrokerError("live trading is off. Set APTRADE_ALLOW_LIVE=1 in .env to allow it.")
            key, sec = os.environ.get("ALPACA_LIVE_API_KEY"), os.environ.get("ALPACA_LIVE_SECRET_KEY")
            if not (key and sec):
                raise BrokerError("ALPACA_LIVE_API_KEY and ALPACA_LIVE_SECRET_KEY are not set (live keys, in .env)")
        else:
            key, sec = os.environ.get("ALPACA_API_KEY"), os.environ.get("ALPACA_SECRET_KEY")
            if not (key and sec):
                raise BrokerError("ALPACA_API_KEY and ALPACA_SECRET_KEY are not set (paper keys, in .env)")
        self.trading = TradingClient(key, sec, paper=not live)
        self.data = StockHistoricalDataClient(key, sec)

    @property
    def mode(self) -> str:
        return "live" if self.live else "paper"

    def account(self) -> dict:
        a = self.trading.get_account()
        return {"equity": float(a.equity), "cash": float(a.cash), "currency": str(a.currency),
                "trading_blocked": bool(a.trading_blocked), "account_blocked": bool(a.account_blocked),
                "status": str(a.status)}

    def positions(self) -> dict:
        return {p.symbol: {"qty": float(p.qty), "market_value": float(p.market_value),
                           "price": float(p.current_price)} for p in self.trading.get_all_positions()}

    def is_open(self, symbols=None) -> bool:
        return bool(self.trading.get_clock().is_open)          # one clock: US regular hours

    def describe(self, symbol: str) -> str:
        return symbol

    def asset(self, symbol: str) -> dict:
        try:
            a = self.trading.get_asset(symbol)
        except Exception:
            return {"tradable": False, "fractionable": False}
        return {"tradable": bool(a.tradable), "fractionable": bool(a.fractionable)}

    def last_price(self, symbol: str) -> float:
        from alpaca.data.requests import StockLatestTradeRequest
        t = self.data.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=symbol))
        return float(t[symbol].price)

    def submit(self, symbol: str, side: str, client_id: str, notional: float | None = None,
               qty: float | None = None) -> dict:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
        req = MarketOrderRequest(symbol=symbol, side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                                 time_in_force=TimeInForce.DAY, client_order_id=client_id,
                                 notional=round(notional, 2) if notional is not None else None,
                                 qty=qty if notional is None else None)
        return self._order(self.trading.submit_order(req))

    def find(self, client_id: str) -> dict | None:
        try:
            return self._order(self.trading.get_order_by_client_id(client_id))
        except Exception:
            return None

    def order(self, order_id: str) -> dict:
        return self._order(self.trading.get_order_by_id(order_id))

    def open_orders(self) -> list:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
        return [self._order(o) for o in self.trading.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))]

    def equity_history(self) -> list:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        h = self.trading.get_portfolio_history(GetPortfolioHistoryRequest(period="1A", timeframe="1D"))
        return [float(x) for x in (h.equity or []) if x]

    @staticmethod
    def _order(o) -> dict:
        return {"id": str(o.id), "client_id": o.client_order_id, "symbol": o.symbol, "side": str(o.side.value),
                "status": str(o.status.value), "filled_qty": float(o.filled_qty or 0),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None}
