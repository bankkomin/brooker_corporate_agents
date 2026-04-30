"""Tests for cross_dept_router module."""
import pytest

from services.shared.cross_dept_router import (
    detect_departments,
    _synthesize_results,
)


class TestDetectDepartments:
    def test_single_dept_cac(self):
        result = detect_departments("What is the current LCR ratio?")
        assert result == ["cac"]

    def test_single_dept_finance(self):
        result = detect_departments("Show me the annual report")
        assert result == ["finance"]

    def test_single_dept_risk(self):
        result = detect_departments("What is the credit risk exposure?")
        assert result == ["risk"]

    def test_single_dept_legal(self):
        result = detect_departments("Check AML compliance status")
        assert result == ["legal"]

    def test_single_dept_hr(self):
        result = detect_departments("What is the current headcount?")
        assert result == ["hr"]

    def test_multi_dept_cac_and_finance(self):
        result = detect_departments("How does the LCR affect the balance sheet?")
        assert "cac" in result
        assert "finance" in result
        assert len(result) == 2

    def test_multi_dept_risk_and_legal(self):
        result = detect_departments("What is the credit risk compliance status?")
        assert "risk" in result
        assert "legal" in result

    def test_no_match_defaults_to_cac(self):
        result = detect_departments("Hello, how are you?")
        assert result == ["cac"]

    def test_case_insensitive(self):
        result = detect_departments("what is the lcr?")
        assert "cac" in result

    def test_cio_keywords(self):
        result = detect_departments("What is the current NAV of the fund?")
        assert "cio" in result

    def test_it_keywords(self):
        result = detect_departments("Review the IT policy for DevOps")
        assert "it" in result

    def test_comms_keywords(self):
        result = detect_departments("Draft a press release for IR")
        assert "comms" in result

    def test_ic_keywords(self):
        result = detect_departments("Show the IC minutes from the due diligence review")
        assert "ic" in result

    def test_vcc_keywords(self):
        result = detect_departments("List all VCC client subscriptions")
        assert "vcc" in result


class TestSynthesizeResults:
    def test_single_success(self):
        results = {"cac": {"response": "LCR is 150%"}}
        output = _synthesize_results("What is LCR?", results)
        assert "**CAC**" in output
        assert "LCR is 150%" in output

    def test_multiple_successes(self):
        results = {
            "cac": {"response": "LCR is 150%"},
            "finance": {"response": "Balance sheet is healthy"},
        }
        output = _synthesize_results("query", results)
        assert "**CAC**" in output
        assert "**FINANCE**" in output
        assert "---" in output

    def test_error_result(self):
        results = {"cac": {"error": "timeout"}}
        output = _synthesize_results("query", results)
        assert "Unable to retrieve" in output
        assert "timeout" in output

    def test_mixed_success_and_error(self):
        results = {
            "cac": {"response": "LCR is 150%"},
            "risk": {"error": "HTTP 500"},
        }
        output = _synthesize_results("query", results)
        assert "LCR is 150%" in output
        assert "Unable to retrieve" in output

    def test_empty_results(self):
        output = _synthesize_results("query", {})
        assert "No departments returned results" in output

    def test_missing_response_key(self):
        results = {"cac": {"data": "something"}}
        output = _synthesize_results("query", results)
        assert "No response" in output
