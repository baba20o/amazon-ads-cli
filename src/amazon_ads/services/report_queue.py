"""Report queue manager for fire-and-forget async reports."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class QueueEntry(BaseModel):
    """A single queued report."""
    report_id: str
    region: str
    report_type: str
    start_date: str
    end_date: str
    status: str = "SUBMITTED"
    submitted_at: str = ""
    completed_at: str | None = None
    download_path: str | None = None
    row_count: int | None = None
    filters: dict[str, Any] | None = None


class ReportQueue:
    """Persistent queue for tracking async report submissions.

    Stores entries in a JSON file at ``{queue_dir}/report_queue.json``.
    Downloaded reports are saved to ``{queue_dir}/reports/``.
    """

    def __init__(self, queue_dir: str = "./data") -> None:
        self._dir = Path(queue_dir)
        self._file = self._dir / "report_queue.json"
        self._reports_dir = self._dir / "reports"

    # ── persistence ───────────────────────────────────────────────────

    def load(self) -> list[QueueEntry]:
        """Load all queue entries from disk."""
        if not self._file.exists():
            return []
        with open(self._file) as f:
            data = json.load(f)
        return [QueueEntry(**entry) for entry in data]

    def save(self, entries: list[QueueEntry]) -> None:
        """Save queue entries to disk."""
        self._dir.mkdir(parents=True, exist_ok=True)
        with open(self._file, "w") as f:
            json.dump(
                [e.model_dump() for e in entries],
                f,
                indent=2,
                default=str,
            )

    # ── mutations ─────────────────────────────────────────────────────

    def add(self, entry: QueueEntry) -> None:
        """Add a new entry to the queue."""
        entries = self.load()
        entries.append(entry)
        self.save(entries)

    def update_status(
        self,
        report_id: str,
        status: str,
        **kwargs: Any,
    ) -> QueueEntry | None:
        """Update the status (and optional fields) of a queue entry.

        Returns the updated entry, or None if not found.
        """
        entries = self.load()
        updated = None
        for entry in entries:
            if entry.report_id == report_id:
                entry.status = status
                for key, val in kwargs.items():
                    if hasattr(entry, key):
                        setattr(entry, key, val)
                updated = entry
                break
        if updated:
            self.save(entries)
        return updated

    # ── queries ───────────────────────────────────────────────────────

    def get_pending(self) -> list[QueueEntry]:
        """Return entries that are still awaiting completion."""
        return [e for e in self.load() if e.status in ("SUBMITTED", "PROCESSING")]

    def get_by_id(self, report_id: str) -> QueueEntry | None:
        """Look up a single entry by report ID."""
        for entry in self.load():
            if entry.report_id == report_id:
                return entry
        return None

    def get_all(
        self,
        status: str | None = None,
        region: str | None = None,
    ) -> list[QueueEntry]:
        """Return entries, optionally filtered by status and/or region."""
        entries = self.load()
        if status:
            entries = [e for e in entries if e.status.upper() == status.upper()]
        if region:
            entries = [e for e in entries if e.region.upper() == region.upper()]
        return entries

    # ── cleanup ───────────────────────────────────────────────────────

    def remove_older_than(self, days: int) -> int:
        """Remove entries older than *days*. Returns count removed."""
        cutoff = datetime.now() - timedelta(days=days)
        entries = self.load()
        keep = []
        removed = 0
        for entry in entries:
            try:
                submitted = datetime.fromisoformat(entry.submitted_at)
                if submitted < cutoff:
                    removed += 1
                    continue
            except (ValueError, TypeError):
                pass
            keep.append(entry)
        self.save(keep)
        return removed

    def clear(self) -> int:
        """Remove all entries. Returns count removed."""
        entries = self.load()
        count = len(entries)
        self.save([])
        return count

    # ── download path helper ──────────────────────────────────────────

    def download_path(self, entry: QueueEntry) -> Path:
        """Compute the download path for a report entry."""
        self._reports_dir.mkdir(parents=True, exist_ok=True)
        short_id = entry.report_id[:8]
        filename = f"{entry.region}-{entry.report_type}-{entry.start_date}-{short_id}.json"
        return self._reports_dir / filename
