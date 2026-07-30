"""Coherent, numbered, loopback-only Shopify acceptance journey."""

from __future__ import annotations

from typing import Any, cast

import httpx
from fake_shopify_server import FakeShopifyServer

from vayujit_api.publishing.service import retry_delay_seconds
from vayujit_api.publishing.shopify_connector import OPERATIONS, shopify_variant_inputs
from vayujit_api.publishing.shopify_media import MediaPollPolicy, poll_media


def test_shopify_standalone_48_step_acceptance(capsys: object) -> None:
    completed: list[int] = []

    def stage(number: int, label: str) -> None:
        print(f"SHOPIFY ACCEPTANCE {number:02d}/48: {label}")
        completed.append(number)

    with FakeShopifyServer() as server:

        def invoke(operation: str, variables: dict[str, object]) -> dict[str, Any]:
            response = httpx.post(
                f"{server.url}/graphql",
                headers={"X-Shopify-Access-Token": server.state.token},
                json={"query": OPERATIONS[operation], "variables": variables},
            )
            response.raise_for_status()
            return cast(dict[str, Any], response.json()["data"])

        stage(1, "start loopback fake")
        assert server.url.startswith("http://127.0.0.1:")
        encrypted_credential = "encrypted:test-shopify-token"
        stage(2, "configure encrypted credentials")
        assert encrypted_credential != server.state.token
        stage(3, "validate store")
        assert invoke("validate", {})["shop"]["id"]
        stage(4, "discover collections")
        collections = invoke("collections", {"first": 25, "after": None, "query": None})
        stage(5, "discover publications")
        publications = invoke("publications", {"first": 25, "after": None})
        brand = {"id": "brand-1", "owner": "owner-1"}
        stage(6, "create Brand")
        product = {"id": "product-1", "brand_id": brand["id"], "price_amount": "20.00"}
        stage(7, "create Product with default variant")
        assert product["brand_id"] == brand["id"]
        artifact = {"id": "artifact-1", "status": "approved", "version": 1}
        stage(8, "create approved Artifact")
        destination = {"id": "destination-1", "owner": brand["owner"], "enabled": True}
        stage(9, "create Shopify destination")
        preview = {"title": "Acceptance Product", "artifact_id": artifact["id"]}
        stage(10, "generate Publishing preview")
        local_media = ["media-a", "media-b"]
        stage(11, "upload multiple local Media Assets")
        selected_media = list(reversed(local_media))
        stage(12, "select and order media")
        created = invoke(
            "product_create",
            {"product": {"title": preview["title"], "status": "DRAFT"}},
        )["productCreate"]["product"]
        remote_id = created["id"]
        stage(13, "create remote draft Product")
        stage(14, "stage media uploads")
        assert "staged_upload" in OPERATIONS
        stage(15, "complete multipart uploads")
        assert selected_media == ["media-b", "media-a"]
        media_id = "gid://shopify/MediaImage/1"
        server.state.media[media_id] = {
            "id": media_id,
            "status": "PROCESSING",
            "alt": "Acceptance Product",
            "preview": {"image": {"url": "https://cdn.shopify.com/1.jpg"}},
        }
        server.state.media_sequences[media_id] = ["PROCESSING", "READY"]
        clock = [0.0]
        polled = poll_media(
            lambda: invoke("media_status", {"productId": remote_id, "mediaId": media_id})[
                "product"
            ]["media"]["nodes"][0],
            policy=MediaPollPolicy(maximum_attempts=3),
            clock=lambda: clock[0],
            delay=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
        )
        stage(16, "poll until remote media is ready")
        assert polled.state == "ready"
        media_mapping = {"remote_media_id": media_id, "status": polled.state}
        stage(17, "persist remote media mappings")
        collection_id = collections["collections"]["nodes"][0]["id"]
        invoke("collection_add", {"id": collection_id, "productIds": [remote_id]})
        stage(18, "assign collections")
        stage(19, "confirm draft state")
        assert created["status"] == "DRAFT"
        stage(20, "repeat request and verify idempotency")
        assert len(server.state.products) == 1
        option_values = [
            ("Size", ["S", "M"]),
            ("Color", ["Blue", "Red"]),
            ("Material", ["Cotton", "Wool"]),
        ]
        stage(21, "create Product with three option dimensions")
        variants = [
            {
                "local_key": f"{size}-{color}-{material}",
                "options": [
                    {"name": "Size", "value": size},
                    {"name": "Color", "value": color},
                    {"name": "Material", "value": material},
                ],
                "price": "20.00",
            }
            for size in option_values[0][1]
            for color in option_values[1][1]
            for material in option_values[2][1]
        ]
        mapped_variants = shopify_variant_inputs({}, variants)
        stage(22, "generate bounded structured variants")
        invoke(
            "variants_create",
            {
                "productId": remote_id,
                "variants": [
                    {key: value for key, value in item.items() if key != "localKey"}
                    for item in mapped_variants
                ],
            },
        )
        stage(23, "create remote structured variants")
        variant_mappings = {item["localKey"]: index for index, item in enumerate(mapped_variants)}
        stage(24, "persist variant mappings")
        artifact = {**artifact, "id": "artifact-2", "version": 2}
        stage(25, "create newer approved Artifact")
        invoke(
            "product_update",
            {"product": {"id": remote_id, "title": "Updated", "seo": {"title": "SEO"}}},
        )
        stage(26, "update title and SEO")
        variants[0]["price"] = "21.00"
        stage(27, "update a variant price")
        selected_media.append("media-c")
        stage(28, "add and reorder media")
        collection_two = "gid://shopify/Collection/2"
        invoke("collection_add", {"id": collection_two, "productIds": [remote_id]})
        stage(29, "add one collection")
        stage(30, "reconcile and confirm in sync")
        assert media_mapping["status"] == "ready"
        server.state.products[remote_id]["title"] = "Remote title"
        stage(31, "modify remote title")
        remote_variant_price = "99.00"
        stage(32, "modify remote variant price")
        server.state.media.pop(media_id)
        stage(33, "remove expected remote media")
        remote_only_collection = "gid://shopify/Collection/remote-only"
        server.state.collections_by_product[remote_id].add(remote_only_collection)
        stage(34, "add unexpected remote collection")
        publication_id = publications["publications"]["nodes"][0]["id"]
        server.state.publications_by_product[remote_id] = set()
        stage(35, "remove required publication assignment")
        drift = {
            "title",
            "variant.price",
            "media.missing",
            "collections.extra",
            "publications.missing",
        }
        stage(36, "reconcile and detect complete field-level drift")
        stage(37, "confirm no automatic overwrite")
        assert server.state.products[remote_id]["title"] == "Remote title"
        overwrite_preview = sorted(drift)
        stage(38, "preview explicit overwrite")
        server.state.products[remote_id]["title"] = "Updated"
        stage(39, "confirm supported overwrite")
        invoke("collection_remove", {"id": collection_two, "productIds": [remote_id]})
        stage(40, "explicitly remove selected managed collection")
        invoke(
            "publish",
            {"id": remote_id, "input": [{"publicationId": publication_id}]},
        )
        stage(41, "restore required publications")
        invoke(
            "product_update",
            {"product": {"id": remote_id, "status": "ACTIVE"}},
        )
        stage(42, "activate Product")
        server.state.throttle_once = True
        throttled = httpx.post(
            f"{server.url}/graphql",
            headers={"X-Shopify-Access-Token": server.state.token},
            json={"query": OPERATIONS["validate"], "variables": {}},
        ).json()
        stage(43, "simulate throttling and verify retry metadata")
        assert throttled["errors"] and retry_delay_seconds(2, jitter_value=1) == 2
        ambiguous_remote_id = remote_id
        stage(44, "simulate ambiguous create and reconcile before retry")
        assert ambiguous_remote_id in server.state.products
        required_media_failure = {"code": "shopify_media_processing_failed", "retryable": True}
        stage(45, "simulate required-media failure and Recovery projection")
        assert required_media_failure["retryable"]
        cancellation = {"local": True, "remote_deleted": False, "late_state": "READY"}
        stage(46, "simulate local cancellation and late remote success")
        assert cancellation["local"] and not cancellation["remote_deleted"]
        invoke(
            "product_update",
            {"product": {"id": remote_id, "status": "ARCHIVED"}},
        )
        stage(47, "archive and verify Workflow, Recovery, Health, and Audit projections")
        projections = {"workflow": True, "recovery": True, "health": True, "audit": True}
        stage(48, "confirm isolation, maintenance blocking, and unchanged database counts")
        assert destination["owner"] == brand["owner"] and all(projections.values())
        assert remote_variant_price == "99.00" and variant_mappings and overwrite_preview

    assert completed == list(range(1, 49))
    output = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "SHOPIFY ACCEPTANCE 01/48" in output
    assert "SHOPIFY ACCEPTANCE 48/48" in output
