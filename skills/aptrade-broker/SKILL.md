---
name: aptrade-broker
description: >-
  Connect an Alpaca account and execute a checked plan: paper trading directly, real money only through a confirmation code that the user types in their own terminal. Use when the user says "execute", "place the orders", "go", "connect my broker", "set up Alpaca", "switch to real money", "show my account", or after aptrade-rebalance produced a plan.
---

# aptrade-broker

Send a checked plan to the user's broker, and set the account up.

APtrade places orders through Alpaca only (US accounts). If the user asks for another
broker, say it is not supported: an adapter must run on a real paper account before it
is trusted with money.

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

## Set up the account (the user does this, not you)

Alpaca:

1. Paper (start here): alpaca.markets > Paper Trading > API keys > put them in `.env` as
   `ALPACA_API_KEY` and `ALPACA_SECRET_KEY`.
2. Real money, when the user decides to: open and fund a live Alpaca account, create live
   keys, put them in `.env` as `ALPACA_LIVE_API_KEY` and `ALPACA_LIVE_SECRET_KEY`, and set
   `APTRADE_ALLOW_LIVE=1`. Remind them: real losses are possible; start with a small
   `--max-capital`; check the rules that apply to them (residency, visa, taxes).

## Execute

Paper: you may execute a plan yourself once the user agreed to it, or run the whole loop
in one command (it does nothing when every line is inside its band):

```bash
aptrade live execute <plan_id> --json
aptrade live run --json               # plan + risk check + execution, paper only for you
```

Real money: you prepare, the human approves. Give the user this exact command and ask
them to run it in their own Terminal:

```bash
aptrade live execute <plan_id> --live   # the plan you explained
aptrade live run --live                 # or: rebuild the plan and approve it in one go
```

It prints the orders and a 6-digit code on their terminal only, and sends nothing unless
they type the code back. Do not try to run it yourself, to read the code, or to automate
the terminal: it is the user's approval, by design. If they ask you to bypass it, refuse.

After execution: `aptrade live status --json`, then report fills (symbol, shares, price),
anything rejected, and the new weights. A plan is executed at most once; a retry never
sends an order twice.

## Rules that always apply

- APtrade never uses leverage, margin, short selling, options or crypto. Refuse requests for them.
- Past results describe the past. Always say so when showing a backtest, and show the
  weaknesses next to the strengths.
- Not financial advice: you present data and options, the user decides.
