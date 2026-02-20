"""CLI command for schema introspection — outputs all commands + args as JSON."""

from __future__ import annotations

import json
import sys
from typing import Any

import click
import typer
from typer.main import get_command


def _param_to_dict(param: click.Parameter) -> dict[str, Any]:
    """Convert a Click parameter to a JSON-serializable dict."""
    info: dict[str, Any] = {
        "name": param.name,
        "required": param.required,
    }

    # Type info
    if hasattr(param.type, "name"):
        info["type"] = param.type.name
    elif hasattr(param.type, "choices"):
        info["type"] = "choice"
        info["choices"] = list(param.type.choices)
    else:
        info["type"] = str(param.type)

    # Choices for Choice types
    if isinstance(param.type, click.Choice):
        info["choices"] = list(param.type.choices)

    # Default value
    if param.default is not None:
        default = param.default
        # Convert enums to their value
        if hasattr(default, "value"):
            default = default.value
        info["default"] = default

    # CLI option flags
    if isinstance(param, click.Option):
        info["flags"] = list(param.opts)
        if param.help:
            info["help"] = param.help
        info["is_flag"] = param.is_flag
        if param.multiple:
            info["multiple"] = True

    return info


def _command_to_dict(cmd: click.BaseCommand, path: str = "") -> dict[str, Any]:
    """Recursively convert a Click command tree to a JSON-serializable dict."""
    info: dict[str, Any] = {
        "name": cmd.name or "",
        "path": path,
    }

    if cmd.help:
        info["help"] = cmd.help.strip().split("\n")[0]  # First line only

    if isinstance(cmd, click.MultiCommand):
        # Group command — recurse into subcommands
        children = []
        for name in cmd.list_commands(click.Context(cmd)):
            sub = cmd.get_command(click.Context(cmd), name)
            if sub:
                child_path = f"{path} {name}" if path else name
                children.append(_command_to_dict(sub, child_path))
        info["commands"] = children
    else:
        # Leaf command — extract parameters
        params = []
        for p in cmd.params:
            if p.name in ("help",):
                continue
            params.append(_param_to_dict(p))
        info["options"] = params

    return info


app = typer.Typer(name="schema", help="Output CLI schema as JSON for agent introspection.")


@app.command("dump")
def schema_dump() -> None:
    """Output the full CLI command tree as JSON.

    Includes all command groups, sub-commands, options, types, defaults,
    and help text. Designed for AI agent introspection.
    """
    from amazon_ads.main import app as main_app

    cli = get_command(main_app)
    schema = _command_to_dict(cli, "amazon-ads")
    schema["version"] = "0.1.0"

    json.dump(schema, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
