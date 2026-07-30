# ruff: noqa: E501
import html
import ipaddress
import re
import socket
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlsplit

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
      productCreate(product:$product) { product { id title handle status onlineStoreUrl
      variants(first:1) { nodes { id sku inventoryItem { id } } } }
      userErrors { field message code } } }""",
    "product_update": """mutation VayujitProductUpdate($product:ProductUpdateInput!) {
      productUpdate(product:$product) { product { id title handle status onlineStoreUrl
      variants(first:100) { nodes { id sku inventoryItem { id } } } }
      userErrors { field message code } } }""",
    "options_create": """mutation VayujitOptionsCreate($productId:ID!,$options:[OptionCreateInput!]!) {
      productOptionsCreate(productId:$productId,options:$options) {
      userErrors { field message code } } }""",
    "variants_create": """mutation VayujitVariantsCreate($productId:ID!,$variants:[ProductVariantsBulkInput!]!) {
      productVariantsBulkCreate(productId:$productId,variants:$variants,strategy:REMOVE_STANDALONE_VARIANT) {
      productVariants { id sku inventoryItem { id } selectedOptions { name value } }
      userErrors { field message code } } }""",
    "variants_update": """mutation VayujitVariantsUpdate($productId:ID!,$variants:[ProductVariantsBulkInput!]!) {
      productVariantsBulkUpdate(productId:$productId,variants:$variants) {
      productVariants { id sku inventoryItem { id } selectedOptions { name value } }
      userErrors { field message code } } }""",
    "collection_add": """mutation VayujitCollectionAdd($id:ID!,$productIds:[ID!]!) {
      collectionAddProducts(id:$id,productIds:$productIds) { userErrors { field message code } } }""",
    "collection_remove": """mutation VayujitCollectionRemove($id:ID!,$productIds:[ID!]!) {
      collectionRemoveProducts(id:$id,productIds:$productIds) { userErrors { field message code } } }""",
    "publish": """mutation VayujitPublish($id:ID!,$input:[PublicationInput!]!) {
      publishablePublish(id:$id,input:$input) { userErrors { field message code } } }""",
    "unpublish": """mutation VayujitUnpublish($id:ID!,$input:[PublicationInput!]!) {
      publishableUnpublish(id:$id,input:$input) { userErrors { field message code } } }""",
    "staged_upload": """mutation VayujitStagedUpload($input:[StagedUploadInput!]!) {
      stagedUploadsCreate(input:$input) { stagedTargets { url resourceUrl parameters { name value } }
      userErrors { field message code } } }""",
    "media_create": """mutation VayujitMediaCreate($productId:ID!,$media:[CreateMediaInput!]!) {
      productCreateMedia(productId:$productId,media:$media) {
      media { id status alt preview { image { url } } } userErrors { field message code } } }""",
    "media_status": """query VayujitMediaStatus($productId:ID!,$mediaId:ID!) {
      product(id:$productId) { id media(first:1,query:$mediaId) {
      nodes { id status alt preview { image { url } } } } }""",
    "product_status": """query VayujitProductStatus($id:ID!) {
      product(id:$id) { id title handle status descriptionHtml vendor productType tags
      seo { title description } updatedAt options { id name values }
      variants(first:100) { nodes { id sku price compareAtPrice barcode
      inventoryItem { id measurement { weight { value unit } } tracked }
      selectedOptions { name value } } pageInfo { hasNextPage } }
      media(first:100) { nodes { id status alt preview { image { url } } } pageInfo { hasNextPage } }
      collections(first:100) { nodes { id } pageInfo { hasNextPage } }
      resourcePublications(first:100) { nodes { publication { id name } isPublished }
      pageInfo { hasNextPage } } } }""",
}

MAX_VARIANTS = 100
MAX_MEDIA_BYTES = 20 * 1024 * 1024
STAGED_UPLOAD_HOSTS = ("storage.googleapis.com", "shopify.com", "myshopify.com")


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


def shopify_variant_inputs(
    snapshot: dict[str, object],
    configured: object,
    *,
    require_price: bool = False,
    require_sku: bool = False,
) -> list[dict[str, object]]:
    values = configured if isinstance(configured, list) else []
    if not values:
        price = snapshot.get("price_amount")
        variant: dict[str, object] = {"localKey": "default"}
        for source, target in (
            ("sku", "sku"),
            ("price_amount", "price"),
            ("compare_at_price_amount", "compareAtPrice"),
            ("barcode", "barcode"),
        ):
            value = snapshot.get(source)
            if value not in (None, ""):
                variant[target] = _money(value) if "price" in source else str(value)[:100]
        if price is None and require_price:
            raise ValueError("A price is required for the default Shopify variant.")
        if not snapshot.get("sku") and require_sku:
            raise ValueError("A SKU is required for the default Shopify variant.")
        if snapshot.get("weight_value") is not None:
            variant["inventoryItem"] = {
                "measurement": {
                    "weight": {
                        "value": float(str(snapshot["weight_value"])),
                        "unit": str(snapshot.get("weight_unit") or "").upper(),
                    }
                },
                "tracked": bool(snapshot.get("inventory_tracking_enabled")),
            }
        return [variant]
    if len(values) > MAX_VARIANTS:
        raise ValueError("Shopify supports at most 100 variants in this workflow.")
    result: list[dict[str, object]] = []
    keys: set[str] = set()
    signatures: set[tuple[tuple[str, str], ...]] = set()
    skus: set[str] = set()
    for raw in values:
        if not isinstance(raw, dict):
            raise ValueError("Shopify variants must use typed objects.")
        key = str(raw.get("local_key") or "").strip()
        options = raw.get("options")
        if not key or not isinstance(options, list) or not 1 <= len(options) <= 3:
            raise ValueError("Structured variants require a stable key and one to three options.")
        signature = tuple(
            (str(item.get("name") or "").strip(), str(item.get("value") or "").strip())
            for item in options
            if isinstance(item, dict)
        )
        if len(signature) != len(options) or any(
            not name or not value for name, value in signature
        ):
            raise ValueError("Variant option names and values cannot be blank.")
        sku = str(raw.get("sku") or "").strip()
        if key.casefold() in keys or signature in signatures or (sku and sku.casefold() in skus):
            raise ValueError("Variant keys, option combinations, and SKUs must be unique.")
        keys.add(key.casefold())
        signatures.add(signature)
        if sku:
            skus.add(sku.casefold())
        price = raw.get("price")
        if price is None and require_price:
            raise ValueError("Every structured Shopify variant requires a price.")
        item: dict[str, object] = {
            "localKey": key,
            "optionValues": [{"optionName": name, "name": value} for name, value in signature],
            "taxable": bool(raw.get("taxable", True)),
        }
        if price is not None:
            item["price"] = _money(price)
        if not sku and require_sku:
            raise ValueError("Every structured Shopify variant requires a SKU.")
        for source, target in (
            ("sku", "sku"),
            ("compare_at_price", "compareAtPrice"),
            ("barcode", "barcode"),
        ):
            value = raw.get(source)
            if value not in (None, ""):
                item[target] = _money(value) if source == "compare_at_price" else str(value)[:100]
        result.append(item)
    return result


def _money(value: object) -> str:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Shopify prices must be valid decimal amounts.") from error
    if amount < 0:
        raise ValueError("Shopify prices cannot be negative.")
    return f"{amount:.2f}"


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
        variants = shopify_variant_inputs(
            snapshot,
            destination.get("shopify_variants"),
            require_price=bool(destination.get("require_variant_price")),
            require_sku=bool(destination.get("require_variant_sku")),
        )
        remote_variant_ids = destination.get("variant_remote_ids")
        if remote_id and isinstance(remote_variant_ids, dict):
            for variant in variants:
                mapped_id = remote_variant_ids.get(str(variant["localKey"]))
                if isinstance(mapped_id, str):
                    variant["id"] = mapped_id
        remote_variants = self._write_variants(
            remote_product_id,
            variants,
            existing=product_result.get("variants"),
            creating=remote_id is None,
        )
        collection_ids = _string_ids(destination.get("default_collection_ids"))
        for collection_id in collection_ids:
            self._mutation(
                "collection_add",
                "collectionAddProducts",
                {"id": collection_id, "productIds": [remote_product_id]},
            )
        publication_ids = _string_ids(destination.get("default_publication_ids"))
        if action == "activate":
            if not publication_ids:
                raise ConnectorFailure(
                    "shopify_publication_required",
                    "Activation requires at least one configured publication.",
                    retryable=False,
                )
            self._mutation(
                "publish",
                "publishablePublish",
                {
                    "id": remote_product_id,
                    "input": [{"publicationId": value} for value in publication_ids],
                },
            )
        handle = str(product_result.get("handle") or "")
        admin_url = (
            f"https://{self.shop_domain}/admin/products/{remote_product_id.rsplit('/', 1)[-1]}"
        )
        return ConnectorResult(
            remote_product_id,
            admin_url,
            {
                "product": product_result,
                "variants": remote_variants,
                "collection_ids": collection_ids,
                "publication_ids": publication_ids if action == "activate" else [],
                "throttle": self.last_throttle.__dict__,
            },
            remote_status=str(product_result.get("status") or "").casefold() or None,
            remote_slug=handle or None,
        )

    def _mutation(
        self, operation: str, payload_key: str, variables: dict[str, object]
    ) -> dict[str, object]:
        data = self.execute(operation, variables)
        payload = data.get(payload_key)
        if not isinstance(payload, dict):
            raise ConnectorFailure(
                "shopify_invalid_response",
                "Shopify mutation response was invalid.",
                retryable=False,
            )
        errors = payload.get("userErrors")
        if isinstance(errors, list) and errors:
            raise ConnectorFailure(
                "shopify_user_error",
                "Shopify rejected one or more mapped fields.",
                retryable=False,
            )
        return payload

    def _write_variants(
        self,
        product_id: str,
        variants: list[dict[str, object]],
        *,
        existing: object,
        creating: bool,
    ) -> list[dict[str, object]]:
        structured = any(item.get("optionValues") for item in variants)
        if structured and creating:
            option_names: list[str] = []
            for variant in variants:
                raw_options = variant.get("optionValues")
                options = raw_options if isinstance(raw_options, list) else []
                for option in options:
                    if isinstance(option, dict) and str(option["optionName"]) not in option_names:
                        option_names.append(str(option["optionName"]))
            self._mutation(
                "options_create",
                "productOptionsCreate",
                {
                    "productId": product_id,
                    "options": [{"name": name, "values": []} for name in option_names],
                },
            )
        mutation_values = []
        for item in variants:
            value = {key: item_value for key, item_value in item.items() if key != "localKey"}
            value["_localKey"] = item["localKey"]
            mutation_values.append(value)
        if not structured and creating:
            nodes = existing.get("nodes") if isinstance(existing, dict) else None
            if len(mutation_values[0]) == 1 and "_localKey" in mutation_values[0]:
                return [
                    {**item, "localKey": "default"}
                    for item in (nodes if isinstance(nodes, list) else [])
                    if isinstance(item, dict)
                ]
            default_id = (
                str(nodes[0].get("id"))
                if isinstance(nodes, list) and nodes and isinstance(nodes[0], dict)
                else ""
            )
            if not default_id:
                raise ConnectorFailure(
                    "shopify_default_variant_missing",
                    "Shopify did not return the default product variant.",
                    retryable=False,
                )
            mutation_values[0]["id"] = default_id
        if not creating and any(not isinstance(item.get("id"), str) for item in mutation_values):
            raise ConnectorFailure(
                "shopify_variant_mapping_missing",
                "A persisted remote mapping is required before updating each variant.",
                retryable=False,
            )
        operation = "variants_create" if structured and creating else "variants_update"
        api_values = [
            {key: value for key, value in item.items() if not key.startswith("_")}
            for item in mutation_values
        ]
        payload = self._mutation(
            operation,
            (
                "productVariantsBulkCreate"
                if operation == "variants_create"
                else "productVariantsBulkUpdate"
            ),
            {"productId": product_id, "variants": api_values},
        )
        remote = payload.get("productVariants")
        if not isinstance(remote, list) or len(remote) != len(variants):
            raise ConnectorFailure(
                "shopify_variant_result_mismatch",
                "Shopify returned an unexpected variant result.",
                retryable=False,
            )
        return [
            {**item, "localKey": variants[index]["localKey"]}
            for index, item in enumerate(remote)
            if isinstance(item, dict)
        ]

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

    def media_status(self, *, product_id: str, media_id: str) -> dict[str, object]:
        data = self.execute("media_status", {"productId": product_id, "mediaId": media_id})
        product = data.get("product")
        if product is None:
            return {"exists": False, "status": "UNKNOWN"}
        media = product.get("media") if isinstance(product, dict) else None
        nodes = media.get("nodes") if isinstance(media, dict) else None
        if not isinstance(nodes, list):
            raise ConnectorFailure(
                "shopify_media_status_invalid",
                "Shopify returned an invalid media status.",
                retryable=True,
            )
        matching = next(
            (
                item
                for item in nodes
                if isinstance(item, dict) and str(item.get("id") or "") == media_id
            ),
            None,
        )
        if matching is None:
            return {"exists": False, "status": "UNKNOWN"}
        preview = matching.get("preview")
        image = preview.get("image") if isinstance(preview, dict) else None
        return {
            "exists": True,
            "id": media_id,
            "status": matching.get("status") or "UNKNOWN",
            "alt": matching.get("alt"),
            "url": image.get("url") if isinstance(image, dict) else None,
        }

    def remove_collection_assignment(self, *, product_id: str, collection_id: str) -> None:
        self._mutation(
            "collection_remove",
            "collectionRemoveProducts",
            {"id": collection_id, "productIds": [product_id]},
        )

    def remove_publication_assignment(self, *, product_id: str, publication_id: str) -> None:
        self._mutation(
            "unpublish",
            "publishableUnpublish",
            {"id": product_id, "input": [{"publicationId": publication_id}]},
        )

    def upload_product_media(
        self,
        *,
        product_id: str,
        filename: str,
        mime_type: str,
        content: bytes,
        alt_text: str,
    ) -> dict[str, object]:
        if mime_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ConnectorFailure(
                "shopify_media_type_rejected",
                "Shopify media must be JPEG, PNG, or WebP.",
                retryable=False,
            )
        if not content or len(content) > MAX_MEDIA_BYTES:
            raise ConnectorFailure(
                "shopify_media_size_rejected",
                "Shopify media exceeded the safe upload size.",
                retryable=False,
            )
        staged = self._mutation(
            "staged_upload",
            "stagedUploadsCreate",
            {
                "input": [
                    {
                        "filename": filename[:255],
                        "mimeType": mime_type,
                        "resource": "IMAGE",
                        "httpMethod": "POST",
                        "fileSize": str(len(content)),
                    }
                ]
            },
        )
        targets = staged.get("stagedTargets")
        if not isinstance(targets, list) or len(targets) != 1 or not isinstance(targets[0], dict):
            raise ConnectorFailure(
                "shopify_staged_target_invalid",
                "Shopify did not return a usable staged-upload target.",
                retryable=False,
            )
        target = targets[0]
        url = str(target.get("url") or "")
        resource_url = str(target.get("resourceUrl") or "")
        _validate_staged_target(url)
        parameters = target.get("parameters")
        if not isinstance(parameters, list) or len(parameters) > 30:
            raise ConnectorFailure(
                "shopify_staged_target_invalid",
                "Shopify returned invalid staged-upload parameters.",
                retryable=False,
            )
        fields = {
            str(item["name"]): str(item["value"])
            for item in parameters
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and isinstance(item.get("value"), str)
        }
        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=False,
                transport=self.transport,
            ) as client:
                response = client.post(
                    url,
                    data=fields,
                    files={"file": (filename[:255], content, mime_type)},
                    headers={"User-Agent": "VAYUJIT-OS-Shopify-Media"},
                )
        except httpx.TimeoutException as error:
            raise ConnectorFailure(
                "shopify_media_upload_timeout",
                "The staged media upload timed out.",
                retryable=True,
            ) from error
        except httpx.RequestError as error:
            raise ConnectorFailure(
                "shopify_media_upload_failed",
                "The staged media upload could not be completed.",
                retryable=True,
            ) from error
        if response.is_redirect or response.status_code >= 400:
            raise ConnectorFailure(
                "shopify_media_upload_failed",
                "The staged media upload was rejected.",
                retryable=response.status_code >= 500,
                status_code=response.status_code,
            )
        created = self._mutation(
            "media_create",
            "productCreateMedia",
            {
                "productId": product_id,
                "media": [
                    {
                        "originalSource": resource_url,
                        "mediaContentType": "IMAGE",
                        "alt": alt_text[:512],
                    }
                ],
            },
        )
        media = created.get("media")
        if not isinstance(media, list) or not media or not isinstance(media[0], dict):
            raise ConnectorFailure(
                "shopify_media_result_invalid",
                "Shopify returned an invalid media result.",
                retryable=False,
            )
        return media[0]


def _retry_after(response: httpx.Response) -> int | None:
    value = response.headers.get("retry-after")
    return int(value) if value and value.isdigit() else None


def _string_ids(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError("Shopify remote identifiers must be a bounded text list.")
    if len(value) > 100:
        raise ValueError("Too many Shopify remote assignments were requested.")
    return list(dict.fromkeys(item for item in value if item))


def _validate_staged_target(value: str) -> None:
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or parsed.fragment
        or not hostname
        or not any(
            hostname == suffix or hostname.endswith(f".{suffix}") for suffix in STAGED_UPLOAD_HOSTS
        )
    ):
        raise ConnectorFailure(
            "shopify_staged_target_rejected",
            "Shopify returned an upload target outside the approved hosts.",
            retryable=False,
        )


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
