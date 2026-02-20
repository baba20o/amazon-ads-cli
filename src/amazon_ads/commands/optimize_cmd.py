"""CLI commands for bid optimization."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.services.optimization import OptimizationService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="optimize", help="Bid optimization using Amazon suggested bids.")

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, OptimizationService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, OptimizationService(client)


@app.command("run")
def optimize_run(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL')")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c", help="Limit to specific campaign")] = None,
    offset: Annotated[float, typer.Option("--offset", help="Bid offset above suggested (default $0.02)")] = 0.02,
    apply: Annotated[bool, typer.Option("--apply/--no-apply", help="Actually apply bid reductions")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show comparison without applying")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Optimize keyword bids by comparing against Amazon suggested bids.

    Fetches all enabled keywords, gets suggested bids from Amazon, and
    identifies keywords where the current bid exceeds suggested + offset.

    Use --apply to actually reduce overbid keywords. Without --apply or
    with --dry-run, only shows the comparison.
    """
    if dry_run:
        apply = False

    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]
    client, service = _build_client(verbose)

    try:
        all_comparisons = []
        for reg in regions:
            comparisons = service.optimize(
                reg, campaign_id=campaign_id, offset=offset, apply=apply
            )
            all_comparisons.extend(comparisons)

        if not all_comparisons:
            console.print("No optimization opportunities found.")
            return

        to_reduce = [c for c in all_comparisons if c["action"] == "REDUCE"]
        columns = [
            "keywordText", "matchType", "currentBid",
            "suggestedBidLow", "suggestedBid", "suggestedBidHigh",
            "newBid", "action", "keywordId",
        ]

        if dry_run or not apply:
            print_output(all_comparisons, output, columns=columns, title="Bid Comparison")
            console.print(
                f"\n[dim]{len(to_reduce)} keywords would be reduced. "
                f"Use --apply to execute.[/dim]"
            )
        else:
            print_output(to_reduce, output, columns=columns, title="Bids Reduced")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("compare")
def optimize_compare(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    offset: Annotated[float, typer.Option("--offset")] = 0.02,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Compare current bids against suggested bids (read-only)."""
    client, service = _build_client(verbose)

    try:
        comparisons = service.optimize(
            region.upper(), campaign_id=campaign_id, offset=offset, apply=False
        )

        if not comparisons:
            console.print("No keywords with suggested bids found.")
            return

        columns = [
            "keywordText", "matchType", "currentBid",
            "suggestedBidLow", "suggestedBid", "suggestedBidHigh",
            "newBid", "action",
        ]
        print_output(comparisons, output, columns=columns, title=f"Bid Comparison ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
