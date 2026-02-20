"""Product targeting management service."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.keywords import (
    CreateNegativeTargetRequest,
    CreateProductTargetRequest,
    UpdateProductTargetRequest,
)
from amazon_ads.services.campaigns import parse_multi_status
from amazon_ads.utils.chunking import chunk_list
from amazon_ads.utils.pagination import paginate

TARGET_CT = CONTENT_TYPES["targets"]
NEG_TARGET_CT = CONTENT_TYPES["negative_targets"]
console = Console(stderr=True)


class TargetingService:
    """Service for Sponsored Products product/category targeting CRUD operations.

    Supports both positive targets (/sp/targets) and negative targets
    (/sp/negativeTargetingClauses).
    """

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    # ── Positive targets ──────────────────────────────────────────

    def list(
        self,
        region: str,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        state: str | None = None,
        max_results: int = 5000,
    ) -> list[dict[str, Any]]:
        """List product targeting clauses with pagination."""
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
                "/sp/targets/list", region, body=b,
                content_type=TARGET_CT, accept=TARGET_CT,
            )
            return resp.json()

        return paginate(fetch, body, "targetingClauses")

    def create(
        self,
        region: str,
        targets: list[CreateProductTargetRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Create product targeting clauses in bulk."""
        payloads = [t.model_dump(by_alias=True, exclude_none=True) for t in targets]
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending target chunk {i}/{len(chunks)}...")
            body = {"targetingClauses": chunk}
            response = self._client.post(
                "/sp/targets", region, body=body,
                content_type=TARGET_CT, accept=TARGET_CT,
            )
            all_responses.append(parse_multi_status(response.json(), "targetingClauses"))

        return all_responses

    def update(
        self,
        region: str,
        targets: list[UpdateProductTargetRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Update product targeting clauses (bid and/or state) in bulk."""
        payloads = [t.model_dump(by_alias=True, exclude_none=True) for t in targets]
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending target update chunk {i}/{len(chunks)}...")
            body = {"targetingClauses": chunk}
            response = self._client.put(
                "/sp/targets", region, body=body,
                content_type=TARGET_CT, accept=TARGET_CT,
            )
            all_responses.append(parse_multi_status(response.json(), "targetingClauses"))

        return all_responses

    def delete(
        self,
        region: str,
        target_ids: list[str],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Delete product targeting clauses by IDs."""
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(target_ids, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending target delete chunk {i}/{len(chunks)}...")
            body = {"targetIdFilter": {"include": chunk}}
            response = self._client.post(
                "/sp/targets/delete", region, body=body,
                content_type=TARGET_CT, accept=TARGET_CT,
            )
            all_responses.append(parse_multi_status(response.json(), "targetingClauses"))

        return all_responses

    # ── Negative targets ──────────────────────────────────────────

    def list_negative(
        self,
        region: str,
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
        state: str | None = None,
        max_results: int = 5000,
    ) -> list[dict[str, Any]]:
        """List negative targeting clauses with pagination."""
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
                "/sp/negativeTargetingClauses/list", region, body=b,
                content_type=NEG_TARGET_CT, accept=NEG_TARGET_CT,
            )
            return resp.json()

        return paginate(fetch, body, "negativeTargetingClauses")

    def create_negative(
        self,
        region: str,
        targets: list[CreateNegativeTargetRequest],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Create negative targeting clauses in bulk."""
        payloads = [t.model_dump(by_alias=True, exclude_none=True) for t in targets]
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(payloads, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending negative target chunk {i}/{len(chunks)}...")
            body = {"negativeTargetingClauses": chunk}
            response = self._client.post(
                "/sp/negativeTargetingClauses", region, body=body,
                content_type=NEG_TARGET_CT, accept=NEG_TARGET_CT,
            )
            all_responses.append(
                parse_multi_status(response.json(), "negativeTargetingClauses")
            )

        return all_responses

    def delete_negative(
        self,
        region: str,
        target_ids: list[str],
        chunk_size: int = 1000,
    ) -> list[dict[str, Any]]:
        """Delete negative targeting clauses by IDs."""
        all_responses: list[dict[str, Any]] = []
        chunks = chunk_list(target_ids, chunk_size)

        for i, chunk in enumerate(chunks, 1):
            if len(chunks) > 1:
                console.print(f"Sending negative target delete chunk {i}/{len(chunks)}...")
            body = {"negativeTargetingClauseIdFilter": {"include": chunk}}
            response = self._client.post(
                "/sp/negativeTargetingClauses/delete", region, body=body,
                content_type=NEG_TARGET_CT, accept=NEG_TARGET_CT,
            )
            all_responses.append(
                parse_multi_status(response.json(), "negativeTargetingClauses")
            )

        return all_responses
