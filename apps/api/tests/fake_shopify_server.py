"""Deterministic loopback-only fake for Shopify GraphQL acceptance tests."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast


@dataclass
class FakeShopifyState:
    token: str = "test-shopify-token"
    products: dict[str, dict[str, Any]] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)
    throttle_once: bool = False
    unavailable_once: bool = False
    next_product: int = 1
    next_variant: int = 1
    next_media: int = 1


class FakeShopifyServer:
    def __init__(self) -> None:
        self.state = FakeShopifyState()
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def do_POST(self) -> None:
                if self.path == "/upload":
                    self.send_response(204)
                    self.end_headers()
                    return
                if self.headers.get("X-Shopify-Access-Token") != state.token:
                    self._json(401, {"errors": [{"message": "unauthorized"}]})
                    return
                if state.unavailable_once:
                    state.unavailable_once = False
                    self._json(503, {"errors": [{"message": "unavailable"}]})
                    return
                length = int(self.headers.get("content-length", "0"))
                request = json.loads(self.rfile.read(length))
                query = str(request.get("query") or "")
                variables = request.get("variables") or {}
                operation = self._operation(query)
                if operation is None:
                    self._json(400, {"errors": [{"message": "unknown operation"}]})
                    return
                state.calls.append(operation)
                if state.throttle_once:
                    state.throttle_once = False
                    self._json(
                        200,
                        {
                            "errors": [
                                {
                                    "message": "throttled",
                                    "extensions": {"code": "THROTTLED"},
                                }
                            ]
                        },
                    )
                    return
                self._json(200, self._response(operation, variables))

            def _operation(self, query: str) -> str | None:
                for marker, name in (
                    ("VayujitValidate", "validate"),
                    ("VayujitCollections", "collections"),
                    ("VayujitPublications", "publications"),
                    ("VayujitProductCreate", "product_create"),
                    ("VayujitProductUpdate", "product_update"),
                    ("VayujitOptionsCreate", "options_create"),
                    ("VayujitVariantsCreate", "variants_create"),
                    ("VayujitVariantsUpdate", "variants_update"),
                    ("VayujitCollectionAdd", "collection_add"),
                    ("VayujitCollectionRemove", "collection_remove"),
                    ("VayujitPublish", "publish"),
                    ("VayujitUnpublish", "unpublish"),
                    ("VayujitStagedUpload", "staged_upload"),
                    ("VayujitMediaCreate", "media_create"),
                    ("VayujitProductStatus", "product_status"),
                ):
                    if marker in query:
                        return name
                return None

            def _response(self, operation: str, variables: dict[str, Any]) -> dict[str, Any]:
                data: dict[str, Any]
                if operation == "validate":
                    data = {
                        "shop": {
                            "id": "gid://shopify/Shop/1",
                            "name": "Fake VAYUJIT Store",
                            "primaryDomain": {"host": "fake.myshopify.com"},
                        }
                    }
                elif operation in {"collections", "publications"}:
                    key = operation
                    nodes = (
                        [
                            {
                                "id": "gid://shopify/Collection/1",
                                "title": "Featured",
                                "handle": "featured",
                            }
                        ]
                        if operation == "collections"
                        else [{"id": "gid://shopify/Publication/1", "name": "Online Store"}]
                    )
                    data = {
                        key: {"nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}
                    }
                elif operation == "product_create":
                    product_id = f"gid://shopify/Product/{state.next_product}"
                    state.next_product += 1
                    product = {
                        **variables["product"],
                        "id": product_id,
                        "handle": "fake-product",
                        "onlineStoreUrl": None,
                        "variants": {
                            "nodes": [
                                {
                                    "id": f"gid://shopify/ProductVariant/{state.next_variant}",
                                    "sku": None,
                                    "inventoryItem": {"id": "gid://shopify/InventoryItem/1"},
                                }
                            ]
                        },
                    }
                    state.next_variant += 1
                    state.products[product_id] = product
                    data = {"productCreate": {"product": product, "userErrors": []}}
                elif operation == "product_update":
                    product = state.products[str(variables["product"]["id"])]
                    product.update(variables["product"])
                    data = {"productUpdate": {"product": product, "userErrors": []}}
                elif operation in {"variants_create", "variants_update"}:
                    variants = []
                    for value in variables["variants"]:
                        variants.append(
                            {
                                **value,
                                "id": value.get("id")
                                or f"gid://shopify/ProductVariant/{state.next_variant}",
                                "inventoryItem": {
                                    "id": f"gid://shopify/InventoryItem/{state.next_variant}"
                                },
                                "selectedOptions": [
                                    {"name": item["optionName"], "value": item["name"]}
                                    for item in value.get("optionValues", [])
                                ],
                            }
                        )
                        state.next_variant += 1
                    key = (
                        "productVariantsBulkCreate"
                        if operation == "variants_create"
                        else "productVariantsBulkUpdate"
                    )
                    data = {key: {"productVariants": variants, "userErrors": []}}
                elif operation == "options_create":
                    data = {"productOptionsCreate": {"userErrors": []}}
                elif operation in {"collection_add", "collection_remove"}:
                    key = (
                        "collectionAddProducts"
                        if operation == "collection_add"
                        else "collectionRemoveProducts"
                    )
                    data = {key: {"userErrors": []}}
                elif operation in {"publish", "unpublish"}:
                    key = "publishablePublish" if operation == "publish" else "publishableUnpublish"
                    data = {key: {"userErrors": []}}
                elif operation == "staged_upload":
                    data = {
                        "stagedUploadsCreate": {
                            "stagedTargets": [
                                {
                                    "url": "https://storage.googleapis.com/upload",
                                    "resourceUrl": "https://storage.googleapis.com/resource",
                                    "parameters": [{"name": "key", "value": "test"}],
                                }
                            ],
                            "userErrors": [],
                        }
                    }
                elif operation == "media_create":
                    data = {
                        "productCreateMedia": {
                            "media": [
                                {
                                    "id": f"gid://shopify/MediaImage/{state.next_media}",
                                    "status": "READY",
                                    "alt": variables["media"][0].get("alt"),
                                }
                            ],
                            "userErrors": [],
                        }
                    }
                    state.next_media += 1
                else:
                    lookup_product = state.products.get(str(variables["id"]))
                    data = {"product": lookup_product}
                return {
                    "data": data,
                    "extensions": {
                        "cost": {
                            "requestedQueryCost": 10,
                            "actualQueryCost": 10,
                            "throttleStatus": {"currentlyAvailable": 990, "restoreRate": 50},
                        }
                    },
                }

            def _json(self, status: int, value: object) -> None:
                body = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = cast(tuple[str, int], self.httpd.server_address)
        return f"http://{host}:{port}"

    def __enter__(self) -> FakeShopifyServer:
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.httpd.shutdown()
        self.thread.join(timeout=2)
        self.httpd.server_close()
