from fastapi.testclient import TestClient

from vayujit_api.main import app, create_app

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


def test_cors_supports_both_local_web_origins_and_rejects_unknown() -> None:
    for origin in ("http://127.0.0.1:4200", "http://localhost:4200"):
        allowed = client.options(
            "/api/v1/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == origin

    denied = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert "access-control-allow-origin" not in denied.headers


def test_cors_headers_survive_unhandled_500() -> None:
    test_app = create_app()

    @test_app.get("/cors-recovery-test")
    def raise_unhandled_error() -> None:
        raise RuntimeError("synthetic failure")

    response = TestClient(test_app, raise_server_exceptions=False).get(
        "/cors-recovery-test", headers={"Origin": "http://localhost:4200"}
    )
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:4200"
