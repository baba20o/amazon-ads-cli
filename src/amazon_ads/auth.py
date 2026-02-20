"""OAuth2 authentication for Amazon Advertising API.

Handles token refresh, caching, and expiry tracking.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from amazon_ads.config import Config
from amazon_ads.models.auth import TokenResponse, TokenStatus


# Buffer before expiry to trigger refresh (matches legacy 5-min behavior)
EXPIRY_BUFFER = timedelta(minutes=5)


class AuthManager:
    """Manages OAuth2 access tokens for Amazon Ads API."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None
        self._http = httpx.Client(timeout=30.0)

    def get_access_token(self, region: str = "US", force_refresh: bool = False) -> str:
        """Get a valid access token, refreshing if needed.

        Args:
            region: Country code (US, GB, etc.) to determine auth endpoint.
            force_refresh: Force a token refresh even if current token is valid.

        Returns:
            A valid access token string.
        """
        if not force_refresh and self._is_token_valid():
            return self._access_token  # type: ignore[return-value]

        self._refresh_token(region)
        return self._access_token  # type: ignore[return-value]

    def get_status(self) -> TokenStatus:
        """Get the current token status."""
        if not self._access_token:
            return TokenStatus(has_token=False, is_expired=True)

        now = datetime.now()
        is_expired = self._token_expiry is None or now > self._token_expiry
        seconds_remaining = None
        if self._token_expiry and not is_expired:
            seconds_remaining = int((self._token_expiry - now).total_seconds())

        return TokenStatus(
            has_token=True,
            is_expired=is_expired,
            expires_at=self._token_expiry,
            seconds_remaining=seconds_remaining,
        )

    def _is_token_valid(self) -> bool:
        """Check if the current token is valid with a safety buffer."""
        if not self._access_token or not self._token_expiry:
            return False
        return datetime.now() + EXPIRY_BUFFER < self._token_expiry

    def _refresh_token(self, region: str) -> None:
        """Refresh the access token using the refresh token flow."""
        profile = self._config.get_region(region)
        refresh_token = self._config.get_refresh_token(region)

        if not refresh_token:
            raise ValueError(
                f"No refresh token configured for auth region '{profile.auth_region}'. "
                "Check your .env file."
            )

        response = self._http.post(
            profile.auth_endpoint,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": self._config.settings.client_id,
                "client_secret": self._config.settings.client_secret,
            },
        )

        if response.status_code != 200:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get("error_description", response.text)
            except Exception:
                pass
            raise RuntimeError(
                f"Token refresh failed (HTTP {response.status_code}): {error_detail}"
            )

        token_data = TokenResponse(**response.json())
        self._access_token = token_data.access_token
        self._token_expiry = datetime.now() + timedelta(seconds=token_data.expires_in)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()
