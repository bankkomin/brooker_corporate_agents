---
title: "IC Monthly Deck — PPTX Generation Template"
type: "template"
department: "ic"
output_format: "pptx"
reference_file: "config/templates/ic/IC-meeting-deck-reference.pptx"
generation_tool: "anthropic-skills:pptx (pptxgenjs from scratch, OR unpack/edit/repack from reference)"
created: "2026-05-06"
updated: "2026-05-06"
tags: ["ic", "template", "pptx", "deck", "generation"]
---

# IC Monthly Deck — PPTX Generation Template

**Reference file:** `config/templates/ic/IC-meeting-deck-reference.pptx` (35 slides, the IC No1 March 2026 deck — used as canonical structure, color palette, and layout reference).

**Generation strategies (pick one):**

1. **Recommended for production:** unpack reference pptx, swap text/figures slide-by-slide, repack. Preserves all native PowerPoint masters / themes / chart styles.
2. **From scratch:** use `pptxgenjs` (anthropic-skills:pptx Creating from Scratch). Higher control but requires re-creating the dark/teal color palette, the gauge / arrow / icon visual motifs, and chart styles.

---

## Canonical slide structure (Mar 2026 deck — 35 slides)

The slide order is the **table of contents** for the meeting deck. Future decks should follow the same structure unless the IC formally changes the agenda.

### Title block (slide 1)

| Slot | Source |
|------|--------|
| Top title | `{Period} Digital Asset Update` (e.g. "Feb 2026 Digital Asset Update") |
| Section list (8 bullet items) | Macro Update · Engine 1 — VCC Strategy · Engine 2 — Advisory · Engine 3 — DAT, Stop list, 40% Investment Co. · Capital Sovereignty & Stay Liquid Doctrine · Prediction Market Arbitrage · Strategic Partner Map |

### Macro Update (slides 2-11)

| Slide | Topic | Data sources |
|-------|-------|--------------|
| 2 | Geopolitics framing (Iran/China current; future: whatever the prevailing macro narrative is) | LLM synthesis from cross-read macro briefs |
| 3 | Global Liquidity dashboards (Fed BS / TGA / Reverse repo / USD funding stress / Credit issuance / ETF flow / Stablecoin supply / China credit impulse) | External macro feeds (out of scope for v1 — leave as image placeholders) |
| 4 | (chart placeholder — typically liquidity overlay) | external |
| 5 | Stablecoin growth chart | external |
| 6 | (chart placeholder — typically crypto-specific liquidity proxy) | external |
| 7 | Regulatory clarity update | LLM synthesis from cross-read `legal_docs` |
| 8 | PMI > 50 thesis (current ISM reading + 3-year wait commentary + theme list) | external macro |
| 9-10 | (chart placeholders) | external |
| 11 | MMF rotation thesis (Detonation Physics) — historical pattern + current MMF size | static narrative + current MMF total ($7.7T as of Mar 2026) |

For v1 ingestion / generation, slides 2-11 can be **carried forward** from the previous deck unchanged unless the macro narrative materially changes. Agents should NOT auto-generate macro slides; instead surface "macro update needed?" as a pre-meeting decision for the human chair.

### Engine 1 — VCC (slides 12-14)

