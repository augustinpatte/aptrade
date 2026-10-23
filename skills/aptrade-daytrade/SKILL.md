---
name: aptrade-daytrade
description: >-
  Research-only access to APtrade's day-trading test (the opening-range breakout from the original day-trader-skill repo): run the backtest and walk-forward on 5-minute bars and report the real results. Never places intraday orders. Use when the user asks about day trading, scalping, the opening range breakout, or the original day-trader-skill.
---

# aptrade-daytrade

The day-trading experiment, reproducible. It does not trade.

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

## Commands

```bash
aptrade intraday backtest              # ORB on 50 liquid US symbols, ~2 years of 5-minute bars
aptrade intraday sweep                 # walk-forward over 36 variants
aptrade intraday backtest --parity     # the original repo's optimistic execution, for comparison
```

## What to tell the user

APtrade's research (results/research.json, approach H0): over 10,954 trades the
opening-range breakout lost about 0.09R per trade after costs, none of 36 variants was
positive, a simulated 5,000 $ account lost about 20% over 18 months while SPY gained 25%,
and even with zero costs it made only +7%. Intraday, costs are 15 to 20% of the typical
move. Strengths: strict risk per trade, no overnight risk. Weaknesses: costs, and the need
to watch the screen.

If the user still wants to day trade with real money, say clearly that APtrade does not
support it, why, and that aptrade-research can test any idea first.
