"""Bid optimization service — get suggested bids, compare, and apply."""

from __future__ import annotations

import time
from typing import Any

from rich.console import Console

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.keywords import UpdateKeywordRequest
from amazon_ads.services.keywords import KeywordService
from amazon_ads.utils.chunking import chunk_list

BID_CT = CONTENT_TYPES["bid_recommendations"]
console = Console(stderr=True)

# Map internal match types to API targeting expression types
_MATCH_TYPE_MAP = {
    "BROAD": "KEYWORD_BROAD_MATCH",
    "EXACT": "KEYWORD_EXACT_MATCH",
    "PHRASE": "KEYWORD_PHRASE_MATCH",
}


class OptimizationService:
    """Service for bid optimization using Amazon suggested bids."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client
        self._keyword_service = KeywordService(client)

    def get_suggested_bids(
        self,
        region: str,
        keywords: list[dict[str, Any]],
        chunk_size: int = 100,
        throttle: float = 0.5,
    ) -> dict[str, dict[str, float]]:
        """Fetch suggested bids for a list of keywords.

        Groups keywords by (campaignId, adGroupId) and requests bid
        recommendations in chunks of 100.

        Returns:
            A dict mapping "KEYWORD_<MATCH>_MATCH_<text>" →
            {"low": x, "suggested": y, "high": z}.
        """
        # Group keywords by (campaignId, adGroupId)
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for kw in keywords:
            key = (kw["campaignId"], kw["adGroupId"])
            groups.setdefault(key, []).append(kw)

        bid_map: dict[str, dict[str, float]] = {}

        request_count = 0
        total_groups = len(groups)

        for gi, ((campaign_id, ad_group_id), group_kws) in enumerate(groups.items(), 1):
            chunks = chunk_list(group_kws, chunk_size)
            for i, chunk in enumerate(chunks, 1):
                # Throttle between requests to avoid 429s
                if request_count > 0 and throttle > 0:
                    time.sleep(throttle)
                request_count += 1

                targeting_expressions = []
                for kw in chunk:
                    api_match = _MATCH_TYPE_MAP.get(kw["matchType"])
                    if not api_match:
                        continue
                    targeting_expressions.append({
                        "type": api_match,
                        "value": kw["keywordText"],
                    })

                if not targeting_expressions:
                    continue

                if total_groups > 5:
                    console.print(
                        f"  [dim]Bid request {request_count} "
                        f"(group {gi}/{total_groups}, chunk {i}/{len(chunks)})[/dim]"
                    )

                body = {
                    "targetingExpressions": targeting_expressions,
                    "campaignId": campaign_id,
                    "recommendationType": "BIDS_FOR_EXISTING_AD_GROUP",
                    "adGroupId": ad_group_id,
                }

                response = self._client.post(
                    "/sp/targets/bid/recommendations",
                    region,
                    body=body,
                    content_type=BID_CT,
                    accept=BID_CT,
                )
                data = response.json()

                # Parse bid recommendations — nested under bidRecommendations[].bidRecommendationsForTargetingExpressions
                recs: list[dict] = []
                for theme_block in data.get("bidRecommendations", []):
                    recs.extend(theme_block.get("bidRecommendationsForTargetingExpressions", []))

                for rec in recs:
                    expr = rec.get("targetingExpression", {})
                    bid_values = rec.get("bidValues", [])
                    if not expr or not bid_values:
                        continue

                    # Extract low/suggested/high from bidValues array
                    # Amazon returns 3 entries: [low, suggested, high]
                    bid_data: dict[str, float] = {}
                    if len(bid_values) >= 3:
                        bid_data["low"] = float(bid_values[0].get("suggestedBid", 0))
                        bid_data["suggested"] = float(bid_values[1].get("suggestedBid", 0))
                        bid_data["high"] = float(bid_values[2].get("suggestedBid", 0))
                    elif len(bid_values) == 2:
                        bid_data["low"] = float(bid_values[0].get("suggestedBid", 0))
                        bid_data["suggested"] = float(bid_values[1].get("suggestedBid", 0))
                        bid_data["high"] = bid_data["suggested"]
                    elif len(bid_values) == 1:
                        val = float(bid_values[0].get("suggestedBid", 0))
                        bid_data = {"low": val, "suggested": val, "high": val}

                    if bid_data.get("suggested"):
                        lookup_key = f"{expr['type']}_{expr['value']}"
                        bid_map[lookup_key] = bid_data

        return bid_map

    def compare_bids(
        self,
        keywords: list[dict[str, Any]],
        bid_map: dict[str, dict[str, float]],
        offset: float = 0.02,
    ) -> list[dict[str, Any]]:
        """Compare current bids against suggested bids.

        Returns a list of dicts with keywordId, keywordText, matchType,
        currentBid, suggestedBidLow/suggested/high, newBid, and action
        for each keyword that has a suggested bid.

        Only flags keywords where current bid > suggested + offset
        (i.e., keywords that are overbid).
        """
        comparisons: list[dict[str, Any]] = []
        for kw in keywords:
            api_match = _MATCH_TYPE_MAP.get(kw["matchType"])
            if not api_match:
                continue

            lookup_key = f"{api_match}_{kw['keywordText']}"
            bid_data = bid_map.get(lookup_key)
            if bid_data is None:
                continue

            suggested = bid_data["suggested"]
            current_bid = float(kw.get("bid", 0))
            new_bid = round(suggested + offset, 2)

            action = "REDUCE" if current_bid > new_bid else "KEEP"

            comparisons.append({
                "keywordId": kw["keywordId"],
                "keywordText": kw["keywordText"],
                "matchType": kw["matchType"],
                "campaignId": kw["campaignId"],
                "adGroupId": kw["adGroupId"],
                "currentBid": current_bid,
                "suggestedBidLow": round(bid_data["low"], 2),
                "suggestedBid": round(suggested, 2),
                "suggestedBidHigh": round(bid_data["high"], 2),
                "newBid": new_bid,
                "action": action,
            })

        return comparisons

    def optimize(
        self,
        region: str,
        campaign_id: str | None = None,
        offset: float = 0.02,
        apply: bool = False,
    ) -> list[dict[str, Any]]:
        """Full optimization flow: fetch keywords → get suggestions → compare → optionally apply.

        Returns the comparison results. If apply=True, also updates overbid keywords.
        """
        console.print(f"Fetching enabled keywords for {region}...")
        keywords = self._keyword_service.list(
            region, campaign_id=campaign_id, state="ENABLED"
        )

        if not keywords:
            console.print(f"No enabled keywords found in {region}")
            return []

        console.print(f"Found {len(keywords)} enabled keywords. Fetching suggested bids...")
        bid_map = self.get_suggested_bids(region, keywords)
        console.print(f"Got suggestions for {len(bid_map)} keywords")

        comparisons = self.compare_bids(keywords, bid_map, offset=offset)

        to_reduce = [c for c in comparisons if c["action"] == "REDUCE"]
        to_keep = [c for c in comparisons if c["action"] == "KEEP"]
        console.print(
            f"Results: {len(to_reduce)} overbid (to reduce), "
            f"{len(to_keep)} within range"
        )

        if apply and to_reduce:
            console.print(f"Applying bid reductions to {len(to_reduce)} keywords...")
            updates = [
                UpdateKeywordRequest(keywordId=c["keywordId"], bid=c["newBid"])
                for c in to_reduce
            ]
            self._keyword_service.update(region, updates)
            console.print(f"Updated {len(updates)} keyword bids")

        return comparisons
