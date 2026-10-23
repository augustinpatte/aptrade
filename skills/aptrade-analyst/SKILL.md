---
name: aptrade-analyst
description: >-
  Read a company's or fund's official numbers and summarise what changed: revenue, earnings per share, margins and guidance from SEC filings, or an ETF's holdings, fees and distributions from its issuer. Use when the user asks "how did X's earnings go", "analyse this stock", "what is inside this ETF", "is this fund expensive".
---

# aptrade-analyst

Facts from official sources, summarised. Information only, not a recommendation.

## Companies (SEC EDGAR, free)

- Ticker to CIK: `https://www.sec.gov/files/company_tickers.json`
- Reported figures (XBRL): `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
  (CIK zero-padded to 10 digits). SEC asks for a User-Agent with a name and email on
  automated requests.
- Latest filings: `https://data.sec.gov/submissions/CIK##########.json` (10-Q, 10-K, 8-K).

Report the last 4 to 8 quarters: revenue, net income, diluted EPS, year-over-year change,
and anything unusual (one-offs, restatements). Quote the filing date and form.

## ETFs

From the issuer's page: expense ratio, number of holdings, top 10 and their weights,
sector or country mix, distribution yield, assets under management, inception date.
Compare the expense ratio with close alternatives.

## Rules

Numbers come from the filing or issuer, never from memory. Say when data is missing.
Past growth is not a forecast. Do not turn an analysis into an order: changes to the
portfolio go through aptrade-allocate and aptrade-research.
