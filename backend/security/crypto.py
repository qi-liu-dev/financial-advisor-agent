from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from backend.config import get_settings


_ENCRYPTED_PREFIX = "enc:v1:"


class DataEncryptionError(RuntimeError):
    """Raised when encrypted application data cannot be encoded or decoded."""


@lru_cache(maxsize=4)
def _fernet_for_key(key: str) -> Fernet:
    try:
        return Fernet(key.encode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise DataEncryptionError(
            "DATA_ENCRYPTION_KEY must be a URL-safe base64-encoded 32-byte Fernet key."
        ) from exc


def encryption_enabled() -> bool:
    return bool(get_settings().data_encryption_key)


def validate_encryption_configuration() -> None:
    key = get_settings().data_encryption_key
    if key:
        _fernet_for_key(key)


def encode_json(value: Any) -> str:
    """Serialise JSON and encrypt it when DATA_ENCRYPTION_KEY is configured.

    Existing plaintext database rows remain readable, which makes enabling
    encryption backwards compatible. New writes are encrypted immediately.
    """

    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    key = get_settings().data_encryption_key
    if not key:
        return raw
    token = _fernet_for_key(key).encrypt(raw.encode("utf-8")).decode("ascii")
    return f"{_ENCRYPTED_PREFIX}{token}"


def decode_json(value: str | None, *, default: Any = None) -> Any:
    if value is None:
        return default

    raw = value
    if value.startswith(_ENCRYPTED_PREFIX):
        key = get_settings().data_encryption_key
        if not key:
            raise DataEncryptionError(
                "Encrypted database data exists but DATA_ENCRYPTION_KEY is not configured."
            )
        try:
            raw = _fernet_for_key(key).decrypt(
                value[len(_ENCRYPTED_PREFIX) :].encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise DataEncryptionError(
                "Unable to decrypt database data with the configured key."
            ) from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DataEncryptionError("Stored application data is not valid JSON.") from exc
