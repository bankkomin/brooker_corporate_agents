# tests/unit/rag_ingestion/test_chunker.py
"""Tests for document chunker."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from services.rag_ingestion.src.chunker import DocumentChunker, TextChunk


@pytest.fixture
def chunker() -> DocumentChunker:
    settings = MagicMock()
    settings.chunk_size = 100
    settings.chunk_overlap = 20
    return DocumentChunker(settings)


class TestChunkerTextSplitting:
    def test_short_text_single_chunk(self, chunker: DocumentChunker) -> None:
        pieces = chunker._split_text("Hello world")
        assert len(pieces) == 1
        assert pieces[0] == "Hello world"

    def test_long_text_multiple_chunks(self, chunker: DocumentChunker) -> None:
        text = "A" * 250
        pieces = chunker._split_text(text)
        assert len(pieces) > 1
        for piece in pieces:
            assert len(piece) <= 100

    def test_overlap_present(self, chunker: DocumentChunker) -> None:
        # chunk_size=100, overlap=20 → chunk0=text[0:100], chunk1=text[80:180]
        text = "A" * 150
        pieces = chunker._split_text(text)
        assert len(pieces) == 2
        # The first 20 chars of chunk1 must equal the last 20 chars of chunk0
        assert pieces[1][:20] == pieces[0][80:]

    def test_exact_chunk_size_returns_single(self, chunker: DocumentChunker) -> None:
        text = "B" * 100
        pieces = chunker._split_text(text)
        assert len(pieces) == 1
        assert pieces[0] == text

    def test_empty_text_returns_single_empty(self, chunker: DocumentChunker) -> None:
        pieces = chunker._split_text("")
        assert len(pieces) == 1
        assert pieces[0] == ""


class TestChunkerFileTypes:
    async def test_unsupported_type_returns_empty(self, chunker: DocumentChunker) -> None:
        result = await chunker.chunk_file(Path("/fake/file.xyz"), doc_type="xyz")
        assert result == []

    async def test_text_file(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hello world from a text file")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert len(result) == 1
        assert isinstance(result[0], TextChunk)
        assert "Hello world" in result[0].text
        assert result[0].metadata["doc_type"] == "txt"
        assert result[0].metadata["source_file"] == str(f)

    async def test_markdown_file(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.md"
        f.write_text("# Heading\n\nSome markdown content.")
        result = await chunker.chunk_file(f, doc_type="md")
        assert len(result) >= 1
        assert result[0].metadata["doc_type"] == "md"

    async def test_empty_file_returns_empty(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "empty.txt"
        f.write_text("")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert result == []

    async def test_whitespace_only_file_returns_empty(
        self, chunker: DocumentChunker, tmp_path: Path
    ) -> None:
        f = tmp_path / "ws.txt"
        f.write_text("   \n\n  ")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert result == []

    async def test_pdf_extraction(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        # fitz is imported inside _extract_pdf → inject via sys.modules.
        # A real file is needed so _hash_file can open it; extraction is mocked.
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake pdf bytes")

        mock_page = MagicMock()
        mock_page.get_text.return_value = "Page 1 content here"

        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page])
        # doc.close() is called directly (no context manager)

        mock_fitz = ModuleType("fitz")
        mock_fitz.open = MagicMock(return_value=mock_doc)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            result = await chunker.chunk_file(fake_pdf, doc_type="pdf")

        assert len(result) >= 1
        assert "Page 1 content" in result[0].text
        assert result[0].metadata["page"] == 1

    async def test_pdf_skips_empty_pages(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"fake pdf bytes")

        mock_page_empty = MagicMock()
        mock_page_empty.get_text.return_value = "   "
        mock_page_content = MagicMock()
        mock_page_content.get_text.return_value = "Actual content"

        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda self: iter([mock_page_empty, mock_page_content])

        mock_fitz = ModuleType("fitz")
        mock_fitz.open = MagicMock(return_value=mock_doc)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            result = await chunker.chunk_file(fake_pdf, doc_type="pdf")

        assert len(result) == 1
        assert result[0].metadata["page"] == 2

    async def test_xlsx_extraction(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        # openpyxl is imported inside _extract_xlsx → inject via sys.modules.
        # A real file is needed so _hash_file can open it; workbook is mocked.
        fake_xlsx = tmp_path / "test.xlsx"
        fake_xlsx.write_bytes(b"fake xlsx bytes")

        mock_ws = MagicMock()
        # values_only=True → iter_rows returns tuples of cell values
        mock_ws.iter_rows.return_value = [("Col A", "Col B"), ("Val 1", "Val 2")]

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Sheet1"]
        mock_wb.__getitem__ = lambda self, k: mock_ws

        mock_openpyxl = ModuleType("openpyxl")
        mock_openpyxl.load_workbook = MagicMock(return_value=mock_wb)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
            result = await chunker.chunk_file(fake_xlsx, doc_type="xlsx")

        assert len(result) >= 1
        assert result[0].metadata["sheet"] == "Sheet1"

    async def test_xlsx_multiple_sheets(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        fake_xlsx = tmp_path / "multi.xlsx"
        fake_xlsx.write_bytes(b"fake xlsx bytes")

        def make_ws(rows: list) -> MagicMock:
            ws = MagicMock()
            ws.iter_rows.return_value = rows
            return ws

        ws1 = make_ws([("A", "B"), ("1", "2")])
        ws2 = make_ws([("X", "Y"), ("3", "4")])
        sheet_map = {"Alpha": ws1, "Beta": ws2}

        mock_wb = MagicMock()
        mock_wb.sheetnames = ["Alpha", "Beta"]
        mock_wb.__getitem__ = lambda self, k: sheet_map[k]

        mock_openpyxl = ModuleType("openpyxl")
        mock_openpyxl.load_workbook = MagicMock(return_value=mock_wb)  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"openpyxl": mock_openpyxl}):
            result = await chunker.chunk_file(fake_xlsx, doc_type="xlsx")

        sheet_names = {c.metadata["sheet"] for c in result}
        assert "Alpha" in sheet_names
        assert "Beta" in sheet_names

    async def test_dept_defaults_to_cac(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Content")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert result[0].metadata["dept"] == "CAC"

    async def test_dept_metadata(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Content")
        result = await chunker.chunk_file(f, doc_type="txt", dept="FINANCE")
        assert result[0].metadata["dept"] == "FINANCE"

    async def test_file_hash_in_metadata(self, chunker: DocumentChunker, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Hash me")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert len(result[0].metadata["file_hash"]) == 64  # SHA-256 hex digest

    async def test_file_hash_is_deterministic(
        self, chunker: DocumentChunker, tmp_path: Path
    ) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Same content")
        r1 = await chunker.chunk_file(f, doc_type="txt")
        r2 = await chunker.chunk_file(f, doc_type="txt")
        assert r1[0].metadata["file_hash"] == r2[0].metadata["file_hash"]

    async def test_source_file_path_in_metadata(
        self, chunker: DocumentChunker, tmp_path: Path
    ) -> None:
        f = tmp_path / "myfile.txt"
        f.write_text("Something")
        result = await chunker.chunk_file(f, doc_type="txt")
        assert result[0].metadata["source_file"] == str(f)

    async def test_extract_failure_returns_empty(self, chunker: DocumentChunker) -> None:
        # Simulate an extraction exception (e.g. corrupt PDF)
        mock_fitz = ModuleType("fitz")
        mock_fitz.open = MagicMock(side_effect=RuntimeError("corrupt file"))  # type: ignore[attr-defined]

        with patch.dict(sys.modules, {"fitz": mock_fitz}):
            result = await chunker.chunk_file(Path("/fake/corrupt.pdf"), doc_type="pdf")

        assert result == []
