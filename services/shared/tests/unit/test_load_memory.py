from services.shared.load_memory import load_memory_node


def test_load_memory_reads_three_files(tmp_path):
    mem_dir = tmp_path / "cac" / "_memory" / "test-agent"
    mem_dir.mkdir(parents=True)
    (mem_dir / "soul.md").write_text("# Soul\nPersonality.")
    (mem_dir / "user.md").write_text("# User\nFacts.")
    (mem_dir / "memory.md").write_text("# Memory\nLessons.")
    state = {"agent_id": "test-agent", "dept_id": "cac", "vault_root": str(tmp_path)}
    result = load_memory_node(state)
    assert "Personality" in result["agent_memory"]
    assert "Facts" in result["agent_memory"]
    assert "Lessons" in result["agent_memory"]


def test_load_memory_handles_missing_files(tmp_path):
    state = {"agent_id": "missing-agent", "dept_id": "cac", "vault_root": str(tmp_path)}
    result = load_memory_node(state)
    assert "agent_memory" in result
    assert result["agent_memory"] == ""
