def test_app_creates():
    from src.main import app
    assert app.title == "read-only-orchestrator"
