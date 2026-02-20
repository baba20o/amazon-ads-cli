"""CLI commands for campaign sync and replication."""

from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.services.sync import SyncService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="sync", help="Sync and replicate campaign structures across regions.")

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, SyncService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, SyncService(client)


@app.command("export")
def export_structure(
    region: Annotated[str, typer.Option("--region", "-r", help="Region to export")] = "US",
    save: Annotated[str | None, typer.Option("--save", "-s", help="Save to JSON file path")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Export full campaign structure (campaigns, ad groups, keywords, product ads).

    Use --save to write the structure to a JSON file for later replication.
    """
    client, service = _build_client(verbose)

    try:
        data = service.export_structure(region.upper(), save_path=save)

        summary = []
        for camp in data:
            ag_count = len(camp.get("adGroups", []))
            kw_count = sum(len(ag.get("keywords", [])) for ag in camp.get("adGroups", []))
            pa_count = sum(len(ag.get("productAds", [])) for ag in camp.get("adGroups", []))
            summary.append({
                "campaignName": camp["campaignName"],
                "targetingType": camp.get("targetingType", ""),
                "adGroups": ag_count,
                "keywords": kw_count,
                "productAds": pa_count,
            })

        columns = ["campaignName", "targetingType", "adGroups", "keywords", "productAds"]
        print_output(summary, output, columns=columns, title=f"Campaign Structure ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("replicate")
def replicate(
    source_region: Annotated[str, typer.Option("--source", help="Source region to replicate from")] = "US",
    target_region: Annotated[str | None, typer.Option("--target", "-t", help="Target region (or 'ALL' for all except source)")] = None,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f", help="Load structure from JSON file instead of live API")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be created without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Replicate campaign structure from source to target region(s).

    Reads the full structure from source (or a saved JSON file), then
    creates campaigns, ad groups, product ads, and keywords in target.
    """
    if not target_region:
        console.print("[red]Provide --target region (e.g. GB, DE, or ALL)[/red]")
        raise typer.Exit(1)

    client, service = _build_client(verbose)

    try:
        # Load source data
        if from_file:
            console.print(f"Loading structure from {from_file}...")
            with open(from_file) as f:
                source_data = json.load(f)
        else:
            source_data = service.export_structure(source_region.upper())

        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would replicate {len(source_data)} campaigns")
            for camp in source_data:
                ag_count = len(camp.get("adGroups", []))
                kw_count = sum(len(ag.get("keywords", [])) for ag in camp.get("adGroups", []))
                console.print(f"  {camp['campaignName']} ({ag_count} ad groups, {kw_count} keywords)")
            return

        # Determine target regions
        if target_region.upper() == "ALL":
            targets = [r for r in ALL_REGIONS if r != source_region.upper()]
        else:
            targets = [target_region.upper()]

        all_results = []
        for target in targets:
            results = service.replicate(source_data, target)
            all_results.extend(results)

        columns = ["campaign", "region", "targetingType", "asins", "keywords", "status"]
        print_output(all_results, output, columns=columns, title="Replication Results")
    except (RuntimeError, FileNotFoundError) as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("keywords")
def sync_keywords(
    source: Annotated[str, typer.Option("--source", help="Source region")] = "US",
    target: Annotated[str | None, typer.Option("--target", "-t", help="Target region (or 'ALL')")] = None,
    campaign_name: Annotated[str | None, typer.Option("--campaign", "-c", help="Sync only this campaign")] = None,
    bid: Annotated[float, typer.Option("--bid", "-b", help="Bid for synced keywords")] = 0.30,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be synced")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Sync keywords from source region to target by matching campaign/ad group names.

    Matches campaigns and ad groups by exact name, then copies keywords
    from source to target with the specified bid.
    """
    if not target:
        console.print("[red]Provide --target region (e.g. GB, DE, or ALL)[/red]")
        raise typer.Exit(1)

    client, service = _build_client(verbose)

    try:
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would sync keywords from {source} → {target}")
            console.print("Use without --dry-run to execute.")
            return

        if target.upper() == "ALL":
            targets = [r for r in ALL_REGIONS if r != source.upper()]
        else:
            targets = [target.upper()]

        all_results = []
        for t in targets:
            results = service.sync_keywords(
                source.upper(), t, campaign_name=campaign_name, bid=bid
            )
            all_results.extend(results)

        columns = ["campaign", "region", "keywordsSynced", "status"]
        print_output(all_results, output, columns=columns, title="Keyword Sync Results")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
