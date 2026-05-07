---
title: "Purple Venture (Robinhood)"
type: "entity"
entity_type: "loan_borrower"
department: "ic"
status: "active_loan"
related: ["robinhood", "structured-loan-portfolio"]
first_seen: "2026-03-19"
last_seen: "2026-03-19"
created: "2026-05-06"
updated: "2026-05-06"
tags: ["ic", "entity", "loan-borrower", "robinhood"]
---

# Purple Venture (Robinhood)

Structured-loan borrower — Robinhood-affiliated SPV (Purple Venture).

| Drawdown | Due | Outstanding (mn) | Collateral | Interest | Status |
|----------|-----|------------------|------------|----------|--------|
| 2025-07-08 | 2026-07-08 | 30 | **0%** (uncollateralized) | **3.75%** (lowest in book) | Current |

## Anomaly

Both **0% collateral** and **3.75% interest** are unique in the book:
- All other "Current" loans carry 14% interest
- All non-reserved loans carry 200%+ collateral
- Likely reflects intra-group / strategic financing rather than commercial lending — pair with [[robinhood]] equity stake context

## Related

- [[robinhood]] — equity / token / IPO position
- [[robinhood-token-ipo]] — running decision

## Source references

- IC No1 Mar 2026 deck slide 27 (loan #12, last in book)
- [[structured-loan-portfolio]]

## Agent Notes

- Treat this as a **related-party / strategic** loan when answering credit-quality questions, not a commercial structured loan.
- Surface the 0%-collateral / 3.75%-interest anomaly explicitly when listed alongside the rest of the book.
