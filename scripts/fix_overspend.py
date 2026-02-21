"""Fix only above-default (overspend) auto-targeting overrides in specified regions."""

import json
import sys

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.keywords import UpdateProductTargetRequest
from amazon_ads.services.ad_groups import AdGroupService
from amazon_ads.services.campaigns import CampaignService
from amazon_ads.services.targeting import TargetingService

TARGET_TYPE_LABELS = {
    "QUERY_HIGH_REL_MATCHES": "Close Match",
    "QUERY_BROAD_REL_MATCHES": "Loose Match",
    "ASIN_SUBSTITUTE_RELATED": "Substitutes",
    "ASIN_ACCESSORY_RELATED": "Complements",
}

REGIONS = sys.argv[1:] if len(sys.argv) > 1 else ["US", "DE", "IT", "CA"]

config = get_config()
auth = AuthManager(config)
client = AmazonAdsClient(config, auth)
campaign_service = CampaignService(client)
ad_group_service = AdGroupService(client)
targeting_service = TargetingService(client)

total_fixed = 0

try:
    for reg in REGIONS:
        print(f"\n{'='*60}")
        print(f"Auditing {reg}...")

        campaigns = campaign_service.list(reg, state="ENABLED")
        auto_camps = {
            str(c["campaignId"]): c["name"]
            for c in campaigns
            if c.get("targetingType") == "AUTO"
        }
        if not auto_camps:
            print(f"  No AUTO campaigns in {reg}")
            continue

        ad_groups = ad_group_service.list(reg, state="ENABLED")
        ag_bids = {}
        for ag in ad_groups:
            cid = str(ag.get("campaignId", ""))
            if cid in auto_camps:
                ag_bids[cid] = ag.get("defaultBid", 0) or 0

        targets = targeting_service.list(reg, state="ENABLED")

        overspend = []
        for t in targets:
            cid = str(t.get("campaignId", ""))
            if cid not in auto_camps:
                continue
            target_bid = t.get("bid")
            if target_bid is None:
                continue
            ag_default = ag_bids.get(cid, 0)
            if ag_default == 0:
                continue
            diff = round(target_bid - ag_default, 2)
            if diff <= 0:
                continue  # skip underbids and exact matches
            expr_type = (t.get("expression") or [{}])[0].get("type", "?")
            overspend.append({
                "targetId": t.get("targetId", ""),
                "campaign": auto_camps[cid],
                "targetType": TARGET_TYPE_LABELS.get(expr_type, expr_type),
                "currentBid": round(target_bid, 2),
                "defaultBid": round(ag_default, 2),
                "diff": diff,
            })

        if not overspend:
            print(f"  No overspend overrides in {reg}")
            continue

        print(f"  Found {len(overspend)} overspend overrides in {reg}")
        for o in overspend:
            print(f"    {o['campaign'][:45]} | {o['targetType']:12} | ${o['currentBid']} → ${o['defaultBid']} (save ${o['diff']})")

        updates = [
            UpdateProductTargetRequest(targetId=o["targetId"], bid=o["defaultBid"])
            for o in overspend
        ]
        print(f"  Resetting {len(updates)} targets in {reg}...")
        targeting_service.update(reg, updates)
        print(f"  ✓ {len(updates)} targets fixed in {reg}")
        total_fixed += len(updates)

    print(f"\n{'='*60}")
    print(f"DONE: Fixed {total_fixed} overspend overrides across {REGIONS}")
finally:
    client.close()
