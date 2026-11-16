from fastapi.testclient import TestClient

from app.main import app, escalations

client = TestClient(app)


def setup_function():
    escalations.clear()


def test_escalation_lifecycle():
    payload = {"ticket_id": 1042, "agent_id": 17, "issue": "Charging fails intermittently"}
    first = client.post("/webhooks/zendesk", json=payload)
    assert first.status_code == 201
    escalation_id = first.json()["escalation_id"]

    repeated = client.post("/webhooks/zendesk", json=payload)
    assert repeated.json()["duplicate"] is True
    assert repeated.json()["escalation_id"] == escalation_id

    reply = client.post(f"/mock/chat-replies/{escalation_id}", json={"manager_id": 5, "message": "Inspect the charger harness."})
    assert reply.status_code == 200
    assert reply.json()["mock_zendesk_action"]["set_status"] == "open"
    assert reply.json()["mock_zendesk_action"]["remove_tag"] == "technical_escalation"
    assert client.get(f"/escalations/{escalation_id}").json()["status"] == "manager_responded"

    repeated_reply = client.post(f"/mock/chat-replies/{escalation_id}", json={"manager_id": 5, "message": "Inspect the charger harness."})
    assert repeated_reply.json()["duplicate"] is True


def test_invalid_ticket():
    response = client.post("/webhooks/zendesk", json={"ticket_id": -1, "agent_id": 17, "issue": "Charging fails"})
    assert response.status_code == 422
