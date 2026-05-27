# /compose-xlsx Endpoint Specification

**Module:** `services/shared/xlsx_compose.py`
**Planned endpoint:** `POST /compose-xlsx` (on `deck-writer`, port TBD — wiring is a later step)
**Status:** library complete; HTTP wiring pending.

---

## Overview

Free-form Excel workbook builder.  Given a JSON spec, produces a polished
`.xlsx` with multiple sheets, formulas, column formatting, optional charts,
and the Brooker house style (navy headers, alternating row bands, grey
borders, Calibri 11).

This is the *free-form* path — the caller owns the entire structure.
For filling `{{placeholders}}` into a user-authored template, use
`services/shared/office_template.py → render_xlsx()` instead.

---

## Endpoint shape

```
POST /compose-xlsx
Content-Type: application/json

Body: XlsxComposeSpec (see schema below)

Response 200:
  Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
  Content-Disposition: attachment; filename="<title or compose_output>.xlsx"

  — OR —

  Content-Type: application/json
  { "artefact": "/data/staging/pending/<uuid>.xlsx",
    "sheets": <N>,
    "cells_written": <N>,
    "charts": <N> }

  (exact response mode determined by caller; artefact path for agent workflows)

Response 422: { "detail": "<validation error message naming sheet/cell>" }
Response 413: { "detail": "spec would write <N> cells; maximum is 100,000" }
```

---

## Request body schema

```json
{
  "sheets": [SheetSpec, ...],    // required, 1–20 sheets
  "charts": [ChartEmbedSpec, ...],  // optional
  "metadata": {                    // optional
    "title":   "string",
    "author":  "string",
    "subject": "string",
    "description": "string",
    "keywords":    "string",
    "category":    "string",
    "company":     "string"   // appended to description (no native xlsx field)
  }
}
```

### SheetSpec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Sheet tab name.  Trimmed to 31 chars; `[]:*?/\` replaced with `_`. |
| `headers` | list[string] | no | Header row.  If present, no data row may have more columns. |
| `rows` | list[list] | yes | Data rows.  Cells may be strings, numbers, booleans, null, or formula strings (starting with `=`). |
| `formulas` | dict[cellRef, string] | no | Override specific cells with formulas, e.g. `{"D2": "=B2*C2"}`.  Values must start with `=`. |
| `column_widths` | dict[colLetter, float] | no | e.g. `{"A": 12, "B": 18}` |
| `column_formats` | dict[colLetter, string] | no | Excel number formats applied to every data cell in the column, e.g. `{"B": "#,##0.00", "C": "0.0%"}` |
| `freeze_panes` | string | no | Cell address for freeze split, e.g. `"A2"` to freeze the header row. |
| `conditional_format` | list[ConditionalFormatRule] | no | See section below. |
| `style` | `"brooker"` \| `"plain"` | no | Default `"brooker"`.  `"plain"` skips all styling. |

### ConditionalFormatRule

Three supported types:

```json
// Data bar (fill proportion relative to min/max in range)
{"range": "B2:B100", "type": "data_bar", "color": "blue"}
// color: "blue" | "green" | "red" | "orange" | any hex string e.g. "638EC6"

// Two-colour scale
{"range": "C2:C100", "type": "color_scale",
 "min_color": "#FFFFFF", "max_color": "#0F3D5C"}

// Cell-value comparison
{"range": "D2:D100", "type": "greater_than", "value": 100, "fill": "#D9EAD3"}
{"range": "D2:D100", "type": "less_than",    "value": 0,   "fill": "#F4CCCC"}
```

### ChartEmbedSpec

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `sheet` | string | yes | Name of the sheet to embed the chart in. |
| `kind` | `"bar"` \| `"line"` \| `"pie"` | yes | Chart type. |
| `data_range` | string | yes | e.g. `"Summary!B1:B10"` |
| `category_range` | string | no | e.g. `"Summary!A2:A10"` |
| `title` | string | no | Chart title. |
| `anchor` | string | no | Top-left anchor cell, e.g. `"F2"`.  Default `"F2"`. |

---

## Constraints

| Constraint | Limit |
|------------|-------|
| Max sheets | 20 |
| Max total cells (data + formulas + headers) | 100,000 |
| Max output file size | 50 MB (enforced at filesystem write; validation is cell-count only) |
| Sheet name length | 31 characters (Excel hard limit) |
| Chart kinds | `bar`, `line`, `pie` |
| Conditional format types | `data_bar`, `color_scale`, `greater_than`, `less_than` |

---

## Brooker house style

Applied to every sheet where `style == "brooker"` (the default):

- **Header row:** bold, white text (`#FFFFFF`) on Brooker navy (`#0F3D5C`), centred.
- **Data rows:** alternating bands — even rows have light grey fill (`#F2F2F2`).
- **Borders:** thin grey (`#D9D9D9`) around every cell with content.
- **Default font:** Calibri 11 on all data cells.
- **Title row:** if `metadata.title` is set, row 1 of the *first sheet only* becomes a merged title cell (bold 14pt, navy text); headers and data shift down by one row.

---

## Example 1 — Simple table

