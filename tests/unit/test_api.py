"""FastAPI service smoke tests (read-only; simulated allocations only)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apexsignal.api.main import create_app

client = TestClient(create_app())


def test_health_reports_safe_mode() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["enable_live_trading"] is False
    assert body["data"]["fixture_race"] is True


def test_version_and_disclaimer() -> None:
    assert client.get("/version").json()["version"]
    assert "not affiliated" in client.get("/disclaimer").json()["disclaimer"]


def test_demo_state_has_drivers() -> None:
    body = client.get("/races/demo/state").json()
    assert body["drivers"]


def test_opportunities_endpoint() -> None:
    body = client.get("/opportunities").json()
    assert "opportunities" in body
    assert isinstance(body["opportunities"], list)


def test_allocations_endpoint() -> None:
    r = client.post("/allocations", json={"bankroll": 10000, "tolerance": "moderate"})
    assert r.status_code == 200
    body = r.json()
    assert body["bankroll"] == 10000
    # Either simulated positions with capped deployment, or the no-opportunity message.
    assert "positions" in body and "message" in body


def test_allocations_rejects_bad_bankroll() -> None:
    assert client.post("/allocations", json={"bankroll": -5}).status_code == 422
