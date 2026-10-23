---
name: aptrade-research
description: >-
  Test any portfolio or strategy honestly against the S&P 500 (SPY) on real data since 2016: last 3 years and whole period, return, worst drop, volatility, Sharpe, costs included. Use when the user asks "how would X have done", "compare my portfolio to the S&P 500", "backtest", "is 60/40 better", "test these weights", or before choosing or changing a target.
---

# aptrade-research

Answer "how would this portfolio have done?" with numbers the user can trust.

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
aptrade test-portfolio --weights SPY=60,IEF=30,GLD=10 --rebalance Q --json   # any tickers, rest in cash
aptrade swing backtest --strategy trend          # the tested strategies: trend, meanrev, blend, static, rotation
```

Without Alpaca keys, read the precomputed results instead: `<repo>/results/results.json`
(`portfolios.alloc_0` ... `alloc_100` = x% SPY + the rest diversified; `trend`, `blend`,
`rotation`, `meanrev`; each has `stats.3y`, `stats.full`, `stats.holdout`, `activity`) and
`<repo>/results/research.json` (strengths, weaknesses, risk per position, targets and outcomes).

## How to present a result

1. A short table: last 3 years and whole period, portfolio vs SPY: total return, per year,
   worst drop, volatility, Sharpe. Show losses as losses.
2. Strengths and weaknesses in two short lists. Translate the worst drop into dollars on
   the user's amount ("on 10,000 $ you would have been 2,300 $ down at the worst point").
3. Costs per year and how often it trades.
4. The caveat: weights chosen knowing the past look better than they are; past results
   do not predict future ones.

Never claim a strategy "beats the market" from one backtest. In APtrade's own research
(results/research.json), no timing strategy beat SPY on a risk-adjusted basis; diversified
allocations traded return for smaller drops.

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
