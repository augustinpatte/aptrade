# Research log

How aptrade got from "a day-trading repo looks promising" to "buy the index, diversify
if you want less risk". Every verdict and number is in `../results/research.json`; the
rules were written down first in `../PREREGISTRATION.md`.

1. **Audit of day-trader-skill.** Clean engineering, sound safeguards, but its own
   history replay on TSLA showed 33 trades at -0.06R before costs, and its 10,000-path
   simulator reported +0.03R: more optimistic than the history it is built from.
2. **H0, intraday ORB on 50 symbols, 18 months of 5-minute SIP bars.** aptrade
   reproduced the original's 33 trades exactly (`tests/test_parity.py`), then added
   next-open fills, costs, gaps, a portfolio with slots and a daily loss limit, coverage
   checks, walk-forward and a locked holdout. Result: -0.09R per trade over 10,954
   trades, 0 of 36 variants positive, -20% for a simulated $5,000 account. At zero
   cost: +7% while SPY made +25%. Costs are 15 to 20% of the intraday move.
3. **Swing, daily bars, ETFs only.** Costs shrink relative to multi-day moves. H1
   (trend) WEAK, H2 (mean reversion) FAIL.
4. **New goal: less risk.** H3 (50/50 SPY + trend) FAIL by 0.2 points on drawdown,
   twice. H4, the control without signal, did just as well: diversification, not
   timing, does the work. H5 (rotation) FAIL, with a holdout that looked like a win and
   was a bigger risk paying off once.

`scripts/` holds the one-shot scripts used to run each stage on a Mac. The intraday
code lives in `aptrade/intraday/` and runs with `aptrade intraday ...`.
