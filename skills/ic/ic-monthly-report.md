---
name: ic-monthly-report
agent: ic-chair-agent
dept: ic
version: 1.4
changelog:
  - "1.4 (2026-05-29): Renumber agenda to 0-9 (Section 0 = Previous Minutes, Section 1 = NEW Macro). Add Macro source ingestion from O:/brooker_database/ic/Macro {Mon} {YYYY}.md. Section 3 Master sheet now shows full per-position holdings table from dashboard rows 5-31. Concentration Policy now computed from dashboard (was hard-coded 'none' — discovered BNB OTC at 28.4% is a breach). Section 7 structured loan now queries dashboard R31 live (Cost / MTM / Gain%). Dashboard canonical path moved to O:/brooker_database/ic/Dashboard 2026.xlsx."
  - "1.3 (2026-05-29): Split HTML output into TWO files — minutes-HTML (long-form, replaces docx role) and deck-HTML (slide-by-slide, replaces pptx role). Both self-contained, browser-rendered."
  - "1.2 (2026-05-29): Switch outputs to markdown + HTML (drop docx + pptx); migrate paths from Y:/brooker_database to O:/brooker_database; new flat-file layout (O:/brooker_database/ic/ holds Weekly BG / BSFL / Coin Weekly directly, no portfolio/{month}/ subfolder); update latest-period detection to filename-pattern + mtime"
  - "1.1 (2026-05-29): Fix BSFL→Sukhothai mapping; add latest-sheet detection; pull prior deck for canonical structured-loan + DAT perf; add Round-1 execution detection; bundle post-sale ratio recomputation formula"
  - "1.0 (2026-05-28): Initial draft"
permissions:
  mode: read_only_with_staging_drafts
  data_zones: [1, 2]
  outbound_apis: []
  read_collections: [ic_docs, ic_knowledge, cio_docs, shared_policies, finance_docs, vcc_docs, legal_docs, cac_docs]
  source_mounts:
    - "O:/brooker_database/ic/"
    - "O:/brooker_database/cio/"
output_types: [draft_md, draft_html_minutes, draft_html_deck]
generation_contract: config/templates/ic/meeting-templates.json
output_directory: data/staging/pending/ic/
---

## Mandate

Produce the **monthly IC report** as **three** staging drafts:

1. **Markdown twin** for vault / RAG indexing (`obsidian-vault/ic/meeting-notes/IC-{date}-draft.md`)
2. **Minutes HTML** — long-form formal minutes (replaces the prior `.docx` role) (`data/staging/pending/ic/IC-{date}-minutes-draft.html`)
3. **Deck HTML** — slide-by-slide presentation (replaces the prior `.pptx` role) (`data/staging/pending/ic/IC-{date}-deck-draft.html`)

Both HTMLs are self-contained (inline CSS, no JS, no external assets), open in any browser, and print cleanly. They share the same underlying data extracted by this skill — the difference is **density and pacing**, not content. Minutes HTML is for the formal record + auditors (scrollable, table-heavy, full footnotes). Deck HTML is for chair prep + board distribution (one section per "slide", larger headings, key numbers spotlighted).

The report follows the canonical **10-section agenda** (0-9) of the IC formal minutes:

- **0. Previous Minutes** (carry-forward from prior meeting)
- **1. Macro** (synthesised from `O:\brooker_database\ic\Macro {Mon} {YYYY}.md` — human-curated research file)
- 2. Liquidity Management Policy
- 3. Master sheet (full per-position holdings breakdown + ratios + Red Flag + concentration)
- 4. Brooker Portfolio
- 5. Sukhothai
- 6. Non listed
- 7. Structured Loan
- 8. Digital Asset Division
- 9. Schedule

Section 1 (Macro) was added in v1.4. Sections 0 and 1 are presentation-only carry-forward; the numeric work happens in 2-9.

Source data is in `O:\brooker_database\ic` (flat file layout: Weekly BG, Coin Weekly, BSFL Monthly, Macro Md, prior IC docx/pptx, Dashboard 2026.xlsx) and `O:\brooker_database\cio` (Hex Trust custody docs + Mining Summary).

This skill is invoked when the user (or a scheduled trigger) says some variant of "draft the next IC meeting", "generate the monthly IC report", "build the IC pack for {month}". It is the operational machine behind the broader [[ic-chair-agent]] — the chair agent decides *what* to say and runs *analysis*; this skill *fetches the data* and *renders the artifacts*.

All outputs are drafts. They land in `data/staging/pending/ic/` and require human approval before sync-back writes them to the corporate share.

**Why HTML, not docx/pptx**: HTML opens in any browser without Office, renders cleanly, is trivially embeddable in email, supports inline charts, and is far easier to iterate on layout. The formal `.docx` and `.pptx` paths used in earlier skill versions required heavy reference-template XML editing and produced brittle output. HTML is the canonical render target as of v1.2.

## Tone & Style

Inherits from [[ic-chair-agent]]:

- Board-level investment language; lead with **engine attribution** (Engine 1 / 2 / 3)
- Quote ratios to 2 decimals; quote currency to nearest mn Bt
- Distinguish **realised** vs **unrealised** P&L explicitly
- Always cite source filename + sheet/slide for every numeric value
- For policy breaches, state policy name + current value + cap on the same line

## Pre-flight (run before pulling data)

