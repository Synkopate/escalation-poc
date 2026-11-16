import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_db():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def test_lifecycle_and_audit(client):
    payload = {
        "ticket_id": 1042,
        "agent_id": 17,
        "issue": "Charging fails intermittently",
    }
    created = client.post("/webhooks/zendesk", json=payload)
    assert created.status_code == 201
    eid = created.json()["escalation_id"]
    duplicate = client.post("/webhooks/zendesk", json=payload)
    assert duplicate.json()["duplicate"] is True
    assert duplicate.json()["escalation_id"] == eid
    reply = client.post(
        f"/mock/chat-replies/{eid}",
        json={"manager_id": 5, "message": "Inspect the charger harness."},
    )
    assert reply.json()["status"] == "response_received"
    assert (
        client.post(
            f"/mock/chat-replies/{eid}",
            json={"manager_id": 5, "message": "Inspect the charger harness."},
        ).json()["duplicate"]
        is True
    )
    assert client.post(f"/mock/complete/{eid}").json()["status"] == "completed"
    assert client.post(f"/mock/complete/{eid}").status_code == 409
    assert [
        e["to_status"] for e in client.get(f"/escalations/{eid}/events").json()
    ] == [
        "created",
        "processing",
        "waiting_for_manager",
        "response_received",
        "completed",
    ]


def test_invalid_ticket(client):
    assert (
        client.post(
            "/webhooks/zendesk",
            json={"ticket_id": -1, "agent_id": 17, "issue": "Charging fails"},
        ).status_code
        == 422
    )


def test_cannot_complete_without_reply(client):
    eid = client.post(
        "/webhooks/zendesk",
        json={"ticket_id": 9, "agent_id": 1, "issue": "Charging fails"},
    ).json()["escalation_id"]
    assert client.post(f"/mock/complete/{eid}").status_code == 409
