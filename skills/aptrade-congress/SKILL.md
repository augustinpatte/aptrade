---
name: aptrade-congress
description: >-
  Look up the stock trades that US members of Congress have publicly disclosed (House periodic transaction reports, Senate eFD), with the disclosure delay stated. Use when the user asks "what did Pelosi buy", "congress trades", "did any senator trade X".
---

# aptrade-congress

Public disclosures of trades by members of Congress. Information only.

## Sources

- House: Clerk's financial disclosures, `https://disclosures-clerk.house.gov/FinancialDisclosure`
  (periodic transaction reports, PTR, as PDFs; yearly index files list them).
- Senate: `https://efdsearch.senate.gov/search/` (electronic financial disclosures).

## Report

For each trade: member, date of the trade, date of the disclosure, asset, buy or sell,
the reported amount range (disclosures give ranges, not exact amounts), and the link.

## Say this every time

Members have up to 45 days to disclose a trade, and the amounts are ranges. By the time
a trade is public, the move it was about may be over. APtrade's research found no edge in
copying trades; treat this as curiosity or context, never as a signal. To test an idea
built on it, use aptrade-research first.
