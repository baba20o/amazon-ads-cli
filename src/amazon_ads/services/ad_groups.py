"""Ad group management service."""

from __future__ import annotations

from typing import Any

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.ad_groups import CreateAdGroupRequest, UpdateAdGroupRequest
from amazon_ads.services.campaigns import parse_multi_status
from amazon_ads.utils.pagination import paginate

SP_CT = CONTENT_TYPES["ad_groups"]


class AdGroupService:
    """Service for Sponsored Products ad group CRUD operations."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    def list(
        self,
        region: str,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        state: str | None = None,
        name: str | None = None,
        max_results: int = 1000,
    ) -> list[dict[str, Any]]:
        """List ad groups with automatic pagination.

        Supports server-side filtering by state, name (broad match),
        campaign ID, and ad group ID.
        """
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

        if name:
            body["nameFilter"] = {
                "include": [name],
                "queryTermMatchType": "BROAD_MATCH",
            }

        def fetch(b: dict[str, Any]) -> dict[str, Any]:
            resp = self._client.post(
                "/sp/adGroups/list", region, body=b,
                content_type=SP_CT, accept=SP_CT,
            )
            return resp.json()

        return paginate(fetch, body, "adGroups")

    def create(self, region: str, request: CreateAdGroupRequest) -> dict[str, Any]:
        """Create a new ad group."""
        body = {"adGroups": [request.model_dump(by_alias=True, exclude_none=True)]}
        response = self._client.post(
            "/sp/adGroups", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "adGroups")

    def update(self, region: str, request: UpdateAdGroupRequest) -> dict[str, Any]:
        """Update an existing ad group."""
        body = {"adGroups": [request.model_dump(by_alias=True, exclude_none=True)]}
        response = self._client.put(
            "/sp/adGroups", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "adGroups")

    def delete(self, region: str, ad_group_ids: list[str]) -> dict[str, Any]:
        """Delete ad groups by IDs."""
        body = {"adGroupIdFilter": {"include": ad_group_ids}}
        response = self._client.post(
            "/sp/adGroups/delete", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "adGroups")
