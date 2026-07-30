import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Literal

import httpx

from vayujit_api.publishing.connector import ConnectorFailure, ConnectorResult

MAX_GRAPHQL_RESPONSE_BYTES = 1_000_000
SHOP_DOMAIN = re.compile(r"^(?=.{4,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.myshopify\.com$")
API_VERSION = re.compile(r"^20\d{2}-(?:01|04|07|10)$")

OPERATIONS = {
    "validate": "query VayujitValidate { shop { id name primaryDomain { host } } }",
    "collections": """query VayujitCollections($first:Int!,$after:String,$query:String) {
      collections(first:$first,after:$after,query:$query) { nodes { id title handle }
      pageInfo { hasNextPage endCursor } } }""",
    "publications": """query VayujitPublications($first:Int!,$after:String) {
      publications(first:$first,after:$after) {
      nodes { id name } pageInfo { hasNextPage endCursor } } }""",
    "product_create": """mutation VayujitProductCreate($product:ProductCreateInput!) {
      productCreate(product:$product) { product { id title handle status onlineStoreUrl }
      userErrors { field message code } } }""",
    "product_update": """mutation VayujitProductUpdate($product:ProductUpdateInput!) {
      productUpdate(product:$product) { product { id title handle status onlineStoreUrl }
      userErrors { field message code } } }""",
    "product_status": """query VayujitProductStatus($id:ID!) {
      product(id:$id) { id title handle status vendor productType tags
      seo { title description } updatedAt } }""",
}


def validate_shop_domain(value: str, *, resolve_dns: bool = True) -> str:
    domain = value.strip().casefold().rstrip(".")
    if "://" in domain or any(char in domain for char in "/?#@"):
        raise ValueError("Enter only a Shopify myshopify.com store domain.")
    if not SHOP_DOMAIN.fullmatch(domain):
        raise ValueError("Shop domain must use the store-name.myshopify.com format.")
    if resolve_dns:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(domain, 443)}
        except socket.gaierror as error:
            raise ValueError("Shopify store domain could not be resolved.") from error
        if not addresses:
            raise ValueError("Shopify store domain could not be resolved.")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_multicast
                or ip.is_reserved
                or ip.is_unspecified
            ):
                raise ValueError("Shopify store domain resolved to a blocked network.")
    return domain


def validate_api_version(value: str) -> str:
    if not API_VERSION.fullmatch(value):
        raise ValueError("Shopify API version must use the YYYY-MM quarterly format.")
    return value


