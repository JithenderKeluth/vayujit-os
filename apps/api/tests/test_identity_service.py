from vayujit_api.identity.service import hasher, normalize_email


def test_email_is_normalized() -> None:
    assert normalize_email(" Owner@Example.COM ") == "owner@example.com"


def test_password_is_argon2_hashed() -> None:
    encoded = hasher.hash("correct horse battery staple")
    assert encoded.startswith("$argon2id$")
    assert "correct horse battery staple" not in encoded
    assert hasher.verify(encoded, "correct horse battery staple")
