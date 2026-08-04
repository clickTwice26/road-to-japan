"""Health probe tests."""

from __future__ import annotations


def test_index_returns_service_metadata(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["service"] == "roadtojapan"
    assert body["environment"] == "testing"


def test_liveness_does_not_touch_dependencies(client):
    resp = client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_readiness_reports_postgres_and_redis(client):
    resp = client.get("/api/v1/health/ready")
    assert resp.status_code == 200

    checks = resp.get_json()["checks"]
    assert checks["postgres"]["ok"] is True
    assert checks["redis"]["ok"] is True


def test_every_response_carries_a_request_id(client):
    resp = client.get("/api/v1/health/live")
    assert resp.headers["X-Request-ID"]


def test_inbound_request_id_is_echoed_back(client):
    resp = client.get("/api/v1/health/live", headers={"X-Request-ID": "abc-123"})
    assert resp.headers["X-Request-ID"] == "abc-123"
