"""CLI commands for ad group management."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.ad_groups import CreateAdGroupRequest, UpdateAdGroupRequest
from amazon_ads.services.ad_groups import AdGroupService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="ad-groups", help="Manage Sponsored Products ad groups.")


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, AdGroupService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, AdGroupService(client)


@app.command("list")
def list_ad_groups(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c", help="Filter by campaign ID")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Filter by name (broad match)")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List ad groups for a region."""
    client, service = _build_client(verbose)
    try:
        ad_groups = service.list(region, campaign_id=campaign_id, state=state, name=name)
        console.print(f"[dim]Found {len(ad_groups)} ad groups[/dim]")
        # Flatten servingStatus if present
        for ag in ad_groups:
            ext = ag.get("extendedData", {})
            ag["servingStatus"] = ext.get("servingStatus", ag.get("servingStatus", ""))
        columns = ["adGroupId", "name", "campaignId", "state", "defaultBid", "servingStatus"]
        print_output(ad_groups, output, columns=columns, title=f"Ad Groups ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create")
def create_ad_group(
    campaign_id: Annotated[str, typer.Option("--campaign-id", "-c", help="Parent campaign ID")] = ...,
    name: Annotated[str, typer.Option("--name", "-n", help="Ad group name")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    default_bid: Annotated[float, typer.Option("--default-bid", "-b", help="Default bid")] = 0.45,
    state: Annotated[str, typer.Option("--state")] = "ENABLED",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create a new ad group."""
    client, service = _build_client(verbose)
    try:
        request = CreateAdGroupRequest(
            campaignId=campaign_id,
            name=name,
            state=state.upper(),
            defaultBid=default_bid,
        )
        if dry_run:
            console.print("[yellow]DRY RUN:[/yellow] Would create ad group:")
            print_output(request.model_dump(by_alias=True, exclude_none=True), output, title="Ad Group [DRY RUN]")
            return
        result = service.create(region, request)
        print_output(result, output, title="Ad Group Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("update")
def update_ad_group(
    ad_group_id: Annotated[str, typer.Option("--ad-group-id", "-a", help="Ad group ID to update")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    state: Annotated[str | None, typer.Option("--state")] = None,
    default_bid: Annotated[float | None, typer.Option("--default-bid", "-b")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Update an ad group (state, bid, name)."""
    client, service = _build_client(verbose)
    try:
        request = UpdateAdGroupRequest(
            adGroupId=ad_group_id,
            state=state.upper() if state else None,
            defaultBid=default_bid,
            name=name,
        )
        if dry_run:
            console.print("[yellow]DRY RUN:[/yellow] Would update ad group:")
            print_output(request.model_dump(by_alias=True, exclude_none=True), output, title="Ad Group Update [DRY RUN]")
            return
        result = service.update(region, request)
        print_output(result, output, title="Ad Group Updated")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete")
def delete_ad_groups(
    ad_group_ids: Annotated[list[str], typer.Option("--ad-group-id", "-a", help="Ad group ID(s) to delete")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be deleted without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete ad groups by ID."""
    client, service = _build_client(verbose)
    try:
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(ad_group_ids)} ad group(s): {ad_group_ids}")
            return
        result = service.delete(region, ad_group_ids)
        print_output(result, output, title="Ad Groups Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
