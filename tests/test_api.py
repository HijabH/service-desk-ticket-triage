from fastapi.testclient import TestClient

from triage import api
from triage.service import TriageService


def client() -> TestClient:
    api.service = TriageService()  # rules only, no network
    return TestClient(api.app)


def test_health():
    response = client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "mode": "rules"}


def test_triage_one_ticket():
    response = client().post("/triage", json={"subject": "Account locked", "body": "password reset needed"})

    assert response.status_code == 200
    data = response.json()
    assert data["category"] == "access"
    assert data["source"] == "rules"


def test_triage_batch_and_metrics():
    c = client()
    response = c.post("/triage/batch", json=[{"subject": "VPN down"}, {"subject": "Outlook not syncing"}])

    assert [r["category"] for r in response.json()] == ["network", "email"]
    assert c.get("/metrics").json()["tickets_triaged"] == 2


def test_rejects_a_ticket_without_subject():
    assert client().post("/triage", json={"body": "no subject"}).status_code == 422
