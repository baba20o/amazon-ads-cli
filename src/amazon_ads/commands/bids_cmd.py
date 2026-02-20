"""CLI commands for bid management, backup, and restore."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.keywords import UpdateKeywordRequest
from amazon_ads.services.keywords import KeywordService
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
