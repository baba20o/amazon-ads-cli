"""Structured error handling for agent-friendly output."""

from __future__ import annotations

import json
import sys

from rich.console import Console

console = Console(stderr=True)

# Actionable hints keyed by error substring
_ERROR_HINTS: list[tuple[str, str]] = [
    ("401", "Token may be expired — run `amazon-ads auth refresh`"),
    ("token", "Token may be expired — run `amazon-ads auth refresh`"),
    ("unauthorized", "Token may be expired — run `amazon-ads auth refresh`"),
    ("429", "Rate limited — wait a moment and retry, or reduce batch size"),
    ("rate limit", "Rate limited — wait a moment and retry, or reduce batch size"),
    ("throttl", "Rate limited — wait a moment and retry, or reduce batch size"),
    ("profile", "Check your config/profiles.yaml region mappings"),
    ("could not find region", "Region not configured — check config/profiles.yaml"),
    ("timeout", "Request timed out — try again or check network connectivity"),
    ("connection", "Connection error — check network connectivity"),
    ("ENTITY_NOT_FOUND", "The specified entity does not exist — verify the ID"),
    ("INVALID_ARGUMENT", "Invalid argument — check parameter values and types"),
    ("MALFORMED_REQUEST", "Malformed request — verify JSON structure"),
]


def _get_hint(error_message: str) -> str | None:
    """Match an error message to an actionable hint."""
    lower = error_message.lower()
    for pattern, hint in _ERROR_HINTS:
        if pattern.lower() in lower:
            return hint
    return None


def handle_error(error: Exception) -> None:
    """Handle an error with structured output to stdout and human-readable output to stderr.

    Outputs a JSON error object to stdout for agent consumption:
    {"error": true, "code": "RUNTIME_ERROR", "message": "...", "hint": "..."}

    Also prints a human-readable error to stderr.
    """
    message = str(error)
    hint = _get_hint(message)

    # Determine error code from exception type or message
    code = "RUNTIME_ERROR"
    if "401" in message or "unauthorized" in message.lower():
        code = "AUTH_ERROR"
    elif "429" in message or "rate limit" in message.lower():
        code = "RATE_LIMITED"
    elif "timeout" in message.lower():
        code = "TIMEOUT"
    elif "connection" in message.lower():
        code = "CONNECTION_ERROR"
    elif "ENTITY_NOT_FOUND" in message:
        code = "NOT_FOUND"
    elif "INVALID_ARGUMENT" in message:
        code = "INVALID_ARGUMENT"

    # Structured JSON to stdout for agents
    error_obj: dict[str, object] = {
        "error": True,
        "code": code,
        "message": message,
    }
    if hint:
        error_obj["hint"] = hint

    json.dump(error_obj, sys.stdout)
    sys.stdout.write("\n")

    # Human-readable to stderr
    console.print(f"[red]Error:[/red] {message}")
    if hint:
        console.print(f"[dim]Hint: {hint}[/dim]")
