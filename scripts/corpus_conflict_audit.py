"""Surface conflicting / stale chunks for each failing use-case test.

For each (canonical-question, expected-fact) pair, this:
  1. Embeds the question via the local embed server.
  2. Pulls the top-K chunks the agent would see across the dept's collections.
  3. Looks for chunks that contain COMPETING values (the "stale" candidates) — the
     ones the LLM is anchoring on instead of the canonical answer.
  4. Writes a per-dept markdown report for the data administrators with: the
     chunk source label, its text, what's wrong, and the recommended action.

Run:  python scripts/corpus_conflict_audit.py
Out:  docs/corpus_conflicts_for_admins.md
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request as u
from datetime import date
from pathlib import Path


def embed(text: str) -> list[float]:
    body = json.dumps({"model": "local-gemma", "input": text}).encode()
    req = u.Request("http://localhost:8765/v1/embeddings",
                    data=body, headers={"Content-Type": "application/json"})
    return json.load(u.urlopen(req, timeout=10))["data"][0]["embedding"]


def search(collection: str, vector: list[float], limit: int = 12) -> list[dict]:
    body = json.dumps({"vector": vector, "limit": limit, "with_payload": True}).encode()
    req = u.Request(f"http://localhost:6333/collections/{collection}/points/search",
                    data=body, headers={"Content-Type": "application/json"})
    return json.load(u.urlopen(req, timeout=15))["result"]


def scroll(collection: str, text_match: str, limit: int = 20) -> list[dict]:
    body = json.dumps({
        "limit": limit, "with_payload": True, "with_vector": False,
        "filter": {"must": [{"key": "text", "match": {"text": text_match}}]}
    }).encode()
    req = u.Request(f"http://localhost:6333/collections/{collection}/points/scroll",
                    data=body, headers={"Content-Type": "application/json"})
    return json.load(u.urlopen(req, timeout=10))["result"]["points"]


# Each entry: (dept, query, canonical_fact, canonical_phrasings, competing_patterns, conflict_explainer)
# competing_patterns: regex strings; chunks matching one of these but NOT the canonical
# answer are the ones we flag for cleanup.
AUDITS = [
    {
        "dept": "CEO", "test": "USE-CASE ceo: North Star AUM target",
        "query": "what is the institutional AUM North Star target?",
        "canonical_fact": "USD 600M institutional AUM (North Star 2028)",
        "canonical_patterns": [r"USD\s*600", r"600\s*M", r"600\s*million", r"US\$\s*600"],
        "competing_patterns": [r"\$5(0|00)\s*m[nN]?", r"AUM\s*Target.*\$5(0|00)",
                                r"50[\s\-]100\s*m[nN]?", r"\$100\s*[mM]"],
        "collections": ["ceo_knowledge", "ceo_docs", "shared_policies"],
        "explainer": "The North Star 2028 target is USD 600M. Multiple stale chunks "
                     "title themselves 'AUM Target' with smaller / interim figures "
                     "($500 mn, $50-100 mn) which the LLM picks up and quotes wrongly.",
    },
    {
        "dept": "CEO", "test": "USE-CASE ceo: North Star recurring income",
        "query": "what is the North Star 2028 recurring income target?",
        "canonical_fact": "THB 500M recurring income (North Star 2028)",
        "canonical_patterns": [r"THB\s*500", r"500\s*M", r"500\s*million",
                                r"Bt\s*500", r"500\s*mn"],
        "competing_patterns": [r"THB\s*(100|200|300|400|600|750)\s*[mM]",
                                r"Bt\s*(100|200|300)"],
        "collections": ["ceo_knowledge", "ceo_docs", "shared_policies"],
        "explainer": "North Star recurring-income target is THB 500M. Watch for chunks "
                     "that cite the THB 100M treasury-yield sub-target as if it were the "
                     "headline recurring-income figure.",
    },
    {
        "dept": "VCC", "test": "USE-CASE vcc: FoF I hard cap",
        "query": "what is the hard cap on Brook LP FoF I?",
        "canonical_fact": "Hard cap US$150M (Supplement Key Commercial Terms)",
        "canonical_patterns": [r"US\$\s*150", r"USD\s*150", r"150\s*M", r"150\s*million"],
        "competing_patterns": [r"US\$\s*100", r"US\$\s*50", r"target.*US\$\s*100"],
        "collections": ["vcc_knowledge", "vcc_docs", "shared_policies"],
        "explainer": "Supplement S.4.1 sets hard cap at US$150M. Older/marketing chunks "
                     "mention the US$100M target or US$50M expected-launch figure — the "
                     "LLM picks those when the canonical chunk isn't ranked first.",
    },
    {
        "dept": "VCC", "test": "USE-CASE vcc: FoF I management fee",
        "query": "what is the management fee on Brook LP FoF I?",
        "canonical_fact": "1.5% p.a. Management Fee (Supplement)",
        "canonical_patterns": [r"1\.5\s*%", r"1\.5\s*percent", r"1\.5\s*per\s*cent"],
        "competing_patterns": [r"residual", r"Technical Services Fee",
                                r"1\.0\s*%.*Brook\s*Turtle"],
        "collections": ["vcc_knowledge", "vcc_docs"],
        "explainer": "1.5% is the FoF I Management Fee. Competing chunks describe the "
                     "Ternary TSA 'residual' fee mechanic (which is the BICL technical "
                     "services fee, NOT the LP-facing mgmt fee) or the Brook Turtle deck "
                     "1.0% figure. Easy LLM mix-up.",
    },
    {
        "dept": "Legal", "test": "USE-CASE legal: PE mitigation",
        "query": "what is the most actionable mitigation for FOF place-of-effective-management risk?",
        "canonical_fact": "Assign FOF bank-account signing authority to a non-Thai-resident, exercise outside Thailand",
        "canonical_patterns": [r"non-Thai\s*resident", r"non-resident", r"outside\s*Thailand",
                                r"offshore\s*signing"],
        "competing_patterns": [r"reverse\s*solicitation", r"Article\s*5\(4\)",
                                r"preparatory\s*/\s*auxiliary"],
        "collections": ["legal_knowledge", "legal_docs"],
        "explainer": "Timblick opinion (para 4(d)/4(e)) names ONE actionable mitigation: "
                     "non-Thai-resident signer, offshore signing. The retrieved chunks "
                     "are about the GENERAL PE doctrine (5(2)(a)/5(4)(e)) and reverse-"
                     "solicitation — adjacent but not the mitigation itself.",
    },
    {
        "dept": "CIO", "test": "USE-CASE cio: BTC holdings",
        "query": "how many BTC do we hold per the coin book?",
        "canonical_fact": "164.6554 BTC (coin book Jan/Feb/Mar/Apr 2026, units constant)",
        "canonical_patterns": [r"164\.65", r"164\.6554", r"164\s*BTC"],
        "competing_patterns": [r"100\s*BTC", r"100\s*bitcoin", r"Sovereignty\s*Buffer.*100"],
        "collections": ["cio_knowledge", "cio_docs"],
        "explainer": "Coin book holds 164.6554 BTC (cost USD 9.4M). 'Sovereignty Buffer: "
                     "100 BTC' is the FLOOR, not the holding. LLM regularly conflates them.",
    },
    {
        "dept": "IC", "test": "USE-CASE ic: 40% rule numerator column",
        "query": "which dashboard column is the numerator for the 40 percent Investment Company rule?",
        "canonical_fact": "'Investment Company Baht' column H (row 32) of [[dashboard-2026-02]]",
        "canonical_patterns": [r"Investment\s*Company\s*Baht", r"col\.?\s*H", r"column\s*H"],
        "competing_patterns": [r"Total\s*Investments", r"col\.?\s*B", r"column\s*B",
                                r"aggregate\s*Management\s*Fee"],
        "collections": ["ic_knowledge", "ic_docs"],
        "explainer": "Hard Rule in skills/ic: numerator is 'Investment Company Baht' (col "
                     "H), NOT 'Total Investments' (col B — yields wrong answer, off by 2× "
                     "for BNB OTC). One earlier LLM run fabricated 'aggregate Management "
                     "Fee paid' as the numerator. The canonical chunk likely needs to be "
                     "boosted with explicit 'numerator' keyword in its header.",
    },
    {
        "dept": "Finance", "test": "USE-CASE finance: PN.35 principal",
        "query": "what is the principal of Promissory Note 35 from BG to BICL?",
        "canonical_fact": "USD 39,023,179.25 principal (PN.35 — renews PN.34)",
        "canonical_patterns": [r"39\.02", r"39,02[0-9]", r"USD\s*39"],
        "competing_patterns": [r"PN\.?\s*36", r"USD\s*2\.3", r"PN\.?\s*34"],
        "collections": ["finance_knowledge", "finance_docs"],
        "explainer": "PN.35 = USD 39,023,179.25. PN.36 = USD 2.3M (different PN!). When "
                     "the LLM mixes them up, the answer becomes wrong.",
    },
]


def find_competing(coll: str, query_vec: list[float], canon: list[str],
                   competing: list[str], k: int = 12) -> list[dict]:
    """Return chunks scoring in top-K that look like competing/stale variants."""
    hits = search(coll, query_vec, limit=k)
    competing_re = [re.compile(p, re.I) for p in competing]
    canon_re = [re.compile(p, re.I) for p in canon]
    out = []
    for h in hits:
        text = h.get("payload", {}).get("text", "") or ""
        looks_competing = any(r.search(text) for r in competing_re)
        looks_canonical = any(r.search(text) for r in canon_re)
        if looks_competing and not looks_canonical:
            out.append({
                "score": h["score"],
                "source": h.get("payload", {}).get("source") or h.get("payload", {}).get("filename") or "(no source label)",
                "text": text[:280],
            })
    return out


def find_canonical(coll: str, canon: list[str], k: int = 5) -> list[dict]:
    """Find chunks that DO contain the canonical answer (so admins know which to keep)."""
    canon_re = [re.compile(p, re.I) for p in canon]
    # Scroll for chunks containing the first canonical literal
    pts = scroll(coll, canon[0].replace(r"\s*", " ").replace(r"\.", "."), limit=10)
    out = []
    for p in pts[:k]:
        text = p.get("payload", {}).get("text", "") or ""
        if any(r.search(text) for r in canon_re):
            out.append({
                "source": p.get("payload", {}).get("source") or p.get("payload", {}).get("filename") or "(no source label)",
                "text": text[:280],
            })
    return out


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    out_path = Path("docs/corpus_conflicts_for_admins.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append("# Corpus conflicts blocking 100% use-case accuracy")
    lines.append("")
    lines.append(f"_Generated {date.today().isoformat()} by scripts/corpus_conflict_audit.py_")
    lines.append("")
    lines.append("Each section is a failing use-case test where the agent abstained or "
                 "answered wrong because the retrieval found a stale / competing chunk "
                 "before (or instead of) the canonical one. Items below need data-owner "
                 "review — either delete the stale chunk, update its source label, or "
                 "re-ingest the canonical version with a header that boosts findability.")
    lines.append("")

    total_conflicts = 0
    for a in AUDITS:
        print(f"auditing  {a['dept']:8}  {a['test']}")
        lines.append(f"## {a['dept']} — {a['test'].split(': ',1)[1] if ': ' in a['test'] else a['test']}")
        lines.append("")
        lines.append(f"**Query:** `{a['query']}`")
        lines.append(f"**Canonical answer:** {a['canonical_fact']}")
        lines.append("")
        lines.append(f"_Why this fails today:_ {a['explainer']}")
        lines.append("")
        try:
            vec = embed(a["query"])
        except Exception as exc:
            lines.append(f"⚠ embed failed: {exc}\n")
            continue
        any_conflict = False
        for col in a["collections"]:
            try:
                conflicts = find_competing(col, vec, a["canonical_patterns"],
                                            a["competing_patterns"])
            except Exception as exc:
                lines.append(f"- ⚠ search `{col}` failed: {exc}")
                continue
            if conflicts:
                any_conflict = True
                lines.append(f"### Conflicting chunks in `{col}` ({len(conflicts)} found)")
                lines.append("")
                for c in conflicts[:5]:
                    lines.append(f"- **score `{c['score']:.3f}`** | source: `{c['source']}`")
                    lines.append(f"  > {c['text']!r}")
                    total_conflicts += 1
                lines.append("")
        if not any_conflict:
            lines.append("_No conflicting chunks detected in expected collections — this "
                         "may be a pure paraphrase-gap rather than a corpus issue._")
            lines.append("")
        # Also surface canonical chunks (the ones admins should KEEP / boost)
        for col in a["collections"][:2]:
            try:
                canons = find_canonical(col, a["canonical_patterns"])
            except Exception:
                canons = []
            if canons:
                lines.append(f"### Canonical chunks already in `{col}` ({len(canons)} found — boost these)")
                for c in canons[:3]:
                    lines.append(f"- source: `{c['source']}`")
                    lines.append(f"  > {c['text']!r}")
                lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(f"## Summary")
    lines.append("")
    lines.append(f"- Tests audited: **{len(AUDITS)}**")
    lines.append(f"- Conflicting chunks surfaced: **{total_conflicts}**")
    lines.append("")
    lines.append("### Recommended actions for data administrators")
    lines.append("1. **Delete or relabel** stale chunks where the figure is genuinely "
                 "outdated (e.g. `AUM Target: $500 mn` — replace with current $600M figure).")
    lines.append("2. **Boost canonical chunks** by adding the question's keywords to "
                 "the chunk header (e.g. add `40% rule numerator: Investment Company Baht "
                 "(col H)` to the dashboard concept's header so it ranks first on that "
                 "phrasing).")
    lines.append("3. **For genuine paraphrase gaps** (no conflicts detected), add an "
                 "alias header to the canonical chunk so embedding search reaches it.")
    lines.append("4. **Re-run** `python scripts/api_test_pipeline.py --only use-case` "
                 "after cleanup to confirm pass rate.")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwrote {out_path}  ({total_conflicts} conflicts surfaced across {len(AUDITS)} tests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
