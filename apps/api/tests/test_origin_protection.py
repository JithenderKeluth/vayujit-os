from fastapi import FastAPI
from fastapi.testclient import TestClient

from vayujit_api.core.origin import OriginProtectionMiddleware


def make_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(OriginProtectionMiddleware)

    @app.post("/change")
    def change() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_browser_development_origin_is_allowed() -> None:
    response = make_client().post("/change", headers={"Origin": "http://127.0.0.1:4200"})
    assert response.status_code == 200


def test_electron_application_origin_is_allowed() -> None:
    response = make_client().post("/change", headers={"Origin": "app://vayujit"})
    assert response.status_code == 200


def test_missing_origin_is_rejected() -> None:
    response = make_client().post("/change")
    assert response.status_code == 403


def test_malformed_origin_is_rejected() -> None:
    response = make_client().post("/change", headers={"Origin": "not an origin"})
    assert response.status_code == 403


def test_disallowed_origin_is_rejected() -> None:
    response = make_client().post("/change", headers={"Origin": "https://example.com"})
    assert response.status_code == 403
