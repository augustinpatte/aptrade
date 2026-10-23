---
name: aptrade-allocate
description: >-
  Choose a target portfolio with the user from their goal, horizon and the biggest drop they can live with, show each option's real history, then save the chosen target. Use when the user says "how should I invest", "build me a portfolio", "I want less risk", "set my allocation", "change my target", or before the first rebalance.
---

# aptrade-allocate

Turn the user's situation into a target portfolio, with numbers, and save it.

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

1. Ask, briefly: amount to invest; horizon (years); the drop from the peak at which they
   would sell in panic (10%, 20%, 35%); any ETF they want or refuse. Do not ask for
   income, savings or identity details.
2. Show 2 or 3 options with their history from `<repo>/results/results.json`
   (`alloc_30`, `alloc_50`, `alloc_70`, `alloc_100`: x% SPY, the rest in 15 diversified
   ETFs), or test the user's own idea with `aptrade test-portfolio --weights ... --json`.
   Pick options whose worst drop fits the stated pain threshold. For each: return per year,
   worst drop in % and in dollars on their amount, volatility. Strengths and weaknesses.
3. Let the user choose. Then save it:

```bash
aptrade target set --alloc 50 --rebalance M --max-capital 2000 --json        # the slider, needs data
aptrade target set --weights SPY=60,IEF=30,GLD=10 --rebalance Q --max-capital 2000 --json
```

`--max-capital` caps the dollars APtrade manages (recommend starting small).
`--drift` (default 2 points) is the band inside which nothing is traded. Anything left
out of the weights stays in cash. Symbols not in the target are never touched.

4. Next step: aptrade-rebalance builds the orders. Start with the paper account.

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
