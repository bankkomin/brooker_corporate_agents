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
