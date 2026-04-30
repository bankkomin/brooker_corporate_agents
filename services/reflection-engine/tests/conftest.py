import pytest


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a temporary vault structure for testing."""
    dept = tmp_path / "cac"
    (dept / "daily-logs").mkdir(parents=True)
    (dept / "_memory" / "liquidity-agent").mkdir(parents=True)
    (dept / "_memory" / "liquidity-agent" / "soul.md").write_text("# Soul\nI am the liquidity agent.")
    (dept / "_memory" / "liquidity-agent" / "user.md").write_text("# User\n")
    (dept / "_memory" / "liquidity-agent" / "memory.md").write_text("# Memory\n")
    return tmp_path