def safe_description_html(value: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", value) if part.strip()]
    return "".join(f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>" for part in paragraphs)[
        :50_000
    ]


def shopify_product_input(
    snapshot: dict[str, object],
    destination: dict[str, object],
    *,
    status: Literal["DRAFT", "ACTIVE", "ARCHIVED"],
    remote_id: str | None = None,
) -> dict[str, object]:
    title = str(snapshot.get("product_title") or snapshot.get("product_name") or "").strip()
    if not title:
        raise ValueError("Shopify products require a title.")
    tags = destination.get("default_tags") or snapshot.get("keywords") or []
    if not isinstance(tags, list) or any(not isinstance(item, str) for item in tags):
        raise ValueError("Shopify tags must be a bounded list of text values.")
    result: dict[str, object] = {
        "title": title[:255],
        "descriptionHtml": safe_description_html(str(snapshot.get("long_description") or "")),
        "status": status,
        "vendor": str(destination.get("default_vendor") or snapshot.get("brand_name") or "")[:255],
        "productType": str(
            destination.get("default_product_type") or snapshot.get("product_category") or ""
        )[:255],
        "tags": list(dict.fromkeys(item.strip()[:255] for item in tags if item.strip()))[:100],
        "seo": {
            "title": str(snapshot.get("seo_title") or "")[:70],
            "description": str(snapshot.get("seo_description") or "")[:320],
        },
    }
    if remote_id:
        result["id"] = remote_id
    return result


@dataclass(frozen=True)
class ShopifyThrottle:
    requested_cost: int | None = None
    actual_cost: int | None = None
    currently_available: int | None = None
    restore_rate: float | None = None


class ShopifyGraphQLClient:
    key = "shopify"
    name = "Shopify"
    connector_type = "remote"

    def __init__(
        self,
        *,
        shop_domain: str,
        access_token: str,
        api_version: str,
        timeout_seconds: int = 45,
        transport: httpx.BaseTransport | None = None,
        resolve_dns: bool = True,
    ) -> None:
        self.shop_domain = validate_shop_domain(shop_domain, resolve_dns=resolve_dns)
        self.api_version = validate_api_version(api_version)
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.endpoint = f"https://{self.shop_domain}/admin/api/{self.api_version}/graphql.json"
        self.last_throttle = ShopifyThrottle()

    def available(self) -> bool:
        return bool(self.access_token)

    def execute(self, operation: str, variables: dict[str, object]) -> dict[str, object]:
        query = OPERATIONS.get(operation)
        if not query:
            raise ValueError("Only predefined Shopify GraphQL operations are allowed.")
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = client.post(
                    self.endpoint,
                    headers={
                        "X-Shopify-Access-Token": self.access_token,
                        "Content-Type": "application/json",
                    },
                    json={"query": query, "variables": variables},
                )
        except httpx.TimeoutException as error:
            raise ConnectorFailure(
                "shopify_timeout",
                "Shopify did not respond before the configured timeout.",
                retryable=True,
                ambiguous=operation in {"product_create", "product_update"},
            ) from error
        except httpx.RequestError as error:
            raise ConnectorFailure(
                "shopify_network_error", "Shopify could not be reached.", retryable=True
            ) from error
        if response.is_redirect:
            raise ConnectorFailure(
                "shopify_redirect_rejected", "Shopify returned an unsafe redirect.", retryable=False
            )
        if len(response.content) > MAX_GRAPHQL_RESPONSE_BYTES:
            raise ConnectorFailure(
                "shopify_response_too_large",
                "Shopify response exceeded the safe limit.",
                retryable=False,
            )
        if response.status_code in {401, 403}:
            raise ConnectorFailure(
                "shopify_auth_failed",
                "Shopify rejected the configured credentials.",
                retryable=False,
            )
        if response.status_code == 429:
            raise ConnectorFailure(
                "shopify_throttled",
                "Shopify temporarily throttled the request.",
                retryable=True,
                status_code=429,
                retry_after=_retry_after(response),
            )
        if response.status_code >= 500:
            raise ConnectorFailure(
                "shopify_unavailable",
                "Shopify is temporarily unavailable.",
                retryable=True,
                status_code=response.status_code,
            )
        if response.status_code >= 400:
            raise ConnectorFailure(
                "shopify_request_rejected",
                "Shopify rejected the request.",
                retryable=False,
                status_code=response.status_code,
            )
        try:
            body = response.json()
        except ValueError as error:
            raise ConnectorFailure(
                "shopify_invalid_response", "Shopify returned an invalid response.", retryable=False
            ) from error
        if not isinstance(body, dict):
            raise ConnectorFailure(
                "shopify_invalid_response", "Shopify returned an invalid response.", retryable=False
            )
        self.last_throttle = _throttle(body)
        errors = body.get("errors")
        if isinstance(errors, list) and errors:
            code = "shopify_graphql_error"
            if any(
                isinstance(item, dict)
                and str((item.get("extensions") or {}).get("code", "")).upper() == "THROTTLED"
                for item in errors
            ):
                code = "shopify_throttled"
            raise ConnectorFailure(
                code,
                "Shopify could not complete the GraphQL operation.",
                retryable=code == "shopify_throttled",
            )
        data = body.get("data")
        if not isinstance(data, dict):
            raise ConnectorFailure(
                "shopify_invalid_response",
                "Shopify response omitted operation data.",
                retryable=False,
            )
        return data

    def validate(self) -> dict[str, object]:
        return self.execute("validate", {})

    def discover(
        self,
        kind: Literal["collections", "publications"],
        *,
        first: int,
        after: str | None,
        search: str = "",
    ) -> dict[str, object]:
        variables: dict[str, object] = {"first": min(max(first, 1), 100), "after": after}
        if kind == "collections":
            variables["query"] = search[:100] or None
        return self.execute(kind, variables)

    def publish(
        self, destination: dict[str, object], snapshot: dict[str, object]
    ) -> ConnectorResult:
        action = str(destination.get("requested_action") or "create_draft")
        status: Literal["DRAFT", "ACTIVE", "ARCHIVED"] = (
            "ACTIVE" if action == "activate" else ("ARCHIVED" if action == "archive" else "DRAFT")
        )
        remote_id = str(destination.get("remote_product_id") or "") or None
        operation = "product_update" if remote_id else "product_create"
        product = shopify_product_input(snapshot, destination, status=status, remote_id=remote_id)
        data = self.execute(operation, {"product": product})
        payload = data.get("productUpdate" if remote_id else "productCreate")
        if not isinstance(payload, dict):
            raise ConnectorFailure(
                "shopify_invalid_response", "Shopify product response was invalid.", retryable=False
            )
        user_errors = payload.get("userErrors")
        if isinstance(user_errors, list) and user_errors:
            raise ConnectorFailure(
                "shopify_user_error",
                "Shopify rejected one or more product fields.",
                retryable=False,
            )
        product_result = payload.get("product")
        if not isinstance(product_result, dict) or not isinstance(product_result.get("id"), str):
            raise ConnectorFailure(
                "shopify_invalid_product", "Shopify product response was invalid.", retryable=False
            )
        remote_product_id = str(product_result["id"])
        handle = str(product_result.get("handle") or "")
        admin_url = (
            f"https://{self.shop_domain}/admin/products/{remote_product_id.rsplit('/', 1)[-1]}"
        )
        return ConnectorResult(
            remote_product_id,
            admin_url,
            {"product": product_result, "throttle": self.last_throttle.__dict__},
            remote_status=str(product_result.get("status") or "").casefold() or None,
            remote_slug=handle or None,
        )

    def reconcile(self, remote_id: str) -> ConnectorResult:
        data = self.execute("product_status", {"id": remote_id})
        product = data.get("product")
        if product is None:
            raise ConnectorFailure(
                "shopify_not_found", "The remote Shopify product no longer exists.", retryable=False
            )
        if not isinstance(product, dict):
            raise ConnectorFailure(
                "shopify_invalid_product", "Shopify product response was invalid.", retryable=False
            )
        return ConnectorResult(
            remote_id,
            f"https://{self.shop_domain}/admin/products/{remote_id.rsplit('/', 1)[-1]}",
            product,
            remote_status=str(product.get("status") or "").casefold() or None,
            remote_slug=str(product.get("handle") or "") or None,
        )


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after")
    return int(value) if value and value.isdigit() else None


def _throttle(body: dict[str, object]) -> ShopifyThrottle:
    extensions = body.get("extensions")
    cost = extensions.get("cost") if isinstance(extensions, dict) else None
    throttle = cost.get("throttleStatus") if isinstance(cost, dict) else None
    return ShopifyThrottle(
        requested_cost=_integer(cost, "requestedQueryCost"),
        actual_cost=_integer(cost, "actualQueryCost"),
        currently_available=_integer(throttle, "currentlyAvailable"),
        restore_rate=_number(throttle, "restoreRate"),
    )


def _integer(value: object, key: str) -> int | None:
    item = value.get(key) if isinstance(value, dict) else None
    return item if isinstance(item, int) else None


def _number(value: object, key: str) -> float | None:
    item = value.get(key) if isinstance(value, dict) else None
    return float(item) if isinstance(item, (int, float)) else None
