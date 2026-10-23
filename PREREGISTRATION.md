# Pre-registration: swing strategies

Written and committed on 2026-10-22, **before any daily data was downloaded or
looked at**. The git history is the proof. Nothing in this file may be changed after
the first `aptrade swing` run; a change means a new pre-registration and a new,
untouched holdout.

## Why these two, and nothing else

The opening-range breakout (intraday) failed: -0.09R per trade after costs over
10,954 trades, 0 of 36 variants positive, and even at zero cost it made +7% while
buying SPY made +25%. Intraday, costs are large relative to the move. Over several
days, the move grows (roughly with the square root of time) and costs become small.

Only two hypotheses are tested, each with an economic reason documented in the
literature. Each extra hypothesis tested on the same data makes a success less
credible, so the list is closed.

Both trade **ETFs only**. Over ten years, a universe of today's individual stocks is
survivorship-biased: buying dips looks brilliant when the companies that went bust
after their dip are not in the list. Broad ETFs do not disappear.

## Common rules

- **Data**: Alpaca daily bars, adjusted for splits and dividends (total return),
  from 2016-01-01 to the day before the first run.
- **Signal and execution**: signals use closes up to day t only; orders execute at
  the open of day t+1. No intraday data, no look-ahead.
- **Costs**: 3 basis points per side on every dollar traded, cash included.
- **Long only, no leverage.** Weights sum to at most 100%; the rest is held in BIL
  (1-3 month Treasury bills ETF), which stands for cash earning the T-bill rate.
- **Fractional shares** in the simulation. Whole-share feasibility for a small
  account is checked separately, later, and only if a candidate survives.
- **Benchmark**: SPY bought and held, same days, same cost model.

## H1: trend following (time-series momentum)

Moskowitz, Ooi and Pedersen (2012). Investors under-react to news, then over-react;
trends persist for months across asset classes. Main promise: smaller drawdowns in
long bear markets, not higher returns in bull markets.

- **Universe (15)**: SPY, QQQ, IWM, EFA, EEM, VNQ, TLT, IEF, TIP, LQD, HYG, GLD,
  SLV, DBC, UUP.
- **Rule**: at each rebalance (last trading day of the week or month, at the close),
  an ETF is held if its total return over the lookback is above zero.
- **Weights**: inverse volatility (60-day standard deviation of daily returns),
  normalised over the WHOLE universe; an ETF in a downtrend gives its weight to BIL.
  So the portfolio is fully invested only when every trend is up.
- **Grid (6 variants)**: lookback in {3, 6, 12} months (63, 126, 252 trading days)
  x rebalance in {weekly, monthly}.

## H2: short-term mean reversion in an uptrend

Liquidity provision: forced or panicked sellers push prices below value for a few
days; whoever buys from them is paid for it. Documented decay since publication.

- **Universe (13)**: SPY, QQQ, IWM, DIA, XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB.
- **Entry**: at the close, close above its 200-day simple moving average AND 2-day
  RSI (Wilder) below the threshold. Buy at the next open.
- **Exit**: at the close, close above its 5-day simple moving average, OR the position
  has been held for the maximum number of days. Sell at the next open. An ETF exited
  at a close cannot be re-entered at that same close (otherwise the maximum hold would
  mean nothing); it is eligible again from the next close. *(Clarification added
  2026-10-22 while writing the tests, still before any daily data was downloaded.)*
- **Sizing**: 5 slots of 20% each. If more signals than free slots, the lowest RSI
  first. Idle slots in BIL.
- **Grid (6 variants)**: RSI threshold in {5, 10, 20} x maximum hold in {5, 10} days.

## Data split

- **Holdout**: the last 25% of trading days, locked in the database the first time a
  swing command runs, separate from the intraday holdout. Never used to choose.
- **Research**: everything before. The first trading day is the first day every
  variant has its indicators (252 days of history for the 12-month lookback and the
  200-day average), so all variants are scored on exactly the same days.
- **Walk-forward** inside research: 5 blocks; for each of the last 4, the variant
  with the best Sharpe on everything before is scored on that block.

## Success criterion

Measured on daily returns, Sharpe ratio annualised with a zero risk-free rate for
both the strategy and SPY (BIL inside the strategy is a return like any other).

A strategy **passes** only if, out of sample:

1. its Sharpe ratio is above SPY's, with the 90% interval of the difference above
   zero (stationary block bootstrap, 20-day blocks, 2,000 resamples), AND
2. its maximum drawdown is smaller than SPY's.

Verdicts: **PASS** (both), **WEAK** (Sharpe above SPY and smaller drawdown, but the
interval includes zero), **FAIL** (anything else). Only a PASS on the walk-forward
record earns one look at the holdout, and only a PASS on the holdout earns paper
trading.

---

# Addendum H3: a 50/50 blend, for less risk

Written and committed on 2026-10-22, **after** the H1 and H2 walk-forward results
were seen on research data, and **before** anything was computed on the swing
holdout, which has never been looked at.

## What happened

