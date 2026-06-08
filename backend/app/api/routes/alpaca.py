"""Per-user Alpaca credential routes. All require auth.

Users connect their own Alpaca *paper* account here; the secret is never returned.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.alpaca import AlpacaConnectRequest, AlpacaStatus
from app.services import alpaca_credentials as creds

router = APIRouter(prefix="/alpaca", tags=["alpaca"])


def _status(cred) -> AlpacaStatus:
    if cred is None:
        return AlpacaStatus(connected=False, api_key_masked=None)
    return AlpacaStatus(connected=True, api_key_masked=creds.masked_key(cred.api_key))


@router.get("/credentials", response_model=AlpacaStatus)
def get_status(db: DbSession, user: CurrentUser) -> AlpacaStatus:
    return _status(creds.get_credential(db, user))


@router.post("/credentials", response_model=AlpacaStatus)
def connect(body: AlpacaConnectRequest, db: DbSession, user: CurrentUser) -> AlpacaStatus:
    try:
        cred = creds.save_credential(db, user, body.api_key, body.api_secret)
    except creds.CredentialError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return _status(cred)


@router.delete("/credentials", response_model=AlpacaStatus)
def disconnect(db: DbSession, user: CurrentUser) -> AlpacaStatus:
    creds.delete_credential(db, user)
    return AlpacaStatus(connected=False, api_key_masked=None)
