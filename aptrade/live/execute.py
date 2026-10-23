"""Execute a plan: risk checks, the human gate for live money, idempotent orders.

The human gate. For a live plan, a fresh 6-digit code is written to the controlling
terminal (/dev/tty) and must be typed back there. An AI agent running commands reads
stdout and stderr, not /dev/tty, and cannot type into it: it can prepare a live plan,
it cannot approve one. When there is no terminal at all (a scheduled job, a sandbox),
live execution is refused.

What this does NOT protect against: an agent deliberately ignoring its instructions and
calling the broker directly with keys it can read. Keep live keys on a machine where
agents ask before running commands, and see SECURITY in the README."""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timezone

from . import risk


class ExecutionRefused(RuntimeError):
    pass


def human_confirms(plan: dict, tty_path: str = "/dev/tty") -> bool:
    """Ask the human, on the terminal itself, to type a code shown only there."""
    code = f"{secrets.randbelow(10**6):06d}"
    try:
        with open(tty_path, "r+") as tty:
            tty.write("\n" + "=" * 64 + "\n")
            tty.write(f"  APtrade LIVE: {len(plan['orders'])} orders, sell {plan['totals']['sell']:,.2f} $, "
                      f"buy {plan['totals']['buy']:,.2f} $\n")
            for o in plan["orders"]:
                amt = f"{o['qty']} sh" if o["qty"] is not None else f"{o['notional']:,.2f} $"
                tty.write(f"    {o['side'].upper():4s} {o['symbol']:6s} {amt:>14s}   "
                          f"{o['current_weight_pct']:5.1f}% -> {o['target_weight_pct']:5.1f}%\n")
            tty.write(f"  Real money. To execute, type this code: {code}\n  > ")
            tty.flush()
            answer = tty.readline().strip()
    except OSError:
        raise ExecutionRefused("live execution needs a human at a real terminal (no /dev/tty here). "
                               "Run `aptrade live execute` yourself in your Terminal.")
    return answer == code


OPEN_STATUSES = ("new", "accepted", "pending_new", "partially_filled", "accepted_for_bidding")


def client_id(plan: dict, i: int) -> str:
    return f"apt-{plan['id']}-{i:02d}"


def execute(plan: dict, broker, data_dir, executed_today: int, confirm=human_confirms,
            wait_seconds: float = 60.0, poll: float = 1.0) -> dict:
    if plan["mode"] != broker.mode:
        raise ExecutionRefused(f"plan was built for {plan['mode']}, broker is {broker.mode}")
    chk = risk.check(plan, data_dir, broker.is_open([o["symbol"] for o in plan["orders"]] or None), executed_today)
    if not chk["ok"]:
        raise ExecutionRefused("; ".join(chk["blocks"]))
    if not plan["orders"]:
        return {"plan": plan["id"], "results": [], "note": "nothing to do: every line is within its band"}
    if plan["mode"] == "live" and not confirm(plan):
        raise ExecutionRefused("wrong or missing confirmation code: nothing was sent")

    results = []
    for i, o in enumerate(plan["orders"]):
        cid = client_id(plan, i)
        existing = broker.find(cid)
        if existing:                                   # already sent (a retry after a crash): never twice
            results.append({**existing, "note": "already submitted"})
            continue
        try:
            r = broker.submit(o["symbol"], o["side"], cid, notional=o.get("notional"), qty=o.get("qty"))
        except Exception as exc:                       # one failure stops the plan: no half-guessed state
            results.append({"client_id": cid, "symbol": o["symbol"], "side": o["side"], "status": "error",
                            "error": str(exc)})
            break
        if o["side"] == "sell":                        # buys wait until sales are filled
            deadline = time.monotonic() + wait_seconds
            while r["status"] not in ("filled", "rejected", "canceled", "expired") and time.monotonic() < deadline:
                time.sleep(poll)
                r = broker.order(r["id"])
            if r["status"] != "filled":
                results.append(r)
                break
        results.append(r)
        if r["status"] in ("rejected", "canceled"):
            break
    # Buys are not waited on one by one; give them a short moment so the report shows fills.
    deadline = time.monotonic() + wait_seconds / 2
    for i, r in enumerate(results):
        while (r.get("id") and r.get("status") in OPEN_STATUSES and time.monotonic() < deadline):
            time.sleep(poll)
            r = results[i] = {**broker.order(r["id"]), **({"note": r["note"]} if r.get("note") else {})}
    done = all(r.get("status") in ("filled", "accepted", "new", "pending_new", "partially_filled")
               or r.get("note") == "already submitted" for r in results) and len(results) == len(plan["orders"])
    return {"plan": plan["id"], "mode": plan["mode"], "results": results, "complete": done,
            "finished_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
