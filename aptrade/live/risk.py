"""Risk checks before a plan is executed. The limits are constants in code: no flag,
config file or environment variable can raise them; changing them takes a visible commit."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

LIMITS = {
    "max_orders_per_plan": 30,
    "plan_ttl_minutes": 15,          # prices move: an older plan must be rebuilt
    "max_live_plans_per_day": 2,     # an agent stuck in a loop cannot trade all day
    "max_buys_vs_cash": 1.0,         # buys never exceed cash + sale proceeds: no leverage, ever
}


def kill_file(data_dir: Path) -> Path:
    return Path(data_dir) / "KILL"


def check(plan: dict, data_dir: Path, broker_open: bool, executed_today: int, now: datetime | None = None) -> dict:
    """Returns {'ok': bool, 'blocks': [...], 'warnings': [...]}. Any block stops execution."""
    now = now or datetime.now(timezone.utc)
    blocks, warns = [], []
    if kill_file(data_dir).exists():
        blocks.append("kill switch is on (aptrade live unkill to remove it)")
    acct = plan["account"]
    if acct.get("trading_blocked") or acct.get("account_blocked"):
        blocks.append("the broker reports the account or trading as blocked")
    if not broker_open:
        blocks.append("market is closed: orders are only sent during regular hours")
    if len(plan["orders"]) > LIMITS["max_orders_per_plan"]:
        blocks.append(f"{len(plan['orders'])} orders: more than {LIMITS['max_orders_per_plan']}")
    created = datetime.fromisoformat(plan["created_utc"])
    age = (now - created).total_seconds() / 60
    if age > LIMITS["plan_ttl_minutes"]:
        blocks.append(f"plan is {age:.0f} minutes old: rebuild it (prices have moved)")
    buys = sum(o["notional_est"] for o in plan["orders"] if o["side"] == "buy")
    sells = sum(o["notional_est"] for o in plan["orders"] if o["side"] == "sell")
    if buys > (acct["cash"] + sells) * LIMITS["max_buys_vs_cash"] + 0.01:
        blocks.append(f"buys {buys:,.2f} exceed cash {acct['cash']:,.2f} + sales {sells:,.2f}: no leverage")
    if plan["mode"] == "live" and executed_today >= LIMITS["max_live_plans_per_day"]:
        blocks.append(f"{executed_today} live plans already executed today (limit {LIMITS['max_live_plans_per_day']})")
    for o in plan.get("open_orders", []):
        blocks.append(f"{o['side']} {o['symbol']} from an earlier plan is still {o['status']}: "
                      "wait for it to fill (aptrade live status) or cancel it at Alpaca, then rerun")
    for o in plan["orders"]:
        if not o.get("tradable", True):
            blocks.append(f"{o['symbol']} is not tradable at this broker")
    for s in plan.get("skipped", []):
        if s.get("reason") == "not tradable":
            blocks.append(f"{s['symbol']} is in the target but not tradable: {s.get('detail', 'not offered')}")
    if plan.get("unmanaged"):
        warns.append("left untouched (not in the target): " + ", ".join(sorted(plan["unmanaged"])))
    if plan["mode"] == "live":
        warns.append("LIVE: real money. Market orders fill at the market price, which can differ from the estimate.")
    return {"ok": not blocks, "blocks": blocks, "warnings": warns}
