"""Campaign management service."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.campaigns import CreateCampaignRequest, UpdateCampaignRequest
from amazon_ads.utils.pagination import paginate

SP_CT = CONTENT_TYPES["campaigns"]
console = Console(stderr=True)


def parse_multi_status(response: dict[str, Any], entity_key: str) -> dict[str, Any]:
    """Parse a multi-status response and warn about failures."""
    entities = response.get(entity_key, {})
    errors = entities.get("error", [])
    if errors:
        for err in errors[:5]:
            console.print(
                f"  [red]Error:[/red] {err.get('errorType', 'UNKNOWN')}: "
                f"{err.get('description', err)}"
            )
        if len(errors) > 5:
            console.print(f"  [red]... and {len(errors) - 5} more errors[/red]")
    return response


class CampaignService:
    """Service for Sponsored Products campaign CRUD operations."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    def list(
        self,
        region: str,
        state: str | None = None,
        name: str | None = None,
        campaign_id: str | None = None,
        portfolio_id: str | None = None,
        max_results: int = 5000,
    ) -> list[dict[str, Any]]:
        """List campaigns with automatic pagination.

        Supports server-side filtering by state, name (broad match),
        campaign ID, and portfolio ID.
        """
        body: dict[str, Any] = {"maxResults": max_results}

        if state:
            body["stateFilter"] = {
                "filterType": "STATE",
                "include": [state.upper()],
            }

        if name:
            body["nameFilter"] = {
                "include": [name],
                "queryTermMatchType": "BROAD_MATCH",
            }

        if campaign_id:
            body["campaignIdFilter"] = {
                "filterType": "CAMPAIGN_ID",
                "include": [campaign_id],
            }

        if portfolio_id:
            body["portfolioIdFilter"] = {
                "filterType": "PORTFOLIO_ID",
                "include": [portfolio_id],
            }

        def fetch(b: dict[str, Any]) -> dict[str, Any]:
            resp = self._client.post(
                "/sp/campaigns/list", region, body=b,
                content_type=SP_CT, accept=SP_CT,
            )
            return resp.json()

        return paginate(fetch, body, "campaigns")

    def create(self, region: str, request: CreateCampaignRequest) -> dict[str, Any]:
        """Create a new campaign."""
        body = {"campaigns": [request.model_dump(by_alias=True, exclude_none=True)]}
        response = self._client.post(
            "/sp/campaigns", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "campaigns")

    def update(self, region: str, request: UpdateCampaignRequest) -> dict[str, Any]:
        """Update an existing campaign."""
        body = {"campaigns": [request.model_dump(by_alias=True, exclude_none=True)]}
        response = self._client.put(
            "/sp/campaigns", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "campaigns")

    def delete(self, region: str, campaign_ids: list[str]) -> dict[str, Any]:
        """Delete campaigns by IDs."""
        body = {"campaignIdFilter": {"include": campaign_ids}}
        response = self._client.post(
            "/sp/campaigns/delete", region, body=body,
            content_type=SP_CT, accept=SP_CT,
        )
        return parse_multi_status(response.json(), "campaigns")
