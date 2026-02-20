"""Negative keyword management service."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.keywords import (
    CreateCampaignNegativeKeywordRequest,
    CreateNegativeKeywordRequest,
)
from amazon_ads.services.campaigns import parse_multi_status
from amazon_ads.utils.chunking import chunk_list
from amazon_ads.utils.pagination import paginate

NEG_CT = CONTENT_TYPES["negative_keywords"]
CAMP_NEG_CT = CONTENT_TYPES["campaign_negative_keywords"]
console = Console(stderr=True)


class NegativeKeywordService:
    """Service for Sponsored Products negative keyword CRUD operations.

    Supports both ad-group-level and campaign-level negative keywords.
    """

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    # ── Ad-group-level negative keywords ──────────────────────────

    def list(
        self,
        region: str,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        state: str | None = None,
        max_results: int = 5000,
    ) -> list[dict[str, Any]]:
        """List ad-group-level negative keywords with pagination."""
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
                "/sp/negativeKeywords/list", region, body=b,
                content_type=NEG_CT, accept=NEG_CT,
            )
            return resp.json()

        return paginate(fetch, body, "negativeKeywords")

    def create(
        self,
        region: str,
        keywords: list[CreateNegativeKeywordRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Create ad-group-level negative keywords in bulk."""
        payloads = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords]
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending negative keyword chunk {i}/{len(chunks)}...")
            body = {"negativeKeywords": chunk}
            response = self._client.post(
                "/sp/negativeKeywords", region, body=body,
                content_type=NEG_CT, accept=NEG_CT,
            )
            all_responses.append(parse_multi_status(response.json(), "negativeKeywords"))

        return all_responses

    def delete(
        self,
        region: str,
        keyword_ids: list[str],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Delete ad-group-level negative keywords by IDs."""
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(keyword_ids, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending negative keyword delete chunk {i}/{len(chunks)}...")
            body = {"negativeKeywordIdFilter": {"include": chunk}}
            response = self._client.post(
                "/sp/negativeKeywords/delete", region, body=body,
                content_type=NEG_CT, accept=NEG_CT,
            )
            all_responses.append(parse_multi_status(response.json(), "negativeKeywords"))

        return all_responses

    # ── Campaign-level negative keywords ──────────────────────────

    def list_campaign_level(
        self,
        region: str,
        campaign_id: str | None = None,
        state: str | None = None,
        max_results: int = 5000,
    ) -> list[dict[str, Any]]:
        """List campaign-level negative keywords with pagination."""
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

        def fetch(b: dict[str, Any]) -> dict[str, Any]:
            resp = self._client.post(
                "/sp/campaignNegativeKeywords/list", region, body=b,
                content_type=CAMP_NEG_CT, accept=CAMP_NEG_CT,
            )
            return resp.json()

        return paginate(fetch, body, "campaignNegativeKeywords")

    def create_campaign_level(
        self,
        region: str,
        keywords: list[CreateCampaignNegativeKeywordRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Create campaign-level negative keywords in bulk."""
        payloads = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords]
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending campaign negative keyword chunk {i}/{len(chunks)}...")
            body = {"campaignNegativeKeywords": chunk}
            response = self._client.post(
                "/sp/campaignNegativeKeywords", region, body=body,
                content_type=CAMP_NEG_CT, accept=CAMP_NEG_CT,
            )
            all_responses.append(
                parse_multi_status(response.json(), "campaignNegativeKeywords")
            )

        return all_responses

    def delete_campaign_level(
        self,
        region: str,
        keyword_ids: list[str],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Delete campaign-level negative keywords by IDs."""
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(keyword_ids, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending campaign negative keyword delete chunk {i}/{len(chunks)}...")
            body = {"campaignNegativeKeywordIdFilter": {"include": chunk}}
            response = self._client.post(
                "/sp/campaignNegativeKeywords/delete", region, body=body,
                content_type=CAMP_NEG_CT, accept=CAMP_NEG_CT,
            )
            all_responses.append(
                parse_multi_status(response.json(), "campaignNegativeKeywords")
            )

        return all_responses
