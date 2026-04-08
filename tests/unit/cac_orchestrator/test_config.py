"""Tests for OrchestratorSettings configuration."""

from __future__ import annotations

import pytest
from services.cac_orchestrator.src.config import OrchestratorSettings


class TestOrchestratorSettingsDefaults:
    def test_vllm_large_url_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.vllm_large_url == "http://nginx:8080/v1"

    def test_vllm_large_url_not_host_docker_internal(self) -> None:
        """Ensure default goes via nginx LB, not host.docker.internal."""
        cfg = OrchestratorSettings()
        assert "host.docker.internal" not in cfg.vllm_large_url

    def test_vllm_large_model_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.vllm_large_model == "qwen-122b"

    def test_qdrant_defaults(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.qdrant_host == "qdrant"
        assert cfg.qdrant_rest_port == 6333

    def test_postgres_defaults(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.postgres_host == "postgres"
        assert cfg.postgres_port == 5432
        assert cfg.postgres_db == "corporate_agents"
        assert cfg.postgres_user == "agents"
        assert cfg.postgres_password == "changeme"

    def test_staging_path_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.staging_path == "/data/staging"

    def test_mirror_path_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.mirror_path == "/data/mirror"

    def test_confidence_threshold_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.confidence_threshold == 0.85

    def test_rag_top_k_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.rag_top_k == 8

    def test_rag_min_relevance_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.rag_min_relevance == 0.70

    def test_escalation_rules_path_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.escalation_rules_path == "/app/config/escalation_rules.json"

    def test_excel_schema_path_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.excel_schema_path == "/app/config/excel_schema/alco_tracker.json"

    def test_skills_path_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.skills_path == "/app/skills"

    def test_log_level_default(self) -> None:
        cfg = OrchestratorSettings()
        assert cfg.log_level == "INFO"


class TestOrchestratorSettingsPostgresDsn:
    def test_postgres_dsn_format(self) -> None:
        cfg = OrchestratorSettings()
        dsn = cfg.postgres_dsn
        assert dsn == "postgresql://agents:changeme@postgres:5432/corporate_agents"

    def test_postgres_dsn_uses_settings_fields(self) -> None:
        cfg = OrchestratorSettings(
            postgres_user="myuser",
            postgres_password="mypass",
            postgres_host="myhost",
            postgres_port=5433,
            postgres_db="mydb",
        )
        assert cfg.postgres_dsn == "postgresql://myuser:mypass@myhost:5433/mydb"


class TestOrchestratorSettingsEnvOverride:
    def test_override_vllm_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("VLLM_LARGE_URL", "http://custom-host:9090/v1")
        cfg = OrchestratorSettings()
        assert cfg.vllm_large_url == "http://custom-host:9090/v1"

    def test_override_rag_top_k(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAG_TOP_K", "16")
        cfg = OrchestratorSettings()
        assert cfg.rag_top_k == 16

    def test_override_confidence_threshold(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CONFIDENCE_THRESHOLD", "0.90")
        cfg = OrchestratorSettings()
        assert cfg.confidence_threshold == pytest.approx(0.90)

    def test_override_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        cfg = OrchestratorSettings()
        assert cfg.log_level == "DEBUG"
