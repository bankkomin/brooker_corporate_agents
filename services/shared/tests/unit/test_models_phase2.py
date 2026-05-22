import pytest
from pydantic import ValidationError

from services.shared.models_phase2 import SkillMeta, SkillPermissions


def test_skill_with_permissions():
    s = SkillMeta(
        name="x", agent="x-agent", dept="x",
        permissions=SkillPermissions(
            mode="read_only", data_zones=[1], outbound_apis=[],
            read_collections=["x_docs"]
        ),
        output_types=["text", "table"]
    )
    assert s.permissions.mode == "read_only"


def test_invalid_mode_rejected():
    with pytest.raises(ValidationError):
        SkillMeta(
            name="x", agent="x", dept="x",
            permissions=SkillPermissions(
                mode="bogus", data_zones=[], outbound_apis=[], read_collections=[]
            ),
            output_types=["text"]
        )


def test_default_output_types():
    s = SkillMeta(
        name="x", agent="x-agent", dept="x",
        permissions=SkillPermissions(
            mode="read_only", data_zones=[1], outbound_apis=[], read_collections=["x_docs"]
        )
    )
    assert s.output_types == ["text"]


def test_skillmeta_shared_skills_defaults_empty():
    meta = SkillMeta(
        name="reporting-agent", agent="reporting-agent", dept="finance",
        permissions=SkillPermissions(
            mode="write_via_staging", data_zones=[1, 2],
            outbound_apis=[], read_collections=["finance_docs"],
        ),
    )
    assert meta.shared_skills == []


def test_skillmeta_shared_skills_accepts_paths():
    meta = SkillMeta(
        name="reporting-agent", agent="reporting-agent", dept="finance",
        permissions=SkillPermissions(
            mode="write_via_staging", data_zones=[1, 2],
            outbound_apis=[], read_collections=["finance_docs"],
        ),
        shared_skills=["shared/investment-cluster/valuation-methodology"],
    )
    assert meta.shared_skills == ["shared/investment-cluster/valuation-methodology"]
