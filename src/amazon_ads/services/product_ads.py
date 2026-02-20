"""Product ad management service."""

from __future__ import annotations

from typing import Any

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.product_ads import CreateProductAdRequest
from amazon_ads.services.campaigns import parse_multi_status
from amazon_ads.utils.pagination import paginate

SP_CT = CONTENT_TYPES["product_ads"]


class ProductAdService:
    """Service for Sponsored Products product ad CRUD operations."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    def list(
        self,
        region: str,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        state: str | None = None,
        max_results: int = 1000,
    ) -> list[dict[str, Any]]:
        """List product ads with automatic pagination."""
        body: dict[str, Any] = {"maxResults": max_results}

        if state:
            body["stateFilter"] = {
                "filterType": "STATE",
                "include": [state.upper()],
            }

        if campaign_id:
            body["campaignIdFilter"] = {
                "filterType": "CAMPAIGN_ID",
                "include": [campaign_id],
            }

        if ad_group_id:
            body["adGroupIdFilter"] = {
                "filterType": "AD_GROUP_ID",
                "include": [ad_group_id],
            }

        def fetch(b: dict[str, Any]) -> dict[str, Any]:
            resp = self._client.post(
                "/sp/productAds/list", region, body=b,
                content_type=SP_CT, accept=SP_CT,
            )
            return resp.json()

        return paginate(fetch, body, "productAds")

    def create(self, region: str, request: CreateProductAdRequest) -> dict[str, Any]:
        """Create a new product ad."""
        body = {"productAds": [request.model_dump(by_alias=True, exclude_none=True)]}
        response = self._client.post(
            "/sp/productAds", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "productAds")
