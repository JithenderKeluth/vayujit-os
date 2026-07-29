import json

import httpx
import pytest

from vayujit_api.publishing.connector import (
    ConnectorFailure,
    WordPressConnector,
    plain_text_to_safe_html,
    validate_media,
    validate_wordpress_site_url,
    wordpress_payload,
)


def connector(handler: httpx.MockTransport) -> WordPressConnector:
    return WordPressConnector(
        site_url="http://127.0.0.1",
        username="owner",
        application_password="application password",
        timeout_seconds=10,
        environment="development",
        transport=handler,
    )


def test_wordpress_url_and_content_safety(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vayujit_api.publishing.connector.socket.getaddrinfo",
        lambda *_args: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    assert (
        validate_wordpress_site_url("https://example.com/wordpress/", environment="production")
        == "https://example.com/wordpress"
    )
    with pytest.raises(ValueError):
        validate_wordpress_site_url("http://example.com", environment="production")
    with pytest.raises(ValueError):
        validate_wordpress_site_url("https://user:pass@example.com", environment="production")
    with pytest.raises(ValueError):
        validate_wordpress_site_url("https://example.com/arbitrary/path", environment="production")
    assert plain_text_to_safe_html("<script>x</script>") == (
        "<p>&lt;script&gt;x&lt;/script&gt;</p>"
    )
    payload = wordpress_payload(
        {"product_name": "Safe Product", "long_description": "<b>not markup</b>"},
        status="draft",
    )
    assert payload["status"] == "draft"
    assert "&lt;b&gt;" in str(payload["content"])


def test_media_validation() -> None:
    validate_media("image.png", "image/png", b"\x89PNG\r\n\x1a\npayload")
    with pytest.raises(ValueError):
        validate_media("../image.png", "image/png", b"\x89PNG\r\n\x1a\npayload")
    with pytest.raises(ValueError):
        validate_media("image.svg", "image/svg+xml", b"<svg/>")


def test_wordpress_validate_create_reconcile_and_draft() -> None:
    posts: dict[int, dict[str, object]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        assert request.headers["authorization"].startswith("Basic ")
        if path.endswith("/users/me"):
            return httpx.Response(200, json={"id": 7, "name": "Owner"})
        if path.endswith("/posts"):
            body = json.loads(request.content)
            posts[41] = {
                "id": 41,
                "status": body["status"],
                "slug": body["slug"],
                "link": "https://example.test/?p=41",
            }
            return httpx.Response(201, json=posts[41])
        if path.endswith("/posts/41") and request.method == "GET":
            return httpx.Response(200, json=posts[41])
        if path.endswith("/posts/41"):
            posts[41]["status"] = json.loads(request.content)["status"]
            return httpx.Response(200, json=posts[41])
        raise AssertionError(path)

    value = connector(httpx.MockTransport(handler))
    assert value.validate()["id"] == 7
    created = value.publish(
        {"post_status": "publish"},
        {"product_name": "A Product", "long_description": "Description"},
    )
    assert created.external_reference == "41"
    assert created.remote_status == "publish"
    assert value.reconcile("41").remote_slug == "a-product"
    assert value.move_to_draft("41").remote_status == "draft"


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "wordpress_auth_failed", False),
        (403, "wordpress_auth_failed", False),
        (404, "wordpress_not_found", False),
        (429, "wordpress_rate_limited", True),
        (503, "wordpress_unavailable", True),
    ],
)
def test_wordpress_safe_error_classification(status: int, code: str, retryable: bool) -> None:
    value = connector(
        httpx.MockTransport(
            lambda _request: httpx.Response(
                status,
                content=b'{"unsafe":"secret should not leak"}',
                headers={"Retry-After": "2"},
            )
        )
    )
    with pytest.raises(ConnectorFailure) as caught:
        value.validate()
    assert caught.value.code == code
    assert caught.value.retryable is retryable
    assert "secret" not in caught.value.safe_message
