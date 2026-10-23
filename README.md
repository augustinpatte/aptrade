# APtrade

**An experiment in testing trading strategies and portfolios honestly against the S&P 500, with a local web app to explore the results and test your own portfolio.** · [Version française](README.fr.md)

> **Live demo:** _link coming soon_

APtrade takes trading ideas, from day trading to multi-month allocations, and runs
each one on real market data (2016 to 2026), with trading costs, strict rules
written down in advance, and the S&P 500 as the benchmark. The web app shows every
approach side by side: returns over 3 years and since 2017, worst drops, volatility,
risk per position, strengths and weaknesses.

It started as an audit of a popular day-trading repo on GitHub and grew into a
complete testing tool.

## Results

Every number below is computed by the code from real Alpaca data, costs included, and
rewritten automatically by `aptrade export`.

<!-- results:start -->
_Run `aptrade export` to fill this table with your data._
<!-- results:end -->

## The approaches

**Diversified allocation (the slider).** Choose your share of US stocks (SPY); the
rest goes to 15 ETFs (bonds, gold, commodities, international, real estate) weighted
by inverse volatility, rebalanced monthly.
- ▲ Simplest approach, very low costs; at 50% SPY it cut the worst drop by about a third.
- ▲ Held up as well as the signal-based strategies with a third of the trading.
- ▼ Less return than SPY in bull markets, roughly in proportion to the non-stock share.
- **Risk per position:** 16 ETFs, the largest line is SPY at the chosen share, no leverage.

**Trend following.** 15 diversified ETFs, each held while its 3-month return is
positive, inverse-volatility weights, the rest in T-bills.
- ▲ The smallest drops of all (max drawdown around 8 to 12% vs 34% for SPY).
- ▲ Risk-adjusted return close to SPY's; steps aside in long bear markets.
- ▼ Much lower return in bull markets; often half in cash.
- **Risk per position:** up to 15 lines, none dominant; low volatility.

**Half S&P 500, half trend following.** The market's engine with a shock absorber.
- ▲ About two thirds of SPY's return for about 60% of its worst drop; very stable.
- ▼ Three times the trading of the plain allocation for a similar result.
- **Risk per position:** half SPY at all times, half spread over up to 15 ETFs or T-bills.

**Momentum rotation.** Each month, the 3 ETFs with the best 12-month return, a third each.
- ▲ The best result of all over the reserved May 2024 to Oct 2026 period (+69% vs +53% for SPY); catches big moves in one asset class.
- ▼ Concentrated, with bigger drops than SPY; weak in the earlier years.
- **Risk per position:** three lines of 33%; the most concentrated approach.

**Buy the dip (3 to 10 days).** Buy an index or sector ETF in an uptrend after a sharp
2-day drop, sell the rebound.
- ▲ Small drawdown, often in cash, clear mechanical rules.
- ▼ Trades a lot: costs of 1 to 3% a year weigh on the result.
- **Risk per position:** at most 5 positions of 20%, held 1 to 10 days.

**Opening-range breakout (day trading).** The original repo's strategy, on 5-minute bars.
- ▲ Strict risk control: 0.25% of the account per trade, 1% daily loss limit, flat every evening.
- ▼ Intraday, costs eat 15 to 20% of the typical move; it needs a screen during market hours.
- **Risk per position:** 0.25% of the account, 2 positions at most.

Full details, targets and outcomes for each approach are in the app's **Strategies**
page and in [PREREGISTRATION.md](PREREGISTRATION.md).

## What the experiment showed

- A fixed diversified allocation kept about two thirds of the S&P 500's return with
  about two thirds of its worst drop, with no trading signal at all.
- Over days to weeks, trading costs become small; intraday, they dominate.
- Timing signals changed the shape of the risk more than the return.
- The S&P 500 itself remained the hardest benchmark to beat on a risk-adjusted basis.

## Safeguards