| Slide | Topic | Vault source |
|-------|-------|--------------|
| 12 | OKR-1 income build table (8 line items) | [[okr-500mb-recurring-income]] full table |
| 13 | VCC Operating System dashboard (current AUM, target, fee run-rate, 40% rule status, GP seed alignment, # LPs, FoF allocation, Yield FoF status, Product Discovery R&D items) | [[singapore-vcc-structure]] + [[brook-limited-partners-fof]] + [[bicl-movie-private-credit]] |
| 14 | Engine 1 actions / events (LP events, sub-fund seeding) | [[singapore-vcc-structure]] events list |

### DAT Doctrine (slide 15)

Pure doctrine slide — Go-game metaphor (optionality / influence / survivability). Generally stable; refresh quantification (Influence Bt 1,000mn etc.) from current portfolio sizing.

Source: [[engine-framework]] DAT doctrine section.

### Engine 3 — DAT plan (slides 16-25)

| Slide | Topic | Vault source |
|-------|-------|--------------|
| 16 | Round 1 Reduction & Reallocation table (Sell & Seed vs Sell only scenarios) | [[dat-sell-call-strategy]] / [[digital-asset-treasury-divestment]] Round 1 table |
| 17-18 | Phase 1/2/3 plan (typically a duplicate slide) | [[dat-sell-call-strategy]] phase plan |
| 19 | Sell + Call problem statement (Blind Sell Problem) | [[dat-sell-call-strategy]] §"Blind Sell Problem" |
| 20 | Strike & leverage logic (Deribit, monthly yields, strike formula, gamma context) | [[dat-sell-call-strategy]] §"Strategy parameters" |
| 21 | Scenario outcomes (1x/2x/3x with sell target, crypto saved, new ratio) | [[dat-sell-call-strategy]] sell-down matrix |
| 22 | Execution & Risk matrix (TWAP/VWAP/OTC + 6 risk rows + committee actions) | [[dat-sell-call-strategy]] risk matrix |
| 23 | Sell-down scenario matrix (BTC/BNB units required at price levels × leverage) | [[dat-sell-call-strategy]] sell-down matrix |
| 24 | Board summary (CAC-Agent advisory output) | LLM synthesis from this very SKILL.md output |
| 25 | Gamma profile reading guide (appendix) | static; refresh quantification from latest [[deribit]] data |
| 26 | DAT MTM update (current MTM, monthly + YTD performance, OKR-1b run-rate) | [[binance-bnb-otc]] + [[okr-500mb-recurring-income]] OKR-1b sub-target |

### Structured Loan (slides 27-29)

| Slide | Topic | Vault source |
|-------|-------|--------------|
| 27 | Loan inventory table (12 active loans, Outstanding / Reserved / Collateral / Interest / Status) | [[structured-loan-portfolio]] canonical inventory |
| 28 | New structure loan plan + 40/60 strategic partner map | [[structured-loan-portfolio]] new loan plan + Strategic Partner Map |
| 29 | BICL Pilot facility terms (LTV, production cap, interest, maturity, total facility) | [[bicl-movie-private-credit]] facility terms |

### Liquidity Management (slide 30)

```
Liquidity Management
Cash Outflow: {fy_outflow_mn} mn {YYYY}
Current Liquidity is Sufficient
Cash & Equivalents: {cash_mn} mn
Current Stocks: {stocks_mn} mn
Current Unlocked Funds: {unlocked_mn} mn
Liquidity Risk: {risk_band}.
D/E Ratio: {de_ratio}x {risk_band}.
```

Source: identical to docx §2 — same data, presentation slide form.

### Capital Sovereignty (slide 31)

Risk list + funding channel options.

Source: [[capital-sovereignty-doctrine]] risks + funding channels.

### Prediction Market Pilot (slide 33)

Three-strategy table (Latency Arb / Delta-Neutral MM / Buy High & Settle) with allocation, win rate, daily yield, monthly, APY + blended row.

Source: [[prediction-market-pilot]] strategy table.

### Action & Approval (slide 34)

Numbered list of every item requiring formal IC vote at this meeting.

Source: latest [[meeting-note]] §"Action & Approval" section.

### Closing slide (slide 35)

```
End
```

---

## Generation algorithm (agent runtime)

```pseudocode
def generate_ic_deck_pptx(target_meeting_date, dashboard_period, decisions_pending):
    sections = {
        "title": f"{period} Digital Asset Update",
        "macro_carryforward": load_prior_deck_macro_slides_unless_refresh_requested(),
        "engine_1_okr_table": load_concept("okr-500mb-recurring-income"),
        "engine_1_vcc_dashboard": load_decision("singapore-vcc-structure"),
        "engine_1_actions": load_decision("singapore-vcc-structure").events,
        "dat_doctrine": load_concept("engine-framework").dat_doctrine,
        "round_1_table": load_decision("dat-sell-call-strategy").round_1,
        "phase_plan": load_decision("dat-sell-call-strategy").phases,
        "sell_call_problem": load_decision("dat-sell-call-strategy").problem_statement,
        "strike_leverage": load_decision("dat-sell-call-strategy").strategy_parameters,
        "scenario_outcomes": load_decision("dat-sell-call-strategy").sell_down_matrix,
        "execution_risk": load_decision("dat-sell-call-strategy").risk_matrix,
        "sell_down_matrix": load_decision("dat-sell-call-strategy").sell_down_matrix,
        "board_summary": agent_advisory_output(),
        "gamma_appendix": static_gamma_explainer(),
        "dat_mtm": {
            "mtm_usd_mn": load_entity("binance-bnb-otc").mtm,
            "monthly_pct": ...,
            "ytd_pct": ...,
            "okr_1b_run_rate": load_concept("okr-500mb-recurring-income").okr_1b
        },
        "loan_inventory": load_entity("structured-loan-portfolio").inventory_table,
        "new_loans_plan": load_entity("structured-loan-portfolio").new_loans_plan,
        "bicl_terms": load_decision("bicl-movie-private-credit").terms,
        "liquidity": render_liquidity_section_v_slide(dashboard),
        "capital_sovereignty": load_decision("capital-sovereignty-doctrine"),
        "prediction_market": load_decision("prediction-market-pilot").strategies,
        "action_approval": decisions_pending,  # list of formal vote items
    }
    pptx_path = write_pptx_via_template(
        reference="config/templates/ic/IC-meeting-deck-reference.pptx",
        sections=sections,
        output_path=f"output/IC-deck-{target_meeting_date}-draft.pptx"
    )
    return pptx_path  # human reviews before presenting
```

## Output handling

- **Draft only.** Output goes to `output/` (or staging), never directly to corporate share.
- **Human approval before circulation.**
- **Companion artifacts** generated alongside:
  - `IC-{YYYY-MM-DD}-draft.docx` (minutes — see [[meeting-minutes-docx]])
  - `IC-{YYYY-MM-DD}-draft.md` (markdown vault twin — auto-indexes to RAG)
  - `dashboard-{YYYY-MM}-draft.md` (markdown trend file from latest dashboard.xlsx)

## Visual style guidelines (preserved from reference)

- **Dark navy / teal** palette for DAT slides (Engine 3)
- **Light backgrounds** for VCC / Engine 1 slides
- **Tables with column headers in bold**, alternating row shading
- **Stat callouts** in large numbers (60-72pt) with small labels below — used on slides 19, 21, 24
- **Gauge / arrow visuals** for ratio breaches (slide 30 has an example)
- **Numbered process steps** in colored circles for multi-step strategies (slides 19-20)
- **Footer**: "ENGINE 3 — DIGITAL ASSET TREASURY · IC NO.1 · MARCH {YYYY}" or equivalent

## Hard rules for generation

- **NEVER** auto-generate macro slides (slides 2-11) — these require human macro narrative; agent surfaces "macro refresh needed" as a pre-meeting question
- **NEVER** invent yields, prices, or volumes; every figure traces to vault or external feed with timestamp
- **ALWAYS** keep slide 35 ("End") as the closing slide
- **For Action & Approval slide:** every item must have a corresponding `ic/decisions/<topic>.md` file; agent does not invent new approval items
- **The reference deck is source-of-truth for layout** — when adding new slides for new initiatives, slot them under the appropriate Engine section, do not change the engine ordering
- **Charts and data visualisations** referenced from external macro feeds (slides 3, 4, 5, 6, 9, 10) are out of scope for agent v1 — leave as image placeholders or carry forward from prior deck
