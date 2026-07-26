from fastapi.testclient import TestClient

from vayujit_api.main import app

client = TestClient(app)


def test_root_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_versioned_health_contract() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "vayujit-api",
        "version": "0.1.0",
        "environment": "development",
    }


def test_cors_is_restricted_to_local_web_origin() -> None:
    allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://127.0.0.1:4200",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:4200"
    assert "access-control-allow-origin" not in denied.headers
