"""Extended Pydantic models for Phase 2 skill permissions and output types."""
from typing import List, Literal

from pydantic import BaseModel, Field


class SkillPermissions(BaseModel):
    mode: Literal["read_only", "write_via_staging", "write_direct"]
    data_zones: List[int]
    outbound_apis: List[Literal["gmail", "slack", "sharepoint"]] = Field(default_factory=list)
    read_collections: List[str]


class SkillMeta(BaseModel):
    """Extended skill metadata for Phase 2."""
    name: str
    agent: str
    dept: str
    version: str = "1.0"
    permissions: SkillPermissions
    output_types: List[Literal["text", "table", "checklist", "decision_tree", "calculation"]] = Field(
        default=["text"]
    )
    deprecated: bool = False
    canonical: str | None = None
