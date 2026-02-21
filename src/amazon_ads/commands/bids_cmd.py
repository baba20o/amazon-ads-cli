"""CLI commands for bid management, backup, and restore."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.keywords import UpdateKeywordRequest, UpdateProductTargetRequest
from amazon_ads.services.ad_groups import AdGroupService
from amazon_ads.services.campaigns import CampaignService
from amazon_ads.services.keywords import KeywordService
from amazon_ads.services.targeting import TargetingService
from amazon_ads.utils.backup import backup_keywords, load_backup
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="bids", help="Manage keyword bids, backup, and restore.")

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, KeywordService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, KeywordService(client)


@app.command("update")
def update_bids(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL' for all regions)")] = "US",
    target_bid: Annotated[float, typer.Option("--target-bid", "-b", help="New bid for all enabled keywords")] = ...,
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c", help="Limit to specific campaign")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would change without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Update all enabled keyword bids to a target value."""
    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]
    client, service = _build_client(verbose)

    try:
        for reg in regions:
            console.print(f"Fetching enabled keywords for {reg}...")
            keywords = service.list(reg, campaign_id=campaign_id, state="ENABLED")

            if not keywords:
                console.print(f"  No enabled keywords found in {reg}")
                continue

            updates = [
                UpdateKeywordRequest(keywordId=kw["keywordId"], bid=target_bid)
                for kw in keywords
            ]

            console.print(f"  {len(updates)} keywords to update in {reg} → ${target_bid}")

            if dry_run:
                console.print(f"  [yellow]DRY RUN:[/yellow] Would update {len(updates)} keywords in {reg}")
                sample = [u.model_dump(by_alias=True, exclude_none=True) for u in updates[:5]]
                print_output(sample, output, title=f"Sample Updates ({reg}) [DRY RUN]")
                continue

            results = service.update(reg, updates)
            print_output(results, output, title=f"Bids Updated ({reg})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("backup")
def backup_bids(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL' for all regions)")] = "ALL",
    backup_dir: Annotated[str, typer.Option("--dir", "-d", help="Backup directory")] = "./backups",
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Backup all enabled keyword bids to CSV and JSON files."""
    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]
    client, service = _build_client(verbose)

    try:
        results = []
        for reg in regions:
            console.print(f"Backing up keywords for {reg}...")
            keywords = service.list(reg, state="ENABLED")

            if not keywords:
                console.print(f"  No enabled keywords in {reg}, skipping")
                continue

            paths = backup_keywords(keywords, reg, backup_dir)
            result = {
                "region": reg,
                "keywords": len(keywords),
                "csv": paths["csv"],
                "json": paths["json"],
            }
            results.append(result)
            console.print(f"  {len(keywords)} keywords → {paths['json']}")

        print_output(results, output, title="Backup Complete")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("restore")
def restore_bids(
    file: Annotated[str, typer.Option("--file", "-f", help="Path to backup file (CSV or JSON)")] = ...,
    region: Annotated[str, typer.Option("--region", "-r", help="Target region")] = ...,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would change without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Restore keyword bids from a backup file."""
    client, service = _build_client(verbose)

    try:
        console.print(f"Loading backup from {file}...")
        backup_data = load_backup(file)

        updates = []
        for kw in backup_data:
            update = UpdateKeywordRequest(
                keywordId=str(kw["keywordId"]),
                bid=float(kw.get("bid", 0)),
                state=kw.get("state"),
            )
            updates.append(update)

        console.print(f"  {len(updates)} keywords to restore in {region}")

        if dry_run:
            console.print(f"  [yellow]DRY RUN:[/yellow] Would restore {len(updates)} keywords")
            sample = [u.model_dump(by_alias=True, exclude_none=True) for u in updates[:5]]
            print_output(sample, output, title=f"Sample Restore ({region}) [DRY RUN]")
            return

        results = service.update(region, updates)
        print_output(results, output, title=f"Bids Restored ({region})")
    except (RuntimeError, FileNotFoundError, ValueError) as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


_TARGET_TYPE_LABELS = {
    "QUERY_HIGH_REL_MATCHES": "Close Match",
    "QUERY_BROAD_REL_MATCHES": "Loose Match",
    "ASIN_SUBSTITUTE_RELATED": "Substitutes",
    "ASIN_ACCESSORY_RELATED": "Complements",
}


@app.command("audit")
def audit_bids(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL' for all regions)")] = "ALL",
    threshold: Annotated[float, typer.Option("--threshold", "-t", help="Min absolute bid diff to flag")] = 0.0,
    fix: Annotated[bool, typer.Option("--fix", help="Reset overrides back to ad group defaults")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Preview fix without applying")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Audit auto-targeting bid overrides on AUTO campaigns.

    Compares targeting-group bids (Close Match, Loose Match, etc.) against
    the ad group default bid.  Use --fix to reset overrides.
    """
    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]
    client, _ = _build_client(verbose)
    campaign_service = CampaignService(client)
    ad_group_service = AdGroupService(client)
    targeting_service = TargetingService(client)

    try:
        all_overrides: list[dict] = []

        for reg in regions:
            console.print(f"Auditing {reg}...")

            campaigns = campaign_service.list(reg, state="ENABLED")
            auto_camps = {
                str(c["campaignId"]): c["name"]
                for c in campaigns
                if c.get("targetingType") == "AUTO"
            }
            if not auto_camps:
                console.print(f"  No AUTO campaigns in {reg}")
                continue

            ad_groups = ad_group_service.list(reg, state="ENABLED")
            ag_bids: dict[str, float] = {}
            for ag in ad_groups:
                cid = str(ag.get("campaignId", ""))
                if cid in auto_camps:
                    ag_bids[cid] = ag.get("defaultBid", 0) or 0

            targets = targeting_service.list(reg, state="ENABLED")

            region_count = 0
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
                if abs(diff) <= threshold:
                    continue

                expr_type = (t.get("expression") or [{}])[0].get("type", "?")
                all_overrides.append({
                    "region": reg,
                    "campaign": auto_camps[cid],
                    "targetType": _TARGET_TYPE_LABELS.get(expr_type, expr_type),
                    "currentBid": round(target_bid, 2),
                    "defaultBid": round(ag_default, 2),
                    "diff": diff,
                    "diffPct": f"{diff / ag_default * 100:+.0f}%",
                    "targetId": t.get("targetId", ""),
                })
                region_count += 1

            console.print(f"  {reg}: {region_count} overrides found")

        if not all_overrides:
            console.print("[green]No auto-targeting bid overrides found.[/green]")
            print_output([], output, title="Bid Audit")
            return

        above = sum(1 for o in all_overrides if o["diff"] > 0)
        below = sum(1 for o in all_overrides if o["diff"] < 0)
        console.print(
            f"\nTotal: {len(all_overrides)} overrides "
            f"({above} above default, {below} below default)"
        )

        columns = [
            "region", "campaign", "targetType",
            "currentBid", "defaultBid", "diff", "diffPct",
        ]
        if not fix:
            print_output(all_overrides, output, columns=columns, title="Bid Audit")
            return

        # --fix mode: reset all overrides to ad group defaults
        if dry_run:
            console.print(
                f"[yellow]DRY RUN:[/yellow] Would reset "
                f"{len(all_overrides)} target bids"
            )
            print_output(all_overrides, output, columns=columns, title="Bid Audit [DRY RUN]")
            return

        # Group fixes by region and apply
        from collections import defaultdict
        by_region: dict[str, list[dict]] = defaultdict(list)
        for o in all_overrides:
            by_region[o["region"]].append(o)

        for reg, overrides in by_region.items():
            updates = [
                UpdateProductTargetRequest(
                    targetId=o["targetId"], bid=o["defaultBid"],
                )
                for o in overrides
            ]
            console.print(f"Resetting {len(updates)} targets in {reg}...")
            targeting_service.update(reg, updates)

        console.print(f"[green]Reset {len(all_overrides)} target bids.[/green]")
        print_output(all_overrides, output, columns=columns, title="Bid Audit — Fixed")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
