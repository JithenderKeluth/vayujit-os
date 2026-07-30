import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from vayujit_api.audit.models import AuditEvent
from vayujit_api.core.database import Base, get_session
from vayujit_api.core.test_database import reset_test_schema
from vayujit_api.identity.router import attempts
from vayujit_api.main import create_app
from vayujit_api.products.models import Product

TEST_DATABASE_URL = os.getenv("VAYUJIT_TEST_DATABASE_URL")
pytestmark = pytest.mark.integration
ORIGIN = {"Origin": "http://127.0.0.1:4200"}
PASSWORD = "correct horse battery staple"
test_factory: sessionmaker[Session] | None = None


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    global test_factory
    assert TEST_DATABASE_URL is not None and TEST_DATABASE_URL.startswith("postgresql")
    engine = create_engine(TEST_DATABASE_URL)
    reset_test_schema(engine, Base.metadata, database_url=TEST_DATABASE_URL)
    attempts.clear()
    test_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def test_session() -> Generator[Session, None, None]:
        assert test_factory is not None
        with test_factory() as session:
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
            "full_name": "Product Owner",
            "email": "owner@example.com",
            "password": PASSWORD,
            "password_confirmation": PASSWORD,
        },
        headers=ORIGIN,
    )
    assert response.status_code == 201


def create_brand(client: TestClient, name: str) -> dict[str, object]:
    response = client.post("/api/v1/brands", json={"name": name}, headers=ORIGIN)
    assert response.status_code == 201, response.text
    return response.json()


def product_payload(name: str, **overrides: object) -> dict[str, object]:
    return {
        "name": name,
        "product_type": "physical",
        "short_description": f"{name} description",
        "price_amount": "19.99",
        "price_currency": "usd",
        "sku": f"SKU-{name.upper().replace(' ', '-')}",
        "inventory_tracking_enabled": True,
        "inventory_quantity": 10,
        "low_stock_threshold": 2,
        **overrides,
    }


