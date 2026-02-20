"""Backup and restore utilities for keyword bids."""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path
from typing import Any


def backup_keywords(
    keywords: list[dict[str, Any]],
    region: str,
    backup_dir: str = "./backups",
) -> dict[str, str]:
    """Backup keywords to CSV and JSON files.

    Args:
        keywords: List of keyword dicts (keywordId, bid, state, keywordText, etc.)
        region: Region code (e.g. US, GB).
        backup_dir: Directory to save backups.

    Returns:
        Dict with paths: {"csv": "...", "json": "..."}
    """
    dir_path = Path(backup_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    today = date.today().isoformat()
    base = f"{region}-{today}"

    csv_path = dir_path / f"{base}.csv"
    json_path = dir_path / f"{base}.json"

    # Write JSON
    with open(json_path, "w") as f:
        json.dump(keywords, f, indent=2, default=str)

    # Write CSV
    if keywords:
        fields = list(keywords[0].keys())
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(keywords)

    return {"csv": str(csv_path), "json": str(json_path)}


def load_backup(file_path: str) -> list[dict[str, Any]]:
    """Load keywords from a backup file (CSV or JSON).

    Args:
        file_path: Path to the backup file.

    Returns:
        List of keyword dicts.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Backup file not found: {file_path}")

    ext = path.suffix.lower()
    if ext == ".json":
        with open(path) as f:
            return json.load(f)
    elif ext == ".csv":
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            return list(reader)
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .csv or .json")
