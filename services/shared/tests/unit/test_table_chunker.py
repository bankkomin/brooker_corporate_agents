from services.shared.table_chunker import chunk_document, chunk_excel_sheet, _classify_line

def test_classify_header():
    assert _classify_line("## Section Title") == "header"

def test_classify_table_row():
    assert _classify_line("| Col1 | Col2 | Col3 |") == "table_row"

def test_classify_separator():
    assert _classify_line("|---|---|---|") == "separator"

def test_classify_text():
    assert _classify_line("This is regular text.") == "text"

def test_classify_tsv():
    assert _classify_line("val1\tval2\tval3\tval4") == "table_row"

def test_table_preserved_in_chunks():
    doc = """# Report
Some intro text.

| Metric | Value | Status |
|--------|-------|--------|
| LCR | 118.5% | Green |
| NSFR | 104.2% | Green |
| Capital | 15.8% | Yellow |

More text after the table.
"""
    chunks = chunk_document(doc, "test.md", max_chunk_size=200)
    table_chunks = [c for c in chunks if c.chunk_type == "table"]
    assert len(table_chunks) >= 1
    # Table header should appear in each table chunk
    for tc in table_chunks:
        assert "Metric" in tc.text
        assert "Value" in tc.text

def test_table_split_preserves_header():
    # Large table that must be split
    rows = "| Name | Value |\n|------|-------|\n"
    for i in range(50):
        rows += f"| Item{i} | {i*100} |\n"

    chunks = chunk_document(rows, "big_table.md", max_chunk_size=300)
    for c in chunks:
        if c.chunk_type == "table":
            assert "Name" in c.text  # header in every chunk
            assert c.row_range is not None

def test_excel_sheet_chunking():
    rows = [
        ["Facility", "Amount", "Rate", "Maturity"],
        ["Term Loan A", "100M", "3.5%", "2027"],
        ["Term Loan B", "200M", "4.0%", "2028"],
        ["Revolver", "50M", "3.0%", "2026"],
    ]
    chunks = chunk_excel_sheet(rows, "Funding", "tracker.xlsx", max_rows_per_chunk=2)
    assert len(chunks) == 2
    assert "Facility" in chunks[0].text  # header in first
    assert "Facility" in chunks[1].text  # header in second
    assert "Term Loan A" in chunks[0].text
    assert "Revolver" in chunks[1].text

def test_text_only_document():
    doc = "This is a simple text document with no tables. " * 20
    chunks = chunk_document(doc, "text.md", max_chunk_size=200)
    assert all(c.chunk_type == "text" for c in chunks)

def test_empty_document():
    chunks = chunk_document("", "empty.md")
    assert chunks == []
