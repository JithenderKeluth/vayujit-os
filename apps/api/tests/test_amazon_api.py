import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.router import attempts
from vayujit_api.main import create_app

pytestmark = pytest.mark.integration
TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    assert TEST_DATABASE_URL is not None and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    attempts.clear()
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def test_amazon_account_lifecycle_and_idempotent_imports(client: TestClient) -> None:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Amazon Owner",
            "email": "amazon-owner@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text

    created = client.post(
        "/api/v1/marketplaces/amazon/accounts",
        json={
            "display_name": "Amazon Sandbox",
            "seller_account_id": "seller-api",
            "credentials": {},
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    account = created.json()
    assert account["enabled"] is False
    assert "token" not in created.text
    account_id = account["id"]

    enabled = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/enable",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert enabled.status_code == 200, enabled.text
    validated = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/validate",
        headers=ORIGIN,
    )
    assert validated.status_code == 200
    disabled = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/disable",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert disabled.status_code == 200
    revalidated = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/revalidate",
        headers=ORIGIN,
    )
    assert revalidated.status_code == 200
    assert revalidated.json()["enabled"] is False

    first_orders = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/orders/import",
        headers=ORIGIN,
    )
    second_orders = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/orders/import",
        headers=ORIGIN,
    )
    assert first_orders.json()["imported"] == 1
    assert second_orders.json()["imported"] == 0

    first_returns = client.get(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/returns",
        headers=ORIGIN,
    )
    assert first_returns.status_code == 200, first_returns.text
    assert first_returns.json()["imported"] == 1
    listed_returns = client.get(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/returns/records",
        headers=ORIGIN,
    )
    assert listed_returns.status_code == 200, listed_returns.text
    assert listed_returns.json()[0]["refunds"][0]["status"] == "reported"

    first_financials = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/financial-events/import",
        headers=ORIGIN,
    )
    second_financials = client.post(
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/financial-events/import",
        headers=ORIGIN,
    )
    assert first_financials.json()["settlements"] == 1
    assert second_financials.json()["settlements"] == 0
    assert second_financials.json()["imported"] == 0

    removed = client.request(
        "DELETE",
        f"/api/v1/marketplaces/amazon/accounts/{account_id}/credentials",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert removed.status_code == 200
    assert removed.json()["credential_status"] == "missing"
