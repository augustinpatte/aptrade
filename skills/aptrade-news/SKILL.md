---
name: aptrade-news
description: >-
  Find and summarise recent news and official filings for the symbols in the portfolio or target: headlines, SEC 8-K filings, ETF issuer notices, with dates and sources. Use when the user asks "any news on my holdings", "what happened to X", "why did X drop", or before a rebalance.
---

# aptrade-news

Recent, sourced information on the user's holdings. Information only: news is not a
trading signal in APtrade, and nothing here places an order.

## Steps

1. Get the symbols: `aptrade target show --json` and, if keys exist, `aptrade live status --json`.
2. Search the web for each symbol's last few days of news. Prefer primary and reputable
   sources: the ETF issuer's site, SEC EDGAR, Reuters, the Wall Street Journal, the
   Financial Times, Bloomberg. For a company:
   `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<TICKER>&type=8-K&dateb=&owner=include&count=10`.
   For an ETF, the issuer's page (fees, holdings, distributions, closures, mergers).
3. Report per symbol: date, one-line summary in your own words, source link. Flag anything
   that changes the holding itself (fund closure, merger, fee change, index change).
4. Say plainly when nothing material happened.

Never present a headline as a reason to trade outside the plan. If the user wants to act
on news, test the idea first with aptrade-research.
