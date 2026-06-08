"""Schemas for per-user Alpaca credential management."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AlpacaConnectRequest(BaseModel):
    api_key: str = Field(min_length=8, max_length=64)
    api_secret: str = Field(min_length=8, max_length=128)


class AlpacaStatus(BaseModel):
    connected: bool
    api_key_masked: str | None = None
