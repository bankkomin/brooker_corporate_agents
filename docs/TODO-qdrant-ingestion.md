# TODO: Qdrant Ingestion Plan — Brook Limited Partners FoF I Documents

> Source folder: `D:\Brook LImited Partners Fund of Funds\`
> Target: Qdrant vector collections + PostgreSQL `ingested_documents` table
> Service: `rag-ingestion` (port 3004)
> Embedding model: Gemini text-embedding-001 (768-dim) or Qwen 3.5 9B (4096-dim)
> Chunk config: `chunk_size=512, chunk_overlap=128`

---

## Priority Legend

- **P0** — Must ingest before any agent queries (foundational context)
- **P1** — High value, ingest in first batch
- **P2** — Ingest when department agents are active
- **P3** — Nice to have, ingest as backlog

---

## 1. CAC (Capital Allocation Committee) — `cac_docs` Collection

These documents contain capital allocation terms, fund commitments, financial controls,
and governance structures directly relevant to the CAC orchestrator and specialist agents
(liquidity, capital, ALM, funding).

| # | PDF File | Priority | Status | Notes |
|---|----------|----------|--------|-------|
| 1 | `1.1 Brook Limited Partners FoF I - Presentation.pdf` | P0 | [ ] | 66-page investor deck. Contains fund terms, GP commitment ($11.2M seeded + $10M additional), concentration limits (20% flagship / 10% emerging), fee structure (1.5% mgmt, tiered carry). **Critical for capital-agent and funding-agent context.** |
| 2 | `1.2 Brook Limited Partners FoF I - Fund Synopsis.pdf` | P1 | [ ] | 1-page fact sheet. Quick reference for fund metadata. |
| 3 | `1.3 Brook Limited Partners FoF I - Summary of Terms.pdf` | P1 | [ ] | 1-page term sheet. Fee structure, fund lifecycle dates, commitment parameters. |
| 4 | `3.1 Brook Limited Partners FoF1 - DDQ - 2026.pdf` | P0 | [ ] | 32-page DDQ. Contains compliance framework, operational controls (dual-authorization "4-eye principle"), leverage limits (40% NAV), governance structure, insurance (D&O $1M), IT security policies, reporting cadence. **Critical for all CAC agents — compliance, risk, governance.** |
| 5 | `4.1.1.3 Master Fund Financial Statements.pdf` | P1 | [ ] | Binance Labs master fund financials. ALCO capital review reference. |
| 6 | `5.2 EY Audit Appointment Letter.pdf` | P1 | [ ] | EY engagement letter. Auditor identity, contact (Rowena Ferareza), compliance with VCC Act Section 14. |
| 7 | `5.3 Master Services Agreement - Formidium.pdf` | P0 | [ ] | 32-page MSA with fund administrator. NAV calculation methodology, AML/CFT responsibilities, fee terms, liability limits, bank account control procedures. **Critical for operations and compliance queries.** |
| 8 | `5.4 Board Resolution & Cash Control Mandate - DBS Bank.pdf` | P0 | [ ] | Board resolution defining authorized signatories, dual-authorization for wire transfers, banking mandate. **Critical for capital-agent and liquidity-agent — defines who can authorize transactions.** |

### After Ingestion — Verify Agent Queries

- [ ] `liquidity-agent` can answer: "What are the cash control procedures for DBS Bank?"
- [ ] `capital-agent` can answer: "What is the GP commitment breakdown?"
- [ ] `compliance` can answer: "Who is the auditor and what compliance framework applies?"

---

## 2. Investment Committee (`invest_docs`) Collection

Documents containing fund performance data, portfolio analysis, investment memos,
and manager evaluations for the investment committee agents.

| # | PDF File | Priority | Status | Notes |
|---|----------|----------|--------|-------|
| 1 | `4.2.1.1 Binance Labs Investor Report Q3 2025.pdf` | P0 | [ ] | Full quarterly report. 68 portfolio companies, $160.7M invested, 2.7x MOIC. Top performers: Sui 11.1x, SPACE ID 37.7x. MTM trend data. **Rich data for portfolio analysis agent.** |
| 2 | `9.2 Internal Investment Memo_Maven11_BVFIII.pdf` | P0 | [ ] | Flagship allocation memo. Score 4.65/5.0. Maven 11 Fund III ($107M). "Modular World" thesis. Fund I: 16.4x TVPI. **Template for investment diligence process.** |
| 3 | `9.3 Internal Investment Memo_Metalayer.pdf` | P0 | [ ] | Emerging manager memo. Score 4.51/5.0. Ex-Two Sigma partners. "Moirai" data platform. Ethena ~47x return. **Template for emerging manager evaluation.** |
| 4 | `9.4 Internal Investment Memo_EQV I.pdf` | P0 | [ ] | Emerging manager memo. Score 4.49/5.0. 90+ person R&D firm. "Code and Capital" thesis. Starknet, Aleo, Polkadot track record. |
| 5 | `9.1 Notice Regarding Representative Investment Memoranda.pdf` | P2 | [ ] | Legal disclaimer. Context for interpreting investment memos. |
| 6 | `4.1.1.1 BV F LP - Contract notes.pdf` | P2 | [ ] | Binance Labs contract notes. |
| 7 | `4.1.1.2 LP Statement - Brooker International.pdf` | P2 | [ ] | LP capital account statement for Binance Labs position. |
| 8 | `4.1.2.1 UVM Signum Blockchain Fund Contract.pdf` | P2 | [ ] | UVM Signum contract notes. |
| 9 | `4.1.2.2 UVM Signum Blockchain Fund VCC.pdf` | P2 | [ ] | UVM Signum VCC documents. |
| 10 | `4.1.3.1 OP Ventures Fund I Contract notes.pdf` | P2 | [ ] | Inception Capital contract notes. |
| 11 | `4.1.3.2 OP Ventures Fund I - Investment Account.pdf` | P2 | [ ] | Inception Capital investment account statement. |
| 12 | `4.1.4.1 Nomad Capital - Contract notes.pdf` | P2 | [ ] | Nomad Capital contract notes. |
| 13 | `4.1.4.2 Nomad Capital NAV Statement.pdf` | P2 | [ ] | Nomad Capital post-incident NAV ($963K exposure). |

### After Ingestion — Verify Agent Queries

- [ ] `portfolio-agent` can answer: "What is the MOIC for Binance Labs Fund?"
- [ ] `valuation-agent` can answer: "What is Maven11 Fund I TVPI?"
- [ ] `due-diligence-agent` can answer: "What is EQV's competitive moat?"

---

## 3. Legal & Compliance (`legal_docs`) Collection

Legal filings, court orders, and compliance documents for the legal committee agents.

| # | PDF File | Priority | Status | Notes |
|---|----------|----------|--------|-------|
| 1 | `5.1.1 Incident Report - December 2024 Security Breach.pdf` | P0 | [ ] | $17.2M crypto theft at Nomad Capital. $10.8M USDT frozen. GP backstop commitment. Remediation measures. **Critical for legal and compliance agents — active litigation context.** |
| 2 | `5.1.2 Exhibit A - Singapore High Court Statement of Claim.pdf` | P0 | [ ] | Formal legal filing HC/OC 939/2025. Claims against Persons Unknown + MaskEX. Wallet address annexes (Ethereum, Solana, Tron, Bitcoin, TON). **Active case reference.** |
| 3 | `5.1.3 Exhibit B - Order of Court for Service Out of Jurisdiction.pdf` | P1 | [ ] | Court order HC/ORC 267/2026. Service via blockchain wallet messaging. Legal precedent. |

### After Ingestion — Verify Agent Queries

- [ ] `compliance-agent` can answer: "What is the status of the Nomad Capital recovery litigation?"
- [ ] `regulatory-agent` can answer: "What court orders are active for HC/OC 939/2025?"

---

## 4. Risk Committee (`risk_docs`) Collection

Risk-related documents for escalation detection and risk scoring.

| # | PDF File | Priority | Status | Notes |
|---|----------|----------|--------|-------|
| 1 | `5.1.1 Incident Report - December 2024 Security Breach.pdf` | P0 | [ ] | **Also ingest into risk_docs** (cross-collection). Security breach patterns, remediation measures, industry context (ByBit $1.5B, DMM Bitcoin $308M). |
| 2 | `3.1 Brook Limited Partners FoF1 - DDQ - 2026.pdf` | P1 | [ ] | Risk management framework: macro, market, leverage (40% NAV), manager drift, concentration limits. |

---

## 5. Shared Policies (`shared_policies`) Collection

Cross-department reference material accessible to all agents.

| # | PDF File | Priority | Status | Notes |
|---|----------|----------|--------|-------|
| 1 | `8.1 The Brooker Group Company Introduction.pdf` | P0 | [ ] | 13-page corporate presentation. Company history, board, management, track record (17 major transactions), awards. **All agents need GP context.** |
| 2 | `7.1 Ternary Fund Management - 2026.pdf` | P1 | [ ] | Fund manager presentation. 16 alternative funds managed, MAS licensing, team bios, regulatory context. |
| 3 | `1.1 Brook Limited Partners FoF I - Presentation.pdf` | P1 | [ ] | **Also ingest into shared_policies** (cross-collection). Master fund reference. |

---

## 6. PostgreSQL `ingested_documents` Table Entries

For each PDF ingested into Qdrant, a row must be created in `ingested_documents`:

```sql
INSERT INTO ingested_documents (filename, dept, doc_type, uploader_id, channel, chunks_count, chroma_collection, file_hash)
VALUES (
  '1.1 Brook Limited Partners FoF I - Presentation.pdf',
  'cac',          -- or 'invest', 'legal', 'risk', 'shared'
  'pdf',
  'system',       -- bulk ingestion
  'bulk-import',  -- not from Slack
  NULL,           -- filled after chunking
  'cac_docs',     -- target Qdrant collection
  NULL            -- filled with SHA-256 hash
);
```

### Documents Requiring Cross-Collection Ingestion

These PDFs should be ingested into **multiple** Qdrant collections:

| PDF | Collections |
|-----|------------|
| `1.1 Presentation.pdf` | `cac_docs` + `shared_policies` |
| `3.1 DDQ 2026.pdf` | `cac_docs` + `risk_docs` |
| `5.1.1 Incident Report.pdf` | `legal_docs` + `risk_docs` |
| `8.1 Brooker Group Intro.pdf` | `shared_policies` (all depts access) |

---

## 7. Documents NOT Accessible (Action Required)

| PDF | Issue | Action |
|-----|-------|--------|
| `4.2.2.1 Inception Venture Q3 2025.pdf` | Stub PDF — points to DocSend link | Download from DocSend (password: `InceptionPUQ3`), save as full PDF, then ingest into `invest_docs` |
| `4.2.3.1 UVM Signum Q3 2025.pdf` | Password-protected PDF | Obtain PDF password from UOB Venture Management, decrypt, then ingest into `invest_docs` |
| `4.2.4.1 Nomad Capital Q3 2025.pdf` | Stub PDF — points to DocSend link | Download from DocSend (password: `Nomadcap_11`), save as full PDF, then ingest into `invest_docs` |

---

## 8. Ingestion Script Template

```bash
# Bulk ingest all P0 documents
curl -X POST http://localhost:3004/ingest \
  -F "file=@/path/to/document.pdf" \
  -F "dept=cac" \
  -F "collection=cac_docs" \
  -F "uploader_id=system" \
  -F "channel=bulk-import"
```

---

## 9. Escalation Rules to Add (`config/escalation_rules.json`)

Based on the incident report and DDQ, add these triggers:

```json
{
  "invest": [
    {
      "trigger": "portfolio_security_breach",
      "description": "Underlying fund reports a security breach or theft",
      "threshold": "any reported breach > $100K",
      "severity": "critical",
      "notify": ["hod", "ceo"]
    },
    {
      "trigger": "nav_discrepancy",
      "description": "NAV reported by fund admin differs >5% from expected",
      "threshold": "> 5% variance",
      "severity": "high",
      "notify": ["hod"]
    }
  ]
}
```

---

## 10. Completion Checklist

- [ ] All P0 documents ingested into target collections
- [ ] All P1 documents ingested
- [ ] Cross-collection documents ingested into all target collections
- [ ] `ingested_documents` table has matching rows with correct `file_hash`
- [ ] Agent query verification tests pass (Section 1-4 "After Ingestion" checks)
- [ ] 3 inaccessible documents resolved and ingested
- [ ] Escalation rules updated in `config/escalation_rules.json`
- [ ] `departments.json` updated if new collections added
