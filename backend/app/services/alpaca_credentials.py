"""Per-user Alpaca credential storage and brokerage construction.

Secrets are encrypted at rest (app.core.crypto). Saving a credential validates it
by calling Alpaca, so a stored credential is always one that authenticated at
least once. `broker_for_user` builds an `AlpacaPaperExecution` bound to *that
user's* keys — this is what makes the app multi-tenant: each user trades their
own Alpaca paper account.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.crypto import decrypt, encrypt
from app.core.logging import get_logger
from app.models.alpaca_credential import AlpacaCredential
from app.models.user import User
from app.services.execution.alpaca import AlpacaPaperExecution
from app.services.execution.base import ExecutionError

logger = get_logger(__name__)


class CredentialError(RuntimeError):
    """Raised when Alpaca credentials are invalid or can't be saved."""


def _build_broker(api_key: str, api_secret: str) -> AlpacaPaperExecution:
    """Construct a per-user Alpaca broker. Indirection point for tests."""
    return AlpacaPaperExecution(api_key=api_key, api_secret=api_secret)


def get_credential(db: Session, user: User) -> AlpacaCredential | None:
    return (
        db.query(AlpacaCredential)
        .filter(AlpacaCredential.user_id == user.id)
        .first()
    )


def is_connected(db: Session, user: User) -> bool:
    return get_credential(db, user) is not None


def masked_key(api_key: str) -> str:
    return f"{api_key[:4]}…{api_key[-4:]}" if len(api_key) >= 8 else "…"


def save_credential(db: Session, user: User, api_key: str, api_secret: str) -> AlpacaCredential:
    """Validate the keys against Alpaca, then store (secret encrypted)."""
    api_key = api_key.strip()
    api_secret = api_secret.strip()
    try:
        _build_broker(api_key, api_secret).get_account()
    except ExecutionError as exc:
        raise CredentialError(
            "Could not connect to Alpaca with those keys — check they're paper "
            "keys and try again."
        ) from exc

    cred = get_credential(db, user)
    if cred is None:
        cred = AlpacaCredential(
            user_id=user.id, api_key=api_key, secret_encrypted=encrypt(api_secret)
        )
        db.add(cred)
    else:
        cred.api_key = api_key
        cred.secret_encrypted = encrypt(api_secret)
    db.commit()
    db.refresh(cred)
    logger.info("alpaca credential saved for user %s", user.id)
    return cred


def delete_credential(db: Session, user: User) -> None:
    cred = get_credential(db, user)
    if cred is not None:
        db.delete(cred)
        db.commit()


def raw_credentials(db: Session, user: User) -> tuple[str, str] | None:
    """The user's (api_key, api_secret) decrypted, or None. For data-API calls."""
    cred = get_credential(db, user)
    if cred is None:
        return None
    secret = decrypt(cred.secret_encrypted)
    if secret is None:
        logger.warning("could not decrypt alpaca secret for user %s", user.id)
        return None
    return cred.api_key, secret


def broker_for_user(db: Session, user: User):
    """An Alpaca broker bound to this user's keys, or None if not connected."""
    creds = raw_credentials(db, user)
    if creds is None:
        return None
    try:
        return _build_broker(*creds)
    except ExecutionError:
        return None
