
from src.promoter import promote_memory


def test_promoter_archives_then_writes(tmp_path):
    mem_dir = tmp_path / "_memory" / "x-agent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "memory.md").write_text("## Old\nold content")

    changes = promote_memory(mem_dir, {
        "memory_md_updates": [{"section": "Lessons", "content": "New lesson learned"}],
        "user_md_updates": [],
        "skill_proposals": [],
    })

    assert changes["memory_updated"] is True
    new_content = (mem_dir / "memory.md").read_text()
    assert "Lessons" in new_content
    assert "New lesson learned" in new_content

    archive_dir = mem_dir / "history"
    assert archive_dir.exists()
    assert any(f.name.endswith("memory.md") for f in archive_dir.iterdir())


def test_promoter_no_updates(tmp_path):
    mem_dir = tmp_path / "_memory" / "y-agent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "memory.md").write_text("## Existing\ncontent")

    changes = promote_memory(mem_dir, {
        "memory_md_updates": [],
        "user_md_updates": [],
        "skill_proposals": [],
    })

    assert changes["memory_updated"] is False
    assert changes["user_updated"] is False
