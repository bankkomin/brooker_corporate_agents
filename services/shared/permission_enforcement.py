"""Runtime permission enforcement for skills."""
import logging

log = logging.getLogger(__name__)


class PermissionError(Exception):
    """Raised when a skill attempts an unauthorized action."""
    pass


def ensure_can_write(skill_permissions: dict, action: str = "staging_proposal") -> None:
    """Check that the skill's permission mode allows write actions via staging only.

    Raises PermissionError if mode is not 'write_via_staging'.
    write_direct is explicitly blocked — all writes MUST go through the staging pipeline.
    """
    mode = skill_permissions.get("mode", "read_only")
    if mode != "write_via_staging":
        raise PermissionError(
            f"Skill with mode '{mode}' cannot perform '{action}'. "
            f"Only write_via_staging mode is allowed. "
            f"All writes must go through the staging pipeline for human approval."
        )


def validate_collections(skill_permissions: dict, known_collections: set[str]) -> list[str]:
    """Validate that all read_collections in the skill are known.

    Returns list of unknown collections (empty if all valid).
    """
    read_cols = skill_permissions.get("read_collections", [])
    unknown = [c for c in read_cols if c not in known_collections]
    if unknown:
        log.warning("Skill references unknown collections: %s", unknown)
    return unknown


def enforce_outbound_apis(skill_permissions: dict, requested_api: str) -> None:
    """Check that the skill is allowed to call the requested outbound API.

    Raises PermissionError if not in the skill's outbound_apis list.
    """
    allowed = skill_permissions.get("outbound_apis", [])
    if requested_api not in allowed:
        raise PermissionError(
            f"Skill not authorized for outbound API '{requested_api}'. "
            f"Allowed: {allowed}"
        )
