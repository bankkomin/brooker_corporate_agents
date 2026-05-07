---
title: "IC Meeting Minutes — DOCX Generation Template"
type: "template"
department: "ic"
output_format: "docx"
reference_file: "config/templates/ic/IC-meeting-minutes-reference.docx"
generation_tool: "anthropic-skills:docx (docx-js for new) or unpack/edit/repack (for incremental from reference)"
created: "2026-05-06"
updated: "2026-05-06"
tags: ["ic", "template", "docx", "generation", "minutes"]
---

# IC Meeting Minutes — DOCX Generation Template

**Reference file:** `config/templates/ic/IC-meeting-minutes-reference.docx` (the Feb 2026 meeting docx, used as the canonical structural / styling reference).

**Generation strategies (pick one):**

1. **Recommended for production:** unpack reference docx → edit XML for fresh content → repack. Preserves all native Word styles / fonts / tab stops.
2. **From scratch:** use `docx-js` (anthropic-skills:docx Creating New Documents). Higher control, but must match style manually.

---

## Section structure (canonical, observed in 3 meetings)

Each section becomes a heading-level paragraph (Heading 1 for top-level, Heading 2 for sub-sections). Use the placeholder names below — these are the field IDs the agent populates from the vault.

### Header block

```
Meeting Number {N}
{HH:MM} {DATE} {YYYY}
```

| Placeholder | Source | Example |
|-------------|--------|---------|
| `{N}` | meeting_number frontmatter of the new meeting note | 1 |
| `{HH:MM}` | meeting_time | 12:30 |
| `{DATE}` | meeting_date formatted "DD MMM YYYY" | 19 Mar 2026 |

### 1. Agenda (numbered list, bullets)

Source: standard 9-item list (or expanded 17-item list if deck-augmented). Use [[meeting-note]] template's Agenda section as the canonical list.

### 2. Liquidity Management Policy (paragraph + key-value lines)

Format observed:
```
Baht
Expected FY Cash Outflow {YYYY}
{value with thousand-separators}
Current Liquidity is Sufficient
Cash & Equivalents: {value} mn
Current Stocks: {value} mn
Current Unlocked Funds: {value} mn
Liquidity Risk: {Low/Medium/High}.
D/E Ratio: {value}x {Low/Medium/High}.
```

| Placeholder | Vault source |
|-------------|--------------|
| `{fy_cash_outflow_bt}` | Latest meeting's frontmatter or [[liquidity-management-policy]] history table |
| `{cash_and_equivalents_mn}` | same |
| `{current_stocks_mn}` | same |
| `{current_unlocked_funds_mn}` | same |
| `{liquidity_risk}` | computed (Cash + Stocks + Unlocked) / FY outflow → band per [[liquidity-management-policy]] |
| `{de_ratio}` | from [[finance/financial-statements]] (cross-read) |

### 3. Outlook (prose, 1-3 paragraphs)

Format observed: SET commentary, then THB, then global commentary.

```
SET. SET was {direction} {pct}% this month and closed at {level}. YTD was {ytd_pct}%. THB {direction} to {fx} for the {period}. Thai markets {commentary}.

In global markets, {global_commentary_paragraph_1}.

{global_commentary_paragraph_2 — optional}.
```

| Placeholder | Vault source |
|-------------|--------------|
| `{set_monthly_pct}` · `{set_close}` · `{set_ytd_pct}` | latest [[portfolio-allocation-history]] or upstream macro feed |
| `{thb_usd_fx}` | from dashboard frontmatter `fx` |
| `{global_commentary}` | LLM synthesis from cross-read `finance_docs` macro briefs OR deck slides 2-11 narrative |

### 4. Master sheet (prose paragraph + tables)

```
Equity (include VC) ratio was {equity_pct}%. Liquidity ratio is {liquidity_status}. Fix income ratio is {fix_pct}%. Structured loan ratio is at {structured_pct}%. Digital Assets ratio was {digital_pct}%. Investment/Total Asset estimated to be {investment_total_pct}% for {Quarter}.

RED FLAG POLICY ->25%:
{numbered_red_flag_list}
{plan_reference_or_note}

CONCENTRATION >25% POLICY:
{concentration_breach_list_or_none}

[Strategy performance table — 6 columns: Fund Strategies | Units | Monthly Return | YTD Return | Volatility | Bias]
{strategy_rows}

SET volatility is at {set_vol_pct}%.
```

| Placeholder | Vault source |
|-------------|--------------|
| All ratio %s | [[dashboard-{YYYY-MM}]] rows 34-37 + investment ratio row 32/38 |
| `{numbered_red_flag_list}` | [[red-flag-portfolio-reduction]] cross-checked against latest dashboard drawdowns |
| `{concentration_breach_list_or_none}` | computed: any position > 25% of Total Investments |
| `{strategy_rows}` | per-strategy entity files (Digital Assets, Non-Listed, Brook, [[sukhothai-fund]], FX) |

