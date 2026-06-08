"""Symmetric encryption for secrets at rest (e.g. users' Alpaca API secrets).

Uses Fernet (AES-128-CBC + HMAC) with a key derived from `SECRET_KEY`. For real
production, set a dedicated high-entropy `SECRET_KEY` (or a separate KMS-managed
key) — deriving from the app secret is fine for this project but rotating the
secret invalidates existing ciphertext.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str | None:
    """Return the plaintext, or None if the token is invalid/undecryptable."""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None
