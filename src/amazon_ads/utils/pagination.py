"""Pagination helpers for Amazon Ads API."""

from __future__ import annotations

from typing import Any, Callable


def paginate(
    fetch_fn: Callable[[dict[str, Any]], dict[str, Any]],
    body: dict[str, Any],
    results_key: str,
) -> list[dict[str, Any]]:
    """Paginate through all results using nextToken.

    Args:
        fetch_fn: A callable that takes a body dict and returns a response dict.
        body: The initial request body.
        results_key: The key in the response containing the results list
                     (e.g. "campaigns", "keywords").

    Returns:
        All results concatenated across pages.
    """
    all_results: list[dict[str, Any]] = []

    while True:
        response = fetch_fn(body)
        items = response.get(results_key, [])
        all_results.extend(items)

        next_token = response.get("nextToken")
        if not next_token:
            break
        body["nextToken"] = next_token

    return all_results
