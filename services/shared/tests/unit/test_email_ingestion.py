import pytest
from unittest.mock import AsyncMock, MagicMock
from services.shared.email_ingestion import EmailIngestionPipeline, EmailMessage, _clean_email_body, _resolve_department
from datetime import datetime

def test_clean_email_body_removes_signature():
    body = "Hi team, the LCR is 118.5% as of today. Best regards, Jane"
    cleaned = _clean_email_body(body)
    assert "118.5%" in cleaned
    assert "Best regards" not in cleaned

def test_clean_email_body_removes_reply_chain():
    body = "The NSFR looks good. -----Original Message----- Previous content here"
    cleaned = _clean_email_body(body)
    assert "NSFR" in cleaned
    assert "Original Message" not in cleaned

def test_resolve_department_exact_match():
    mapping = {"jane@brooker.com": "finance", "@brooker.com": "cac"}
    assert _resolve_department("jane@brooker.com", [], mapping) == "finance"

def test_resolve_department_domain_fallback():
    mapping = {"@brooker.com": "cac"}
    assert _resolve_department("unknown@brooker.com", [], mapping) == "cac"

def test_resolve_department_default():
    assert _resolve_department("external@other.com", [], {}) == "cac"
