"""Keyword management service."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.keywords import CreateKeywordRequest, UpdateKeywordRequest
from amazon_ads.services.campaigns import parse_multi_status
from amazon_ads.utils.chunking import chunk_list
from amazon_ads.utils.pagination import paginate


SP_CT = CONTENT_TYPES["keywords"]
console = Console(stderr=True)

# Regions where native language locale should be set for EU API
_EU_NATIVE_LOCALE_REGIONS = {"DE", "FR", "IT", "ES"}


class KeywordService:
    """Service for Sponsored Products keyword CRUD operations."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    def list(
        self,
        region: str,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        keyword_id: str | None = None,
        state: str | None = None,
        match_type: str | None = None,
        keyword_text: str | None = None,
        max_results: int = 5000,
    ) -> list[dict[str, Any]]:
        """List keywords with automatic pagination."""
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

        if keyword_id:
            body["keywordIdFilter"] = {
                "filterType": "KEYWORD_ID",
                "include": [keyword_id],
            }

        if match_type:
            body["matchTypeFilter"] = {
                "filterType": "MATCH_TYPE",
                "include": [match_type.upper()],
            }

        if keyword_text:
            body["keywordTextFilter"] = {
                "include": [keyword_text],
                "queryTermMatchType": "BROAD_MATCH",
            }

        def fetch(b: dict[str, Any]) -> dict[str, Any]:
            resp = self._client.post(
                "/sp/keywords/list", region, body=b, content_type=SP_CT, accept=SP_CT
            )
            return resp.json()

        return paginate(fetch, body, "keywords")

    def create(
        self,
        region: str,
        keywords: list[CreateKeywordRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Create keywords in bulk with automatic chunking.

        For EU regions (DE, FR, IT, ES), automatically sets
        nativeLanguageLocale to en_GB if not already set.
        """
        payloads = []
        for kw in keywords:
            data = kw.model_dump(by_alias=True, exclude_none=True)
            # Auto-set native language locale for non-English EU regions
            if (
                region.upper() in _EU_NATIVE_LOCALE_REGIONS
                and "nativeLanguageLocale" not in data
            ):
                data["nativeLanguageLocale"] = "en_GB"
            payloads.append(data)

        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending keyword chunk {i}/{len(chunks)}...")
            body = {"keywords": chunk}
            response = self._client.post(
                "/sp/keywords", region, body=body, content_type=SP_CT, accept=SP_CT
            )
            all_responses.append(parse_multi_status(response.json(), "keywords"))

        return all_responses

    def update(
        self,
        region: str,
        keywords: list[UpdateKeywordRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Update keywords in bulk with automatic chunking."""
        payloads = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords]
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending keyword update chunk {i}/{len(chunks)}...")
            body = {"keywords": chunk}
            response = self._client.put(
                "/sp/keywords", region, body=body, content_type=SP_CT, accept=SP_CT
            )
            all_responses.append(parse_multi_status(response.json(), "keywords"))

        return all_responses

    def delete(
        self,
        region: str,
        keyword_ids: list[str],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Delete keywords by IDs with automatic chunking."""
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(keyword_ids, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending keyword delete chunk {i}/{len(chunks)}...")
            body = {"keywordIdFilter": {"include": chunk}}
            response = self._client.post(
                "/sp/keywords/delete", region, body=body, content_type=SP_CT, accept=SP_CT
            )
            all_responses.append(parse_multi_status(response.json(), "keywords"))

        return all_responses
