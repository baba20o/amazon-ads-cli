"""CLI commands for negative keyword management."""

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
    CreateCampaignNegativeKeywordRequest,
    CreateNegativeKeywordRequest,
)
from amazon_ads.services.negative_keywords import NegativeKeywordService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="negatives", help="Manage Sponsored Products negative keywords.")


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, NegativeKeywordService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, NegativeKeywordService(client)


# ── Ad-group-level negative keywords ──────────────────────────────


@app.command("list")
def list_negatives(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List ad-group-level negative keywords."""
    client, service = _build_client(verbose)
    try:
        keywords = service.list(
            region, campaign_id=campaign_id, ad_group_id=ad_group_id, state=state
        )
        console.print(f"[dim]Found {len(keywords)} negative keywords[/dim]")
        columns = [
            "keywordId", "keywordText", "matchType",
            "campaignId", "adGroupId", "state",
        ]
        print_output(keywords, output, columns=columns, title=f"Negative Keywords ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create")
def create_negative(
    keyword_text: Annotated[str | None, typer.Option("--keyword-text", "-k", help="Keyword text")] = None,
    match_type: Annotated[str, typer.Option("--match-type", "-m", help="NEGATIVE_EXACT or NEGATIVE_PHRASE")] = "NEGATIVE_EXACT",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin", help="Read from stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f", help="Read from JSON file")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create ad-group-level negative keywords.

    Single: --keyword-text "brand" --campaign-id X --ad-group-id Y --match-type NEGATIVE_EXACT

    Bulk: --from-file negatives.json
    JSON: [{"campaignId":"X","adGroupId":"Y","keywordText":"...","matchType":"NEGATIVE_EXACT"}]
    """
    client, service = _build_client(verbose)
    try:
        keywords: list[CreateNegativeKeywordRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            keywords = [CreateNegativeKeywordRequest(**kw) for kw in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            keywords = [CreateNegativeKeywordRequest(**kw) for kw in data]
        elif keyword_text and campaign_id and ad_group_id:
            keywords = [
                CreateNegativeKeywordRequest(
                    campaignId=campaign_id,
                    adGroupId=ad_group_id,
                    keywordText=keyword_text,
                    matchType=match_type.upper(),
                )
            ]
        else:
            console.print(
                "[red]Provide --keyword-text with --campaign-id and --ad-group-id, "
                "or use --from-file/--from-stdin[/red]"
            )
            raise typer.Exit(1)

        console.print(f"Creating {len(keywords)} negative keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would create {len(keywords)} negative keyword(s)")
            sample = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords[:5]]
            print_output(sample, output, title="Sample Negative Keywords [DRY RUN]")
            return
        results = service.create(region, keywords)
        print_output(results, output, title="Negative Keywords Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete")
def delete_negatives(
    keyword_ids: Annotated[list[str] | None, typer.Option("--keyword-id", "-k", help="Negative keyword ID(s)")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete ad-group-level negative keywords by ID."""
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
        elif keyword_ids:
            ids = keyword_ids
        else:
            console.print("[red]Provide --keyword-id or --from-file[/red]")
            raise typer.Exit(1)

        console.print(f"Deleting {len(ids)} negative keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(ids)} negative keyword(s)")
            return
        results = service.delete(region, ids)
        print_output(results, output, title="Negative Keywords Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


# ── Campaign-level negative keywords ─────────────────────────────


@app.command("list-campaign")
def list_campaign_negatives(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List campaign-level negative keywords."""
    client, service = _build_client(verbose)
    try:
        keywords = service.list_campaign_level(
            region, campaign_id=campaign_id, state=state
        )
        console.print(f"[dim]Found {len(keywords)} campaign negative keywords[/dim]")
        columns = [
            "keywordId", "keywordText", "matchType", "campaignId", "state",
        ]
        print_output(
            keywords, output, columns=columns,
            title=f"Campaign Negative Keywords ({region})",
        )
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create-campaign")
def create_campaign_negative(
    keyword_text: Annotated[str | None, typer.Option("--keyword-text", "-k")] = None,
    match_type: Annotated[str, typer.Option("--match-type", "-m")] = "NEGATIVE_EXACT",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create campaign-level negative keywords.

    Single: --keyword-text "brand" --campaign-id X --match-type NEGATIVE_EXACT

    Bulk: --from-file negatives.json
    JSON: [{"campaignId":"X","keywordText":"...","matchType":"NEGATIVE_EXACT"}]
    """
    client, service = _build_client(verbose)
    try:
        keywords: list[CreateCampaignNegativeKeywordRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            keywords = [CreateCampaignNegativeKeywordRequest(**kw) for kw in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            keywords = [CreateCampaignNegativeKeywordRequest(**kw) for kw in data]
        elif keyword_text and campaign_id:
            keywords = [
                CreateCampaignNegativeKeywordRequest(
                    campaignId=campaign_id,
                    keywordText=keyword_text,
                    matchType=match_type.upper(),
                )
            ]
        else:
            console.print(
                "[red]Provide --keyword-text with --campaign-id, "
                "or use --from-file/--from-stdin[/red]"
            )
            raise typer.Exit(1)

        console.print(f"Creating {len(keywords)} campaign negative keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would create {len(keywords)} campaign negative keyword(s)")
            sample = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords[:5]]
            print_output(sample, output, title="Sample Campaign Negatives [DRY RUN]")
            return
        results = service.create_campaign_level(region, keywords)
        print_output(results, output, title="Campaign Negative Keywords Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete-campaign")
def delete_campaign_negatives(
    keyword_ids: Annotated[list[str] | None, typer.Option("--keyword-id", "-k")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_file: Annotated[str | None, typer.Option("--from-file", "-f")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete campaign-level negative keywords by ID."""
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
        elif keyword_ids:
            ids = keyword_ids
        else:
            console.print("[red]Provide --keyword-id or --from-file[/red]")
            raise typer.Exit(1)

        console.print(f"Deleting {len(ids)} campaign negative keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(ids)} campaign negative keyword(s)")
            return
        results = service.delete_campaign_level(region, ids)
        print_output(results, output, title="Campaign Negative Keywords Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
