"""CLI commands for authentication management."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.config import get_config
from amazon_ads.auth import AuthManager
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="auth", help="Manage authentication tokens.")


@app.command()
def login(
    region: Annotated[str, typer.Option("--region", "-r", help="Region to authenticate against")] = "US",
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output format")] = OutputFormat.TABLE,
) -> None:
    """Authenticate and display token status."""
    config = get_config()
    auth = AuthManager(config)

    try:
        console.print(f"Authenticating for region [bold]{region}[/bold]...", style="yellow")
        auth.get_access_token(region)
        status = auth.get_status()
        result = {
            "status": "authenticated",
            "expires_at": str(status.expires_at),
            "seconds_remaining": status.seconds_remaining,
        }
        print_output(result, output, title="Authentication")
    except Exception as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise typer.Exit(1)
    finally:
        auth.close()


@app.command()
def status(
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output format")] = OutputFormat.TABLE,
) -> None:
    """Show current token status."""
    config = get_config()
    auth = AuthManager(config)

    token_status = auth.get_status()
    result = {
        "has_token": token_status.has_token,
        "is_expired": token_status.is_expired,
        "expires_at": str(token_status.expires_at) if token_status.expires_at else "N/A",
        "seconds_remaining": token_status.seconds_remaining or 0,
    }
    print_output(result, output, title="Token Status")
    auth.close()


@app.command()
def refresh(
    region: Annotated[str, typer.Option("--region", "-r", help="Region to authenticate against")] = "US",
    output: Annotated[OutputFormat, typer.Option("--output", "-o", help="Output format")] = OutputFormat.TABLE,
) -> None:
    """Force refresh the access token."""
    config = get_config()
    auth = AuthManager(config)

    try:
        console.print(f"Force refreshing token for region [bold]{region}[/bold]...", style="yellow")
        auth.get_access_token(region, force_refresh=True)
        status = auth.get_status()
        result = {
            "status": "refreshed",
            "expires_at": str(status.expires_at),
            "seconds_remaining": status.seconds_remaining,
        }
        print_output(result, output, title="Token Refreshed")
    except Exception as e:
        console.print(f"[red]Token refresh failed:[/red] {e}")
        raise typer.Exit(1)
    finally:
        auth.close()
