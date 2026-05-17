#!/usr/bin/env python3
"""Extract raw corporate source files into readable markdown for wiki authoring.

Part of the `brooker-db-to-wiki` workflow. Walks `O:\\brooker_database\\{dept}\\`,
converts each docx/pdf/xlsx/pptx file to plain markdown, and writes the result to
`.source-extracts/{dept}/` (gitignored) so wiki articles can be authored from real
content rather than filenames.

`O:\\brooker_database` is external corporate data — this script only READS from it.

Usage:
    python scripts/extract_sources.py ceo        # one department
    python scripts/extract_sources.py all        # every department

Requires: pdfplumber, python-docx, openpyxl, python-pptx, xlrd
"""
from __future__ import annotations

import sys
from pathlib import Path

SOURCE_ROOT = Path("O:/brooker_database")
REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACT_ROOT = REPO_ROOT / ".source-extracts"

DEPARTMENTS = ["ceo", "cio", "comms", "finance", "hr", "ic", "legal", "vcc"]
SKIP_EXT = {".jpg", ".jpeg", ".png", ".gif"}


def extract_pdf(path: Path) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            parts.append(f"\n\n--- page {i} ---\n\n{text}")
            for table in page.extract_tables():
                rows = ["| " + " | ".join((c or "").strip() for c in row) + " |" for row in table]
                if rows:
                    parts.append("\n" + "\n".join(rows))
    return "".join(parts)


def extract_docx(path: Path) -> str:
    import docx

    document = docx.Document(str(path))
    parts: list[str] = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip().replace("\n", " ") for c in row.cells]
            parts.append("| " + " | ".join(cells) + " |")
    return "\n\n".join(parts)


def extract_xlsx(path: Path) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(str(path), data_only=True, read_only=True)
    parts: list[str] = []
    for sheet in wb.worksheets:
        parts.append(f"\n\n## sheet: {sheet.title}\n")
        for row in sheet.iter_rows(values_only=True):
            if any(v is not None for v in row):
                cells = ["" if v is None else str(v) for v in row]
                parts.append("| " + " | ".join(cells) + " |")
    wb.close()
    return "\n".join(parts)


def extract_xls(path: Path) -> str:
    import xlrd

    book = xlrd.open_workbook(str(path))
    parts: list[str] = []
    for sheet in book.sheets():
        parts.append(f"\n\n## sheet: {sheet.name}\n")
        for r in range(sheet.nrows):
            cells = [str(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
            if any(c.strip() for c in cells):
                parts.append("| " + " | ".join(cells) + " |")
    return "\n".join(parts)


def extract_pptx(path: Path) -> str:
    from pptx import Presentation

    prs = Presentation(str(path))
    parts: list[str] = []
    for i, slide in enumerate(prs.slides, start=1):
        parts.append(f"\n\n--- slide {i} ---\n")
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in para.runs).strip()
                    if text:
                        parts.append(text)
            if shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip().replace("\n", " ") for c in row.cells]
                    parts.append("| " + " | ".join(cells) + " |")
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                parts.append(f"\n[speaker notes]\n{notes}")
    return "\n\n".join(parts)


EXTRACTORS = {
    ".pdf": extract_pdf,
    ".docx": extract_docx,
    ".xlsx": extract_xlsx,
    ".xls": extract_xls,
    ".pptx": extract_pptx,
}


def extract_department(dept: str) -> None:
    src_dir = SOURCE_ROOT / dept
    if not src_dir.is_dir():
        print(f"  [skip] {dept}: no source folder at {src_dir}")
        return

    out_dir = EXTRACT_ROOT / dept
    out_dir.mkdir(parents=True, exist_ok=True)

    for path in sorted(p for p in src_dir.rglob("*") if p.is_file()):
        ext = path.suffix.lower()
        rel = path.relative_to(src_dir)
        if ext in SKIP_EXT:
            print(f"  [image] {rel} — skipped")
            continue
        out_path = out_dir / rel.with_suffix(rel.suffix + ".md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        extractor = EXTRACTORS.get(ext)
        if extractor is None:
            out_path.write_text(
                f"# {path.name}\n\n> Unsupported format `{ext}` — extract manually "
                f"via the anthropic-skills toolkit.\n",
                encoding="utf-8",
            )
            print(f"  [manual] {rel} — unsupported {ext}")
            continue
        try:
            content = extractor(path)
        except Exception as exc:  # noqa: BLE001 - report and continue
            out_path.write_text(
                f"# {path.name}\n\n> Extraction failed: {exc}\n", encoding="utf-8"
            )
            print(f"  [error] {rel} — {exc}")
            continue
        out_path.write_text(
            f"# {path.name}\n\n_Source: `{path}`_\n\n{content}\n", encoding="utf-8"
        )
        print(f"  [ok]    {rel} -> {out_path.relative_to(REPO_ROOT)}")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 1
    target = argv[1].lower()
    depts = DEPARTMENTS if target == "all" else [target]
    if target != "all" and target not in DEPARTMENTS:
        print(f"Unknown department '{target}'. Choose from: {', '.join(DEPARTMENTS)}, all")
        return 1
    for dept in depts:
        print(f"Extracting {dept}/ ...")
        extract_department(dept)
    print(f"\nDone. Extracts written to {EXTRACT_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
