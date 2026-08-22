import base64
import os
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

PREFIX = "v1"
ROTATABLE_PREFIX = "v2"
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


def encrypt_credential(value: str, configured_key: str | None, *, key_id: str = "") -> str:
    raw = value.encode()
    if not raw or len(raw) > MAX_CREDENTIAL_BYTES:
        raise CredentialError("Credential length is invalid.")
    nonce = os.urandom(12)
    prefix = f"{ROTATABLE_PREFIX}.{key_id}" if key_id else PREFIX
    encrypted = AESGCM(encryption_key(configured_key)).encrypt(nonce, raw, prefix.encode())
    return f"{prefix}.{base64.urlsafe_b64encode(nonce + encrypted).decode()}"


def decrypt_credential(
    value: str,
    configured_key: str | None,
    *,
    key_id: str = "",
    previous_keys: Mapping[str, str] | None = None,
) -> str:
    try:
        parts = value.split(".", 2)
        if len(parts) == 2 and parts[0] == PREFIX:
            aad = PREFIX
            encoded = parts[1]
            keys = [("current", configured_key)]
        elif len(parts) == 3 and parts[0] == ROTATABLE_PREFIX:
            stored_key_id, encoded = parts[1], parts[2]
            aad = f"{ROTATABLE_PREFIX}.{stored_key_id}"
            keys = [(stored_key_id, configured_key if stored_key_id == key_id else None)]
            if previous_keys and stored_key_id in previous_keys:
                keys.append((stored_key_id, previous_keys[stored_key_id]))
        else:
            raise CredentialError("Credential version is unsupported.")
        packed = base64.urlsafe_b64decode(encoded.encode())
        for _name, candidate in keys:
            if not candidate:
                continue
            try:
                return (
                    AESGCM(encryption_key(candidate))
                    .decrypt(packed[:12], packed[12:], aad.encode())
                    .decode()
                )
            except Exception:
                continue
        raise CredentialError("Credential could not be decrypted.")
    except CredentialError:
        raise
    except Exception as error:
        raise CredentialError("Credential could not be decrypted.") from error


def rotate_credential(
    value: str, current_key: str | None, new_key: str | None, *, new_key_id: str
) -> str:
    plaintext = decrypt_credential(value, current_key)
    return encrypt_credential(plaintext, new_key, key_id=new_key_id)


def mask_credential(value: str) -> str:
    return (
        f"\u2022\u2022\u2022\u2022{value[-4:]}" if len(value) >= 4 else "\u2022\u2022\u2022\u2022"
    )
