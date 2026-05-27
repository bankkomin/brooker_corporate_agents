---
title: "IB Operations Log"
type: log
department: "ib"
---

## [2026-05-22] expand | OctaiPipe knowledge expansion + ABB entity

Expanded [[octaipipe]] from the brief-only stub into a full entity using public web research
(accessed 2026-05-22): company background (founded 2016, London; CEO & co-founder Eric
Topham, CTO Ivan Scattergood, CGO George Hancock), technology (federated ML + multi-agent
reinforcement learning + digital twins, on-prem / no new hardware), the typical-50 MW
benchmark metrics, funding & investors (Momenta + Kyra Ventures co-led round announced
30 Sep 2025; existing investors SuperSeed + Atlas; ABB Motion Ventures minority stake
announced early Dec 2025, terms undisclosed), and named customers (Analog Devices, CPI,
Italtel, ABB).

New article (1): [[abb]] — ABB / ABB Motion Ventures, strategic investor + distribution
partner in OctaiPipe; linked from [[index]] under Investors & partners.

Provenance: every external fact is labelled *(public)* with a split Source References
(Brooker brief vs external URLs). Flagged a discrepancy — the brief states "ABB 10%" while
public sources report an **undisclosed minority** stake; both recorded, neither asserted as
a verified percentage. No `config/document_inventory.json` change (web research, not a new
corporate source file).

## [2026-05-22] ingest | 11 articles from brooker_database/ib

First knowledge ingest for the IB department, from
`SuperSeed_Brooker_Portfolio_Brief.pdf` (a confidential May 2026 SuperSeed Fund III
briefing for Brooker Group). The source PDF was read directly (the batch extractor lacked
`pdfplumber`); articles authored from the real 3-page content.

New articles (11):
- Concept (1): [[physical-ai-investment-thesis]] — "AI for the physical economy" thesis,
  three pillars, sector framework, strategic-not-passive rationale.
- Meeting note (1): [[2026-05-08-superseed-fund-iii-brooker-briefing]] — the source
  briefing hub.
- Entities (9): fund [[superseed-fund-iii]] (GP: SuperSeed Ventures LLP) and eight
  portfolio companies — [[all3]], [[hive-autonomy]] (Buildings & Infrastructure);
  [[thingtrax]], [[ai-build]] (Manufacturing); [[octaipipe]], [[freightsuite]] (Energy &
  Logistics); [[messium]], [[biographica]] (Agriculture).

Also created `ib/index.md` (first index for the department) and registered the source in
`config/document_inventory.json` (`doc_ib_superseed_portfolio_brief`).

> All portfolio metrics are vendor claims from the GP pitch; no commitment size or fund
> terms were stated in the brief.
