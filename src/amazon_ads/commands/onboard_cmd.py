"""CLI commands for product onboarding."""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.services.onboarding import OnboardingService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="onboard", help="Onboard new products with AUTO+MANUAL campaign pairs.")

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, OnboardingService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, OnboardingService(client)


@app.command("product")
def onboard_product(
    title: Annotated[str, typer.Option("--title", "-t", help="Product title for campaign naming")] = ...,
    asin: Annotated[list[str], typer.Option("--asin", "-a", help="ASIN(s) to advertise")] = ...,
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL' for all regions)")] = "ALL",
    keywords_file: Annotated[str | None, typer.Option("--keywords-file", "-k", help="JSON file with keywords")] = None,
    keywords_stdin: Annotated[bool, typer.Option("--keywords-stdin", help="Read keywords JSON from stdin")] = False,
    budget: Annotated[float, typer.Option("--budget", "-b", help="Daily budget per campaign")] = 100.0,
    default_bid: Annotated[float, typer.Option("--default-bid", help="Default ad group bid")] = 0.45,
    keyword_bid: Annotated[float, typer.Option("--keyword-bid", help="Bid for keywords")] = 0.30,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be created")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Onboard a product with AUTO + MANUAL campaign pairs across regions.

    Creates two campaigns per region:
    - {title}-AUTOMATIC-PRODUCTION (AUTO targeting)
    - {title}-MANUAL-PRODUCTION (MANUAL targeting + keywords)

    Each campaign gets an ad group with the specified ASINs as product ads.
    Keywords are only added to the MANUAL campaign.

    Example:

        amazon-ads onboard product --title "My Book" --asin B0ABC123 --asin B0DEF456

        amazon-ads onboard product --title "My Book" --asin B0ABC123 --keywords-file kw.json
    """
    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]

    # Load keywords if provided
    keywords: list[dict[str, str]] | None = None
    if keywords_stdin:
        keywords = json.load(sys.stdin)
    elif keywords_file:
        with open(keywords_file) as f:
            keywords = json.load(f)

    if dry_run:
        console.print(f"[yellow]DRY RUN:[/yellow] Would onboard '{title}' across {len(regions)} region(s)")
        console.print(f"  ASINs: {asin}")
        console.print(f"  Budget: ${budget}/day")
        console.print(f"  Keywords: {len(keywords) if keywords else 0}")
        console.print(f"  Regions: {', '.join(regions)}")
        console.print("\nCampaigns that would be created per region:")
        console.print(f"  1. {title}-AUTOMATIC-PRODUCTION (AUTO)")
        console.print(f"  2. {title}-MANUAL-PRODUCTION (MANUAL)")
        return

    client, service = _build_client(verbose)

    try:
        results = service.onboard_product(
            title=title,
            asins=asin,
            regions=regions,
            keywords=keywords,
            budget=budget,
            default_bid=default_bid,
            keyword_bid=keyword_bid,
        )

        # Flatten results for display
        flat_results = []
        for r in results:
            for camp_type in ("auto", "manual"):
                camp = r.get(camp_type, {})
                if camp:
                    flat_results.append({
                        "region": r["region"],
                        "campaign": camp.get("campaignName", ""),
                        "type": camp.get("targetingType", camp_type.upper()),
                        "campaignId": camp.get("campaignId", ""),
                        "asins": camp.get("asins", 0),
                        "keywords": camp.get("keywords", 0),
                        "status": camp.get("status", r.get("status", "")),
                    })

        columns = ["region", "campaign", "type", "campaignId", "asins", "keywords", "status"]
        print_output(flat_results, output, columns=columns, title="Onboarding Results")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