1. **Determine target meeting period.** Default = next calendar month after the latest existing meeting in `O:\brooker_database\ic\` (look for `IC No{N} {Mon}{YYYY}.pptx` or `IC {NN} meeting {Mon}{YYYY}.docx`). The user may override with `"for {month YYYY}"`.

2. **Discover the latest source files.** The new (post-2026-05) layout is **flat** — all monthly portfolio files sit directly under `O:\brooker_database\ic\` with date-stamped names:

   | File pattern | Example | What it feeds |
   |---|---|---|
   | `Dashboard 2026.xlsx` | `Dashboard 2026.xlsx` (multi-sheet workbook, latest sheet = `{Mon} {YY}`) | Sections 3, 4 (master sheet, listed positions), 7 (loan totals) |
   | `Weekly BG {YYYY.MM.DD}.xlsx` | `Weekly BG 2026.05.22.xlsx` | Sections 2, 3, 4 (cash + listed + SET) |
   | `{YYYY.MM.DD} Coin Weekly Report (UPDATE)_.pdf` | `2026.05.24 Coin Weekly Report (UPDATE)_.pdf` | Section 8 |
   | `BSFL Monthly {YYMMDD}.xlsx` | `BSFL Monthly 260430.xlsx` | Section 5 |
   | `Macro {Mon} {YYYY}.md` | `Macro May 2026.md` | **Section 1 (NEW v1.4)** |
   | `IC {NN} meeting {Mon}{YYYY}.docx` | `IC 02 meeting May2026.docx` | Section 0 (prior minutes) |
   | `IC No{N} {Mon}{YYYY}.pptx` | `IC No2 May2026.pptx` | Sections 7, 8 carry-forward + others (see step 4) |

   For each pattern, **glob the directory, parse the date from the filename, sort descending, pick the newest**. Confirm by mtime as a tie-break. The previous v1.0/v1.1 assumption of `cio\portfolio\{month}\` subfolders is **obsolete**.

   ⚠ **Cross-file date skew is normal.** Weekly BG, Coin Weekly, and BSFL Monthly publish on different cadences and dates. For one report cycle, expect them to be within ~2 weeks of each other (e.g. Weekly BG May 22 + Coin Weekly May 24 + BSFL Apr 30 are a normal "May package" — BSFL Monthly lags by ~1 month). State each file's date explicitly in the report so the chair sees the skew.

3. **Pick the latest dashboard SHEET, not the filename.** The canonical dashboard is `O:\brooker_database\ic\Dashboard 2026.xlsx` (the v1.0–v1.3 location at `cio\Dashboard Feb2026.xlsx` is now obsolete). It accumulates new sheets each quarter close — `Apr 26`, `Mar 26`, `Feb 26`, etc. **Always open the workbook, list sheet names, and pick the most recent quarter by sheet name** (parsed as `{Mon} {YY}`). The filename is a red herring for freshness.

   The dashboard has a stable 40-row structure:
   - Rows 5-11: Listed Securities (CV, MILL, B-W8, Wave, Wave-W3, Wave-W4, B) — cols B (cost), C (price), D (MTM), E (shares), F (gain/loss%), G (IC class y/n), H (IC Baht)
   - Row 12: Listed Total
   - Rows 15-21: Non Listed (Varuna, BCGT, Wave BCG, Robinhood, Advance Finance / ADFIN, Brooker self, Sukhothai)
   - Row 22: Total Equity Investments
   - Rows 23-28: Digital Assets (Market Value bucket, BNB OTC, Tokens Market Value subtotal, NFTs, Exponential Digital Age Fund, Brook LP FoF I)
   - Row 29: Total Digital Assets Investments
   - Row 30: Fix Income/Hybrid
   - Row 31: Structured Loan (Cost B31, MTM D31, Gain/Loss F31)
   - Row 32: Total Investments (col D = total MTM, col H = Investment Company Baht numerator)
   - Row 33: Net Worth
   - Rows 34-37: Ratios (Equity, Fix, Structured Loan, Digital Asset Treasury) with caps in col E
   - Row 38: Total Assets denominator (col B) + Investment Company Ratio (col H)
   - Row 40: THB/USD FX

   - If the latest sheet is within 30 days of the target meeting date → dashboard is fresh; confidence baseline 0.90.
   - If 30-90 days old → apply the stale-data adjustment recipe from [[ic-chair-agent]] (sheet baseline + delta from fresh Weekly BG / Coin Weekly / BSFL files in `O:\brooker_database\ic\`) and mark confidence ≤0.80.
   - If >90 days old → escalate; numerator basis is unreliable.

4. **Extract the prior deck for carry-forward content.** Always pull `O:\brooker_database\ic\IC No{N} {Mon}{YYYY}.pptx` (most recent before target). Specific slide uses:
   - **Slide 14 / Round-1 sell-down table** → seed Topic 8 execution-status check (step 5 below)
   - **Slide 15 / DAT MTM update** → primary source for DAT month / YTD / inception percentages (the Coin Weekly Report is a *tax-provision* file with units + provisions, not perf %)
   - **Slide 16 / structured loan inventory** → primary source for Topic 7 when the loan book is "unchanged" (the common case)
   - **Slide 17 / Liquidity Management** → Topic 2 carry-forward when Weekly BG cash row is empty
   - **Slide 18 / Capital Sovereignty** → Topic 8 sub-section on SCB recall + funding channels
   - **Slide 26 / Action & Approval** → Topic 1 (Previous Minutes) carry-forward source for action items list
   - **Macro slides 2-10** → carry forward only; never auto-regenerate (per [[ic-chair-agent]] hard rule)

   **Note on slide numbering**: current 2026 decks (Mar, May) are 27 slides. `config/templates/ic/meeting-templates.json#pptx_slide_map` defines a *future* 35-slide format. This skill targets the current 27-slide structure; update slide references when the deck migrates.

