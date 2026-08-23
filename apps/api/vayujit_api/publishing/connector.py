import hashlib
import html
import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import httpx

MAX_RESPONSE_BYTES = 1_000_000
MAX_MEDIA_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class ConnectorCapabilities:
    supports_draft: bool
    supports_publish: bool
    supports_update: bool
    supports_media: bool
    supports_unpublish: bool
    supports_delete: bool = False
    supports_categories: bool = False
    supports_tags: bool = False
    supports_featured_image: bool = False
    supports_custom_excerpt: bool = False
    supports_slug: bool = False
    supports_remote_status_lookup: bool = False
    supports_idempotency_key: bool = False
    supports_native_scheduling: bool = False


@dataclass(frozen=True)
class ConnectorResult:
    external_reference: str
    external_url: str
    payload: dict[str, object]
    remote_status: str | None = None
    remote_slug: str | None = None


class ConnectorFailure(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        retry_after: int | None = None,
        ambiguous: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.retryable = retryable
        self.status_code = status_code
        self.retry_after = retry_after
        self.ambiguous = ambiguous


class PublishingConnector(Protocol):
    key: str
    name: str
    connector_type: str
    capabilities: ConnectorCapabilities

    def available(self) -> bool: ...
    def publish(
        self, destination: dict[str, object], snapshot: dict[str, object]
    ) -> ConnectorResult: ...


class MockPublishingConnector:
    key = "mock_publisher_v1"
    name = "Deterministic Local Mock Publisher"
    connector_type = "mock"
    capabilities = ConnectorCapabilities(
        supports_draft=False,
        supports_publish=True,
        supports_update=False,
        supports_media=False,
        supports_unpublish=False,
        supports_idempotency_key=True,
    )

    def available(self) -> bool:
        return True

    def publish(
        self, destination: dict[str, object], snapshot: dict[str, object]
    ) -> ConnectorResult:
        failure = destination.get("simulate_failure")
        if failure:
            retryable = destination.get("failure_type") == "retryable"
            raise ConnectorFailure(
                "mock_retryable_failure" if retryable else "mock_permanent_failure",
                "The local mock publisher deliberately failed.",
                retryable=retryable,
            )
        normalized = json.dumps({"destination": destination, "content": snapshot}, sort_keys=True)
        checksum = hashlib.sha256(normalized.encode()).hexdigest()
        prefix = str(destination.get("publication_prefix") or "PUB").upper()
        reference = f"{prefix}-{checksum[:12]}"
        return ConnectorResult(
            reference,
            f"https://example.invalid/publications/{reference.lower()}",
            {"publication_id": reference, "status": "published", "checksum": checksum},
            remote_status="published",
        )


def validate_wordpress_site_url(value: str, *, environment: str) -> str:
    parsed = urlparse(value)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("WordPress URL cannot contain credentials, query values, or fragments.")
    local_environment = environment in {"development", "test"}
    schemes = {"http", "https"} if local_environment else {"https"}
    if parsed.scheme not in schemes or not parsed.hostname:
        raise ValueError("WordPress URL must use HTTPS outside local development.")
    if len(parsed.path) > 200 or parsed.path.rstrip("/") not in {"", "/wordpress"}:
        raise ValueError("WordPress URL path is unsupported.")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)}
    except socket.gaierror as error:
        raise ValueError("WordPress host could not be resolved.") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        blocked = (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
        if blocked and not local_environment:
            raise ValueError("Private and local WordPress networks are blocked.")
    return value.rstrip("/")


def plain_text_to_safe_html(value: str) -> str:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", value) if part.strip()]
    return "".join(f"<p>{html.escape(part).replace(chr(10), '<br>')}</p>" for part in paragraphs)


def wordpress_payload(
    snapshot: dict[str, object],
    *,
    status: str,
    categories: list[int] | None = None,
    tags: list[int] | None = None,
    author: int | None = None,
) -> dict[str, object]:
    title = str(snapshot.get("product_title") or snapshot.get("product_name") or "")[:200]
    long_description = str(snapshot.get("long_description") or "")[:5000]
    excerpt = str(snapshot.get("short_description") or "")[:500]
    slug_source = str(snapshot.get("seo_title") or snapshot.get("product_name") or "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug_source.casefold()).strip("-")[:180]
    payload: dict[str, object] = {
        "title": title,
        "content": plain_text_to_safe_html(long_description),
        "excerpt": excerpt,
        "slug": slug,
        "status": status,
    }
    if categories:
        payload["categories"] = categories[:100]
    if tags:
        payload["tags"] = tags[:100]
    if author:
        payload["author"] = author
    return payload


def validate_media(filename: str, mime_type: str, data: bytes) -> None:
    if len(data) > MAX_MEDIA_BYTES or not data:
        raise ValueError("Media size is invalid.")
    extension = filename.rsplit(".", 1)[-1].casefold() if "." in filename else ""
    signatures = {
        "image/jpeg": ({"jpg", "jpeg"}, data.startswith(b"\xff\xd8\xff")),
        "image/png": ({"png"}, data.startswith(b"\x89PNG\r\n\x1a\n")),
        "image/webp": ({"webp"}, data.startswith(b"RIFF") and data[8:12] == b"WEBP"),
    }
    allowed, signature = signatures.get(mime_type, (set(), False))
    if extension not in allowed or not signature or "/" in filename or "\\" in filename:
        raise ValueError("Media type, filename, or signature is invalid.")


class WordPressConnector:
    key = "wordpress"
    name = "WordPress"
    connector_type = "remote"
    capabilities = ConnectorCapabilities(
        supports_draft=True,
        supports_publish=True,
        supports_update=True,
        supports_media=True,
        supports_unpublish=True,
        supports_categories=True,
        supports_tags=True,
        supports_featured_image=True,
        supports_custom_excerpt=True,
        supports_slug=True,
        supports_remote_status_lookup=True,
    )

    def __init__(
        self,
        *,
        site_url: str,
        username: str,
        application_password: str,
        timeout_seconds: int,
        environment: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.site_url = validate_wordpress_site_url(site_url, environment=environment)
        self.username = username
        self.application_password = application_password
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.api_url = f"{self.site_url}/wp-json/wp/v2"

    def available(self) -> bool:
        return bool(self.application_password and self.username)

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        json_body: dict[str, object] | None = None,
        content: bytes | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str | int] | None = None,
        ambiguous_on_timeout: bool = False,
    ) -> dict[str, object] | list[object]:
        if not re.fullmatch(
            r"/(?:users/me|posts(?:/\d+)?|media(?:/\d+)?|categories|tags|users)", endpoint
        ):
            raise ConnectorFailure(
                "invalid_endpoint", "WordPress endpoint is not allowed.", retryable=False
            )
        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout_seconds),
                follow_redirects=False,
                transport=self.transport,
                auth=httpx.BasicAuth(self.username, self.application_password),
            ) as client:
                response = client.request(
                    method,
                    f"{self.api_url}{endpoint}",
                    json=json_body,
                    content=content,
                    headers=headers,
                    params=params,
                )
            if len(response.content) > MAX_RESPONSE_BYTES:
                raise ConnectorFailure(
                    "response_too_large", "WordPress response was too large.", retryable=False
                )
            if response.is_redirect:
                raise ConnectorFailure(
                    "redirect_blocked", "WordPress redirect was blocked.", retryable=False
                )
            if response.status_code in {401, 403}:
                raise ConnectorFailure(
                    "wordpress_auth_failed",
                    "WordPress authentication or permission check failed.",
                    retryable=False,
                    status_code=response.status_code,
                )
            if response.status_code == 404:
                raise ConnectorFailure(
                    "wordpress_not_found",
                    "The WordPress resource was not found.",
                    retryable=False,
                    status_code=404,
                )
            if response.status_code in {408, 429} or response.status_code >= 500:
                raise ConnectorFailure(
                    (
                        "wordpress_rate_limited"
                        if response.status_code == 429
                        else "wordpress_unavailable"
                    ),
                    "WordPress is temporarily unavailable.",
                    retryable=True,
                    status_code=response.status_code,
                    retry_after=_retry_after(response.headers.get("retry-after")),
                )
            if response.is_error:
                raise ConnectorFailure(
                    "wordpress_request_rejected",
                    "WordPress rejected the request.",
                    retryable=False,
                    status_code=response.status_code,
                )
            value = response.json()
            if not isinstance(value, (dict, list)):
                raise ValueError
            return value
        except (httpx.TimeoutException, httpx.NetworkError) as error:
            raise ConnectorFailure(
                (
                    "wordpress_timeout"
                    if isinstance(error, httpx.TimeoutException)
                    else "wordpress_network_error"
                ),
                (
                    "The WordPress request timed out."
                    if isinstance(error, httpx.TimeoutException)
                    else "The WordPress network request failed."
                ),
                retryable=True,
                ambiguous=ambiguous_on_timeout,
            ) from error
        except (ValueError, json.JSONDecodeError) as error:
            raise ConnectorFailure(
                "wordpress_invalid_response",
                "WordPress returned an invalid response.",
                retryable=False,
            ) from error

    def validate(self) -> dict[str, object]:
        value = self.request("GET", "/users/me")
        if not isinstance(value, dict) or not isinstance(value.get("id"), int):
            raise ConnectorFailure(
                "wordpress_invalid_user", "WordPress user response was invalid.", retryable=False
            )
        return value

    def publish(
        self, destination: dict[str, object], snapshot: dict[str, object]
    ) -> ConnectorResult:
        status = str(destination.get("post_status") or "draft")
        raw_categories = destination.get("category_ids")
        raw_tags = destination.get("tag_ids")
        payload = wordpress_payload(
            snapshot,
            status=status,
            categories=(
                [int(str(x)) for x in raw_categories] if isinstance(raw_categories, list) else []
            ),
            tags=[int(str(x)) for x in raw_tags] if isinstance(raw_tags, list) else [],
            author=(int(str(destination["author_id"])) if destination.get("author_id") else None),
        )
        if destination.get("featured_media_remote_id"):
            payload["featured_media"] = int(str(destination["featured_media_remote_id"]))
        remote_id = destination.get("remote_post_id")
        endpoint = f"/posts/{int(str(remote_id))}" if remote_id else "/posts"
        value = self.request(
            "POST", endpoint, json_body=payload, ambiguous_on_timeout=not bool(remote_id)
        )
        if not isinstance(value, dict) or not isinstance(value.get("id"), int):
            raise ConnectorFailure(
                "wordpress_invalid_post", "WordPress post response was invalid.", retryable=False
            )
        post_id = str(value["id"])
        link = str(value.get("link") or f"{self.site_url}/?p={post_id}")[:500]
        return ConnectorResult(
            post_id,
            link,
            {
                "remote_post_id": post_id,
                "status": str(value.get("status") or status),
                "slug": str(value.get("slug") or payload["slug"]),
            },
            remote_status=str(value.get("status") or status),
            remote_slug=str(value.get("slug") or payload["slug"]),
        )

    def reconcile(self, remote_id: str) -> ConnectorResult:
        value = self.request("GET", f"/posts/{int(remote_id)}")
        assert isinstance(value, dict)
        link = str(value.get("link") or f"{self.site_url}/?p={remote_id}")[:500]
        return ConnectorResult(
            remote_id,
            link,
            value,
            remote_status=str(value.get("status") or "unknown"),
            remote_slug=str(value.get("slug") or ""),
        )

    def move_to_draft(self, remote_id: str) -> ConnectorResult:
        value = self.request("POST", f"/posts/{int(remote_id)}", json_body={"status": "draft"})
        assert isinstance(value, dict)
        return ConnectorResult(
            remote_id,
            str(value.get("link") or f"{self.site_url}/?p={remote_id}")[:500],
            value,
            remote_status="draft",
            remote_slug=str(value.get("slug") or ""),
        )

    def upload_media(self, filename: str, mime_type: str, data: bytes) -> dict[str, object]:
        validate_media(filename, mime_type, data)
        value = self.request(
            "POST",
            "/media",
            content=data,
            headers={
                "Content-Type": mime_type,
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
        if not isinstance(value, dict) or not isinstance(value.get("id"), int):
            raise ConnectorFailure(
                "wordpress_invalid_media", "WordPress media response was invalid.", retryable=False
            )
        return value


def _retry_after(value: str | None) -> int | None:
    try:
        return min(max(int(value or ""), 0), 8)
    except ValueError:
        return None


class ConnectorRegistry:
    def __init__(self) -> None:
        self.mock = MockPublishingConnector()

    def get(self, key: str) -> PublishingConnector:
        if key == self.mock.key:
            return self.mock
        raise KeyError(key)


registry = ConnectorRegistry()
connector = registry.mock
