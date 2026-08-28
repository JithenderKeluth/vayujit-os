# ruff: noqa: E501
# mypy: ignore-errors
from __future__ import annotations

from types import SimpleNamespace

import pytest

from vayujit_api.core.config import Settings
from vayujit_api.intelligence import external_provider
from vayujit_api.intelligence.external_provider import (
    ApprovedWebFetcher,
    UnsafeURL,
    validate_external_url,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        url: str = "https://docs.example.org/page",
        body: bytes = b"ok",
        content_type: str = "text/plain",
        location: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.content = body
        self.encoding = "utf-8"
        self.headers = {"content-type": content_type}
        if location:
            self.headers["location"] = location

    def iter_bytes(self):
        yield self.content

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, responses: list[FakeResponse], calls: list[str]):
        self.responses = responses
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, url: str, **_kwargs):
        self.calls.append(url)
        if not self.responses:
            raise AssertionError("unexpected outbound request")
        return self.responses.pop(0)


def settings(**kwargs: object) -> Settings:
    return Settings(
        environment="test",
        intelligence_fetch_max_bytes=1024,
        intelligence_fetch_max_redirects=3,
        intelligence_fetch_timeout_seconds=5,
        **kwargs,
    )


def public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        external_provider,
        "_resolved_addresses",
        lambda _host: [
            SimpleNamespace(
                is_private=False,
                is_loopback=False,
                is_link_local=False,
                is_reserved=False,
                is_unspecified=False,
            )
        ],
    )


def test_html_is_safely_extracted_and_provenance_is_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    response = FakeResponse(
        url="https://docs.example.org/page",
        body=b'<html><head><title>Safe title</title><meta name="description" content="summary"><link rel="canonical" href="/canonical"></head><body>Hello <script>alert(1)</script><iframe>bad</iframe><form>bad</form><a href="javascript:alert(1)">world</a></body></html>',
        content_type="text/html",
    )
    public_dns(monkeypatch)
    monkeypatch.setattr(
        external_provider.httpx, "Client", lambda **_kwargs: FakeClient([response], calls)
    )
    result = ApprovedWebFetcher(settings()).fetch(
        "https://docs.example.org/page", allowed_domains=("example.org",)
    )
    extracted = result["extracted"]
    assert result["classification"] == "UNTRUSTED_EXTERNAL_DATA"
    assert extracted["title"] == "Safe title"
    assert extracted["canonical_url"] == "https://docs.example.org/canonical"
    assert "alert" not in str(extracted["text"])
    assert "bad" not in str(extracted["text"])
    assert result["redirect_count"] == 0
    assert calls == ["https://docs.example.org/page"]


def test_redirects_are_revalidated_before_each_request(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    responses = [
        FakeResponse(status_code=302, location="https://docs.example.org/next"),
        FakeResponse(),
    ]
    public_dns(monkeypatch)
    monkeypatch.setattr(
        external_provider.httpx, "Client", lambda **_kwargs: FakeClient(responses, calls)
    )
    result = ApprovedWebFetcher(settings()).fetch(
        "https://docs.example.org/page", allowed_domains=("example.org",)
    )
    assert result["redirect_count"] == 1
    assert calls == ["https://docs.example.org/page", "https://docs.example.org/next"]


def test_redirect_to_blocked_domain_never_fetches_target(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    responses = [FakeResponse(status_code=302, location="https://blocked.example/next")]
    public_dns(monkeypatch)
    monkeypatch.setattr(
        external_provider.httpx, "Client", lambda **_kwargs: FakeClient(responses, calls)
    )
    with pytest.raises(RuntimeError, match="redirect_blocked"):
        ApprovedWebFetcher(settings()).fetch(
            "https://docs.example.org/page",
            allowed_domains=("example.org",),
            blocked_domains=("blocked.example",),
        )
    assert calls == ["https://docs.example.org/page"]


def test_streaming_response_limit_stops_without_unbounded_buffer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_dns(monkeypatch)
    response = FakeResponse(body=b"x" * 1025)
    monkeypatch.setattr(
        external_provider.httpx, "Client", lambda **_kwargs: FakeClient([response], [])
    )
    with pytest.raises(RuntimeError, match="response_too_large"):
        ApprovedWebFetcher(settings()).fetch(
            "https://docs.example.org/page", allowed_domains=("example.org",)
        )


def test_unsupported_mime_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    public_dns(monkeypatch)
    response = FakeResponse(content_type="application/pdf")
    monkeypatch.setattr(
        external_provider.httpx, "Client", lambda **_kwargs: FakeClient([response], [])
    )
    with pytest.raises(RuntimeError, match="mime_blocked"):
        ApprovedWebFetcher(settings()).fetch(
            "https://docs.example.org/page", allowed_domains=("example.org",)
        )


SECURITY_URLS = [
    "http://example.org",
    "ftp://example.org",
    "file:///tmp/a",
    "javascript:alert(1)",
    "data:text/plain,x",
    "https://localhost/x",
    "https://127.0.0.1/x",
    "https://10.0.0.1/x",
    "https://172.16.0.1/x",
    "https://192.168.1.1/x",
    "https://169.254.169.254/x",
    "https://[::1]/x",
    "https://[fc00::1]/x",
    "https://[fe80::1]/x",
    "https://0.0.0.0/x",
    "https://user:pass@example.org/x",
    "https://example.org:8443/x",
    "https://metadata.google.internal/x",
] + [f"https://blocked-{i}.invalid/x" for i in range(36)]


@pytest.mark.parametrize("value", SECURITY_URLS)
def test_security_matrix_rejects_unsafe_or_unapproved_urls(value: str) -> None:
    with pytest.raises(UnsafeURL):
        validate_external_url(value, allowed_domains=("example.org",))


def test_explicit_user_agent_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    response = FakeResponse()

    class HeaderClient(FakeClient):
        def get(self, url: str, **kwargs):
            seen.update(kwargs.get("headers", {}))
            return super().get(url, **kwargs)

    public_dns(monkeypatch)
    monkeypatch.setattr(
        external_provider.httpx, "Client", lambda **_kwargs: HeaderClient([response], [])
    )
    ApprovedWebFetcher(settings(intelligence_external_fetch_user_agent="VAYUJIT-Test/1.0")).fetch(
        "https://docs.example.org/page", allowed_domains=("example.org",)
    )
    assert seen["User-Agent"] == "VAYUJIT-Test/1.0"
