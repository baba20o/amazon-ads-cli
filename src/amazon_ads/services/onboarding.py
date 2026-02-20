"""Product onboarding service — automated AUTO+MANUAL campaign creation across regions."""

from __future__ import annotations

from typing import Any

from rich.console import Console

from amazon_ads.client import AmazonAdsClient
from amazon_ads.models.ad_groups import CreateAdGroupRequest
from amazon_ads.models.campaigns import CreateCampaignRequest
from amazon_ads.models.keywords import CreateKeywordRequest
from amazon_ads.models.product_ads import CreateProductAdRequest
from amazon_ads.services.ad_groups import AdGroupService
from amazon_ads.services.campaigns import CampaignService
from amazon_ads.services.keywords import KeywordService
from amazon_ads.services.product_ads import ProductAdService
from amazon_ads.services.sync import _extract_id

console = Console(stderr=True)

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]


class OnboardingService:
    """Service for onboarding new products with AUTO+MANUAL campaign pairs."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client
        self._campaigns = CampaignService(client)
        self._ad_groups = AdGroupService(client)
        self._keywords = KeywordService(client)
        self._product_ads = ProductAdService(client)

    def onboard_product(
        self,
        title: str,
        asins: list[str],
        regions: list[str] | None = None,
        keywords: list[dict[str, str]] | None = None,
        budget: float = 100.0,
        default_bid: float = 0.45,
        keyword_bid: float = 0.30,
    ) -> list[dict[str, Any]]:
        """Create AUTO + MANUAL campaign pair for a product across regions.

        Args:
            title: Product title used in campaign naming.
            asins: List of ASINs (e.g., Kindle + Paperback).
            regions: Regions to onboard in. Defaults to all 8 regions.
            keywords: Optional keywords for MANUAL campaigns.
                Each dict should have "keywordText" and optionally "matchType" (defaults to BROAD).
            budget: Daily budget per campaign.
            default_bid: Default bid for ad groups.
            keyword_bid: Bid for keywords in MANUAL campaigns.

        Returns:
            List of results per region.
        """
        target_regions = regions or ALL_REGIONS
        all_results: list[dict[str, Any]] = []

        for region in target_regions:
            console.print(f"\nOnboarding '{title}' in {region}...")

            region_result: dict[str, Any] = {
                "region": region,
                "title": title,
                "auto": {},
                "manual": {},
                "status": "SUCCESS",
            }

            try:
                # ── AUTO Campaign ────────────────────────────
                auto_name = f"{title}-AUTOMATIC-PRODUCTION"
                auto_ag_name = f"{title}-replicate"

                auto_result = self._create_campaign_set(
                    region=region,
                    campaign_name=auto_name,
                    ad_group_name=auto_ag_name,
                    targeting_type="AUTO",
                    asins=asins,
                    budget=budget,
                    default_bid=default_bid,
                )
                region_result["auto"] = auto_result

                # ── MANUAL Campaign ──────────────────────────
                manual_name = f"{title}-MANUAL-PRODUCTION"

                manual_result = self._create_campaign_set(
                    region=region,
                    campaign_name=manual_name,
                    ad_group_name=manual_name,
                    targeting_type="MANUAL",
                    asins=asins,
                    keywords=keywords,
                    budget=budget,
                    default_bid=default_bid,
                    keyword_bid=keyword_bid,
                )
                region_result["manual"] = manual_result

            except RuntimeError as e:
                console.print(f"  [red]Error in {region}:[/red] {e}")
                region_result["status"] = "ERROR"
                region_result["error"] = str(e)

            all_results.append(region_result)

        return all_results

    def _create_campaign_set(
        self,
        region: str,
        campaign_name: str,
        ad_group_name: str,
        targeting_type: str,
        asins: list[str],
        keywords: list[dict[str, str]] | None = None,
        budget: float = 100.0,
        default_bid: float = 0.45,
        keyword_bid: float = 0.30,
    ) -> dict[str, Any]:
        """Create a single campaign with ad group, product ads, and optional keywords."""
        result: dict[str, Any] = {
            "campaignName": campaign_name,
            "targetingType": targeting_type,
        }

        # Create campaign
        from amazon_ads.models.campaigns import CampaignBudget

        campaign_req = CreateCampaignRequest(
            name=campaign_name,
            targetingType=targeting_type,
            state="ENABLED",
            budget=CampaignBudget(budgetType="DAILY", budget=budget),
        )
        camp_resp = self._campaigns.create(region, campaign_req)
        campaign_id = _extract_id(camp_resp, "campaigns", "campaignId")

        if not campaign_id:
            result["status"] = "FAILED"
            result["error"] = "Could not create campaign"
            console.print(f"  [red]Failed to create '{campaign_name}'[/red]")
            return result

        result["campaignId"] = campaign_id
        console.print(f"  Created campaign '{campaign_name}' ({campaign_id})")

        # Create ad group
        ag_req = CreateAdGroupRequest(
            campaignId=campaign_id,
            name=ad_group_name,
            state="ENABLED",
            defaultBid=default_bid,
        )
        ag_resp = self._ad_groups.create(region, ag_req)
        ad_group_id = _extract_id(ag_resp, "adGroups", "adGroupId")

        if not ad_group_id:
            result["status"] = "PARTIAL"
            result["error"] = "Could not create ad group"
            console.print(f"  [red]Failed to create ad group for '{campaign_name}'[/red]")
            return result

        result["adGroupId"] = ad_group_id

        # Create product ads for each ASIN
        for asin in asins:
            pa_req = CreateProductAdRequest(
                campaignId=campaign_id,
                adGroupId=ad_group_id,
                asin=asin,
                state="ENABLED",
            )
            self._product_ads.create(region, pa_req)

        result["asins"] = len(asins)
        console.print(f"  Added {len(asins)} product ad(s)")

        # Create keywords for MANUAL campaigns only
        kw_count = 0
        if targeting_type == "MANUAL" and keywords:
            kw_requests = []
            for kw in keywords:
                text = kw.get("keywordText", kw.get("keyword_text", ""))
                match_type = kw.get("matchType", kw.get("match_type", "BROAD"))
                if not text:
                    continue
                kw_requests.append(
                    CreateKeywordRequest(
                        campaignId=campaign_id,
                        adGroupId=ad_group_id,
                        keywordText=text,
                        matchType=match_type.upper(),
                        bid=keyword_bid,
                    )
                )

            if kw_requests:
                self._keywords.create(region, kw_requests)
                kw_count = len(kw_requests)
                console.print(f"  Added {kw_count} keyword(s)")

        result["keywords"] = kw_count
        result["status"] = "SUCCESS"
        return result