def create_product(client: TestClient, name: str, **overrides: object) -> dict[str, object]:
    response = client.post(
        "/api/v1/products",
        json=product_payload(name, **overrides),
        headers=ORIGIN,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_unauthenticated_access_and_missing_active_brand(client: TestClient) -> None:
    assert client.get("/api/v1/products").status_code == 401
    assert (
        client.post("/api/v1/products", json=product_payload("No Auth"), headers=ORIGIN).status_code
        == 401
    )
    authenticate(client)
    assert client.get("/api/v1/products").json()["items"] == []
    no_brand = client.post("/api/v1/products", json=product_payload("No Brand"), headers=ORIGIN)
    assert no_brand.status_code == 409


def test_complete_product_lifecycle_brand_move_and_audit(client: TestClient) -> None:
    authenticate(client)
    brand_a = create_brand(client, "Brand A")
    product = create_product(client, "Product A")
    assert product["brand_id"] == brand_a["id"]
    assert product["status"] == "draft"
    assert product["price_amount"] == "19.99"
    assert product["price_currency"] == "USD"

    activated = client.post(f"/api/v1/products/{product['id']}/activate", headers=ORIGIN)
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"

    brand_b = create_brand(client, "Brand B")
    moved = client.patch(
        f"/api/v1/products/{product['id']}",
        json={"brand_id": brand_b["id"]},
        headers=ORIGIN,
    )
    assert moved.status_code == 200
    assert moved.json()["brand_id"] == brand_b["id"]
    assert client.get(f"/api/v1/products?brand_id={brand_a['id']}").json()["total"] == 0
    assert client.get(f"/api/v1/products?brand_id={brand_b['id']}").json()["total"] == 1

    drafted = client.post(f"/api/v1/products/{product['id']}/move-to-draft", headers=ORIGIN)
    assert drafted.status_code == 200 and drafted.json()["status"] == "draft"
    assert (
        client.post(f"/api/v1/products/{product['id']}/move-to-draft", headers=ORIGIN).status_code
        == 200
    )
    archived = client.post(f"/api/v1/products/{product['id']}/archive", headers=ORIGIN)
    assert archived.status_code == 200 and archived.json()["archived_at"]
    assert (
        client.post(f"/api/v1/products/{product['id']}/archive", headers=ORIGIN).status_code == 200
    )
    assert client.get("/api/v1/products?all_brands=true").json()["total"] == 0
    assert client.get("/api/v1/products?all_brands=true&include_archived=true").json()["total"] == 1
    restored = client.post(f"/api/v1/products/{product['id']}/restore", headers=ORIGIN)
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"
    assert restored.json()["archived_at"] is None
    assert (
        client.post(f"/api/v1/products/{product['id']}/restore", headers=ORIGIN).status_code == 200
    )

    details = client.get(f"/api/v1/products/{product['id']}").json()
    assert {event["action"] for event in details["recent_audit_events"]} >= {
        "product.created",
        "product.activated",
        "product.brand_changed",
        "product.updated",
        "product.moved_to_draft",
        "product.archived",
        "product.restored",
    }


def test_uniqueness_scopes_and_partial_update(client: TestClient) -> None:
    authenticate(client)
    first_brand = create_brand(client, "First")
    second_brand = create_brand(client, "Second")
    first = create_product(client, "  Alpha   Product  ", brand_id=first_brand["id"])

    duplicate_name = client.post(
        "/api/v1/products",
        json=product_payload("alpha product", brand_id=first_brand["id"], sku="OTHER-SKU"),
        headers=ORIGIN,
    )
    assert duplicate_name.status_code == 409
    same_name_other_brand = create_product(
        client,
        "Alpha Product",
        brand_id=second_brand["id"],
        sku="SECOND-SKU",
        barcode="BAR-2",
    )
    assert same_name_other_brand["brand_id"] == second_brand["id"]
    duplicate_sku = client.post(
        "/api/v1/products",
        json=product_payload("Different", brand_id=second_brand["id"], sku=first["sku"]),
        headers=ORIGIN,
    )
    assert duplicate_sku.status_code == 409
    duplicate_barcode = create_product(
        client,
        "Barcode One",
        brand_id=first_brand["id"],
        sku="BARCODE-ONE",
        barcode="123456",
    )
    assert (
        client.post(
            "/api/v1/products",
            json=product_payload(
                "Barcode Two",
                brand_id=second_brand["id"],
                sku="BARCODE-TWO",
                barcode=duplicate_barcode["barcode"],
            ),
            headers=ORIGIN,
        ).status_code
        == 409
    )

    updated = client.patch(
        f"/api/v1/products/{first['id']}",
        json={"category": "New Category", "is_featured": True},
        headers=ORIGIN,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == first["name"]
    assert updated.json()["category"] == "New Category"
    assert updated.json()["is_featured"] is True
    assert (
        client.patch(
            f"/api/v1/products/{first['id']}",
            json={"name": None},
            headers=ORIGIN,
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/v1/products/{first['id']}",
            json={"tags": None},
            headers=ORIGIN,
        ).status_code
        == 422
    )


def test_money_inventory_weight_and_activation_validation(client: TestClient) -> None:
    authenticate(client)
    create_brand(client, "Commerce")
    invalid_payloads = [
        product_payload("Float Money", price_amount=19.99),
        product_payload("Negative Money", price_amount="-1.00"),
        product_payload("Bad Compare", price_amount="20.00", compare_at_price_amount="19.99"),
        product_payload("Bad Currency", price_currency="US"),
        product_payload("Bad Inventory", inventory_quantity=-1),
        product_payload("Bad Weight", weight_value="-1.000", weight_unit="kg"),
        product_payload("Missing Weight Unit", weight_value="1.250"),
    ]
    for payload in invalid_payloads:
        assert client.post("/api/v1/products", json=payload, headers=ORIGIN).status_code == 422

    incomplete = create_product(
        client,
        "Incomplete Service",
        product_type="service",
        short_description=None,
        price_amount=None,
        price_currency=None,
    )
    activation = client.post(f"/api/v1/products/{incomplete['id']}/activate", headers=ORIGIN)
    assert activation.status_code == 409
    assert activation.json()["detail"]["code"] == "product_not_ready"
    assert activation.json()["detail"]["fields"] == ["description"]


def test_list_filters_search_sort_and_pagination(client: TestClient) -> None:
    authenticate(client)
    active_brand = create_brand(client, "Active Brand")
    other_brand = create_brand(client, "Other Brand")
    create_product(
        client,
        "Zulu",
        brand_id=active_brand["id"],
        sku="SEARCH-001",
        category="Shoes",
        is_featured=True,
        inventory_quantity=2,
    )
    beta = create_product(
        client,
        "Beta",
        brand_id=active_brand["id"],
        sku="SEARCH-002",
        product_type="digital",
        category="Books",
        inventory_tracking_enabled=False,
        inventory_quantity=0,
    )
    create_product(
        client,
        "Other Product",
        brand_id=other_brand["id"],
        sku="OTHER-001",
    )
    client.post(f"/api/v1/products/{beta['id']}/archive", headers=ORIGIN)

    assert client.get("/api/v1/products").json()["total"] == 1
    assert client.get("/api/v1/products?all_brands=true").json()["total"] == 2
    assert client.get("/api/v1/products?search=zulu").json()["total"] == 1
    assert client.get("/api/v1/products?search=search-001").json()["total"] == 1
    assert client.get("/api/v1/products?sku=001").json()["total"] == 1
    assert client.get("/api/v1/products?category=Shoes").json()["total"] == 1
    assert client.get("/api/v1/products?product_type=physical").json()["total"] == 1
    assert client.get("/api/v1/products?featured=true").json()["total"] == 1
    archived = client.get("/api/v1/products?include_archived=true&status=archived").json()
    assert archived["total"] == 1
    page = client.get(
        "/api/v1/products?all_brands=true&page_size=1&page=2"
        "&sort_by=inventory_quantity&sort_direction=desc"
    ).json()
    assert page["pages"] == 2 and len(page["items"]) == 1


def test_archived_brand_restrictions_and_owner_safe_not_found(client: TestClient) -> None:
    authenticate(client)
    brand = create_brand(client, "Temporary")
    product = create_product(client, "Temporary Product", brand_id=brand["id"])
    client.post(f"/api/v1/products/{product['id']}/archive", headers=ORIGIN)
    client.post(f"/api/v1/brands/{brand['id']}/archive", headers=ORIGIN)

    assert (
        client.post(
            "/api/v1/products",
            json=product_payload("Blocked", brand_id=brand["id"]),
            headers=ORIGIN,
        ).status_code
        == 409
    )
    assert (
        client.post(f"/api/v1/products/{product['id']}/restore", headers=ORIGIN).status_code == 409
    )
    random_id = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/v1/products/{random_id}").status_code == 404
    assert (
        client.post(
            "/api/v1/products",
            json=product_payload("Unknown Brand", brand_id=random_id),
            headers=ORIGIN,
        ).status_code
        == 404
    )
    assert client.get("/api/v1/products/not-a-uuid").status_code == 422


def test_product_audit_metadata_is_bounded_and_safe(client: TestClient) -> None:
    authenticate(client)
    create_brand(client, "Audited")
    product = create_product(
        client, "Audited Product", description="Sensitive full product description"
    )
    assert test_factory is not None
    with test_factory() as db:
        event = db.scalar(select(AuditEvent).where(AuditEvent.entity_id == product["id"]))
        assert event is not None
        assert "description" not in str(event.metadata_json)
        assert db.scalar(select(func.count(Product.id))) == 1
