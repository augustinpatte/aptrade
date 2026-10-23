"""Turn a target and the current account into a list of orders.

Only the symbols in the target are managed. Their current value plus the account's
cash is the managed capital (capped by target.max_capital). Each line is brought back
to its weight when it drifts more than target.drift_pts points away, or when it is new.
Sales come first; buys are scaled down if cash plus sales would not cover them."""
from __future__ import annotations

import math
import secrets
from datetime import datetime, timezone

from .target import Target


def build(target: Target, broker) -> dict:
    acct = broker.account()
    pos = broker.positions()
    # Orders sent earlier but not filled yet are invisible in positions: planning on top of
    # them would buy twice (e.g. a run interrupted, or orders sent just before the close).
    pending = [o for o in broker.open_orders() if o["symbol"] in target.weights]
    managed = {s: pos[s]["market_value"] for s in target.weights if s in pos}
    unmanaged = sorted(s for s in pos if s not in target.weights)
    capital = sum(managed.values()) + acct["cash"]
    if target.max_capital is not None:
        capital = min(capital, target.max_capital)

    orders, skipped = [], []
    for sym, w in target.weights.items():
        info = broker.asset(sym)
        if not info["tradable"]:
            skipped.append({"symbol": sym, "reason": "not tradable",
                            "detail": info.get("reason") or "the broker does not offer it"})
            continue
        price = pos[sym]["price"] if sym in pos else broker.last_price(sym)
        current = managed.get(sym, 0.0)
        want = w * capital
        diff = want - current
        cur_w = 100 * current / capital if capital else 0.0
        if current > 0 and abs(100 * diff / capital) < target.drift_pts:
            skipped.append({"symbol": sym, "reason": f"within band ({cur_w:.1f}% vs {100 * w:.1f}%)"})
            continue
        if abs(diff) < target.min_order_usd:
            skipped.append({"symbol": sym, "reason": f"order under {target.min_order_usd:.0f} (account currency)"})
            continue
        side = "buy" if diff > 0 else "sell"
        o = {"symbol": sym, "side": side, "target_weight_pct": round(100 * w, 2),
             "current_weight_pct": round(cur_w, 2), "price_est": round(price, 4), "tradable": True,
             "fractionable": info["fractionable"], "instrument": info.get("label", sym)}
        if side == "sell":
            held = pos[sym]["qty"]
            q = abs(diff) / price
            q = min(held, round(q, 6) if info["fractionable"] else math.floor(q))
            if q <= 0:
                skipped.append({"symbol": sym, "reason": "less than one whole share to sell"})
                continue
            o.update(qty=q, notional=None, notional_est=round(q * price, 2))
        else:
            if info["fractionable"]:
                o.update(qty=None, notional=round(diff, 2), notional_est=round(diff, 2))
            else:
                q = math.floor(diff / price)
                if q < 1:
                    skipped.append({"symbol": sym, "reason": "less than one whole share to buy (not fractionable)"})
                    continue
                o.update(qty=float(q), notional=None, notional_est=round(q * price, 2))
        orders.append(o)

    sells = [o for o in orders if o["side"] == "sell"]
    buys = [o for o in orders if o["side"] == "buy"]
    available = acct["cash"] + sum(o["notional_est"] for o in sells)
    need = sum(o["notional_est"] for o in buys)
    scaled = None
    if need > available and need > 0:
        scaled = available / need * 0.995            # a small margin for price moves
        kept = []
        for o in buys:
            if o["notional"] is not None:
                o["notional"] = o["notional_est"] = round(o["notional"] * scaled, 2)
            else:
                o["qty"] = float(math.floor(o["qty"] * scaled))
                o["notional_est"] = round(o["qty"] * o["price_est"], 2)
            if o["notional_est"] >= target.min_order_usd and (o["qty"] is None or o["qty"] >= 1):
                kept.append(o)
            else:
                skipped.append({"symbol": o["symbol"], "reason": "dropped after scaling buys to the cash available"})
        buys = kept

    return {
        "id": secrets.token_hex(4),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": broker.mode,
        "broker": getattr(broker, "name", "alpaca"),
        "account": acct, "capital": round(capital, 2), "target": target.to_dict(),
        "orders": sells + buys, "skipped": skipped, "unmanaged": unmanaged, "buy_scale": scaled,
        "open_orders": [{"symbol": o["symbol"], "side": o["side"], "status": o["status"]} for o in pending],
        "totals": {"sell": round(sum(o["notional_est"] for o in sells), 2),
                   "buy": round(sum(o["notional_est"] for o in buys), 2)},
    }
