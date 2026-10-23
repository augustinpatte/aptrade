---
name: aptrade-budget
description: >-
  Size a portfolio to an amount of money: how much each line gets, whole versus fractional shares, the minimum order, what stays in cash, and the cap on the capital APtrade manages. Use when the user says "I have 500 $", "how many shares", "invest only part of my account", "can I start with a small amount", or when a plan skips lines because they are too small.
---

# aptrade-budget

Make the amounts work: dollars per line, shares, cash left over.

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

## What decides the sizes

- Managed capital = value of the target's symbols + cash, capped by the target's
  `max_capital`. Raise or lower it with `aptrade target set ... --max-capital 1000`.
- Each line gets weight x managed capital. Fractionable ETFs are bought in dollars
  (fractional shares); others in whole shares, rounded down. A line under the minimum
  order (5 $ by default) is skipped; the plan says so.
- With a small amount and non-fractionable symbols, some lines cannot be bought at all.
  Suggest fractionable ETFs or fewer lines rather than forcing it.
- Buys never exceed cash + sale proceeds: if they would, they are scaled down (no leverage).

## Commands

```bash
aptrade live status --json       # equity, cash, positions
aptrade live plan --json         # exact sizes for the current target
```

Present the sizes as a small table: symbol, target %, dollars, shares, and what stays in cash.

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