| Safeguard | What it does |
|---|---|
| Rules written before the data | Each approach, its parameters and its target were committed in [PREREGISTRATION.md](PREREGISTRATION.md) before the data was downloaded. No tuning after the fact. |
| A reserved test period | The most recent 25% of days are locked away, never used to choose, and every look is counted. |
| Walk-forward | When parameters are compared, the winner is chosen on the past and scored on data it never saw. |
| Realistic trading | Signals on closing prices, orders at the next open, 3 bps per side on every dollar traded, gaps through a stop filled at the gap. |
| No leverage, no shorting | At most 100% invested; the rest sits in 1-3 month T-bills (BIL). |
| Hard risk limits (intraday) | At most 1% of equity at risk per trade, 3% daily loss, 5 positions, 10 trades a day, written in code. |
| Honest statistics | Block-bootstrap confidence intervals; the bar rises with every extra idea tested. |
| No look-ahead | A test wrecks every price after a given day and checks that no earlier decision changes. |
| Your keys stay yours | Keys live in `.env` on your machine, ignored by git; `./check_secrets.sh` blocks a push that would leak them. |

## Use it yourself: step-by-step tutorial

### 1. Install (5 minutes)

You need Python 3.10 or newer: check with `python3 --version`. On a Mac, if it is
older, install the latest Python from [python.org](https://www.python.org/downloads/).

**macOS / Linux**

```bash
git clone https://github.com/augustinpatte/aptrade.git
cd aptrade
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/augustinpatte/aptrade.git
cd aptrade
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### 2. Open the app

```bash
aptrade app
```

Your browser opens on the dashboard. The **Dashboard**, **Allocation**, **Strategies**
and **Method** pages work immediately from the results included in the repo.

### 3. Get your own free Alpaca keys (needed for "My portfolio" and fresh data)

1. Create a free account on [alpaca.markets](https://alpaca.markets) (an email is enough
   for a paper account; no deposit).
2. In the dashboard, switch to **Paper Trading**, then generate an **API key**. Copy the
   key and the secret: the secret is shown only once.
3. Give them to APtrade, either way:
   - in the app: **Settings** page, paste both, **Save**; or
   - in the terminal:

```bash
cp .env.example .env
# then open .env in any text editor and fill in:
# ALPACA_API_KEY=your_key_here
# ALPACA_SECRET_KEY=your_secret_here
```

The keys are stored in `.env` on your machine only. Never paste them in a chat, an issue
or a public website. Reading data never places an order; orders only come from `aptrade live execute` or `aptrade live run`.

### 4. Download fresh data and recompute everything

```bash
aptrade swing fetch      # daily bars for the 26 ETFs since 2016 (a minute)
aptrade export           # recompute the results, the app and the tables of this README
aptrade app
```

Or click **Update** on the **Settings** page.

### 5. Test your own portfolio

In the app, **My portfolio**: pick ETFs (or type any ticker), set the weights (at most
100%; the rest is held in cash), choose how often to rebalance, and click **Run**. You get
the same KPIs, charts and comparison with SPY as the research.

### Next time

```bash
cd aptrade
source .venv/bin/activate      # Windows: .venv\Scripts\Activate.ps1
aptrade app
```

### Troubleshooting

- `command not found: aptrade`: the virtual environment is not active; run the
  `source .venv/bin/activate` line again.
- `python3` asks you to accept an Xcode license on a Mac: install Python from python.org
  instead of using Apple's.
- `ALPACA_API_KEY and ALPACA_SECRET_KEY are not set`: step 3.
- `subscription does not permit querying recent SIP data`: APtrade falls back to the free
  IEX feed by itself and tells you; results are then a little less precise.

## Use it with an AI agent (Claude Code, Codex, Grok)

APtrade ships 11 skills in the open Agent Skills format (`skills/*/SKILL.md`), read by
Claude Code, OpenAI Codex, Grok Build and other agents:

| Skill | What the agent does with it |
|---|---|
| `aptrade-research` | Tests any portfolio or strategy against SPY, last 3 years and since 2016 |
| `aptrade-allocate` | Asks your amount, horizon and pain threshold, shows options with their history, saves your target |
| `aptrade-rebalance` | Compares your account with the target and builds the orders |
| `aptrade-budget` | Sizes each line to your amount: dollars, shares, cash left |
| `aptrade-risk` | Checks every plan against hard limits; kill switch |
| `aptrade-broker` | Connects Alpaca and executes: paper by itself, real money with your code |
| `aptrade-alerts` | Drift, drop from the peak, rebalance due |
| `aptrade-news` | Recent news and filings on your holdings, with sources |
| `aptrade-analyst` | Earnings from SEC filings, ETF fees and holdings |
| `aptrade-congress` | Trades disclosed by members of Congress, with the 45-day delay stated |
| `aptrade-daytrade` | The day-trading experiment, research only |

**Install.** Inside the repo, the skills are already visible (`.claude/skills` and
`.agents/skills`). To have them in every project:

```bash
./install_skills.sh                                   # links them into ~/.claude, ~/.agents and ~/.grok
```

Claude Code can also install them as a plugin:

```
/plugin marketplace add augustinpatte/aptrade
/plugin install aptrade@aptrade
```

Then just ask: *"Build me a portfolio with at most a 20% drop, 2,000 $, and rebalance my paper account."*

## Manage a real portfolio

The agent (or you, from the terminal) can run the whole loop:

```bash
aptrade target set --weights SPY=60,IEF=30,GLD=10 --rebalance M --max-capital 2000
aptrade live run               # paper: plan + risk checks + orders, in one command
aptrade live alerts            # drift, drawdown, rebalance due
```

`aptrade live run` does nothing when every line is inside its band, so it is safe to run
every day or let an agent run it on a schedule. To review before sending, split it in two:
`aptrade live plan` then `aptrade live execute <plan_id>`.

For real money, add your live keys to `.env` (`ALPACA_LIVE_API_KEY`,
`ALPACA_LIVE_SECRET_KEY`) and set `APTRADE_ALLOW_LIVE=1`. Then:

```bash
aptrade live run --live                 # YOU run this: shows the orders, then a code to type back
```

Or in two steps: an agent prepares `aptrade live plan --live` and explains it, then you
run `aptrade live execute <plan_id> --live`. Either way, real orders leave only after you
type the code. In practice: the agent watches (`aptrade live alerts`), tells you when a
rebalance is due, and you spend 30 seconds approving it, about once a month.

**How your money is protected**

- Only the symbols in your target are traded; everything else in the account is left alone.
- `--max-capital` caps what APtrade manages. Start small.
- Hard limits in code: no leverage, no shorting, market hours only, plans expire after 15
  minutes, at most 30 orders per plan and 2 live plans per day, kill switch
  (`aptrade live kill`).
- Paper and live use different keys; a paper key can never place a real order.
- A live plan needs a 6-digit code shown only on your terminal. An agent reads the
  output of its commands, not your terminal, so it can prepare a live plan but cannot
  approve it.
- Each order has a unique id: a retry after a crash never sends it twice.

**What it cannot protect against.** An agent with full access to your computer can read
`.env`. The code gate stops an agent that follows its instructions or makes a mistake;
it does not stop one that deliberately ignores them and calls the broker itself. Keep
your agent in "ask before running commands" mode on the machine that holds live keys,
and do not keep live keys on a machine where agents run unattended.

## Data sources

Price data for research comes from one of three sources, chosen with `APTRADE_DATA`
in `.env`:

| Source | Key | Coverage | Caveat |
|---|---|---|---|
| `alpaca` | your Alpaca keys | US stocks and ETFs | free with a paper account |
| `tiingo` | free key (tiingo.com) | US stocks and ETFs | official API, daily limits on the free plan |
| `yahoo` | none | US and international | unofficial endpoint: can change or rate-limit without notice, personal use |

`auto` (default) picks Alpaca if its keys are set, else Tiingo if its key is set, else
Yahoo. So someone with no key at all can still test portfolios. Each source has its own
cache in `data/cache/<source>/`, and prices are adjusted for splits and dividends.

Orders go through Alpaca only (US accounts). Interactive Brokers and Trading 212 were
considered and left out: an adapter is only published once it has run on a real paper
account. The broker interface is in `aptrade/brokers/base.py` if you want to add one.

## Command line

```bash
aptrade app                                   # the web app
aptrade swing fetch                           # daily data for the 26 ETFs
aptrade export                                # recompute results/results.json and the README tables
aptrade swing backtest --strategy trend       # one strategy vs SPY (trend, meanrev, blend, static, rotation)
aptrade swing sweep --strategy trend          # walk-forward over its pre-registered parameters
aptrade swing holdout --strategy blend        # one look at the reserved test period, recorded
aptrade intraday backtest                     # the day-trading test on 5-minute bars
aptrade runs                                  # every run, from the local SQLite journal
aptrade test-portfolio --weights SPY=60,IEF=40   # any weights vs SPY (--json for agents)
aptrade target set|show                       # the portfolio APtrade maintains
aptrade live status|plan|execute|alerts|kill  # a paper or real Alpaca account
```

## Publish your own demo

[Streamlit Community Cloud](https://streamlit.io/cloud) hosts the app for free from GitHub:

1. `aptrade export`, then commit `results/results.json` and the README.
2. On share.streamlit.io: **New app**, choose your repo, main file `app/Home.py`.
3. In the app's **Settings > Secrets**, add `APTRADE_PUBLIC_DEMO = "1"`. In this mode the app
   never asks for keys and never downloads anything: visitors must not type their keys
   into a public site.

## Data and licensing

Prices come from Alpaca with your own key and stay on your machine (`data/`, ignored by
git). Market-data agreements generally forbid redistributing raw data, so the repo
publishes only monthly returns and statistics (`results/results.json`). The one
exception is a small TSLA test fixture taken from the MIT-licensed original repo
(`tests/fixtures/NOTICE.md`).

## Known limits

- Ten years is one market history; the future can be different.
- The reserved test period covers about 2.4 years: enough to reject an idea, not to prove one.
- Simulations use fractional shares and a fixed cost per side, without taxes.
- The 15 diversified ETFs were chosen in 2026; they all existed in 2016, but choosing
  them is a decision made with hindsight.
- Order execution has run on an Alpaca paper account. The real-money path (`--live`) is the
  same code plus the confirmation code, but it has not been run with real money yet: start
  with a small `--max-capital`.
- Yahoo prices come from an unofficial endpoint that can change without notice.

## Project layout

```
aptrade/
├── app/                 the web app (Streamlit), English and French
├── aptrade/
│   ├── swing/           daily engine, strategies, metrics vs SPY, walk-forward, custom portfolios
│   ├── live/            real or paper account: target, plan, risk limits, execution, alerts
│   ├── brokers/         broker interface and the Alpaca adapter
│   ├── sources.py       Yahoo and Tiingo daily prices
│   ├── intraday/        the day-trading research (5-minute bars)
│   ├── data.py          Alpaca data with a local cache
│   ├── store.py         SQLite journal of runs
│   ├── export.py        results for the app, without prices
│   └── cli.py           the aptrade command
├── results/             research.json (approaches) and results.json (app data)
├── skills/              the 11 agent skills (also linked from .claude/skills and .agents/skills)
├── research/            the research log and the scripts used at each stage
├── tests/               offline tests (python -m unittest discover -s tests -t .)
├── PREREGISTRATION.md   the rules, written before the data
└── check_secrets.sh     run before every push
```

## Not financial advice

APtrade is educational software and an experiment. It does arithmetic on historical
market data; it cannot see the future, and past performance does not predict future
results. It places orders only on the account you connect, within the limits above, and real-money orders only after you type a confirmation code.

MIT License · Augustin Patte · Built from an audit of
[day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT).
