"""Output formatting utilities for agent-friendly CLI output."""

from __future__ import annotations

import json
import sys
from enum import Enum
from typing import Any

from rich.console import Console
from rich.table import Table

console = Console(stderr=True)


class OutputFormat(str, Enum):
    TABLE = "table"
    JSON = "json"
    CSV = "csv"


def print_output(
    data: list[dict[str, Any]] | dict[str, Any],
    fmt: OutputFormat = OutputFormat.TABLE,
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Print data in the requested format.

    Args:
        data: The data to display (list of dicts or single dict).
        fmt: Output format (table, json, csv).
        columns: Which columns to show in table/csv mode. None = all.
        title: Optional title for table output.
    """
    if fmt == OutputFormat.JSON:
        print_json(data)
    elif fmt == OutputFormat.CSV:
        print_csv(data, columns)
    else:
        print_table(data, columns, title)


def print_json(data: Any) -> None:
    """Print data as formatted JSON to stdout."""
    json.dump(data, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def print_table(
    data: list[dict[str, Any]] | dict[str, Any],
    columns: list[str] | None = None,
    title: str | None = None,
) -> None:
    """Print data as a Rich table."""
    if isinstance(data, dict):
        data = [data]

    if not data:
        console.print("[dim]No results.[/dim]")
        return

    # Auto-detect columns from first row if not specified
    if columns is None:
        columns = list(data[0].keys())

    table = Table(title=title, show_lines=False)
    for col in columns:
        table.add_column(col, overflow="fold")

    for row in data:
        table.add_row(*[str(row.get(col, "")) for col in columns])

    console.print(table)


def print_csv(
    data: list[dict[str, Any]] | dict[str, Any],
    columns: list[str] | None = None,
) -> None:
    """Print data as CSV to stdout."""
    import csv
    import io

    if isinstance(data, dict):
        data = [data]

    if not data:
        return

    if columns is None:
        columns = list(data[0].keys())

    writer = csv.DictWriter(io.TextIOWrapper(sys.stdout.buffer, newline=""), fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in data:
        writer.writerow({k: row.get(k, "") for k in columns})
