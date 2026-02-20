"""Sync & replication service — export campaign structures and replicate across regions."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
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

console = Console(stderr=True)


class SyncService:
    """Service for exporting, replicating, and syncing campaign structures across regions."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client
        self._campaigns = CampaignService(client)
        self._ad_groups = AdGroupService(client)
        self._keywords = KeywordService(client)
        self._product_ads = ProductAdService(client)

    # ── Export ────────────────────────────────────────────────────────

    def export_structure(
        self,
        region: str,
        save_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export the full campaign hierarchy for a region.

        Returns a list of campaign dicts, each containing adGroups,
        which in turn contain productAds and keywords.
        """
        console.print(f"Exporting campaign structure for {region}...")

        campaigns = self._campaigns.list(region, state="ENABLED")
        ad_groups = self._ad_groups.list(region, state="ENABLED")
        keywords = self._keywords.list(region, state="ENABLED")
        product_ads = self._product_ads.list(region, state="ENABLED")

        # Index ad groups, keywords, and product ads by parent ID
        ag_by_campaign: dict[str, list[dict]] = {}
        for ag in ad_groups:
            ag_by_campaign.setdefault(ag["campaignId"], []).append(ag)

        kw_by_ad_group: dict[str, list[dict]] = {}
        for kw in keywords:
            kw_by_ad_group.setdefault(kw["adGroupId"], []).append(kw)

        pa_by_ad_group: dict[str, list[dict]] = {}
        for pa in product_ads:
            pa_by_ad_group.setdefault(pa["adGroupId"], []).append(pa)

        # Build structured data
        structured: list[dict[str, Any]] = []
        for campaign in campaigns:
            cid = campaign["campaignId"]
            campaign_obj: dict[str, Any] = {
                "campaignId": cid,
                "campaignName": campaign["name"],
                "targetingType": campaign.get("targetingType", "MANUAL"),
                "adGroups": [],
            }

            for ag in ag_by_campaign.get(cid, []):
                agid = ag["adGroupId"]
                ag_obj: dict[str, Any] = {
                    "adGroupId": agid,
                    "adGroupName": ag["name"],
                    "productAds": [
                        {"adId": pa["adId"], "asin": pa.get("asin", "")}
                        for pa in pa_by_ad_group.get(agid, [])
                    ],
                    "keywords": [
                        {
                            "keywordId": kw["keywordId"],
                            "keywordText": kw["keywordText"],
                            "matchType": kw["matchType"],
                        }
                        for kw in kw_by_ad_group.get(agid, [])
                    ],
                }
                campaign_obj["adGroups"].append(ag_obj)

            structured.append(campaign_obj)

        console.print(
            f"Exported {len(campaigns)} campaigns, {len(ad_groups)} ad groups, "
            f"{len(keywords)} keywords, {len(product_ads)} product ads"
        )

        if save_path:
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(structured, indent=2))
            console.print(f"Saved to {path}")

        return structured

    # ── Replicate ────────────────────────────────────────────────────

    def replicate(
        self,
        source_data: list[dict[str, Any]],
        target_region: str,
    ) -> list[dict[str, Any]]:
        """Replicate a full campaign structure into a target region.

        Creates campaigns, ad groups, product ads, and keywords (for MANUAL only).

        Returns a list of results for each campaign created.
        """
        today = date.today().strftime("%m-%d-%Y")
        results: list[dict[str, Any]] = []

        for campaign in source_data:
            campaign_name = campaign["campaignName"]
            targeting_type = campaign.get("targetingType", "MANUAL")

            # Detect targeting type from name if not in data
            if "automatic" in campaign_name.lower() or "auto" in campaign_name.lower():
                targeting_type = "AUTO"

            replicate_name = f"{campaign_name}-{today}-replicate"

            console.print(f"Creating campaign '{replicate_name}' in {target_region}...")

            # Create campaign
            campaign_req = CreateCampaignRequest(
                name=replicate_name,
                targetingType=targeting_type,
                state="ENABLED",
            )
            camp_resp = self._campaigns.create(target_region, campaign_req)
            created_campaign_id = _extract_id(camp_resp, "campaigns", "campaignId")

            if not created_campaign_id:
                console.print(f"  [red]Failed to create campaign '{replicate_name}'[/red]")
                results.append({"campaign": replicate_name, "status": "FAILED", "region": target_region})
                continue

            # Collect all ASINs and keywords across ad groups
            all_asins: list[str] = []
            all_keywords: list[dict] = []
            for ag in campaign.get("adGroups", []):
                for pa in ag.get("productAds", []):
                    asin = pa.get("asin", "")
                    if asin and asin not in all_asins:
                        all_asins.append(asin)
                all_keywords.extend(ag.get("keywords", []))

            # Create single ad group
            ag_req = CreateAdGroupRequest(
                campaignId=created_campaign_id,
                name=replicate_name,
                state="ENABLED",
            )
            ag_resp = self._ad_groups.create(target_region, ag_req)
            created_ag_id = _extract_id(ag_resp, "adGroups", "adGroupId")

            if not created_ag_id:
                console.print(f"  [red]Failed to create ad group for '{replicate_name}'[/red]")
                results.append({"campaign": replicate_name, "status": "PARTIAL", "region": target_region})
                continue

            # Create product ads for all ASINs
            for asin in all_asins:
                pa_req = CreateProductAdRequest(
                    campaignId=created_campaign_id,
                    adGroupId=created_ag_id,
                    asin=asin,
                    state="ENABLED",
                )
                self._product_ads.create(target_region, pa_req)

            # Only create keywords for MANUAL campaigns
            kw_count = 0
            if targeting_type == "MANUAL" and all_keywords:
                kw_requests = [
                    CreateKeywordRequest(
                        campaignId=created_campaign_id,
                        adGroupId=created_ag_id,
                        keywordText=kw["keywordText"],
                        matchType=kw["matchType"],
                        bid=0.30,
                    )
                    for kw in all_keywords
                ]
                self._keywords.create(target_region, kw_requests)
                kw_count = len(kw_requests)

            results.append({
                "campaign": replicate_name,
                "campaignId": created_campaign_id,
                "targetingType": targeting_type,
                "adGroupId": created_ag_id,
                "asins": len(all_asins),
                "keywords": kw_count,
                "region": target_region,
                "status": "SUCCESS",
            })
            console.print(
                f"  Created: {len(all_asins)} product ads, {kw_count} keywords"
            )

        return results

    # ── Keyword Sync ─────────────────────────────────────────────────

    def sync_keywords(
        self,
        source_region: str,
        target_region: str,
        campaign_name: str | None = None,
        bid: float = 0.30,
    ) -> list[dict[str, Any]]:
        """Sync keywords from source region to target region by matching campaign/ad group names.

        If campaign_name is provided, syncs only that campaign.
        Otherwise, syncs all matching campaigns.

        Returns a list of sync results per campaign.
        """
        console.print(f"Syncing keywords from {source_region} → {target_region}...")

        source_campaigns = self._campaigns.list(source_region, state="ENABLED")
        target_campaigns = self._campaigns.list(target_region, state="ENABLED")

        # Build target lookup by name
        target_camp_map: dict[str, dict] = {}
        for tc in target_campaigns:
            target_camp_map[tc["name"]] = tc

        if campaign_name:
            source_campaigns = [c for c in source_campaigns if c["name"] == campaign_name]
            if not source_campaigns:
                console.print(f"[red]Campaign '{campaign_name}' not found in {source_region}[/red]")
                return []

        results: list[dict[str, Any]] = []

        for source_camp in source_campaigns:
            camp_name = source_camp["name"]
            target_camp = target_camp_map.get(camp_name)

            if not target_camp:
                console.print(f"  Skipping '{camp_name}': no match in {target_region}")
                results.append({
                    "campaign": camp_name,
                    "status": "SKIPPED",
                    "reason": "No matching campaign in target",
                })
                continue

            # Get ad groups for both
            source_ags = self._ad_groups.list(
                source_region, campaign_id=source_camp["campaignId"], state="ENABLED"
            )
            target_ags = self._ad_groups.list(
                target_region, campaign_id=target_camp["campaignId"], state="ENABLED"
            )

            target_ag_map: dict[str, dict] = {}
            for tag in target_ags:
                target_ag_map[tag["name"]] = tag

            total_synced = 0

            for source_ag in source_ags:
                ag_name = source_ag["name"]
                target_ag = target_ag_map.get(ag_name)

                if not target_ag:
                    console.print(f"    Skipping ad group '{ag_name}': no match in target")
                    continue

                # Get source keywords
                source_kws = self._keywords.list(
                    source_region,
                    ad_group_id=source_ag["adGroupId"],
                    state="ENABLED",
                )

                if not source_kws:
                    continue

                # Create keywords in target
                kw_requests = [
                    CreateKeywordRequest(
                        campaignId=target_camp["campaignId"],
                        adGroupId=target_ag["adGroupId"],
                        keywordText=kw["keywordText"],
                        matchType=kw["matchType"],
                        bid=bid,
                    )
                    for kw in source_kws
                ]
                self._keywords.create(target_region, kw_requests)
                total_synced += len(kw_requests)
                console.print(
                    f"    Synced {len(kw_requests)} keywords from "
                    f"'{ag_name}' → {target_region}"
                )

            results.append({
                "campaign": camp_name,
                "region": target_region,
                "keywordsSynced": total_synced,
                "status": "SUCCESS" if total_synced > 0 else "NO_KEYWORDS",
            })

        return results


def _extract_id(
    response: dict[str, Any], entity_key: str, id_key: str
) -> str | None:
    """Extract a created entity ID from an Amazon Ads API response."""
    entities = response.get(entity_key, {})
    success = entities.get("success", [])
    if success and isinstance(success, list) and len(success) > 0:
        return str(success[0].get(id_key, ""))
    # Sometimes the response nests differently
    if isinstance(entities, list) and len(entities) > 0:
        return str(entities[0].get(id_key, ""))
    return None
