"""CLI commands for keyword management."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.keywords import CreateKeywordRequest, UpdateKeywordRequest
from amazon_ads.services.keyword_generation import generate_keywords
from amazon_ads.services.keywords import KeywordService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="keywords", help="Manage Sponsored Products keywords.")


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, KeywordService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, KeywordService(client)


@app.command("list")
def list_keywords(
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s", help="Filter by state (ENABLED, PAUSED, ARCHIVED)")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """List keywords with automatic pagination."""
    client, service = _build_client(verbose)
    try:
        keywords = service.list(
            region, campaign_id=campaign_id, ad_group_id=ad_group_id, state=state
        )
        console.print(f"[dim]Found {len(keywords)} keywords[/dim]", style="dim")
        columns = ["keywordId", "keywordText", "matchType", "campaignId", "adGroupId", "state", "bid"]
        print_output(keywords, output, columns=columns, title=f"Keywords ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("create")
def create_keyword(
    keyword_text: Annotated[str | None, typer.Option("--keyword-text", "-k", help="Keyword text (single keyword mode)")] = None,
    match_type: Annotated[str, typer.Option("--match-type", "-m", help="BROAD, PHRASE, or EXACT")] = "BROAD",
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a")] = None,
    bid: Annotated[float, typer.Option("--bid", "-b", help="Keyword bid")] = 0.30,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin", help="Read keywords JSON from stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f", help="Read keywords from JSON file")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create keywords (single, from file, or from stdin).

    Single mode: --keyword-text "my keyword" --campaign-id X --ad-group-id Y

    Bulk mode: --from-file keywords.json or --from-stdin
    JSON format: [{"campaignId": "X", "adGroupId": "Y", "keywordText": "...", "matchType": "BROAD", "bid": 0.30}]
    """
    client, service = _build_client(verbose)
    try:
        keywords: list[CreateKeywordRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            keywords = [CreateKeywordRequest(**kw) for kw in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            keywords = [CreateKeywordRequest(**kw) for kw in data]
        elif keyword_text and campaign_id and ad_group_id:
            keywords = [
                CreateKeywordRequest(
                    campaignId=campaign_id,
                    adGroupId=ad_group_id,
                    keywordText=keyword_text,
                    matchType=match_type.upper(),
                    bid=bid,
                )
            ]
        else:
            console.print("[red]Provide --keyword-text with --campaign-id and --ad-group-id, or use --from-file/--from-stdin[/red]")
            raise typer.Exit(1)

        console.print(f"Creating {len(keywords)} keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would create {len(keywords)} keyword(s)")
            sample = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords[:5]]
            print_output(sample, output, title=f"Sample Keywords [DRY RUN]")
            return
        results = service.create(region, keywords)
        print_output(results, output, title="Keywords Created")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("update")
def update_keyword(
    keyword_id: Annotated[str | None, typer.Option("--keyword-id", "-k", help="Keyword ID (single mode)")] = None,
    state: Annotated[str | None, typer.Option("--state", "-s")] = None,
    bid: Annotated[float | None, typer.Option("--bid", "-b")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_stdin: Annotated[bool, typer.Option("--from-stdin", help="Read updates from stdin")] = False,
    from_file: Annotated[str | None, typer.Option("--from-file", "-f", help="Read updates from JSON file")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be sent without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Update keyword state and/or bid.

    Single mode: --keyword-id X --bid 0.50 --state ENABLED

    Bulk mode: --from-file updates.json
    JSON format: [{"keywordId": "X", "bid": 0.50, "state": "ENABLED"}]
    """
    client, service = _build_client(verbose)
    try:
        keywords: list[UpdateKeywordRequest] = []

        if from_stdin:
            data = json.load(sys.stdin)
            keywords = [UpdateKeywordRequest(**kw) for kw in data]
        elif from_file:
            with open(from_file) as f:
                data = json.load(f)
            keywords = [UpdateKeywordRequest(**kw) for kw in data]
        elif keyword_id:
            keywords = [
                UpdateKeywordRequest(
                    keywordId=keyword_id,
                    state=state.upper() if state else None,
                    bid=bid,
                )
            ]
        else:
            console.print("[red]Provide --keyword-id or use --from-file/--from-stdin[/red]")
            raise typer.Exit(1)

        console.print(f"Updating {len(keywords)} keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would update {len(keywords)} keyword(s)")
            sample = [kw.model_dump(by_alias=True, exclude_none=True) for kw in keywords[:5]]
            print_output(sample, output, title="Sample Updates [DRY RUN]")
            return
        results = service.update(region, keywords)
        print_output(results, output, title="Keywords Updated")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("delete")
def delete_keywords(
    keyword_ids: Annotated[list[str] | None, typer.Option("--keyword-id", "-k", help="Keyword ID(s)")] = None,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    from_file: Annotated[str | None, typer.Option("--from-file", "-f", help="File with keyword IDs (one per line or JSON array)")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be deleted without executing")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Delete keywords by ID."""
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

        console.print(f"Deleting {len(ids)} keyword(s) in {region}...")
        if dry_run:
            console.print(f"[yellow]DRY RUN:[/yellow] Would delete {len(ids)} keyword(s): {ids[:10]}...")
            return
        results = service.delete(region, ids)
        print_output(results, output, title="Keywords Deleted")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


def _resolve_api_key(provider: str, api_key: str | None) -> str:
    """Resolve the API key from the flag or environment variables."""
    import os

    if api_key:
        return api_key

    env_vars = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
    }
    env_var = env_vars.get(provider.lower(), "")
    val = os.environ.get(env_var, "")
    if val:
        return val

    raise ValueError(
        f"No API key provided. Pass --api-key or set the {env_var} environment variable."
    )


@app.command("generate")
def generate(
    title: Annotated[str, typer.Option("--title", "-t", help="Product/book title for keyword ideation")] = ...,
    region: Annotated[str, typer.Option("--region", "-r", help="Target region for language localisation")] = "US",
    provider: Annotated[str, typer.Option("--provider", "-p", help="LLM provider: anthropic or openai")] = "anthropic",
    model: Annotated[str | None, typer.Option("--model", "-m", help="Model name (default: claude-sonnet-4-20250514 / gpt-4o)")] = None,
    api_key: Annotated[str | None, typer.Option("--api-key", help="Provider API key (or set ANTHROPIC_API_KEY / OPENAI_API_KEY)")] = None,
    prompt_text: Annotated[str | None, typer.Option("--prompt", help="Custom prompt (must request JSON with 'keywords' key)")] = None,
    prompt_file: Annotated[str | None, typer.Option("--prompt-file", help="Read custom prompt from a file")] = None,
    expand_match_types: Annotated[bool, typer.Option("--expand-match-types/--no-expand", help="Expand each keyword into BROAD/PHRASE/EXACT")] = True,
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", "-c", help="Attach campaign ID to output records")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", "-a", help="Attach ad group ID to output records")] = None,
    bid: Annotated[float | None, typer.Option("--bid", "-b", help="Keyword bid to attach to each record")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show the prompt that would be sent without calling the LLM")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.JSON,
) -> None:
    """Generate keywords using an LLM (Anthropic or OpenAI).

    Sends a prompt to the chosen LLM provider and returns keyword suggestions
    as structured JSON. Output is pipeable to `keywords create --from-stdin`.

    Examples:

        amazon-ads keywords generate --title "My Book" --provider anthropic

        amazon-ads keywords generate --title "My Book" --provider openai --model gpt-4o

        amazon-ads keywords generate --title "My Book" | amazon-ads keywords create --from-stdin --region US
    """
    # Load custom prompt if provided
    custom_prompt: str | None = prompt_text
    if prompt_file:
        with open(prompt_file) as f:
            custom_prompt = f.read()

    if dry_run:
        from amazon_ads.services.keyword_generation import _DEFAULT_PROMPT

        effective_prompt = custom_prompt or _DEFAULT_PROMPT.format(title=title, region=region)
        console.print(f"[yellow]DRY RUN:[/yellow] Would call {provider} ({model or 'default model'})")
        console.print(f"  Region: {region}")
        console.print(f"  Expand match types: {expand_match_types}")
        console.print(f"\n[bold]Prompt:[/bold]\n{effective_prompt}")
        return

    try:
        resolved_key = _resolve_api_key(provider, api_key)
        console.print(f"[dim]Generating keywords for '{title}' via {provider}...[/dim]")

        results = generate_keywords(
            title=title,
            region=region,
            provider=provider,
            api_key=resolved_key,
            model=model,
            custom_prompt=custom_prompt,
            expand_match_types=expand_match_types,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            bid=bid,
        )

        console.print(f"[dim]Generated {len(results)} keyword record(s)[/dim]")
        print_output(results, output, title="Generated Keywords")
    except (ValueError, ImportError, Exception) as e:
        handle_error(e)
        raise typer.Exit(1)
