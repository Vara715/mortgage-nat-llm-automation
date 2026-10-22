"""
test_api_e2e.py
===============
End-to-end tests for all FastAPI REST endpoints.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert data["service"] in ["morgage-loan-automation", "MortgageGuard AI", "mortgage_assistant", "mortgagae_assistent"]
    assert data["database"] == "connected"


def test_sources_endpoint():
    res = client.get("/api/sources")
    assert res.status_code == 200
    sources = res.json()
    assert len(sources) > 0
    assert any(s["jurisdiction"] == "US" for s in sources)
    assert any(s["jurisdiction"] == "IN" for s in sources)


def test_regulations_search():
    res = client.get("/api/regulations/search?query=points%20and%20fees&jurisdiction=US")
    assert res.status_code == 200
    data = res.json()
    assert data["jurisdiction"] == "US"
    assert len(data["results"]) > 0


def test_documents_list_and_get():
    res = client.get("/api/documents")
    assert res.status_code == 200
    docs = res.json()
    assert len(docs) > 0

    doc_id = docs[0]["id"]
    res_single = client.get(f"/api/documents/{doc_id}")
    assert res_single.status_code == 200
    assert res_single.json()["id"] == doc_id
    assert len(res_single.json()["extracted_fields"]) > 0


def test_compliance_analyses():
    res = client.get("/api/compliance/analyses")
    assert res.status_code == 200
    analyses = res.json()
    assert len(analyses) > 0

    analysis_id = analyses[0]["analysis_id"]
    res_single = client.get(f"/api/compliance/analyses/{analysis_id}")
    assert res_single.status_code == 200
    data = res_single.json()
    assert data["analysis_id"] == analysis_id
    assert len(data["findings"]) > 0
    assert "limitations" in data


def test_review_tasks_and_decision():
    res = client.get("/api/reviews/tasks")
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) > 0

    task = tasks[0]
    task_id = task["id"]

    # Submit review decision
    decision_payload = {
        "decision": "ACCEPTED",
        "new_status": "POTENTIAL_ISSUE",
        "comments": "Reviewed by senior compliance officer; points & fees violation confirmed.",
    }
    res_dec = client.post(f"/api/reviews/tasks/{task_id}/decision", json=decision_payload)
    assert res_dec.status_code == 200
    dec_data = res_dec.json()
    assert dec_data["decision"] == "ACCEPTED"
    assert dec_data["review_task_id"] == task_id


def test_hmda_analytics_api():
    res = client.get("/api/hmda/analytics")
    assert res.status_code == 200
    data = res.json()
    assert data["total_records"] >= 100
    assert data["avg_loan_amount"] > 0
    assert "disclaimer" in data


def test_audit_events_api():
    res = client.get("/api/audit/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) > 0
    assert any(e["event_type"] in ["REVIEW_DECISION_RECORDED", "COMPLIANCE_ANALYSIS_COMPLETED", "DOCUMENT_UPLOADED"] for e in events)


def test_report_pdf_download():
    # Fetch an analysis id
    res = client.get("/api/compliance/analyses")
    analyses = res.json()
    assert len(analyses) > 0
    analysis_id = analyses[0]["analysis_id"]

    res_pdf = client.get(f"/api/reports/{analysis_id}/pdf")
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert len(res_pdf.content) > 1000  # valid non-empty PDF bytes
