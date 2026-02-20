"""Auth-related data models."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Response from Amazon OAuth2 token endpoint."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: str | None = None


class TokenStatus(BaseModel):
    """Current state of the cached access token."""
    has_token: bool
    is_expired: bool
    expires_at: datetime | None = None
    seconds_remaining: int | None = None
