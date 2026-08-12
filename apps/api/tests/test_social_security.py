import pytest

from vayujit_api.social.service import _safe_url


@pytest.mark.parametrize(
    "value",
    [
        "javascript:alert(1)",
        "file:///tmp/a",
        "data:text/plain,hello",
        "http://example.com",
        "https://user:pass@example.com/a",
        "C:\\secret\\file.txt",
    ],
)
def test_social_destination_url_security(value: str) -> None:
    with pytest.raises(ValueError):
        _safe_url(value)


def test_social_https_destination_url_is_preserved() -> None:
    assert _safe_url("https://example.com/product") == "https://example.com/product"
