"""CLI commands for profile and account management."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.config import get_config
from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.services.profiles import ProfileService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="profiles", help="Manage advertising profiles and accounts.")


@app.command("list")
def list_profiles(
    region: Annotated[str, typer.Option("--region", "-r", help="Region to query")] = "US",
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output format")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show request details")] = False,
) -> None:
    """List all advertising profiles."""
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    service = ProfileService(client)

    try:
        profiles = service.list_profiles(region)
        if not profiles:
            console.print("[dim]No profiles found.[/dim]")
            raise typer.Exit(0)

        columns = ["profileId", "countryCode", "currencyCode", "timezone", "accountInfo"]
        print_output(profiles, output, columns=columns, title="Advertising Profiles")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("accounts")
def list_accounts(
    region: Annotated[str, typer.Option("--region", "-r", help="Region to query")] = "US",
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output format")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show request details")] = False,
) -> None:
    """List all ads accounts."""
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    service = ProfileService(client)

    try:
        accounts = service.list_accounts(region)
        if not accounts:
            console.print("[dim]No accounts found.[/dim]")
            raise typer.Exit(0)

        print_output(accounts, output, title="Ads Accounts")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
