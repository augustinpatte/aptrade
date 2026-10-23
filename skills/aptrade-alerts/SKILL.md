---
name: aptrade-alerts
description: >-
  Check the portfolio for what needs attention: lines that drifted from their target, a drop from the account's peak, a rebalance that is due. Use when the user asks "how is my portfolio", "anything to do", "check my positions", "did it drop", or on a daily or weekly schedule.
---

# aptrade-alerts

A short health check of the managed portfolio. Read-only: it never trades.

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

## Command

```bash
aptrade live alerts --json          # paper
aptrade live alerts --live --json   # real money
```

Returns equity, cash, managed capital, drawdown from the 12-month peak, each line's
current vs target weight and drift, and alerts: `drift` (beyond the band), `drawdown`
(beyond the target's alert threshold, 10% by default), `rebalance_due` (monthly,
quarterly or yearly since the last executed plan).

## Report

One line per alert, then the action: a due rebalance or a drift goes to
aptrade-rebalance; a drawdown is information, not a signal to sell. Remind the user what
the target's history said about drops of that size, from results/results.json.

## Scheduling

If your agent can run tasks on a schedule, a weekly `aptrade live alerts --json` is
enough. A schedule may build plans and execute them on paper; it never executes a live
plan (that needs the user at a terminal).

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