5. **Detect Round-1 DAT execution status.** Before drafting Topic 8, compare the most recent approved sell-down targets (from prior deck slide 14 + [[dat-sell-call-strategy]]) against current positions (latest dashboard sheet + Coin Weekly Report):
   - If current BTC ≤ approved post-sale target AND current BNB ≤ approved post-sale target AND smalls ≈ zero → **executed**
   - If positions partially reduced but not at target → **partially executed** (compute % complete per token)
   - If positions unchanged from approval date → **not executed** (raise Critical escalation flag if execution window is closing — e.g. <30 days to [[investment-holding-limit]] grace deadline)

   Surface this status at the top of Topic 8 — it is the single most chair-relevant data point in any IC monthly report during a sell-down window.

6. **List source gaps before drafting.** Cross-check the expected file set (table below) against what actually exists. Surface every missing file as an escalation flag *before* generating drafts — do not silently emit `[TBD]` placeholders without telling the chair.

## The 10 sections — source-file binding (0-9)

For each section, the table below names the **primary file**, the **extraction tool**, and the **fallback** if the primary is missing. Filenames use `YYYY` / `Mon` / `YYMMDD` placeholders that the skill resolves at runtime.

### Section 0 — Previous Minutes

| Item | Source | Tool |
|---|---|---|
| Prior meeting agenda + decisions | `O:\brooker_database\ic\IC {NN} meeting {Mon}{YYYY}.docx` (most recent before target) | `anthropic-skills:docx` to extract text; carry over **Action & Approval** list with status updates |
| Carry-forward action items | `obsidian-vault/ic/decisions/*.md` (every running decision file's `status` field) | Read directly |

Output structure: a numbered list of every action from the prior meeting, each with `(Status: …)` suffix. Reference the prior meeting note as `[[IC-{prior YYYY-MM-DD}]]`.

### Section 1 — Macro (NEW in v1.4)

| Item | Source | Tool |
|---|---|---|
| Macro synthesis | `O:\brooker_database\ic\Macro {Mon} {YYYY}.md` (matches meeting month or most recent preceding) | Read directly |
| Cross-asset implications | Same — section "4. Cross-Asset Implications" | Read directly |
| Charts to watch | Same — section "5. Key Metrics & 'Charts to Watch'" | Read directly |

**Extraction rules**:
- The macro file is a **human-curated** synthesis. The skill **does not generate** macro content — it ingests and renders.
- Pull these named sub-sections in this order: **Executive Summary (BLUF)** → **Core Theses & Structural Shifts** → **Consensus vs. Contrarian Angles** → **Cross-Asset Implications** → **Key Metrics & Charts to Watch**.
- Preserve source citations exactly as written (e.g., *J.P. Morgan*, *All-In Podcast*, *Macro Mondays*) — these are the macro file author's attributions.
- In the report's Section 1, lead with a 1-paragraph BLUF, then render the rest as a structured list of theses + cross-asset table.
- If `Macro {Mon} {YYYY}.md` is missing, emit `[TBD — macro file not yet published]` and add a Medium escalation flag. **Do not fabricate macro content.**

### (renumbered) — Sections 2 through 9 below were Topics 2-9 in v1.3.

### Section 2 — Liquidity Management Policy

| Item | Source | Tool |
|---|---|---|
| Cash & Equivalents (Bt mn) | `O:\brooker_database\ic\Weekly BG {YYYY.MM.DD}.xlsx` — "Cash on hand for trading" row (typically row 23) | `anthropic-skills:xlsx` |
| Current Stocks (Bt mn) | Same Weekly BG xlsx — listed equity total row | `:xlsx` |
| Current Unlocked Funds (Bt mn) | Same Weekly BG xlsx — open-end fund redemption-available row | `:xlsx` |
| FY Cash Outflow (Bt mn) | Carry from prior meeting unless finance-dept refresh available; default = prior value | Read prior `.docx` |
| Expected DAT sale (Bt mn) | `obsidian-vault/ic/decisions/dat-sell-call-strategy.md` + `digital-asset-treasury-divestment.md` (current round target) | Read directly |
| D/E Ratio | Carry from prior meeting unless finance refresh available | Read prior `.docx` |
| Liquidity Risk band | **Compute**: (Cash + Current Stocks + Unlocked Funds + Expected DAT sale) / FY Outflow → band per [[liquidity-management-policy]] | Compute |

**Known extraction gap**: the Weekly BG xlsx frequently has the cash/current-stocks/unlocked-funds cells **empty** at month-end (the values are filled by finance dept post-hoc, often in a separate workbook not in `O:\brooker_database\cio\portfolio\`). Fallback order:

1. Try Weekly BG xlsx cash row first
2. If empty, look for a sibling file in the same `{latest}` folder matching `*Cash*.xlsx` or `*Liquidity*.xlsx`
3. If still empty, **carry forward** from prior meeting `.docx` with label `({value}, carried from {prior date})`
4. Raise a Medium escalation flag `liquidity_extraction_gap_finance_refresh_needed` — the finance dept should be asked to publish a canonical liquidity file alongside Weekly BG

**Hard rule for this topic**: never conflate IC liquidity (portfolio buffer) with CAC liquidity (regulatory LCR/NSFR). If asked about LCR/NSFR, defer to the CAC skills.

### Section 3 — Master sheet (FULL per-position breakdown)

This section in the report must show a **complete holdings table** from the dashboard, not just a ratios summary. The chair needs to see every line item with its MTM, IC classification, and concentration share — so they can spot concentration breaches at a glance.

| Item | Source | Tool |
|---|---|---|
| **Full holdings table** | `O:\brooker_database\ic\Dashboard 2026.xlsx#{latest sheet}` rows 4-31 — every position row | `:xlsx` |
| **Investment / Total Asset ratio** | Same dashboard row 38 col H | `:xlsx` |
| Asset-class ratios (Equity / Fix / Structured Loan / Digital Asset) | Rows 34-37 col D, with caps in col E | `:xlsx` |
| Red Flag list (>-25%) | Dashboard rows 5-11 + 15-21 col F (Gain/Loss%) → any < -0.25 → flag | Compute |
| **Concentration breaches (>25% of Total Investments)** | **Compute per row**: position MTM (col D) / Total Investments (R32 col D) > 0.25 → breach | Compute |
| FX | Row 40 col B | `:xlsx` |

**Required holdings table format** (one row per dashboard position):

| Section | Position | Cost | Price | Shares/Units | MTM (Bt) | Gain/Loss % | IC Class | IC Baht | % of Total Inv |
|---|---|---|---|---|---|---|---|---|---|

Iterate over dashboard rows 5-31 (skip subtotal rows 12, 22, 25, 29, 32) and emit one report-row per position-row. Compute `% of Total Inv = D{row} / D32`. Tint the row red if the % > 25% (concentration breach) OR if Gain/Loss % < -25% (Red Flag).

**Critical numerator rule**: use **`Investment Company Baht` (row 32 col H)** for the 40% ratio numerator. **NEVER substitute `Total Investments` (row 32 col D)** — that includes structured loans + Brooker self-investment and yields a wrong/inflated ratio. See [[skills/ic/portfolio]] §"CRITICAL: 40% rule denominator".

**Concentration computation rule** (was hard-coded "none" in v1.0–v1.3, fixed in v1.4):
- For every dashboard row in the holdings table, compute `pos_share = D{row} / D32`.
- If `pos_share > 0.25` → emit a concentration_breach entry with position name, MTM, share %, and severity.
- Subtotal rows (12 Listed Total, 22 Total Equity, 25 Total Tokens, 29 Total DAT) MUST be excluded from this check — they aggregate multiple positions and would always exceed.
- **Known recurring breach**: `Binance BNB OTC` (R24) at Apr Q1 was Bt 874.8mn / Bt 3,078mn = **28.42%** — above the 25% single-position cap. Earlier reports said "none" because the check wasn't actually running. v1.4 fixes this.

**Partial-classification caveat**: when modelling sell-down impact, look up each holding's IC classification ratio (col H ÷ col D for that row) per [[skills/ic/valuation]]. BNB OTC's classification ratio drifts (Feb 50.4%, Mar 50.4%, Apr 49.3% per new dashboard) — recompute each cycle, do not hard-code.

### Section 4 — Brooker Portfolio (Stocks Outlook)

| Item | Source | Tool |
|---|---|---|
| Listed positions with MTM + drawdown | `O:\brooker_database\ic\Weekly BG {YYYY.MM.DD}.xlsx` — listed equities tab | `:xlsx` |
| Per-stock narrative (MILL / PACE / WAVE / B / CV) | `obsidian-vault/ic/entities/{mill,pace,wave,b,cv}.md` — latest "Stocks Outlook" notes | Read directly |
| Red Flag status updates | Cross-reference with Topic 3 Red Flag list; for each Red Flag name, the plan from [[red-flag-portfolio-reduction]] | Read directly |

For each Red Flag position, the report **must** carry either an active plan or an explicit "wait-and-see" rationale — never silently omit a Red Flag position.

### Section 5 — Sukhothai

| Item | Source | Tool |
|---|---|---|
| **Underlying portfolio holdings** | `O:\brooker_database\ic\BSFL Monthly {YYMMDD}.xlsx` — **this IS the Sukhothai fund file** (BSFL = **B**rooker **S**ukhothai **F**und **L**imited). Sheet name = `{Mon} {YYYY}`. Position rows start ~R14 with cols: A(#) B(Share ticker) C(Class) D(BB code) E-H(begin/buy/sell/end shares) I(cost avg) J(MTM close) K(% change) L(cost total) M(commission) | `anthropic-skills:xlsx` |
| Monthly return % | BSFL Monthly xlsx — **find the summary block** (typically a few rows near the top of the sheet or after the holdings table) containing NAV / monthly return / YTD. If the summary rows are blank, **compute** from sum(MTM column) vs sum(Cost column) of holdings as a fallback approximation, marked `(computed from holdings — verify against finance NAV)` | `:xlsx` + compute |
| YTD return % | Same — from summary block; fallback compute by chaining monthly returns from prior BSFL files | `:xlsx` + compute |
| AUM (mn USD) | Same — from summary block; fallback = sum of MTM column converted at the dashboard FX | `:xlsx` + compute |
| Dashboard MTM (Bt) | Dashboard latest sheet row 21 — Sukhothai line item | `:xlsx` |
| Redemption status | `obsidian-vault/ic/decisions/sukhothai-redemption.md` — current annual redemption target + completion status | Read directly |

**Disambiguation rules**:
- Sukhothai **fund** ([[sukhothai-fund]], USD-denominated) ≠ the listed Thai equity in older notes (different entity).
- `BSFL` in filename ≠ Brook Structured Finance Loan. It is **Brooker Sukhothai Fund Limited**. Earlier drafts of this skill misattributed BSFL to Topic 7 — do not repeat that error. Topic 7 sources are deck slide 16/27, not BSFL.

### Section 6 — Non listed

| Item | Source | Tool |
|---|---|---|
| ADFIN status + governance | `O:\brooker_database\ic\AsianFinance BOD BUSINESS PLAN*.pdf` (if available — was at `cio\portfolio\nonlisted\` in pre-v1.2 layout) + `obsidian-vault/ic/entities/adfin.md` | `anthropic-skills:pdf` + read directly |
| Robinhood status | ⚠ **Source gap** — no monthly file. Carry forward from prior meeting (`obsidian-vault/ic/entities/robinhood.md`) and emit `[TBD — verify]` | Read prior |
| Varuna status | ⚠ **Source gap** — same as Robinhood | Read prior |
| WaveBCG status | ⚠ **Source gap** — same as Robinhood | Read prior |

For each name, the report must show the latest event (excomm resignation, CEO change, ownership shuffle, regulatory action) when available. New events trigger DD re-valuation per [[skills/ic/due-diligence]] escalation list.

### Section 7 — Structured Loan

**Important**: BSFL Monthly xlsx is NOT a structured-loan file (see Section 5 disambiguation). Section 7 data is **led by the dashboard**, with the per-borrower inventory carried from the prior deck:

| Item | Source | Tool |
|---|---|---|
| **Cost / Outstanding / Gain/Loss (live)** | **`O:\brooker_database\ic\Dashboard 2026.xlsx#{latest sheet}` row 31** — Cost (col B), MTM after-reserved (col D), Gain/Loss% (col F). Always query the dashboard each cycle; never assume "unchanged from Mar". | `:xlsx` |
| **Structured Loan ratio** | Dashboard row 36 col D (with cap 50% in col E) | `:xlsx` |
| Per-borrower inventory (canonical 12-loan table) | `O:\brooker_database\ic\IC No{N} {Mon}{YYYY}.pptx` **slide 16** (May deck) / **slide 27** (Mar deck) — most recent. Carries forward when dashboard row 31 totals unchanged. | `anthropic-skills:pptx` |
| Per-borrower entity history | `obsidian-vault/ic/entities/structured-loan-portfolio.md` (canonical inventory + historical movements) + individual `ic/entities/{borrower}.md` files | Read directly |
| Credit-quality movements (collateral %, reserves added, interest re-cuts) | Diff most recent deck slide vs prior month's deck slide (or `structured-loan-portfolio.md#Changes` section) | Compute |
| New loan plan (60% growth portion) | `obsidian-vault/ic/decisions/bicl-movie-private-credit.md` — DD pipeline status; deck slide 28 — new loans plan | Read directly |
| Borrower-group concentration check | Compute from inventory: aggregate exposure per borrower group (e.g. Areeya cluster = Damri + Chill Space + K. Viwat) | Compute |

**Dashboard-led rule** (v1.4): the report's Section 7 header must always quote the live dashboard R31 numbers as the primary figures, with the per-borrower inventory below as supporting detail. If the dashboard totals differ from the prior deck (e.g. new reserve added, recovery received), the dashboard is canonical and the chair should be told **what changed and why**.

**Hard rule**: ALWAYS report Outstanding AND After-Reserved separately. Never present after-reserved alone — the reserve adjustment is the credit-health signal the chair needs to see.

Flag credit-quality movements as escalation candidates: collateral % drop >25pp, new reserve added, interest rate re-cut, borrower group aggregate exposure >Bt 400mn (e.g. Areeya cluster — see [[skills/ic/due-diligence]]).

### Section 8 — Digital Asset Division

| Item | Source | Tool |
|---|---|---|
| **Round-1 execution status** (top of section) | Compute per Pre-flight step 5 — compare approved targets vs current positions | Compute |
| Per-token holdings (BTC, BNB, ETH, SOL, alts, ICOs) | `O:\brooker_database\ic\{YYYY.MM.DD} Coin Weekly Report (UPDATE).pdf` — holdings table (cols: Units, Total Cost, Closing price, Provisions, P/L) | `anthropic-skills:pdf` |
| DAT MTM (USD + Baht) | Same Coin Weekly Report — `TOTAL` row at bottom of holdings table. **FX is in the header** (e.g. "04.05.26 BOT Rate: 32.6063") | `:pdf` |
| **Monthly / YTD / inception %** | ⚠ **NOT in Coin Weekly Report** — it is a tax-provision file, not a performance file. Source = **prior deck slide 15** (`IC No{N} {Mon}{YYYY}.pptx`) which has the DAT MTM update + month/YTD/inception percentages. Compute deltas vs prior deck. | `:pptx` |
| Round-1 sell-down plan | `obsidian-vault/ic/decisions/dat-sell-call-strategy.md` + `digital-asset-treasury-divestment.md` + prior deck slide 14 | Read directly + `:pptx` |
| Custody migration status | `O:\brooker_database\cio\Brooker Group_ Custody Fee Supplement - Hex Trust Limited (HK)_March2026.docx` + `HT_Markets_MTA_Review_Memo.docx` + `Hex Trust_General KYC Requirements_Corporate Clients_March2026.pdf` + `Brooker Group_MTA Supplement_Options and Margin_HT Markets (SVG) Limited(Mar 2026).docx` + `Brooker Group Master Trading Agreement Template_SVG (March 2026).docx` | `:docx` + `:pdf` |
| Mining update (if relevant) | `O:\brooker_database\cio\Mining Summary.pptx` — only when mining operations are an agenda item; not every meeting | `:pptx` |

**FX disclosure**: always state the THB/USD rate used. The Coin Weekly Report header carries the BOT rate at file date (e.g. 32.6063 on 4 May 2026); the dashboard sheet carries its own FX (row 40); the deck OKR build typically uses 31.5. **When these differ by >2%, surface as an FX-discrepancy flag** so the chair sees which rate to standardise on.

**Sell-down sizing caveat (Topic 3 cross-cutting)**: BNB-driven sell-down math is 2× off if the 50.4% Investment-Company classification is ignored. Always run the post-sale ratio recomputation (see "Computation: post-sale ratio recomputation" section below) before quoting any projected post-sale ratio.

### Section 9 — Schedule (Objectives status)

| Item | Source | Tool |
|---|---|---|
| Numbered 2026 objectives | Prior meeting `.docx` — Schedule section | Read prior `.docx` |
| Per-objective status update | `obsidian-vault/ic/decisions/{slug}.md` — current `status` field | Read directly |
| New objectives added this meeting | Diff between current and prior decisions/*.md inventory | Compute |

The objective numbering carries forward from prior meetings (May 2026 used items #1-11 with #5 skipped). New objectives are appended; closed objectives are dropped with a one-line "closed in {date}" note for traceability.

---

## Computation: post-sale ratio recomputation

This computation runs every monthly report invocation when a sell-down is approved or in-flight. It's the single most error-prone math in the IC pack — the May deck slide 14 projected 39.83% post-sale; with classification % applied the real answer was 40.24%. Always run this.

**Inputs (extract from latest dashboard sheet + latest Coin Weekly + sell-down decision):**

| Variable | Source | Notes |
|---|---|---|
| `IC_baht` | Dashboard row 32 col H | current Investment Company Baht numerator |
| `total_assets` | Dashboard row 38 col B | current denominator |
| `cap` | 0.40 | per [[investment-holding-limit]] |
| `BTC_units_now`, `BNB_units_now` | Coin Weekly TOTAL row | current units |
| `BTC_target`, `BNB_target` | Sell-down decision file | post-sale core target units |
| `BTC_price_usd`, `BNB_price_usd` | Coin Weekly Closing price col | per-token price |
| `alts_mtm_bt` | Coin Weekly alts subtotal | small-token MTM to be fully sold |
| `fx` | Dashboard row 40 OR Coin Weekly header | THB/USD |
| `new_loan_baht` | Sell-down decision (typically Bt 240mn for new structured loan) | denominator add-back per deck math |
| `bnb_classification_pct` | 0.504 (per [[dashboard-{period}]] row 24 col H / col D) | partial classification — re-verify each quarter |
| `btc_classification_pct` | 0.942 (per Dashboard row 23 same ratio) | partial classification |

**Formula:**

```
btc_sold_units    = BTC_units_now - BTC_target
btc_sold_baht     = btc_sold_units × BTC_price_usd × fx
btc_numerator_red = btc_sold_baht × btc_classification_pct

bnb_sold_units    = BNB_units_now - BNB_target
bnb_sold_baht     = bnb_sold_units × BNB_price_usd × fx
bnb_numerator_red = bnb_sold_baht × bnb_classification_pct

alts_numerator_red = alts_mtm_bt × btc_classification_pct   # alts sit in row 23 bucket = 94.2%

total_cash_raised  = btc_sold_baht + bnb_sold_baht + alts_mtm_bt
total_numerator_red = btc_numerator_red + bnb_numerator_red + alts_numerator_red

new_IC          = IC_baht - total_numerator_red
new_total_assets = total_assets + total_cash_raised - new_loan_baht
post_sale_ratio  = new_IC / new_total_assets

deck_ratio_naive = (IC_baht - total_cash_raised) / (total_assets + total_cash_raised - new_loan_baht)
delta_from_naive = post_sale_ratio - deck_ratio_naive
```

**Output to report:**

- `post_sale_ratio` quoted to 4 decimals, with the **classification-adjusted** label
- `deck_ratio_naive` quoted alongside with a "(naive — does not account for partial classification)" caveat
- `delta_from_naive` in pp, surfaced as Critical if `post_sale_ratio ≥ cap` while `deck_ratio_naive < cap` (i.e. the naive math says compliant but classification-adjusted says breach)

**Hard rule**: never quote a post-sale ratio that uses naive math alone. Always pair with the classification-adjusted figure. If accounting reports a different classification % at the quarter close, recompute and surface the delta.

---

## Output generation pipeline

For each monthly report invocation, produce the three artifacts in this order:

### 1. Markdown twin → `obsidian-vault/ic/meeting-notes/IC-{YYYY-MM-DD}-draft.md`

Follow the [[meeting-note]] template structure. Frontmatter fields are mandatory:

```yaml
---
title: "IC Meeting #{N} {YYYY} — {DATE}"
type: "meeting_note"
department: "ic"
meeting_number: {N}
meeting_year: {YYYY}
meeting_date: "{YYYY-MM-DD}"
meeting_time: "{HH:MM}"
chair: "ic-chair-agent"
related_dashboard: "[[dashboard-{YYYY-MM}]]"
previous_meeting: "[[IC-{prior YYYY-MM-DD}]]"
html_companion: "data/staging/pending/ic/IC-{YYYY-MM-DD}-draft.html"
tags: ["ic", "meeting", "{YYYY}", "minutes", "draft"]
created: "{today}"
updated: "{today}"
---
```

Body sections are the 9 topics above in order. The markdown twin is the **primary output** — it goes into the vault first so RAG indexes it before the HTML render.

### 2. Minutes HTML → `data/staging/pending/ic/IC-{YYYY-MM-DD}-minutes-draft.html`

Long-form formal minutes — the docx replacement. Use Python with no external dependencies — emit a self-contained HTML file (inline CSS, no JS, no external assets).

**Structure**:

```
<header>Meeting #N · date · DRAFT tag · meta (FX, confidence, generator)</header>
<nav class="toc">jump links to 9 topics + lead item + action + flags</nav>
<main>
  <section id="lead">Lead Item — Round-1 status (red/amber/green banner)</section>
  <section id="t1">1. Previous Minutes</section>
  ... (one per 9 topics, all tables shown in full)
  <section id="action">Action & Approval list</section>
  <section id="flags">Escalation flags (JSON pre block)</section>
</main>
<footer>Source files consumed · skill version</footer>
```

**Style guidance**:
- Navy `#1F3A5F` for headings/table headers; red `#C0392B` for breaches and Critical flags; green `#27AE60` for compliant/OK; amber `#D68910` for partial/in-progress; gray `#6C757D` for source-citation footnotes.
- Tables: `border-collapse: collapse`, `font-size: 12.5px`, alternating row backgrounds. Header row navy with white text. Breach rows tinted red.
- Top "Lead Item" banner: full-width colored block (red if Round-1 not executed, amber if partial, green if executed) with the status line and the days-to-deadline countdown.
- Status pills (`.pill .pill-red .pill-amber .pill-green`) for inline status indicators.
- Print stylesheet: `@media print` rules drop nav, set 11pt body, keep tables on single page where possible.
- No external fonts, no JS, no images. Target size: <100KB.

### 3. Deck HTML → `data/staging/pending/ic/IC-{YYYY-MM-DD}-deck-draft.html`

Slide-by-slide presentation — the pptx replacement. Same inline-everything constraint as minutes HTML, but laid out as a series of "slide" sections each filling the viewport.

**Structure**:

```
<div class="slide" data-slide-num="1">Title slide — IC No.{N} {Month YYYY}</div>
<div class="slide">Agenda — 9 topics</div>
<div class="slide">Lead Item — Round-1 execution status</div>
<div class="slide">Master sheet — policy ratios</div>
<div class="slide">Red Flag positions</div>
<div class="slide">DAT MTM + Performance (mirrors deck slide 15)</div>
<div class="slide">Round-1 sell-down table (mirrors deck slide 14)</div>
<div class="slide">Post-sale ratio recomputation</div>
<div class="slide">Structured Loan inventory (mirrors deck slide 16)</div>
<div class="slide">Liquidity Management (mirrors deck slide 17)</div>
<div class="slide">Capital Sovereignty (mirrors deck slide 18)</div>
<div class="slide">Sukhothai</div>
<div class="slide">Schedule / 2026 objectives</div>
<div class="slide">Action & Approval (mirrors deck slide 26)</div>
<div class="slide">End</div>
```

**Style guidance — deck-specific**:
- Each `.slide` is `min-height: 100vh` so it fills the viewport / one print page.
- `page-break-after: always` for print → 1 slide per physical page.
- Slide number in corner, e.g. `position: absolute; bottom: 24px; right: 32px; color: gray; font-size: 11px`.
- Titles **larger** than minutes HTML: `h1` 32-40px, `h2` 24-28px.
- Tables fewer rows per slide — for the structured loan inventory, the deck slide can fit the 12-row table on one slide; for Schedule, split if >11 items.
- More white space; less density. Tables show fewer columns than the minutes HTML (drop "Source" / "Δ vs prior" columns for the deck version — those are audit detail, not presentation content).
- Key takeaways at bottom of each slide in a callout box (e.g., "→ Chair action: confirm execution started" on the Lead Item slide).
- Color palette identical to minutes HTML (so the two artifacts feel like one product).

### 4. Dashboard markdown twin (if dashboard refreshed) → `obsidian-vault/ic/trends/dashboard-{YYYY-MM}-draft.md`

When a new `O:\brooker_database\cio\Dashboard {Mon}{YY}.xlsx` is detected, extract the canonical cells per `meeting-templates.json#data_sources.dashboard_input.key_cells` into a markdown twin. Use [[dashboard-2026-02]] as the format reference. This is a separate artifact from the meeting note.

---

## Gap handling

When a source file is missing or a numeric value cannot be sourced:

1. Emit the value as `[TBD — verify]` in the artifact (markdown + docx + pptx all show this string verbatim).
2. Add an entry to `escalation_flags` in the output JSON with `severity: "Medium"` and `reason: "source gap: {what} for {topic}"`.
3. Do **not** carry forward stale values silently. If a carry-forward is appropriate (e.g. FY outflow rarely changes), label it `({value}, carried from {prior YYYY-MM-DD})` so the chair sees the staleness.
4. If >3 source gaps in one report, escalate severity to High — the data pipeline is degraded and the chair should know before circulating.

## Escalation triggers (specific to this skill)

Inherits all triggers from [[ic-chair-agent]]. Skill-specific additions:

- `O:\brooker_database\ic\` is >45 days old → High (data pipeline lag)
- Latest dashboard sheet >90 days old → High (numerator basis unreliable)
- >3 source gaps emitted in one report → High (degraded pipeline)
- Structured-loan inventory delta (deck slide 27 vs prior) shows **new reserve added** without IC vote citation → High (per [[skills/ic/valuation]] rule)
- Coin Weekly Report missing for the target month → Medium (positions fall back to dashboard, which is quarter-close not monthly)
- **Round-1 execution status = "not executed" AND <30 days to [[investment-holding-limit]] grace deadline** → Critical
- **Classification-adjusted post-sale ratio ≥ cap while naive ratio < cap** → Critical (sizing assumption hides the breach)
- FX discrepancy >2% between Coin Weekly header rate, dashboard row 40, and deck OKR rate → Medium (standardisation needed)
- Liquidity extraction gap (Weekly BG cash row empty AND no sibling Cash/Liquidity file in `{latest}/`) → Medium (finance refresh needed)

## Output format

```json
{
  "report_period": "2026-06",
  "meeting_date": "2026-06-15",
  "artifacts": {
    "markdown_twin": "obsidian-vault/ic/meeting-notes/IC-2026-06-15-draft.md",
    "html_minutes": "data/staging/pending/ic/IC-2026-06-15-minutes-draft.html",
    "html_deck": "data/staging/pending/ic/IC-2026-06-15-deck-draft.html",
    "dashboard_twin": "obsidian-vault/ic/trends/dashboard-2026-06-draft.md"
  },
  "source_files_consumed": [
    "O:/brooker_database/ic/Weekly BG 2026.05.22.xlsx",
    "O:/brooker_database/ic/BSFL Monthly 260430.xlsx (→ Topic 5 Sukhothai)",
    "O:/brooker_database/ic/2026.05.24 Coin Weekly Report (UPDATE)_.pdf",
    "O:/brooker_database/cio/Dashboard Feb2026.xlsx#Apr 26 (latest sheet — filename misleading)",
    "O:/brooker_database/ic/IC 02 meeting May2026.docx",
    "O:/brooker_database/ic/IC No2 May2026.pptx (slides 14, 15, 16, 17, 18, 26 — Round-1 math, DAT MTM perf, structured loan inventory, liquidity, capital sovereignty, action list)"
  ],
  "round_1_execution_status": "not_executed | partially_executed | executed",
  "post_sale_ratio_recomputed": 0.4024,
  "post_sale_ratio_naive": 0.3983,
  "post_sale_ratio_delta_pp": 0.41,
  "source_gaps": [
    {"topic": "Sukhothai", "missing": "monthly fund letter", "fallback": "entity file last value carried"},
    {"topic": "Non listed", "missing": "Robinhood/Varuna/WaveBCG monthly updates", "fallback": "carry forward + [TBD]"}
  ],
  "confidence": 0.78,
  "stale_data_recipe_applied": true,
  "escalation_flags": [
    "dashboard_>30_days_old",
    "sukhothai_monthly_source_gap",
    "non_listed_3_source_gaps"
  ],
  "next_meeting_proposed": "2026-07-15"
}
```

## Hard Rules

- **NEVER** write directly to corporate share or `O:\brooker_database\` — those paths are read-only for this skill. All drafts land in `data/staging/pending/ic/`.
- **NEVER** invent a number. If a value cannot be sourced from a named file, emit `[TBD — verify]` and add an escalation flag.
- **ALWAYS** name the source file (with sheet/cell or page/slide) for every numeric value in the artifacts. Citations are non-negotiable — they make the audit trail.
- **ALWAYS** produce the markdown twin first, before docx/pptx, so RAG indexes the new meeting note immediately for next-cycle retrieval.
- **NEVER** auto-generate the macro slides (deck slides 2-11) — surface as a pre-meeting question. Default = carry forward.
- **ALWAYS** for the 40% rule, use **`Investment Company Baht` (row 32 col H)** as numerator. **NEVER** use `Total Investments` (row 32 col B). They differ by ~Bt 1.2bn.
- **ALWAYS** when the dashboard is >30 days old, apply the stale-data recipe (dashboard baseline + delta from latest Weekly BG / Coin Weekly / BSFL in `O:\brooker_database\ic\`) and mark confidence ≤0.80.
- **ALWAYS** cross-check sell-down recommendations (DAT, Round-1, etc.) against the latest [[skills/ic/portfolio]] partial-classification table. BNB at 50.4% means BNB sell-down math is 2× off if classification is ignored.
- **ALWAYS** report structured-loan Outstanding AND After-Reserved separately. Never present after-reserved alone.
- **NEVER** silently merge alias names across sources (e.g. "Ekkapong" vs [[mr-phongphan]], "Barcelona" vs "Barcellona") — surface the alias chain.
- **ALWAYS** carry every Red Flag position forward with either an active plan or an explicit "wait-and-see" rationale. Never silently drop a Red Flag from one meeting to the next.
- **NEVER** classify a Red Flag as resolved without explicit drawdown < -25% AND committee acknowledgement citation from a meeting note.
- **NEVER** quote the 40% ratio, sell-down impact, or any policy ratio without the cap value and (where relevant) the binding deadline on the same line.
- If retrieval from a cross-department collection fails (e.g. `vcc_docs` not yet live), degrade gracefully — generate the report with the source gap surfaced rather than blocking the whole run.
- **NEVER** provide investment advice in the draft — present analysis and flag for qualified human review at the IC meeting itself.