- H2 (mean reversion): **FAIL**. Out-of-sample Sharpe 0.38 vs 0.74 for SPY; turnover
  of 34 to 102 times a year costs up to 3% a year.
- H1 (trend following): **WEAK**. Out-of-sample Sharpe 0.82 vs 0.74, max drawdown 8%
  vs 34%, but the 90% interval of the Sharpe difference (-0.52 to +0.69) includes
  zero. Its return was +21% vs +110% for SPY. Under the rules above, no holdout.
- A flaw in the H1/H2 criterion, found when reading the results: Sharpe was computed
  with a zero risk-free rate, which flatters a strategy that sits half in T-bills.
  H3 corrects it.

## The goal changed

The owner's stated goal is now **less risk, at the price of a somewhat lower return**,
with a pain threshold of a 15 to 20% drawdown. Beating SPY is no longer the goal.
H1's research results show what such a goal can use: a Sharpe close to SPY's with a
quarter of its drawdown, and low correlation with SPY.

## H3 rules

- **Portfolio**: 50% SPY + 50% the H1 trend sleeve with lookback 63 trading days and
  monthly rebalance (the variant chosen in 3 of the 4 walk-forward folds and the best
  over the research period). Inside the trend sleeve, everything H1 says applies.
- **Rebalance**: at the last close of each month, back to exactly 50/50, executed at
  the next open. Between month-ends, weights drift.
- **The 50% is not optimised.** It comes from the owner's drawdown tolerance, not
  from the data. No other weight will be tested.
- Costs, data, execution, BIL as cash, long only, no leverage: as above.

## H3 criterion

Sharpe here is computed on returns **in excess of BIL** (the T-bill rate), for both
the blend and SPY.

The blend **passes** if, over the same days:

1. its maximum drawdown is at most **60% of SPY's** maximum drawdown, AND
2. its excess Sharpe is at least **SPY's excess Sharpe minus 0.10**, AND
3. its annual return (CAGR) is at least **half of SPY's** (or at least SPY's, if
   SPY's is negative).

## H3 test plan

1. Research data: the blend is reported for context. Nothing is chosen from it.
2. **Holdout: exactly one look, whatever the research result.** The decision to look
   is made here, now, so a good or bad research number cannot influence it.
3. PASS on the holdout: paper trading with the rules frozen. FAIL: stop, and keep
   buying an index fund.

The holdout covers about 2.4 years. That is enough to show the blend failing its
goal; it is not enough to prove statistically that it is better. The verdict is
read with that limit in mind.

---

# Addendum H4 and H5: the control, and the last untested family

Written and committed on 2026-10-22, after the H3 holdout look, before anything
was computed for H4 or H5. Neither has been run on any data.

## H3 result, recorded as it came

FAIL on research and on the holdout, each time by 0.2 points on condition 1:
max drawdown 20.5% vs a limit of 20.3% (research), 11.5% vs 11.3% (holdout).
Conditions 2 and 3 passed both times. The verdict stays FAIL.

## H4: the control (does the trend signal add anything?)

H3 cut risk, but it holds bonds, gold and T-bills: maybe the diversification did the
work and the trend signal added nothing. H4 is H3 **without the signal**.

- **Portfolio**: 50% SPY + 50% the 15 H1 ETFs at inverse-volatility weights (60-day),
  always held, no trend filter. Back to these weights at every month-end close,
  executed at the next open.
- **Criterion**: the H3 criterion, unchanged (drawdown at most 60% of SPY's, excess
  Sharpe within 0.10 of SPY's, CAGR at least half of SPY's).
- **Reading**: if H4 does as well as H3, the trend code is not worth running and a
  fixed allocation is the better product (simpler, cheaper, fewer decisions).

## H5: relative momentum rotation

The one large family not tested yet: cross-sectional (relative) momentum across asset
classes (Faber 2010, Antonacci 2014). Investors chase recent winners slowly; asset
classes that led over the past year tend to keep leading for a while.

- **Universe**: the 15 H1 ETFs.
- **Rule**: at each month-end close, rank the 15 by total return over 252 trading
  days. Hold the top 3 at 1/3 each, but only those whose 252-day return beats BIL's
  over the same window (absolute momentum filter). Empty slots go to BIL.
- **No grid.** Lookback 12 months and top 3 are fixed from the literature, so H5 is a
  single test, not a search.
- **Criterion**: beat SPY risk-adjusted. Excess Sharpe (over BIL) above SPY's, with
  the lower bound of the interval of the difference above zero, AND a smaller max
  drawdown than SPY.

## Multiple testing

With H5, five hypotheses have been tested on the same years (H1 to H5). If each had
a 10% chance of a false PASS, at least one false PASS among five would be likely. So
for H4 and H5 the interval is **98%** instead of 90% (Bonferroni: 10% / 5). H4's
criterion has no interval; its comparison with H3 is descriptive.

## Test plan

Rules are fixed, no parameter is chosen, so no walk-forward is needed. For each of H4
and H5: the research period is reported, then the holdout is looked at **once**,
whatever the research result. Each hypothesis has its own holdout count.
