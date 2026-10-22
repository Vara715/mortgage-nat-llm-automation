"""
test_admin_api.py
=================
Tests for the Administration & Governance API endpoints.
"""

from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_admin_overview_endpoint():
    response = client.get("/api/admin/overview")
    assert response.status_code == 200
    data = response.json()
    assert data["system_name"] in ["mortgage_assistant", "mortgagae_assistent", "morgage-loan-automation"]
    assert data["database_connected"] is True
    assert data["registered_agents_count"] >= 6
    assert "optimizer_telemetry" in data


def test_admin_agents_telemetry():
    response = client.get("/api/admin/agents")
    assert response.status_code == 200
    agents = response.json()
    assert len(agents) >= 6
    agent_names = [a["name"] for a in agents]
    assert "IngestionExtractionAgent" in agent_names
    assert "ComplianceAuditAgent" in agent_names
    assert "HITLAgent" in agent_names


def test_admin_cache_clear():
    response = client.post("/api/admin/cache/clear")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["cache_size_now"] == 0


def test_admin_audit_trail_endpoint():
    response = client.get("/api/admin/audit-trail?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert "events" in data
