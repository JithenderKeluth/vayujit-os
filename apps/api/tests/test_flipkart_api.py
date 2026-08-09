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


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    assert TEST_DATABASE_URL is not None
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    attempts.clear()
    app = create_app()
    app.dependency_overrides[get_session] = test_session
    with TestClient(app) as value:
        yield value
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    engine.dispose()


def test_flipkart_account_lifecycle(client: TestClient) -> None:
    setup = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Flipkart Owner",
            "email": "flipkart-owner@example.com",
            "password": "correct horse battery staple",
            "password_confirmation": "correct horse battery staple",
        },
        headers=ORIGIN,
    )
    assert setup.status_code == 201, setup.text
    created = client.post(
        "/api/v1/marketplaces/flipkart/accounts",
        json={
            "display_name": "Flipkart Sandbox",
            "seller_account_id": "seller-flipkart",
            "credentials": {},
        },
        headers=ORIGIN,
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]
    validated = client.post(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/validate", headers=ORIGIN
    )
    assert validated.status_code == 200, validated.text
    enabled = client.post(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/enable",
        json={"confirm": True},
        headers=ORIGIN,
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["enabled"] is True

    imported = client.post(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/orders/import",
        headers=ORIGIN,
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["orders"] == 1
    assert imported.json()["cancellations"] == 1
    assert imported.json()["returns"] == 1
    assert imported.json()["refunds"] == 1

    financials = client.post(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/financial-events/import",
        headers=ORIGIN,
    )
    assert financials.status_code == 200, financials.text
    assert financials.json()["settlements"] == 1
    assert financials.json()["lines"] == 1

    orders = client.get(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/orders", headers=ORIGIN
    )
    assert orders.status_code == 200, orders.text
    assert orders.json()[0]["fulfilments"][0]["remote_fulfilment_id"] == "FK-FULFILMENT-001"
    records = client.get(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/returns/records",
        headers=ORIGIN,
    )
    assert records.status_code == 200, records.text
    assert records.json()[0]["refunds"][0]["currency"] == "INR"
    profitability = client.get(
        f"/api/v1/marketplaces/flipkart/accounts/{account_id}/profitability",
        headers=ORIGIN,
    )
    assert profitability.status_code == 200, profitability.text
    assert profitability.json()["profit_status"] == "unavailable"
