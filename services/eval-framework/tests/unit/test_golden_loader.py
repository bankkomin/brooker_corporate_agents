"""Tests for the golden answer YAML loader."""

from unittest.mock import patch

from src.golden_loader import load_golden_answers


class TestGoldenLoader:
    """Test YAML loading of golden answers."""

    def test_load_valid_yaml(self, tmp_path):
        yaml_content = """
golden_answers:
  - id: ga_test_001
    category: lookup
    question: "What is the LCR?"
    expected_answer: "The LCR is 130%."
    acceptable_keywords: ["LCR"]
    expected_citations: ["alco_tracker"]
  - id: ga_test_002
    category: analytical
    question: "Is the CAR above minimum?"
    expected_answer: "Yes, the CAR is above the 8.5% minimum."
    acceptable_keywords: ["CAR", "minimum"]
    expected_citations: ["alco_tracker"]
"""
        yaml_file = tmp_path / "test_dept.yaml"
        yaml_file.write_text(yaml_content)

        with patch("src.golden_loader.settings") as mock_settings:
            mock_settings.EVAL_DATASET_PATH = str(tmp_path)
            result = load_golden_answers("test_dept")

        assert len(result) == 2
        assert result[0]["id"] == "ga_test_001"
        assert result[0]["category"] == "lookup"
        assert result[0]["question"] == "What is the LCR?"
        assert result[1]["id"] == "ga_test_002"

    def test_load_nonexistent_file(self, tmp_path):
        with patch("src.golden_loader.settings") as mock_settings:
            mock_settings.EVAL_DATASET_PATH = str(tmp_path)
            result = load_golden_answers("nonexistent")

        assert result == []

    def test_load_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")

        with patch("src.golden_loader.settings") as mock_settings:
            mock_settings.EVAL_DATASET_PATH = str(tmp_path)
            result = load_golden_answers("empty")

        assert result == []

    def test_load_yaml_without_golden_answers_key(self, tmp_path):
        yaml_content = """
other_key:
  - something: else
"""
        yaml_file = tmp_path / "no_key.yaml"
        yaml_file.write_text(yaml_content)

        with patch("src.golden_loader.settings") as mock_settings:
            mock_settings.EVAL_DATASET_PATH = str(tmp_path)
            result = load_golden_answers("no_key")

        assert result == []

    def test_load_yaml_with_all_fields(self, tmp_path):
        yaml_content = """
golden_answers:
  - id: ga_full_001
    category: edge_case
    question: "What if rates drop 200bps?"
    expected_answer: "EVE would decrease significantly."
    acceptable_keywords: ["EVE", "decrease"]
    unacceptable_keywords: ["guaranteed", "exact"]
    expected_citations: ["alco_tracker"]
"""
        yaml_file = tmp_path / "full.yaml"
        yaml_file.write_text(yaml_content)

        with patch("src.golden_loader.settings") as mock_settings:
            mock_settings.EVAL_DATASET_PATH = str(tmp_path)
            result = load_golden_answers("full")

        assert len(result) == 1
        ga = result[0]
        assert ga["id"] == "ga_full_001"
        assert ga["category"] == "edge_case"
        assert ga["unacceptable_keywords"] == ["guaranteed", "exact"]
        assert ga["acceptable_keywords"] == ["EVE", "decrease"]
        assert ga["expected_citations"] == ["alco_tracker"]

    def test_load_yaml_with_minimal_fields(self, tmp_path):
        yaml_content = """
golden_answers:
  - id: ga_min_001
    category: lookup
    question: "Simple question?"
    expected_answer: "Simple answer."
"""
        yaml_file = tmp_path / "minimal.yaml"
        yaml_file.write_text(yaml_content)

        with patch("src.golden_loader.settings") as mock_settings:
            mock_settings.EVAL_DATASET_PATH = str(tmp_path)
            result = load_golden_answers("minimal")

        assert len(result) == 1
        assert result[0]["id"] == "ga_min_001"
        # Optional fields should not be present (loaded as raw dict from YAML)
        assert "unacceptable_keywords" not in result[0]
