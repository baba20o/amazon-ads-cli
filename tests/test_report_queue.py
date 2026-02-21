"""Tests for services/report_queue.py — persistent report queue."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from amazon_ads.services.report_queue import QueueEntry, ReportQueue


@pytest.fixture
def queue(tmp_path):
    """ReportQueue backed by a temp directory."""
    return ReportQueue(queue_dir=str(tmp_path))


def _entry(**overrides) -> QueueEntry:
    """Build a QueueEntry with sensible defaults."""
    defaults = {
        "report_id": "rpt-001",
        "region": "US",
        "report_type": "spCampaigns",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "status": "SUBMITTED",
        "submitted_at": datetime.now().isoformat(),
    }
    defaults.update(overrides)
    return QueueEntry(**defaults)


# ── persistence ───────────────────────────────────────────────────────

def test_load_empty(queue):
    assert queue.load() == []


def test_add_and_load(queue):
    queue.add(_entry(report_id="rpt-1"))
    entries = queue.load()
    assert len(entries) == 1
    assert entries[0].report_id == "rpt-1"


def test_add_multiple(queue):
    queue.add(_entry(report_id="rpt-1"))
    queue.add(_entry(report_id="rpt-2"))
    assert len(queue.load()) == 2


def test_save_creates_directory(tmp_path):
    nested = tmp_path / "a" / "b" / "c"
    q = ReportQueue(queue_dir=str(nested))
    q.save([_entry()])
    assert (nested / "report_queue.json").exists()


def test_roundtrip_preserves_data(queue):
    entry = _entry(
        report_id="rpt-rt",
        region="DE",
        report_type="spKeywords",
        status="COMPLETED",
        completed_at="2026-02-01T12:00:00",
        download_path="data/reports/test.json",
        row_count=42,
        filters={"campaign_ids": ["111", "222"]},
    )
    queue.add(entry)
    loaded = queue.load()[0]
    assert loaded.report_id == "rpt-rt"
    assert loaded.region == "DE"
    assert loaded.report_type == "spKeywords"
    assert loaded.status == "COMPLETED"
    assert loaded.completed_at == "2026-02-01T12:00:00"
    assert loaded.download_path == "data/reports/test.json"
    assert loaded.row_count == 42
    assert loaded.filters == {"campaign_ids": ["111", "222"]}


# ── update_status ─────────────────────────────────────────────────────

def test_update_status(queue):
    queue.add(_entry(report_id="rpt-u1"))
    result = queue.update_status("rpt-u1", "COMPLETED", completed_at="2026-02-01T12:00:00")
    assert result is not None
    assert result.status == "COMPLETED"
    assert result.completed_at == "2026-02-01T12:00:00"

    # Verify persisted
    loaded = queue.get_by_id("rpt-u1")
    assert loaded.status == "COMPLETED"


def test_update_status_not_found(queue):
    queue.add(_entry(report_id="rpt-1"))
    result = queue.update_status("nonexistent", "COMPLETED")
    assert result is None


def test_update_status_with_row_count(queue):
    queue.add(_entry(report_id="rpt-rows"))
    queue.update_status("rpt-rows", "DOWNLOADED", row_count=500, download_path="test.json")
    loaded = queue.get_by_id("rpt-rows")
    assert loaded.row_count == 500
    assert loaded.download_path == "test.json"


# ── queries ───────────────────────────────────────────────────────────

def test_get_pending(queue):
    queue.add(_entry(report_id="rpt-1", status="SUBMITTED"))
    queue.add(_entry(report_id="rpt-2", status="PROCESSING"))
    queue.add(_entry(report_id="rpt-3", status="COMPLETED"))
    queue.add(_entry(report_id="rpt-4", status="DOWNLOADED"))

    pending = queue.get_pending()
    ids = [e.report_id for e in pending]
    assert ids == ["rpt-1", "rpt-2"]


def test_get_by_id(queue):
    queue.add(_entry(report_id="rpt-find"))
    entry = queue.get_by_id("rpt-find")
    assert entry is not None
    assert entry.report_id == "rpt-find"


def test_get_by_id_not_found(queue):
    assert queue.get_by_id("nonexistent") is None


def test_get_all_no_filter(queue):
    queue.add(_entry(report_id="rpt-1"))
    queue.add(_entry(report_id="rpt-2"))
    assert len(queue.get_all()) == 2


def test_get_all_filter_status(queue):
    queue.add(_entry(report_id="rpt-1", status="SUBMITTED"))
    queue.add(_entry(report_id="rpt-2", status="COMPLETED"))
    queue.add(_entry(report_id="rpt-3", status="COMPLETED"))

    result = queue.get_all(status="COMPLETED")
    assert len(result) == 2


def test_get_all_filter_region(queue):
    queue.add(_entry(report_id="rpt-1", region="US"))
    queue.add(_entry(report_id="rpt-2", region="DE"))
    queue.add(_entry(report_id="rpt-3", region="US"))

    result = queue.get_all(region="US")
    assert len(result) == 2


def test_get_all_filter_both(queue):
    queue.add(_entry(report_id="rpt-1", region="US", status="SUBMITTED"))
    queue.add(_entry(report_id="rpt-2", region="US", status="COMPLETED"))
    queue.add(_entry(report_id="rpt-3", region="DE", status="COMPLETED"))

    result = queue.get_all(status="COMPLETED", region="US")
    assert len(result) == 1
    assert result[0].report_id == "rpt-2"


# ── cleanup ───────────────────────────────────────────────────────────

def test_remove_older_than(queue):
    old_time = (datetime.now() - timedelta(days=10)).isoformat()
    recent_time = datetime.now().isoformat()

    queue.add(_entry(report_id="old", submitted_at=old_time))
    queue.add(_entry(report_id="recent", submitted_at=recent_time))

    removed = queue.remove_older_than(days=7)
    assert removed == 1
    assert len(queue.load()) == 1
    assert queue.load()[0].report_id == "recent"


def test_remove_older_than_none_match(queue):
    queue.add(_entry(report_id="rpt-1"))
    removed = queue.remove_older_than(days=7)
    assert removed == 0
    assert len(queue.load()) == 1


def test_clear(queue):
    queue.add(_entry(report_id="rpt-1"))
    queue.add(_entry(report_id="rpt-2"))
    removed = queue.clear()
    assert removed == 2
    assert len(queue.load()) == 0


# ── download_path ─────────────────────────────────────────────────────

def test_download_path_format(queue):
    entry = _entry(report_id="504a5bbb-0176-4261-8ad9-b3c76f28eadf")
    path = queue.download_path(entry)
    assert path.name == "US-spCampaigns-2026-01-01-504a5bbb.json"


def test_download_path_creates_dir(queue):
    entry = _entry()
    path = queue.download_path(entry)
    assert path.parent.exists()
