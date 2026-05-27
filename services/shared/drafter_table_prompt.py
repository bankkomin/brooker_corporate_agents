"""Drafter prompt-template helpers for table emission.

Two entry points:

table_emission_prompt_snippet()
    Returns a system-prompt chunk instructing the LLM to emit structured tables
    as fenced ```table JSON blocks when comparison or tabular data would help.

extract_tables_from_text(text)
    Parses drafter output: finds all ```table ... ``` JSON blocks, removes them
    from the text, and returns (cleaned_text, [parsed_table_specs]).
    Robust to malformed JSON — logs a warning and skips the bad block rather
    than crashing.
"""
from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# Regex: captures everything between ```table and the closing ```.
# Uses non-greedy match so multiple blocks in the same text are parsed
# independently.  DOTALL so the content can span multiple lines.
_TABLE_BLOCK_RE = re.compile(r"```table\s*(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# Prompt snippet
# ---------------------------------------------------------------------------

_SNIPPET = """\
## Structured Table Output

When you need to compare items across attributes — such as engine performance \
metrics, portfolio allocations, limit breaches, or multi-period trend data — \
output a ```table JSON block instead of a bullet list.  Use tables sparingly \
(no more than 3 per document).

Rules:
- Every row must have exactly as many cells as there are headers.
- Use plain strings in all cells (no markdown inside cells).
- The `title` field is optional but recommended for context.
- Only emit a table when a grid genuinely aids comprehension; \
do not force tabular form onto narrative content.

Format (fence the JSON with ```table ... ```):

```table
{
  "title": "Engine performance — May 2026",
  "headers": ["Engine", "Return YTD", "Status"],
  "rows": [
    ["VCC", "12.4%", "On-track"],
    ["DAT", "8.1%", "Watch"]
  ]
}
```
"""


def table_emission_prompt_snippet() -> str:
    """Return a system-prompt chunk instructing the LLM to emit ```table blocks.

    Paste this into the system prompt of any agent whose output is later rendered
    by add_table_to_docx / add_table_to_pptx via extract_tables_from_text.
    """
    return _SNIPPET


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def extract_tables_from_text(text: str) -> tuple[str, list[dict]]:
    """Parse drafter output for ```table ... ``` JSON blocks.

    For each block found:
    - Attempts to parse the content as JSON.
    - On success: removes the block from the text and appends the parsed dict to
      the table specs list.
    - On failure: logs a warning, still removes the block from the text (so
      broken fence markers do not leak into the final document), and continues.

    Returns:
        (cleaned_text, [parsed_table_specs])

    The cleaned_text has all ```table ... ``` blocks stripped out.
    Whitespace around removed blocks is normalised (collapsed to single newlines).
    """
    table_specs: list[dict] = []
    blocks_found: list[tuple[str, str]] = []  # (full_match, json_content)

    for m in _TABLE_BLOCK_RE.finditer(text):
        full_match = m.group(0)
        json_content = m.group(1).strip()
        blocks_found.append((full_match, json_content))

    cleaned = text
    for full_match, json_content in blocks_found:
        # Remove the block from the output text regardless of parse outcome
        cleaned = cleaned.replace(full_match, "")

        try:
            parsed = json.loads(json_content)
            if not isinstance(parsed, dict):
                raise ValueError(
                    f"Expected a JSON object, got {type(parsed).__name__}"
                )
            table_specs.append(parsed)
        except Exception as exc:
            logger.warning(
                "extract_tables_from_text: skipping malformed table block — %s",
                exc,
            )

    # Collapse multiple blank lines introduced by block removal
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return cleaned, table_specs
