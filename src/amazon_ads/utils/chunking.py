"""Chunking utilities for batch API operations."""

from __future__ import annotations

from typing import Any, TypeVar

T = TypeVar("T")


def chunk_list(items: list[T], chunk_size: int = 1000) -> list[list[T]]:
    """Split a list into chunks of the given size.

    Args:
        items: The list to split.
        chunk_size: Maximum items per chunk (Amazon API limit is typically 1000).

    Returns:
        A list of sub-lists, each with at most chunk_size items.
    """
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
