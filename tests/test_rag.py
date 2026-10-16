import sys
from datetime import date
sys.path.insert(0, "src/rag")
from retriever import answer, check_claim

def test_current_policy_used():
    assert "14 days" in answer("What is the refund window?")

def test_historical_policy():
    assert "7 days" in answer("What was the refund window?", as_of=date(2026, 3, 1))

def test_future_policy_ignored():
    assert "30 days" not in answer("What is the refund window?")

def test_restricted_doc_blocked():
    assert "Sorry" in answer("Who are the escalation contacts?", role="public")

def test_restricted_doc_allowed_for_admin():
    assert "admins only" in answer("Who are the escalation contacts?", role="admin")

def test_injection_removed():
    assert "admin data" not in answer("How do I reset my device?")

def test_missing_evidence_refused():
    assert "Sorry" in answer("Do you offer laptop warranty?")

def test_historical_without_date_asks_clarification():
    assert "Which date" in answer("What was the refund window?")

def test_unsupported_claims_detected():
    assert check_claim("Refunds are allowed within 30 days of delivery.").startswith("CONTRADICTED")
    assert check_claim("We offer free laptop insurance.").startswith("UNSUPPORTED")