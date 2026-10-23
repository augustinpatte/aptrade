---
name: aptrade-risk
description: >-
  Explain and enforce APtrade's risk limits before any order: market hours, kill switch, plan age, number of orders, no leverage, tradable symbols, daily limit on live plans, untouched non-target holdings. Use when the user asks "is this safe", "what are the limits", "stop everything", "kill switch", "why was my order blocked", or before every execution.
---

# aptrade-risk

The gate between a plan and the broker. A block is final: never work around it.

## Setup (once)

APtrade is a Python tool. Check it is installed with `aptrade --help`. If not:

```bash
git clone https://github.com/augustinpatte/aptrade.git && cd aptrade
python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

If `aptrade` is not on PATH, call it as `<repo>/.venv/bin/aptrade`. Commands that read
market data or an account need the user's own Alpaca keys in `<repo>/.env` (see
`.env.example`). **Never ask the user to paste a key or secret in the chat**: tell them
to put it in `.env` themselves, or to use the app's Settings page (`aptrade app`).

## The limits (in code, aptrade/live/risk.py; they cannot be raised from the command line)

| Check | Rule |
|---|---|
| Kill switch | `aptrade live kill` stops all order sending until `aptrade live unkill` |
| Market hours | orders only while the market is open |
| Plan age | a plan older than 15 minutes must be rebuilt |
| Size | at most 30 orders per plan |
| No leverage | buys never exceed cash + sale proceeds |
| Tradable | every target symbol must be tradable at the broker |
| Daily limit | at most 2 live plans executed per day |
| Scope | symbols outside the target are never sold or bought |
| Live switch | real money needs separate live keys AND APTRADE_ALLOW_LIVE=1 AND a code typed by a human in a terminal |

## Steps

Read `risk` from `aptrade live plan --json`: `ok`, `blocks`, `warnings`. Report every block
and warning in plain words. If the user wants to stop everything now: `aptrade live kill`.

Never edit risk.py, the .env switches or the database to get a plan through, and never
call the broker API directly. If the user asks you to, explain why not and stop.

Also watch for risks the code cannot see: a target more concentrated than the user's
stated tolerance, money the user needs soon, or a request to "double down" after a loss.
Say so plainly.

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
