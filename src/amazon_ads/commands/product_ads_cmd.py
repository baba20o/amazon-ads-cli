"""CLI commands for product ad management."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.product_ads import CreateProductAdRequest
from amazon_ads.services.product_ads import ProductAdService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="product-ads", help="Manage Sponsored Products product ads.")


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, ProductAdService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, ProductAdService(client)


@app.command("list")
def list_product_ads(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List product ads for a region."""
    client, service = _build_client(verbose)
    try:
        ads = service.list(region, campaign_id=campaign_id, ad_group_id=ad_group_id, state=state)
        columns = ["adId", "campaignId", "adGroupId", "asin", "state"]
        print_output(ads, output, columns=columns, title=f"Product Ads ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create")
def create_product_ad(
    asin: Annotated[str, typer.Option("--asin", help="Product ASIN")] = ...,
    campaign_id: Annotated[str, typer.Option("--campaign-id", "-c")] = ...,
    ad_group_id: Annotated[str, typer.Option("--ad-group-id", "-a")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    state: Annotated[str, typer.Option("--state")] = "ENABLED",
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create a new product ad."""
    client, service = _build_client(verbose)
    try:
        request = CreateProductAdRequest(
            campaignId=campaign_id,
            adGroupId=ad_group_id,
            asin=asin,
            state=state.upper(),
        )
        if dry_run:
            console.print("[yellow]DRY RUN:[/yellow] Would create product ad:")
            print_output(request.model_dump(by_alias=True, exclude_none=True), output, title="Product Ad [DRY RUN]")
            return
        result = service.create(region, request)
        print_output(result, output, title="Product Ad Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
