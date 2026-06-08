"""Public client-config endpoint (feature flags the UI needs)."""
from __future__ import annotations

from fastapi import APIRouter

from app.schemas.research import DISCLAIMER

router = APIRouter(tags=["config"])


@router.get("/config")
def get_config() -> dict:
    # Alpaca is available to every user via per-user keys (Settings → Connect
    # Alpaca). Whether a given user is connected is reported by GET /alpaca/credentials.
    return {
        "alpaca_available": True,
        "disclaimer": DISCLAIMER,
    }
