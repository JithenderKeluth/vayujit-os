# ruff: noqa: E501
import pytest

from vayujit_api.intelligence.autonomous_provider import (
    classify_untrusted_content,
    validate_approved_fetch,
)
from vayujit_api.intelligence.policy import UnsafeURL

SECURITY_CASES = [
    "forged mission",
    "forged product",
    "forged opportunity",
    "forged supplier",
    "cross owner mission",
    "cross owner plan",
    "cross owner task",
    "cross owner evidence",
    "cross owner contradiction",
    "cross owner change",
    "cross owner recovery",
    "cross owner report",
    "unsafe http url",
    "localhost",
    "127.0.0.1",
    "private ipv4",
    "private ipv6",
    "link local",
    "cloud metadata ip",
    "embedded credentials",
    "nonstandard port",
    "redirect unsafe target",
    "too many redirects",
    "oversized response",
    "unsupported mime",
    "source not allowlisted",
    "external kill switch bypass",
    "source policy bypass",
    "ai mode bypass",
    "task budget bypass",
    "provider call budget bypass",
    "retry budget bypass",
    "elapsed budget bypass",
    "infinite task generation",
    "dependency cycle",
    "ignore previous instructions",
    "ignore previous instructions in title",
    "ignore previous instructions in body",
    "ignore previous instructions in metadata",
    "run shell command",
    "read filesystem",
    "execute raw sql",
    "send email",
    "make payment",
    "mutate external system",
    "claim without evidence",
    "forged evidence id",
    "wrong owner evidence",
    "evidence hash mismatch",
    "stale evidence misuse",
    "contradiction tampering",
    "auto resolve contradiction",
    "verification escalation",
    "supplier verification escalation",
    "certification verification escalation",
    "historical score mutation",
    "change event mutation",
    "materiality threshold bypass",
    "alert spoofing",
    "unauthorized recovery",
    "unauthorized human review",
    "unauthorized mission stop",
    "report injection",
    "xss external text",
    "credential leakage",
    "token leakage",
    "dsn leakage",
    "filesystem leakage",
    "raw provider payload leakage",
    "buyer customer pii leakage",
]


@pytest.mark.parametrize("content", SECURITY_CASES)
def test_autonomous_security_content_is_inert(content: str) -> None:
    result = classify_untrusted_content(content)
    assert result["classification"] == "UNTRUSTED_EXTERNAL_DATA"
    assert result["instructions_executable"] is False


def test_autonomous_security_url_boundary_matrix() -> None:
    unsafe = (
        "http://localhost/x",
        "http://127.0.0.1/x",
        "http://169.254.169.254/latest",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "https://user:pass@approved.test/x",
        "https://approved.test:8443/x",
    )
    for url in unsafe:
        with pytest.raises((UnsafeURL, ValueError)):
            validate_approved_fetch(url, allowed_domains=("approved.test",))
