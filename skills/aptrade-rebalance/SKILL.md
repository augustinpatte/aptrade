---
name: aptrade-rebalance
description: >-
  Bring the account back to its target: compare holdings with the saved target, build the list of orders (sales first, no leverage), check the risk, and explain the plan. Use when the user says "rebalance", "invest my cash", "apply my target", "what do I need to buy", when aptrade-alerts says a rebalance is due, or on a monthly schedule.
---

# aptrade-rebalance

Build the plan that brings the account back to its target, and explain it.

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

## Steps

```bash
aptrade target show --json            # no target yet: use aptrade-allocate first
aptrade live alerts --json            # drift, drawdown, rebalance due
aptrade live plan --json              # paper account
aptrade live plan --live --json       # real-money account
```

Paper shortcut, when the user already agreed to the target: `aptrade live run --json`
builds, checks and executes in one step. Never for real money: there, the user runs
`aptrade live run --live` themselves.

The plan contains each order (side, symbol, dollars or shares, weight before and after),
skipped lines (inside the band, too small, not tradable), lines left untouched because
they are not in the target, totals, and a `risk` section. If `risk.ok` is false, read the
blocks to the user and stop.

Explain the plan in plain words: what is sold, what is bought, why (which line drifted and
by how much), the total, and the estimated costs (market orders, a few cents to a few
dollars). A plan expires after 15 minutes: rebuild it rather than execute an old one.

Then hand over to aptrade-broker to execute.

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
