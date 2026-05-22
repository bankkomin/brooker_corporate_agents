"""API endpoints for human-curated agent memory management."""
import logging

from fastapi import APIRouter, HTTPException, Request

from .auth import AuthError, extract_claims
from .rate_limit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.get("/{dept_id}/{agent_id}")
@limiter.limit("30/minute")
async def get_memory(dept_id: str, agent_id: str, request: Request):
    """Get current memory state for an agent."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    from services.shared.human_memory import get_memory as _get_memory

    state = _get_memory(dept_id, agent_id)
    return {
        "dept_id": state.dept_id,
        "agent_id": state.agent_id,
        "soul": state.soul,
        "user_entries": [
            {"section": e.section, "content": e.content, "author": e.author, "pinned": e.pinned}
            for e in state.user_entries
        ],
        "memory_entries": [
            {"section": e.section, "content": e.content, "author": e.author, "pinned": e.pinned}
            for e in state.memory_entries
        ],
    }


@router.post("/{dept_id}/{agent_id}/{file_type}")
@limiter.limit("10/minute")
async def add_entry(dept_id: str, agent_id: str, file_type: str, request: Request):
    """Add a memory entry. file_type must be 'memory' or 'user'."""
    try:
        claims = extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    body = await request.json()
    from services.shared.human_memory import MemoryEntry, add_memory_entry

    entry = MemoryEntry(
        section=body.get("section", "General"),
        content=body.get("content", ""),
        author=claims.sub,
        pinned=body.get("pinned", False),
    )

    success = add_memory_entry(dept_id, agent_id, file_type, entry)
    if not success:
        raise HTTPException(400, "Failed to add entry")

    return {"status": "added", "section": entry.section, "author": entry.author}


@router.delete("/{dept_id}/{agent_id}/{file_type}/{section_name}")
@limiter.limit("10/minute")
async def remove_section(
    dept_id: str, agent_id: str, file_type: str, section_name: str, request: Request,
):
    """Remove a section from memory."""
    try:
        extract_claims(request)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    from services.shared.human_memory import remove_memory_section

    success = remove_memory_section(dept_id, agent_id, file_type, section_name)
    if not success:
        raise HTTPException(404, "Section not found")

    return {"status": "removed", "section": section_name}
