# services/rag-ingestion/src/chunker.py
"""Document chunking pipeline for PDF, DOCX, XLSX, Markdown, and plain text."""
from __future__ import annotations

import hashlib
from pathlib import Path

import structlog

from .config import RAGSettings

try:
    from services.shared.table_chunker import chunk_document as table_aware_chunk
    from services.shared.table_chunker import chunk_excel_sheet
except ImportError:
    table_aware_chunk = None
    chunk_excel_sheet = None

logger = structlog.get_logger("rag-ingestion.chunker")


class TextChunk:
    """A chunk of text with metadata."""

    __slots__ = ("text", "metadata")

    def __init__(self, text: str, metadata: dict[str, str | int | None]) -> None:
        self.text = text
        self.metadata = metadata


class DocumentChunker:
    """Chunks documents into text segments with metadata."""

    def __init__(self, settings: RAGSettings) -> None:
        self._chunk_size = settings.chunk_size
        self._overlap = settings.chunk_overlap

    async def chunk_file(
        self,
        file_path: Path,
        doc_type: str,
        dept: str = "CAC",
        extra_meta: dict[str, str] | None = None,
    ) -> list[TextChunk]:
        """Chunk a file into TextChunks with metadata."""
        handler = self._get_handler(doc_type)
        if handler is None:
            logger.warning("chunker.unsupported_type", doc_type=doc_type, path=str(file_path))
            return []

        try:
            raw_sections = handler(file_path)
        except Exception as exc:
            logger.error("chunker.extract_failed", path=str(file_path), error=str(exc))
            return []

        if not raw_sections:
            return []

        file_hash = self._hash_file(file_path)
        file_ext = file_path.suffix.lower()
        chunks: list[TextChunk] = []
        for section in raw_sections:
            text = section["text"].strip()
            if not text:
                continue

            # Use table-aware chunking if available and document contains tables
            if table_aware_chunk is not None and ("|---|" in text or file_ext in (".xlsx", ".csv")):
                table_chunks = table_aware_chunk(text, source=str(file_path), max_chunk_size=self._chunk_size)
                for c in table_chunks:
                    meta: dict[str, str | int | None] = {
                        "source_file": str(file_path),
                        "file_hash": file_hash,
                        "doc_type": doc_type,
                        "dept": dept,
                        "page": section.get("page"),
                        "section": section.get("section"),
                        "sheet": section.get("sheet"),
                        "chunk_type": c.chunk_type,
                    }
                    if extra_meta:
                        for k, v in extra_meta.items():
                            if v:
                                meta[k] = v
                    if c.metadata:
                        for k, v in c.metadata.items():
                            meta[k] = v
                    chunks.append(TextChunk(text=c.text, metadata=meta))
                continue

            for piece in self._split_text(text):
                meta = {
                    "source_file": str(file_path),
                    "file_hash": file_hash,
                    "doc_type": doc_type,
                    "dept": dept,
                    "page": section.get("page"),
                    "section": section.get("section"),
                    "sheet": section.get("sheet"),
                }
                if extra_meta:
                    for k, v in extra_meta.items():
                        if v:  # only add non-empty values
                            meta[k] = v
                chunks.append(TextChunk(text=piece, metadata=meta))

        logger.info("chunker.done", path=str(file_path), chunks=len(chunks))
        return chunks

    def _get_handler(self, doc_type: str):  # noqa: ANN202
        handlers = {
            "pdf": self._extract_pdf,
            "docx": self._extract_docx,
            "xlsx": self._extract_xlsx,
            "md": self._extract_text,
            "txt": self._extract_text,
        }
        return handlers.get(doc_type)

    def _extract_pdf(self, path: Path) -> list[dict]:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        sections = []
        for i, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                sections.append({"text": text, "page": i + 1, "section": None})
        doc.close()
        return sections

    def _extract_docx(self, path: Path) -> list[dict]:
        from docx import Document

        doc = Document(str(path))
        sections = []
        for i, para in enumerate(doc.paragraphs):
            if para.text.strip():
                sections.append({"text": para.text, "page": None, "section": f"para_{i}"})
        return sections

    def _extract_xlsx(self, path: Path) -> list[dict]:
        from openpyxl import load_workbook

        wb = load_workbook(str(path), read_only=True, data_only=True)
        sections = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                row_vals = [c for c in row if c is not None]
                row_text = " | ".join(str(c) for c in row_vals)
                if row_text.strip():
                    rows.append(row_text)

            # Use table-aware Excel chunker if available
            if chunk_excel_sheet is not None and rows:
                structured_rows = []
                for row in ws.iter_rows(values_only=True):
                    structured_rows.append([str(c) if c is not None else "" for c in row])
                excel_chunks = chunk_excel_sheet(
                    structured_rows,
                    sheet_name=sheet_name,
                    source=str(path),
                    max_chunk_size=self._chunk_size,
                )
                for c in excel_chunks:
                    sections.append({
                        "text": c.text,
                        "page": None,
                        "section": None,
                        "sheet": sheet_name,
                        "chunk_type": c.chunk_type,
                    })
            elif rows:
                sections.append({
                    "text": "\n".join(rows),
                    "page": None,
                    "section": None,
                    "sheet": sheet_name,
                })
        wb.close()
        return sections

    def _extract_text(self, path: Path) -> list[dict]:
        text = path.read_text(encoding="utf-8", errors="replace")
        return [{"text": text, "page": None, "section": None}] if text.strip() else []

    def _split_text(self, text: str) -> list[str]:
        """Simple character-based splitter with overlap."""
        if len(text) <= self._chunk_size:
            return [text]
        pieces = []
        start = 0
        while start < len(text):
            end = start + self._chunk_size
            pieces.append(text[start:end])
            start = end - self._overlap
        return pieces

    @staticmethod
    def _hash_file(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                h.update(block)
        return h.hexdigest()
