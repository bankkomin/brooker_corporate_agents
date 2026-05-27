# Office templates (user-authored)

This is where you (the user) author **Microsoft Word / Excel / PowerPoint templates** in the real Office apps. The agents will open them, fill in `{{placeholders}}`, and save a populated copy to `data/reports/` (or `data/decks/`) for delivery. Images, brand themes, slide masters, charts, conditional formatting — all preserved as-is.

**The existing programmatic builders are kept as fallback.** If a template doesn't exist for a given report, the agent uses the code-built version. Edit templates here at any time; effect is immediate on the next run.

## Directory layout

```
config/templates/office/
├── cac/
│   └── CAC_Monthly_Report.docx       ← author this in Word
├── ic/
│   ├── IC_Meeting_Minutes.docx       ← author in Word
│   ├── IC_Dashboard.xlsx              ← author in Excel
│   └── IC_Monthly_Deck.pptx           ← author in PowerPoint
├── vcc/
│   └── VCC_LP_Report.docx
├── finance/
│   └── CFO_Quarterly_Report.docx
└── ceo/
    └── Board_PreRead.docx
```

The filenames above are what the code looks for. Both `CAC_Monthly_Report.docx` and `CAC_Monthly_Report_template.docx` are accepted (the `_template` suffix is optional).

## Placeholder syntax

Type `{{snake_case_key}}` anywhere in the document — paragraphs, table cells, headers, footers, slide text frames, Excel cells. Spaces inside the braces are ignored: `{{ total_assets }}` works the same as `{{total_assets}}`.

**Formatting tip:** type the placeholder as plain text first, format the surrounding content after. Mid-placeholder formatting changes (e.g. bolding part of `{{key}}`) can split the text into multiple Word "runs" — the renderer handles this but may flatten run-level formatting *inside* the placeholder. Surrounding bold/italic/colour is fully preserved.

**Unknown keys are left visible** (`{{not_a_real_key}}` will appear in the output exactly as typed) so a missed placeholder is loud, not silent.

## Placeholder reference

### CAC Monthly Report (`cac/CAC_Monthly_Report.docx`)

Author a Word doc with your branding + put these placeholders wherever you want the values:

**Headline**
- `{{month}}` — e.g. `May 2026`
- `{{prepared_date}}` — `2026-05-26`
- `{{status_line}}` — `DRAFT — for committee review`

**Balance Sheet**
- `{{total_assets}}` — `THB 3,127.97M`
- `{{total_liabilities}}` — `THB 631M`
- `{{bank_debt}}` — `THB 800M`
- `{{net_worth}}` — `THB 2,435.11M`
- `{{de_ratio}}` — `0.26x`
- `{{inv_ratio}}` — `54.6%`

**Liquidity (Stay Liquid)**
- `{{operating_cash}}` — `THB 340M`
- `{{near_cash}}` — `THB 1,554M`
- `{{monthly_burn}}` — `THB 13.75M`
- `{{runway_months}}` — `138`
- `{{sovereignty_buffer_btc}}` — `100`
- `{{contingency_funding_plan}}` — `none`

**Funding & Covenants**
- `{{facility_drawn}}` — `THB 800M`
- `{{facility_available}}` — `THB 0M`
- `{{facility_util}}` — `100.0%`
- `{{cost_of_funds}}` — `2.78%`

**Asset-Liability**
- `{{duration_gap_yr}}` — `0.90`
- `{{refinancing_due_12m}}` — `300mn. Repay with excess cashflow`
- `{{collateral_sufficiency}}` — `n/a`
- `{{fx_exposure}}` — `41.3mn usd`

**On-chain**
- `{{on_chain_dtv}}` — `0.0%`
- `{{treasury_native_yield}}` — `1.0%`

**Engine performance**

Three-Engine Strategy allocations (Khao Yai §2.4). Label keys hold the engine name (so the template can keep one column heading); value keys hold the THB-millions figure pulled from `2 Capital Allocation`. Missing engine rows render as `n/a` (a warning is logged).

- `{{engine_1_vcc_label}}` — `Engine 1 — VCC`
- `{{engine_1_vcc_value}}` — `THB 253.87M`
- `{{engine_2_listed_label}}` — `Engine 2 — Listed equities`
- `{{engine_2_listed_value}}` — `THB 1,080.49M`
- `{{engine_3_dat_label}}` — `Engine 3 — DAT`
- `{{engine_3_dat_value}}` — `THB 1,592.69M`
- `{{engine_total_label}}` — `Total invested`
- `{{engine_total_value}}` — `THB 2,927.05M`

**Breach summary**
- `{{num_breaches}}` — `1`
- `{{num_watch_items}}` — `2`
- `{{num_total_flags}}` — `3`
- `{{breach_list}}` — one bullet per flagged metric, ready to drop in as a paragraph block

### Other report templates

The same convention applies to every report. Placeholders specific to other report types (IC minutes, VCC LP report, CFO quarterly, etc.) will be documented here as those pipelines come online. Until then, the programmatic builder is the source of truth.

## Tips for designing the templates

1. **Start from your existing brand template.** Open the firm's Word/PPT/Excel template (with logo, colours, fonts, footer) and add placeholders inline.
2. **Use Word's built-in styles** (Heading 1, Heading 2, Quote, etc.) — the rendered output will use them too.
3. **Tables work great.** Put `{{breach_list}}` inside a cell or use the placeholders inside a table you've designed.
4. **Images** placed in the template (logo, signatures) come through unchanged.
5. **Headers / footers** (page numbers, "DRAFT" watermark, your logo) survive intact.
6. **Excel formulas** are preserved. Put `{{net_worth}}` in cell C5; another cell can `=C5*1.1` and it'll still work.
7. **PowerPoint slide masters / theme** survive — slide colours, fonts, layouts inherited.

## How the agent decides which path to use

```
when /report/cac-meeting is called:
  if  config/templates/office/cac/CAC_Monthly_Report.docx EXISTS:
      → render that template with the {{placeholders}}
  else:
      → run the deterministic programmatic builder (current backup behaviour)
```

So you can add / remove a template at any time, no code changes needed. The fallback is always there.
