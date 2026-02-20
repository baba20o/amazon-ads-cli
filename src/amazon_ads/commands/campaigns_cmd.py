"""CLI commands for campaign management."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.campaigns import (
    CampaignBudget,
    CreateCampaignRequest,
    DynamicBidding,
    PlacementBid,
    UpdateCampaignRequest,
)
from amazon_ads.services.campaigns import CampaignService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="campaigns", help="Manage Sponsored Products campaigns.")


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, CampaignService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, CampaignService(client)


@app.command("list")
def list_campaigns(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (US, GB, DE, etc.)")] = "US",
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state (ENABLED, PAUSED, ARCHIVED)")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="Filter by name (broad match)")] = None,
    portfolio_id: Annotated[str | None, typer.Option("--portfolio-id", "-p", help="Filter by portfolio ID")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output format")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List campaigns for a region."""
    client, service = _build_client(verbose)
    try:
        campaigns = service.list(region, state=state, name=name, portfolio_id=portfolio_id)
        console.print(f"[dim]Found {len(campaigns)} campaigns[/dim]")
        columns = [
            "campaignId", "name", "state", "targetingType",
            "budget", "dynamicBidding", "deliveryStatus",
        ]
        # Flatten deliveryStatus from extendedData if present
        for c in campaigns:
            ext = c.get("extendedData", {})
            c["deliveryStatus"] = ext.get("servingStatus", c.get("servingStatus", ""))
        print_output(campaigns, output, columns=columns, title=f"Campaigns ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create")
def create_campaign(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    name: Annotated[str, typer.Option("--name", "-n", help="Campaign name")] = ...,
    targeting_type: Annotated[str, typer.Option("--targeting-type", "-t", help="AUTO or MANUAL")] = "AUTO",
    budget: Annotated[float, typer.Option("--budget", "-b", help="Daily budget")] = 100.0,
    bid_strategy: Annotated[str, typer.Option("--bid-strategy", help="LEGACY_FOR_SALES, AUTO_FOR_SALES, MANUAL")] = "LEGACY_FOR_SALES",
    state: Annotated[str, typer.Option("--state", help="Initial state")] = "ENABLED",
    end_date: Annotated[str | None, typer.Option("--end-date", help="Campaign end date (YYYYMMDD)")] = None,
    portfolio_id: Annotated[str | None, typer.Option("--portfolio-id", "-p", help="Portfolio ID")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create a new campaign."""
    client, service = _build_client(verbose)
    try:
        request = CreateCampaignRequest(
            name=name,
            targetingType=targeting_type.upper(),
            state=state.upper(),
            budget=CampaignBudget(budget=budget),
            dynamicBidding=DynamicBidding(strategy=bid_strategy),
            endDate=end_date,
            portfolioId=portfolio_id,
        )
        if dry_run:
            console.print("[yellow]DRY RUN:[/yellow] Would create campaign:")
            print_output(request.model_dump(by_alias=True, exclude_none=True), output, title="Campaign [DRY RUN]")
            return
        result = service.create(region, request)
        print_output(result, output, title="Campaign Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("update")
def update_campaign(
    campaign_id: Annotated[str, typer.Option("--campaign-id", "-c", help="Campaign ID to update")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    state: Annotated[str | None, typer.Option("--state", help="New state")] = None,
    name: Annotated[str | None, typer.Option("--name", "-n", help="New campaign name")] = None,
    budget: Annotated[float | None, typer.Option("--budget", "-b", help="New daily budget")] = None,
    bid_strategy: Annotated[str | None, typer.Option("--bid-strategy", help="LEGACY_FOR_SALES, AUTO_FOR_SALES, MANUAL")] = None,
    end_date: Annotated[str | None, typer.Option("--end-date", help="Campaign end date (YYYYMMDD)")] = None,
    portfolio_id: Annotated[str | None, typer.Option("--portfolio-id", "-p", help="Move to portfolio")] = None,
    top_placement: Annotated[float | None, typer.Option("--top-placement", help="Top-of-search bid percentage")] = None,
    product_page_placement: Annotated[float | None, typer.Option("--product-page-placement", help="Product page bid percentage")] = None,
    rest_of_search_placement: Annotated[float | None, typer.Option("--rest-of-search-placement", help="Rest of search bid percentage")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Update a campaign (state, budget, name, placement bids, end date, portfolio)."""
    client, service = _build_client(verbose)
    try:
        # Build placement bidding if any percentages provided
        dynamic_bidding = None
        placements = []
        if top_placement is not None:
            placements.append(PlacementBid(placement="PLACEMENT_TOP", percentage=top_placement))
        if product_page_placement is not None:
            placements.append(PlacementBid(placement="PLACEMENT_PRODUCT_PAGE", percentage=product_page_placement))
        if rest_of_search_placement is not None:
            placements.append(PlacementBid(placement="PLACEMENT_REST_OF_SEARCH", percentage=rest_of_search_placement))
        if placements or bid_strategy:
            dynamic_bidding = DynamicBidding(
                strategy=bid_strategy or "LEGACY_FOR_SALES",
                placementBidding=placements if placements else None,
            )

        request = UpdateCampaignRequest(
            campaignId=campaign_id,
            state=state.upper() if state else None,
            name=name,
            budget=CampaignBudget(budget=budget) if budget else None,
            dynamicBidding=dynamic_bidding,
            endDate=end_date,
            portfolioId=portfolio_id,
        )
        if dry_run:
            console.print("[yellow]DRY RUN:[/yellow] Would update campaign:")
            print_output(request.model_dump(by_alias=True, exclude_none=True), output, title="Campaign Update [DRY RUN]")
            return
        result = service.update(region, request)
        print_output(result, output, title="Campaign Updated")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete")
def delete_campaigns(
    campaign_ids: Annotated[list[str], typer.Option("--campaign-id", "-c", help="Campaign ID(s) to delete")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be deleted without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete campaigns by ID."""
    client, service = _build_client(verbose)
    try:
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(campaign_ids)} campaign(s): {campaign_ids}")
            return
        result = service.delete(region, campaign_ids)
        print_output(result, output, title="Campaigns Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
