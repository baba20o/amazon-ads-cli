"""Profile and account management service."""

from __future__ import annotations

from typing import Any

from amazon_ads.client import AmazonAdsClient


class ProfileService:
    """Service for fetching Amazon Ads profiles and accounts."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    def list_profiles(self, region: str = "US") -> list[dict[str, Any]]:
        """List all advertising profiles."""
        response = self._client.get("/v2/profiles", region)
        return response.json()

    def list_accounts(self, region: str = "US") -> list[dict[str, Any]]:
        """List all ads accounts."""
        response = self._client.post("/adsAccounts/list", region)
        data = response.json()
        return data.get("adsAccounts", data)
