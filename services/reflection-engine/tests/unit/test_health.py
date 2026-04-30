from fastapi.testclient import TestClient


def test_health(monkeypatch):
    monkeypatch.setenv("POSTGRES_DSN", "postgresql://localhost/test")
    monkeypatch.setenv("REFLECTION_POSTGRES_DSN", "postgresql://localhost/test")
    # Import after env is set
    from src.main import app
    # Can't fully test lifespan without DB, just verify app creation
    assert app.title == "reflection-engine"
