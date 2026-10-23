"""What deserves the owner's attention: drift from the target, a drop from the peak,
a rebalance that is due. Read-only."""
from __future__ import annotations

from datetime import datetime, timezone

from .target import Target

DUE_DAYS = {"M": 31, "Q": 92, "Y": 366}


def check(target: Target, broker, last_executed_utc: str | None, local_history=None) -> dict:
    acct = broker.account()
    pos = broker.positions()
    capital = sum(pos[s]["market_value"] for s in target.weights if s in pos) + acct["cash"]
    if target.max_capital is not None:
        capital = min(capital, target.max_capital)
    lines, alerts = [], []
    for s, w in target.weights.items():
        cur = 100 * pos.get(s, {}).get("market_value", 0.0) / capital if capital else 0.0
        drift = cur - 100 * w
        lines.append({"symbol": s, "target_pct": round(100 * w, 2), "current_pct": round(cur, 2),
                      "drift_pts": round(drift, 2)})
        if abs(drift) >= target.drift_pts:
            alerts.append({"kind": "drift", "symbol": s,
                           "message": f"{s} is at {cur:.1f}% vs {100 * w:.1f}% target ({drift:+.1f} pts)"})
    hist = broker.equity_history() or list(local_history or [])
    if hist:
        peak, now = max(hist), acct["equity"]
        dd = 100 * (1 - now / peak) if peak > 0 else 0.0
        if dd >= target.alert_drawdown_pct:
            alerts.append({"kind": "drawdown", "message": f"account is {dd:.1f}% below its 12-month peak "
                                                          f"({now:,.0f} vs {peak:,.0f})"})
    else:
        dd = None
    due = True
    if last_executed_utc:
        days = (datetime.now(timezone.utc) - datetime.fromisoformat(last_executed_utc)).days
        due = days >= DUE_DAYS[target.rebalance]
    if due:
        alerts.append({"kind": "rebalance_due", "message": "a rebalance is due (run aptrade live plan)"})
    return {"mode": broker.mode, "equity": round(acct["equity"], 2), "cash": round(acct["cash"], 2),
            "managed_capital": round(capital, 2), "drawdown_pct": round(dd, 2) if dd is not None else None,
            "lines": lines, "alerts": alerts, "last_rebalance_utc": last_executed_utc}
