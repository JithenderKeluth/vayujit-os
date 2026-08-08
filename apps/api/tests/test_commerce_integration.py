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

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
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


def authenticate(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/setup-owner",
        json={
            "full_name": "Commerce Owner",
            "email": "commerce@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text


def create_product(client: TestClient) -> tuple[str, str]:
    brand = client.post("/api/v1/brands", json={"name": "Commerce Brand"}, headers=ORIGIN)
    assert brand.status_code == 201, brand.text
    product = client.post(
        "/api/v1/products",
        json={
            "brand_id": brand.json()["id"],
            "name": "Commerce Product",
            "product_type": "physical",
        },
        headers=ORIGIN,
    )
    assert product.status_code == 201, product.text
    return brand.json()["id"], product.json()["id"]


def test_fake_marketplace_flow_is_owner_scoped_and_idempotent(client: TestClient) -> None:
    authenticate(client)
    brand_id, product_id = create_product(client)
    account = client.post(
        "/api/v1/marketplaces/accounts",
        json={
            "marketplace": "amazon",
            "display_name": "Fake Amazon",
            "seller_account_id": "seller-1",
        },
        headers=ORIGIN,
    )
    assert account.status_code == 201, account.text
    account_id = account.json()["id"]
    assert "credentials" not in account.json()
    validated = client.post(f"/api/v1/marketplaces/accounts/{account_id}/validate", headers=ORIGIN)
    assert validated.status_code == 200
    assert (
        client.post(
            f"/api/v1/marketplaces/accounts/{account_id}/enable", headers=ORIGIN
        ).status_code
        == 200
    )
    listing_payload = {
        "brand_id": brand_id,
        "product_id": product_id,
        "account_id": account_id,
        "title": "Commerce Product Listing",
        "idempotency_key": "listing-1",
    }
    listing = client.post("/api/v1/marketplaces/listings", json=listing_payload, headers=ORIGIN)
    assert listing.status_code == 201, listing.text
    repeated = client.post("/api/v1/marketplaces/listings", json=listing_payload, headers=ORIGIN)
    assert repeated.status_code == 201
    assert repeated.json()["id"] == listing.json()["id"]
    listing_id = listing.json()["id"]
    inventory = client.post(
        "/api/v1/marketplaces/inventory",
        json={"listing_id": listing_id, "available_quantity": 4, "idempotency_key": "inventory-1"},
        headers=ORIGIN,
    )
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()["available_quantity"] == 4
    assert (
        client.post(
            f"/api/v1/marketplaces/orders/import?account_id={account_id}", headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/marketplaces/settlements/import?account_id={account_id}", headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/marketplaces/orders").json()[0]["buyer_summary"]["display_name"]
        == "Masked buyer"
    )
    analytics = client.get("/api/v1/marketplaces/analytics")
    assert analytics.status_code == 200
    assert analytics.json()["profit_status"] == "unavailable"
    assert (
        client.post(
            f"/api/v1/marketplaces/listings/{listing_id}/reconcile", headers=ORIGIN
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/marketplaces/categories", params={"account_id": account_id}).status_code
        == 200
    )


def test_marketplace_writes_require_origin_and_owner_scope(client: TestClient) -> None:
    authenticate(client)
    response = client.post(
        "/api/v1/marketplaces/accounts",
        json={"marketplace": "meesho", "display_name": "No Origin", "seller_account_id": "seller"},
    )
    assert response.status_code == 403
    assert client.get("/api/v1/marketplaces/accounts").status_code == 200
    assert client.get("/api/v1/marketplaces/listings").json() == []
