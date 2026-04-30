"""Table-aware document chunking — keeps table rows together instead of splitting mid-table."""
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


@dataclass
class Chunk:
    text: str
    source: str
    chunk_type: str  # "text", "table", "header", "list"
    page: int | None = None
    row_range: str | None = None  # e.g., "rows 5-15" for table chunks
    metadata: dict = field(default_factory=dict)


def chunk_document(
    text: str,
    source: str,
    max_chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Chunk]:
    """Split document into chunks, preserving table structures.

    Strategy:
    1. Detect table regions (markdown tables, CSV-like rows, tab-separated)
    2. Keep table rows together — a table becomes 1 or more chunks, never split mid-row
    3. Text sections use standard character-split with overlap
    4. Headers stay attached to the content that follows them
    """
    sections = _split_into_sections(text)
    chunks = []

    for section in sections:
        if section["type"] == "table":
            chunks.extend(_chunk_table(section["text"], source, max_chunk_size))
        elif section["type"] == "header":
            # Headers are attached to the next section, not standalone
            continue
        else:
            chunks.extend(_chunk_text(
                section["text"], source, max_chunk_size, chunk_overlap,
                header=section.get("header", ""),
            ))

    return chunks


def _split_into_sections(text: str) -> list[dict]:
    """Split text into sections, identifying tables vs prose."""
    sections = []
    lines = text.split("\n")
    current_type = "text"
    current_lines: list[str] = []
    current_header = ""

    for line in lines:
        line_type = _classify_line(line)

        if line_type == "header":
            # Flush current section
            if current_lines:
                sections.append({
                    "type": current_type,
                    "text": "\n".join(current_lines),
                    "header": current_header,
                })
                current_lines = []
            current_header = line
            current_type = "text"

        elif line_type == "table_row":
            if current_type != "table" and current_lines:
                sections.append({
                    "type": current_type,
                    "text": "\n".join(current_lines),
                    "header": current_header,
                })
                current_lines = []
            current_type = "table"
            current_lines.append(line)

        elif line_type == "separator":
            # Table separators (---|---|---) belong to the table
            if current_type == "table":
                current_lines.append(line)
            # Otherwise skip

        else:  # text
            if current_type == "table" and current_lines:
                sections.append({
                    "type": "table",
                    "text": "\n".join(current_lines),
                    "header": current_header,
                })
                current_lines = []
            current_type = "text"
            current_lines.append(line)

    # Flush remaining
    if current_lines:
        sections.append({
            "type": current_type,
            "text": "\n".join(current_lines),
            "header": current_header,
        })

    return sections


def _classify_line(line: str) -> str:
    """Classify a single line as header, table_row, separator, or text."""
    stripped = line.strip()

    if not stripped:
        return "text"

    # Markdown header
    if re.match(r"^#{1,6}\s", stripped):
        return "header"

    # Table separator (---|---|---)
    if re.match(r"^\|?[\s-:|]+\|[\s-:|]+$", stripped):
        return "separator"

    # Markdown table row (| col | col | col |)
    if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 3:
        return "table_row"

    # Tab-separated (likely table data)
    if stripped.count("\t") >= 2:
        return "table_row"

    # CSV-like (commas with consistent column count)
    if stripped.count(",") >= 3 and not stripped.startswith("#"):
        return "table_row"

    return "text"


def _chunk_table(table_text: str, source: str, max_size: int) -> list[Chunk]:
    """Chunk a table while keeping rows intact."""
    lines = table_text.split("\n")

    # First line is usually the header row
    header_line = lines[0] if lines else ""
    separator_line = ""
    data_lines = []

    for i, line in enumerate(lines):
        if _classify_line(line) == "separator":
            separator_line = line
        else:
            if i == 0:
                continue  # skip header, we'll prepend it
            data_lines.append(line)

    if not data_lines:
        return [Chunk(text=table_text, source=source, chunk_type="table")]

    # Build chunks of rows, prepending the header to each chunk
    header_block = header_line
    if separator_line:
        header_block += "\n" + separator_line
    header_size = len(header_block)

    chunks = []
    current_rows: list[str] = []
    current_size = header_size
    start_row = 1

    for i, row in enumerate(data_lines):
        row_size = len(row) + 1  # +1 for newline

        if current_size + row_size > max_size and current_rows:
            # Flush current chunk
            chunk_text = header_block + "\n" + "\n".join(current_rows)
            chunks.append(Chunk(
                text=chunk_text,
                source=source,
                chunk_type="table",
                row_range=f"rows {start_row}-{start_row + len(current_rows) - 1}",
            ))
            current_rows = []
            current_size = header_size
            start_row = i + 1

        current_rows.append(row)
        current_size += row_size

    # Flush remaining
    if current_rows:
        chunk_text = header_block + "\n" + "\n".join(current_rows)
        chunks.append(Chunk(
            text=chunk_text,
            source=source,
            chunk_type="table",
            row_range=f"rows {start_row}-{start_row + len(current_rows) - 1}",
        ))

    return chunks


def _chunk_text(
    text: str,
    source: str,
    max_size: int,
    overlap: int,
    header: str = "",
) -> list[Chunk]:
    """Standard character-split chunking for prose text."""
    if not text.strip():
        return []

    full_text = f"{header}\n{text}" if header else text

    if len(full_text) <= max_size:
        return [Chunk(text=full_text.strip(), source=source, chunk_type="text")]

    chunks = []
    start = 0
    while start < len(full_text):
        end = start + max_size

        # Try to break at a sentence boundary
        if end < len(full_text):
            # Look for last period, newline, or semicolon before the limit
            for sep in [". ", "\n", "; ", ", "]:
                last_sep = full_text.rfind(sep, start, end)
                if last_sep > start + max_size // 2:
                    end = last_sep + len(sep)
                    break

        chunk_text = full_text[start:end].strip()
        if chunk_text:
            chunks.append(Chunk(text=chunk_text, source=source, chunk_type="text"))

        start = end - overlap

    return chunks


def chunk_excel_sheet(
    rows: list[list[str]],
    sheet_name: str,
    source: str,
    max_rows_per_chunk: int = 20,
) -> list[Chunk]:
    """Chunk an Excel sheet by rows, keeping the header row in each chunk.

    Args:
        rows: List of rows, each row is a list of cell values
        sheet_name: Name of the Excel tab
        source: Source file path
        max_rows_per_chunk: Maximum data rows per chunk (header not counted)
    """
    if not rows:
        return []

    header_row = rows[0]
    data_rows = rows[1:]

    header_text = " | ".join(str(c) for c in header_row)
    chunks = []

    for i in range(0, len(data_rows), max_rows_per_chunk):
        batch = data_rows[i:i + max_rows_per_chunk]
        row_texts = [" | ".join(str(c) for c in row) for row in batch]
        chunk_text = f"[{sheet_name}]\n{header_text}\n" + "\n".join(row_texts)

        chunks.append(Chunk(
            text=chunk_text,
            source=source,
            chunk_type="table",
            row_range=f"rows {i+2}-{i+1+len(batch)}",  # +2 because row 1 is header
            metadata={"sheet": sheet_name},
        ))

    return chunks
