import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "v1"
MAX_CREDENTIAL_BYTES = 4096


class CredentialError(ValueError):
    pass


def encryption_key(configured: str | None) -> bytes:
    if not configured:
        raise CredentialError("Credential encryption is not configured.")
    try:
        key = base64.urlsafe_b64decode(configured.encode())
    except Exception as error:
        raise CredentialError("Credential encryption key is invalid.") from error
    if len(key) != 32:
        raise CredentialError("Credential encryption key must decode to 32 bytes.")
    return key


def encrypt_credential(value: str, configured_key: str | None) -> str:
    raw = value.encode()
    if not raw or len(raw) > MAX_CREDENTIAL_BYTES:
        raise CredentialError("Credential length is invalid.")
    nonce = os.urandom(12)
    encrypted = AESGCM(encryption_key(configured_key)).encrypt(nonce, raw, PREFIX.encode())
    return f"{PREFIX}.{base64.urlsafe_b64encode(nonce + encrypted).decode()}"


def decrypt_credential(value: str, configured_key: str | None) -> str:
    try:
        version, encoded = value.split(".", 1)
        if version != PREFIX:
            raise CredentialError("Credential version is unsupported.")
        packed = base64.urlsafe_b64decode(encoded.encode())
        return (
            AESGCM(encryption_key(configured_key))
            .decrypt(packed[:12], packed[12:], PREFIX.encode())
            .decode()
        )
    except CredentialError:
        raise
    except Exception as error:
        raise CredentialError("Credential could not be decrypted.") from error


def mask_credential(value: str) -> str:
    return f"••••{value[-4:]}" if len(value) >= 4 else "••••"
