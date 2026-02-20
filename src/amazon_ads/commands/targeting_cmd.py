"""CLI commands for product targeting management."""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.keywords import (
    CreateNegativeTargetRequest,
    CreateProductTargetRequest,
    UpdateProductTargetRequest,
)
from amazon_ads.services.targeting import TargetingService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="targets", help="Manage Sponsored Products product/category targeting.")


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, TargetingService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, TargetingService(client)


# ── Positive targets ──────────────────────────────────────────────


@app.command("list")
def list_targets(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List product targeting clauses."""
    client, service = _build_client(verbose)
    try:
        targets = service.list(
            region, campaign_id=campaign_id, ad_group_id=ad_group_id, state=state
        )
        console.print(f"[dim]Found {len(targets)} targets[/dim]")
        columns = [
            "targetId", "expression", "expressionType",
            "campaignId", "adGroupId", "state", "bid",
        ]
        print_output(targets, output, columns=columns, title=f"Targets ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create")
def create_target(
    campaign_id: Annotated[str, typer.Option("--campaign-id", "-c", help="Campaign ID")] = ...,
    ad_group_id: Annotated[str, typer.Option("--ad-group-id", "-a", help="Ad group ID")] = ...,
    asin: Annotated[str | None, typer.Option("--asin", help="Target a specific ASIN")] = None,
    category: Annotated[str | None, typer.Option("--category", help="Target a category ID")] = None,
    bid: Annotated[float, typer.Option("--bid", "-b")] = 0.30,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create product targeting clauses.

    Single ASIN: --campaign-id X --ad-group-id Y --asin B00EXAMPLE --bid 0.50

    Single category: --campaign-id X --ad-group-id Y --category 1234567 --bid 0.40

    Bulk: --from-file targets.json
    JSON: [{"campaignId":"X","adGroupId":"Y","expression":[{"type":"asinSameAs","value":"B00EXAMPLE"}],"bid":0.50}]
    """
    client, service = _build_client(verbose)
    try:
        targets: list[CreateProductTargetRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            targets = [CreateProductTargetRequest(**t) for t in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            targets = [CreateProductTargetRequest(**t) for t in data]
        elif asin:
            targets = [
                CreateProductTargetRequest(
                    campaignId=campaign_id,
                    adGroupId=ad_group_id,
                    expression=[{"type": "asinSameAs", "value": asin}],
                    bid=bid,
                )
            ]
        elif category:
            targets = [
                CreateProductTargetRequest(
                    campaignId=campaign_id,
                    adGroupId=ad_group_id,
                    expression=[{"type": "asinCategorySameAs", "value": category}],
                    bid=bid,
                )
            ]
        else:
            console.print(
                "[red]Provide --asin or --category with --campaign-id and --ad-group-id, "
                "or use --from-file/--from-stdin[/red]"
            )
            raise typer.Exit(1)

        console.print(f"Creating {len(targets)} target(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would create {len(targets)} target(s)")
            sample = [t.model_dump(by_alias=True, exclude_none=True) for t in targets[:5]]
            print_output(sample, output, title="Sample Targets [DRY RUN]")
            return
        results = service.create(region, targets)
        print_output(results, output, title="Targets Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("update")
def update_target(
    target_id: Annotated[str | None, typer.Option("--target-id", "-t", help="Target ID (single mode)")] = None,
    bid: Annotated[float | None, typer.Option("--bid", "-b", help="New bid")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s", help="New state (ENABLED, PAUSED, ARCHIVED)")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin", help="Read updates from stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f", help="Read updates from JSON file")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Update target bid and/or state.

    Single: --target-id X --bid 0.40

    Bulk: --from-file updates.json
    JSON: [{"targetId": "X", "bid": 0.40}, {"targetId": "Y", "state": "PAUSED"}]
    """
    client, service = _build_client(verbose)
    try:
        targets: list[UpdateProductTargetRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            targets = [UpdateProductTargetRequest(**t) for t in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            targets = [UpdateProductTargetRequest(**t) for t in data]
        elif target_id:
            targets = [
                UpdateProductTargetRequest(
                    targetId=target_id,
                    bid=bid,
                    state=state.upper() if state else None,
                )
            ]
        else:
            console.print("[red]Provide --target-id or use --from-file/--from-stdin[/red]")
            raise typer.Exit(1)

        console.print(f"Updating {len(targets)} target(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would update {len(targets)} target(s)")
            sample = [t.model_dump(by_alias=True, exclude_none=True) for t in targets[:5]]
            print_output(sample, output, title="Sample Target Updates [DRY RUN]")
            return
        results = service.update(region, targets)
        print_output(results, output, title="Targets Updated")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete")
def delete_targets(
    target_ids: Annotated[list[str] | None, typer.Option("--target-id", "-t", help="Target ID(s)")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete product targeting clauses by ID."""
    client, service = _build_client(verbose)
    try:
        ids: list[str] = []
        if from_file:
            with open(from_file) as f:
                content = f.read().strip()
            try:
                ids = json.loads(content)
            except json.JSONDecodeError:
                ids = [line.strip() for line in content.splitlines() if line.strip()]
        elif target_ids:
            ids = target_ids
        else:
            console.print("[red]Provide --target-id or --from-file[/red]")
            raise typer.Exit(1)

        console.print(f"Deleting {len(ids)} target(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(ids)} target(s)")
            return
        results = service.delete(region, ids)
        print_output(results, output, title="Targets Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


# ── Negative targets ──────────────────────────────────────────────


@app.command("list-negative")
def list_negative_targets(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List negative targeting clauses."""
    client, service = _build_client(verbose)
    try:
        targets = service.list_negative(
            region, campaign_id=campaign_id, ad_group_id=ad_group_id, state=state
        )
        console.print(f"[dim]Found {len(targets)} negative targets[/dim]")
        columns = [
            "targetId", "expression", "expressionType",
            "campaignId", "adGroupId", "state",
        ]
        print_output(
            targets, output, columns=columns,
            title=f"Negative Targets ({region})",
        )
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create-negative")
def create_negative_target(
    campaign_id: Annotated[str, typer.Option("--campaign-id", "-c")] = ...,
    ad_group_id: Annotated[str, typer.Option("--ad-group-id", "-a")] = ...,
    asin: Annotated[str | None, typer.Option("--asin", help="ASIN to negatively target")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create negative targeting clauses.

    Single ASIN: --campaign-id X --ad-group-id Y --asin B00EXAMPLE

    Bulk: --from-file negatives.json
    """
    client, service = _build_client(verbose)
    try:
        targets: list[CreateNegativeTargetRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            targets = [CreateNegativeTargetRequest(**t) for t in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            targets = [CreateNegativeTargetRequest(**t) for t in data]
        elif asin:
            targets = [
                CreateNegativeTargetRequest(
                    campaignId=campaign_id,
                    adGroupId=ad_group_id,
                    expression=[{"type": "asinSameAs", "value": asin}],
                )
            ]
        else:
            console.print(
                "[red]Provide --asin with --campaign-id and --ad-group-id, "
                "or use --from-file/--from-stdin[/red]"
            )
            raise typer.Exit(1)

        console.print(f"Creating {len(targets)} negative target(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would create {len(targets)} negative target(s)")
            sample = [t.model_dump(by_alias=True, exclude_none=True) for t in targets[:5]]
            print_output(sample, output, title="Sample Negative Targets [DRY RUN]")
            return
        results = service.create_negative(region, targets)
        print_output(results, output, title="Negative Targets Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete-negative")
def delete_negative_targets(
    target_ids: Annotated[list[str] | None, typer.Option("--target-id", "-t")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete negative targeting clauses by ID."""
    client, service = _build_client(verbose)
    try:
        ids: list[str] = []
        if from_file:
            with open(from_file) as f:
                content = f.read().strip()
            try:
                ids = json.loads(content)
            except json.JSONDecodeError:
                ids = [line.strip() for line in content.splitlines() if line.strip()]
        elif target_ids:
            ids = target_ids
        else:
            console.print("[red]Provide --target-id or --from-file[/red]")
            raise typer.Exit(1)

        console.print(f"Deleting {len(ids)} negative target(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(ids)} negative target(s)")
            return
        results = service.delete_negative(region, ids)
        print_output(results, output, title="Negative Targets Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
