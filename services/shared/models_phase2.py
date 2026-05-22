"""Extended Pydantic models for Phase 2 skill permissions and output types."""
from typing import Literal

from pydantic import BaseModel, Field


class SkillPermissions(BaseModel):
    mode: Literal["read_only", "write_via_staging", "write_direct"]
    data_zones: list[int]
    outbound_apis: list[Literal["gmail", "slack", "sharepoint"]] = Field(default_factory=list)
    read_collections: list[str]


class SkillMeta(BaseModel):
    """Extended skill metadata for Phase 2."""
    name: str
    agent: str
    dept: str
    version: str = "1.0"
    permissions: SkillPermissions
    output_types: list[
        Literal["text", "table", "checklist", "decision_tree", "calculation"]
    ] = Field(default=["text"])
    shared_skills: list[str] = Field(default_factory=list)
    deprecated: bool = False
    canonical: str | None = None
