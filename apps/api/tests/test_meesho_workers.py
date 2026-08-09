from vayujit_api.commerce.meesho import MeeshoCommerceConnector, reset_fake_meesho_state


def test_meesho_worker_idempotency_reuses_remote_listing() -> None:
    reset_fake_meesho_state()
    connector = MeeshoCommerceConnector(seller_id="worker-seller")
    first = connector.submit(
        sku="MS-WORKER-1", payload={"title": "Worker"}, idempotency_key="worker-1"
    )
    second = connector.submit(
        sku="MS-WORKER-1", payload={"title": "Worker"}, idempotency_key="worker-1"
    )
    assert first.remote_id == second.remote_id


def test_meesho_crash_before_connector_recovery_is_idempotent() -> None:
    reset_fake_meesho_state()
    connector = MeeshoCommerceConnector(seller_id="crash-before")
    first = connector.submit(
        sku="MS-CRASH-1", payload={"title": "Crash"}, idempotency_key="crash-before-1"
    )
    recovered = connector.submit(
        sku="MS-CRASH-1", payload={"title": "Crash"}, idempotency_key="crash-before-1"
    )
    assert first.remote_id == recovered.remote_id
    assert connector.reconcile_listing(str(first.remote_id))["status"] == "ACTIVE"


def test_meesho_crash_after_ambiguous_update_reconciles_remote_state() -> None:
    reset_fake_meesho_state()
    connector = MeeshoCommerceConnector(seller_id="crash-after")
    submitted = connector.submit(
        sku="MS-CRASH-2", payload={"title": "Before"}, idempotency_key="crash-after-submit"
    )
    result = connector.transport.update_listing(
        remote_id=str(submitted.remote_id),
        title="After",
        sku=None,
        idempotency_key="ambiguous-crash-after",
    )
    assert result.ambiguous is True
    reconciled = connector.reconcile_listing(str(submitted.remote_id))
    assert reconciled["status"] == "ACTIVE"
    assert reconciled["payload"]["title"] == "After"


def test_meesho_ambiguous_price_inventory_and_throttle_are_safe() -> None:
    reset_fake_meesho_state()
    connector = MeeshoCommerceConnector(seller_id="edge-cases")
    submitted = connector.submit(
        sku="MS-EDGE-1", payload={"title": "Edge"}, idempotency_key="edge-submit"
    )
    price = connector.update_price(
        remote_id=str(submitted.remote_id),
        payload={"selling_price": "99", "currency": "INR"},
        idempotency_key="ambiguous-price",
    )
    assert price["ambiguous"] is True
    inventory = connector.update_inventory("MS-EDGE-1", 4, "ambiguous-inventory")
    assert inventory["ambiguous"] is True
    throttled = connector.submit(
        sku="MS-EDGE-2", payload={"title": "Throttle"}, idempotency_key="throttle-submit"
    )
    assert throttled.retryable is True
    retried = connector.submit(
        sku="MS-EDGE-2", payload={"title": "Throttle"}, idempotency_key="throttle-submit"
    )
    assert retried.remote_id is not None