### 5. Objectives for {YYYY} (2-column table)

```
Objectives for {YYYY}
| Item | Status |
| ---- | ------ |
| {objective_1} | {status_1} |
...
```

| Placeholder | Vault source |
|-------------|--------------|
| Each row | each running `ic/decisions/<topic>.md` file's **Status timeline** entry for the meeting period |

The `ic-chair-agent` MUST cross-reference every running decision file and emit a row per running objective. Closed / cancelled items still appear with status "Cancelled" / "Complete" until removed.

### 6. Brooker Port (prose + bullet list)

```
Brooker Port

This month's performance was {monthly_pct}%, bringing YTD to {ytd_pct}%.

Stocks Outlook
{stock_name} ({status}): {commentary}.
{stock_name} ({status}): {commentary}.
...
```

| Placeholder | Vault source |
|-------------|--------------|
| `{monthly_pct}` / `{ytd_pct}` | from [[brooker]] entity history table |
| Per-stock bullets | latest entity file `ic/entities/{stock}.md` with current drawdown + outlook commentary; bullets ordered by Red Flag severity then market cap |

### 7. Sukhothai (prose)

```
Sukhothai

Sukhothai was {monthly_pct}% this month bringing YTD to {ytd_pct}%. AUM at {aum_mn} mn USD.

Next Steps: {next_steps}
```

Source: [[sukhothai-fund]] performance table + [[sukhothai-redemption]] decision file.

### 8. Non listed (prose, name-by-name)

One short paragraph per non-listed entity that has news for this period. Order: [[varuna]] · [[wavebcg]] · [[adfin]] · [[robinhood]] · then any new.

For each, pull from the entity's latest `## Updates` or `## Source references` section if present in the corresponding meeting period.

### 9. Structured loan (table — 7 columns)

```
| Name | Loan Date / Drawdown Date | Due Date | Outstanding MB | Collateral | Interest | Status |
```

Source: [[structured-loan-portfolio]] canonical inventory table. Include every active loan; mark settled ones as removed in commentary above the table.

### 10. Digital Assets and VC (single line)

```
Digital Assets and VC -Please refer to presentation. Please refer to appendix.
```

The deck carries the substance — this is intentionally a stub.

### 11. Schedule (one line)

```
Schedule for {YYYY} (tentative)
```

Followed by either dates list or empty.

---

## Generation algorithm (agent runtime)

```pseudocode
def generate_ic_minutes_docx(target_meeting_date, dashboard_period):
    new_meeting_id = f"IC-{target_meeting_date}"
    prev_meeting = latest_meeting_before(target_meeting_date)
    dashboard = load_trend(f"dashboard-{dashboard_period}")

    sections = {
        "header": render_header(meeting_number, time, date),
        "agenda": load_agenda_template(),
        "liquidity": render_liquidity_section(dashboard, finance_cross_read=True),
        "outlook": synthesize_outlook(macro_briefs, dashboard.fx),
        "master_sheet": render_master_sheet(dashboard),
        "objectives": render_objectives_table([
            load_decision(d) for d in running_decisions()
        ]),
        "brooker_port": render_brooker_port([
            load_entity(name) for name in BROOKER_PORTFOLIO_NAMES
        ]),
        "sukhothai": render_sukhothai(load_entity("sukhothai-fund"), load_decision("sukhothai-redemption")),
        "non_listed": render_non_listed([
            load_entity(name) for name in NON_LISTED_NAMES
        ]),
        "structured_loan": render_loan_table(load_entity("structured-loan-portfolio")),
        "digital_asset_stub": "Digital Assets and VC -Please refer to presentation.",
        "schedule": render_schedule(next_meeting_date),
    }

    docx_path = write_docx_via_template(
        reference="config/templates/ic/IC-meeting-minutes-reference.docx",
        sections=sections,
        output_path=f"output/{new_meeting_id}-draft.docx"
    )
    return docx_path  # human reviews before circulating
```

## Output handling

- **Draft only.** Generated docx is written to `output/` (or staging area), NEVER directly into corporate share.
- **Human approval required** before the docx is treated as canonical (per Brooker corporate-agent staging pipeline rules).
- **Markdown twin auto-generated:** alongside the .docx, write `obsidian-vault/ic/meeting-notes/IC-{YYYY-MM-DD}-draft.md` so vault_watcher indexes the new minutes immediately for retrieval.

## Hard rules for generation

- **NEVER** invent figures. Every number cited must trace to a vault file or cross-read `finance_docs` source.
- **ALWAYS** keep the canonical 9-item agenda even if the deck has 17 items; the docx is the formal minutes, the deck is the narrative.
- **NEVER** drop the "Please refer to presentation" stub for sections covered by the deck — that's the documented hand-off pattern.
- **If a value is unknown** (e.g. SET monthly returns when macro feed is unavailable) → emit `[TBD — verify]` instead of guessing. Surface in the agent's escalation_flags.
