---
title: "HT Markets (SVG) Limited"
type: "entity"
entity_type: "trading_counterparty"
department: "cio"
status: "under_review"
sources: ["Brooker Group Master Trading Agreement Template_SVG (March 2026).docx", "Brooker Group_MTA Supplement_Options and Margin_HT Markets (SVG) Limited(Mar 2026).docx", "HT_Markets_MTA_Review_Memo.docx"]
related: ["hex-trust", "ht-markets-trading-arrangement", "2026-04-22-ht-markets-mta-review", "bicl", "dat-sell-call-strategy"]
created: "2026-05-17"
updated: "2026-05-17"
confidence: "high"
coverage: "high"
tags: ["cio", "entity", "counterparty", "trading", "digital-asset", "svg"]
---

# HT Markets (SVG) Limited

## Overview

HT Markets (SVG) Limited is the cryptocurrency **OTC trading counterparty** associated
with the Hex Trust group. It is the entity on the other side of Brooker's
[[ht-markets-trading-arrangement|Master Trading Agreement]] for spot, forward and option
trades. It is **not** the same legal entity as Hex Trust's regulated custody companies —
a distinction the [[2026-04-22-ht-markets-mta-review|review memo]] flags as the single
largest structural concern.

## Key Facts

| Attribute | Value |
|-----------|-------|
| Legal name | HT Markets (SVG) Limited |
| Incorporation | Saint Vincent and the Grenadines, company no. 26756 |
| Role | OTC crypto trading counterparty (spot, forward, options) |
| Regulator | None — SVG does not license crypto derivatives activity |
| Group affiliation | Associated with the Hex Trust brand / group |
| Brooker counterparty entity | [[bicl]] (Brooker International Company Limited) |
| Risk rating (review memo) | HIGH for a treasury user |

## Risk Profile

The MTA review memo's structural concerns about this entity:

- **Unregulated:** the SVG Financial Services Authority does not license forex/crypto
  derivatives — there is no prudential regulator behind HT Markets (SVG).
- **Title transfer:** all assets delivered (Pre-funding, Margin, purchase price) become
  HT's property; on HT insolvency Brooker ranks as an **unsecured creditor**.
- **Enforcement:** disputes go to Hong Kong (HKIAC) arbitration with an explicit bar on
  interim/injunctive relief; enforcing an award against an SVG letterbox is slow.
- **Recommended mitigations:** parent guarantee from the regulated Hex Trust group
  entity, or move the contract onto a regulated Hex Trust entity directly.

## Relationships

- **[[hex-trust]]** — affiliated regulated custodian (HK/UAE/Singapore entities)
- **[[bicl]]** — the Brooker subsidiary that contracts with HT Markets
- Provides the option-writing venue contemplated by [[dat-sell-call-strategy]]

## History

- **Mar 2026** — MTA + Options/Margin Supplement templates received.
- **22 Apr 2026** — AI-assisted contract review completed ([[2026-04-22-ht-markets-mta-review]]); HIGH risk; do not execute without Tier-1 redlines.

## Sources

- `Brooker Group Master Trading Agreement Template_SVG (March 2026).docx`
- `Brooker Group_MTA Supplement_Options and Margin_HT Markets (SVG) Limited(Mar 2026).docx`
- `HT_Markets_MTA_Review_Memo.docx`

## Agent Notes

"HT", "HT Markets" and "HT Markets (SVG)" all refer here. Do NOT conflate with the
regulated [[hex-trust]] custody entities. The contracting Brooker party is BICL, signed
by Varut Bulakul.