```json
{
  "sheets": [
    {
      "name": "Q1 Revenue",
      "headers": ["Region", "Revenue (THB M)", "vs Budget"],
      "rows": [
        ["North",  45.2, "+3.1%"],
        ["South",  38.7, "-1.4%"],
        ["East",   52.1, "+7.8%"],
        ["West",   29.4, "-0.2%"]
      ],
      "column_widths": {"A": 14, "B": 20, "C": 14},
      "column_formats": {"B": "#,##0.00"},
      "freeze_panes": "A2"
    }
  ],
  "metadata": {
    "title": "Q1 2026 Revenue Summary",
    "author": "Finance Agent",
    "subject": "Finance"
  }
}
```

---

## Example 2 — Formula-driven financial model

```json
{
  "sheets": [
    {
      "name": "P&L Model",
      "headers": ["Line Item", "Jan", "Feb", "Mar", "Q1 Total"],
      "rows": [
        ["Revenue",        1200000, 1350000, 1280000, null],
        ["Cost of Sales",   600000,  700000,  660000, null],
        ["Gross Profit",      null,     null,    null, null],
        ["OpEx",            250000,  270000,  265000, null],
        ["EBIT",              null,     null,    null, null]
      ],
      "formulas": {
        "B4": "=B2-B3",  "C4": "=C2-C3",  "D4": "=D2-D3",
        "B6": "=B4-B5",  "C6": "=C4-C5",  "D6": "=D4-D5",
        "E2": "=SUM(B2:D2)",
        "E3": "=SUM(B3:D3)",
        "E4": "=SUM(B4:D4)",
        "E5": "=SUM(B5:D5)",
        "E6": "=SUM(B6:D6)"
      },
      "column_widths": {"A": 20, "B": 16, "C": 16, "D": 16, "E": 16},
      "column_formats": {"B": "#,##0", "C": "#,##0", "D": "#,##0", "E": "#,##0"},
      "freeze_panes": "B2",
      "conditional_format": [
        {"range": "E2:E6", "type": "data_bar", "color": "blue"}
      ]
    }
  ],
  "metadata": {
    "title": "P&L Model — Q1 2026",
    "author": "CFO Agent"
  }
}
```

---

## Example 3 — Multi-sheet workbook with chart

```json
{
  "sheets": [
    {
      "name": "Summary",
      "headers": ["Month", "Revenue", "Costs", "Profit"],
      "rows": [
        ["Jan 2026", 1200000, 900000, 300000],
        ["Feb 2026", 1350000, 980000, 370000],
        ["Mar 2026", 1280000, 940000, 340000],
        ["Apr 2026", 1410000, 1020000, 390000]
      ],
      "formulas": {
        "D2": "=B2-C2", "D3": "=B3-C3",
        "D4": "=B4-C4", "D5": "=B5-C5"
      },
      "column_widths": {"A": 12, "B": 18, "C": 18, "D": 18},
      "column_formats": {"B": "#,##0", "C": "#,##0", "D": "#,##0"},
      "freeze_panes": "A2",
      "conditional_format": [
        {"range": "D2:D5", "type": "greater_than", "value": 350000, "fill": "#D9EAD3"},
        {"range": "D2:D5", "type": "less_than",    "value": 320000, "fill": "#F4CCCC"}
      ]
    },
    {
      "name": "Detail",
      "headers": ["Category", "Amount", "% of Revenue"],
      "rows": [
        ["Salaries",    540000, null],
        ["Marketing",   180000, null],
        ["Infra",        90000, null],
        ["Other",        90000, null]
      ],
      "formulas": {
        "C2": "=B2/Summary!B2",
        "C3": "=B3/Summary!B2",
        "C4": "=B4/Summary!B2",
        "C5": "=B5/Summary!B2"
      },
      "column_formats": {"C": "0.0%"}
    }
  ],
  "charts": [
    {
      "sheet": "Summary",
      "kind": "bar",
      "data_range": "Summary!B1:D5",
      "category_range": "Summary!A2:A5",
      "title": "Revenue vs Costs vs Profit",
      "anchor": "F2"
    }
  ],
  "metadata": {
    "title": "Monthly P&L Dashboard — Q1 2026",
    "author": "Finance Agent",
    "company": "Brooker Group",
    "subject": "Finance"
  }
}
```

---

## Integration pattern

```python
from services.shared.xlsx_compose import compose_xlsx

result = compose_xlsx(spec, "/data/staging/pending/report_q1.xlsx")
# result → {"out": "/data/staging/pending/report_q1.xlsx",
#            "sheets": 2, "cells_written": 48, "charts": 1}
```

Writes go to `/data/staging/pending/` — never to `/data/mirror/` (read-only zone).

---

## Public Python API

```python
from services.shared.xlsx_compose import compose_xlsx, validate_xlsx_spec

# Validate a raw dict before use (raises ValueError on bad input)
normalised_spec = validate_xlsx_spec(raw_dict)

# Build the workbook
result = compose_xlsx(normalised_spec, out_path)
# Returns: {"out": str, "sheets": int, "cells_written": int, "charts": int}
```

`validate_xlsx_spec` normalises in place:
- Trims sheet names to 31 chars and replaces `[]:*?/\` with `_`.
- Fills `style` default (`"brooker"`).
- Raises `ValueError` naming the offending sheet/row on first violation.
