"""CLI tests for reports command group."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.reports_cmd import app
from amazon_ads.services.report_queue import ReportQueue

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── create (no-wait) ────────────────────────────────────────────────

def test_create_report_no_wait():
    svc = MagicMock()
    svc.create_report.return_value = "rpt-123"

    with patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--start-date", "2025-01-01", "--end-date", "2025-01-31",
            "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    assert "rpt-123" in result.stdout


# ── create (with wait) ──────────────────────────────────────────────

def test_create_report_with_wait():
    svc = MagicMock()
    svc.create_report.return_value = "rpt-456"
    svc.wait_and_download.return_value = [{"campaign": "c1", "cost": 10.0}]

    with patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--start-date", "2025-01-01", "--end-date", "2025-01-31",
            "--region", "US", "--wait", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.wait_and_download.assert_called_once()


# ── summary error ────────────────────────────────────────────────────

def test_summary_error():
    svc = MagicMock()
    svc.get_performance_summary.side_effect = RuntimeError("timeout")

    with patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "summary", "--region", "US",
        ])
    assert result.exit_code == 1


# ── create with filters ──────────────────────────────────────────────

def test_create_with_campaign_filter():
    svc = MagicMock()
    svc.create_report.return_value = "rpt-filtered"

    with patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--start-date", "2025-01-01", "--end-date", "2025-01-31",
            "--campaign-id", "111,222,333", "--output", "json",
        ])
    assert result.exit_code == 0
    call_kwargs = svc.create_report.call_args[1]
    assert call_kwargs["campaign_ids"] == ["111", "222", "333"]


def test_create_with_custom_columns():
    svc = MagicMock()
    svc.create_report.return_value = "rpt-cols"

    with patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--start-date", "2025-01-01", "--end-date", "2025-01-31",
            "--columns", "campaignId,cost,clicks", "--output", "json",
        ])
    assert result.exit_code == 0
    call_kwargs = svc.create_report.call_args[1]
    assert call_kwargs["columns"] == ["campaignId", "cost", "clicks"]


# ── submit ────────────────────────────────────────────────────────────

def test_submit_single_type(tmp_path):
    svc = MagicMock()
    svc.create_report.return_value = "rpt-submit-1"
    queue = ReportQueue(queue_dir=str(tmp_path))

    with (
        patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)),
        patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue),
    ):
        result = runner.invoke(app, [
            "submit", "--start-date", "2025-01-01", "--end-date", "2025-01-31",
            "--region", "US", "--report-type", "spCampaigns", "--output", "json",
        ])
    assert result.exit_code == 0
    assert svc.create_report.call_count == 1
    entries = queue.load()
    assert len(entries) == 1
    assert entries[0].report_id == "rpt-submit-1"
    assert entries[0].region == "US"
    assert entries[0].report_type == "spCampaigns"


def test_submit_all_types(tmp_path):
    svc = MagicMock()
    svc.create_report.side_effect = ["rpt-1", "rpt-2", "rpt-3", "rpt-4"]
    queue = ReportQueue(queue_dir=str(tmp_path))

    with (
        patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)),
        patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue),
    ):
        result = runner.invoke(app, [
            "submit", "--start-date", "2025-01-01", "--end-date", "2025-01-31",
            "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    assert svc.create_report.call_count == 4
    assert len(queue.load()) == 4


# ── queue ─────────────────────────────────────────────────────────────

def test_queue_list(tmp_path):
    queue = ReportQueue(queue_dir=str(tmp_path))
    from amazon_ads.services.report_queue import QueueEntry
    queue.add(QueueEntry(
        report_id="rpt-q1", region="US", report_type="spCampaigns",
        start_date="2025-01-01", end_date="2025-01-31",
        submitted_at="2026-02-20T10:00:00",
    ))

    with patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue):
        result = runner.invoke(app, ["queue", "--output", "json"])
    assert result.exit_code == 0
    assert "rpt-q1" in result.stdout


def test_queue_empty(tmp_path):
    queue = ReportQueue(queue_dir=str(tmp_path))
    with patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue):
        result = runner.invoke(app, ["queue"])
    assert result.exit_code == 0
    assert "empty" in result.stdout.lower()


# ── poll ──────────────────────────────────────────────────────────────

def test_poll_downloads_completed(tmp_path):
    svc = MagicMock()
    svc.get_report_status.return_value = {"status": "COMPLETED", "url": "https://example.com/report.gz"}
    svc._download_and_decompress.return_value = [{"campaign": "c1", "cost": 5.0}]

    queue = ReportQueue(queue_dir=str(tmp_path))
    from amazon_ads.services.report_queue import QueueEntry
    queue.add(QueueEntry(
        report_id="rpt-poll-1", region="US", report_type="spCampaigns",
        start_date="2025-01-01", end_date="2025-01-31",
        submitted_at="2026-02-20T10:00:00",
    ))

    with (
        patch("amazon_ads.commands.reports_cmd._build_client", return_value=_mock_build(svc)),
        patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue),
    ):
        result = runner.invoke(app, ["poll", "--output", "json"])
    assert result.exit_code == 0
    updated = queue.get_by_id("rpt-poll-1")
    assert updated.status == "DOWNLOADED"
    assert updated.row_count == 1


def test_poll_no_pending(tmp_path):
    queue = ReportQueue(queue_dir=str(tmp_path))
    with patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue):
        result = runner.invoke(app, ["poll"])
    assert result.exit_code == 0
    assert "no pending" in result.stdout.lower()


# ── clean ─────────────────────────────────────────────────────────────

def test_clean_all(tmp_path):
    queue = ReportQueue(queue_dir=str(tmp_path))
    from amazon_ads.services.report_queue import QueueEntry
    queue.add(QueueEntry(
        report_id="rpt-c1", region="US", report_type="spCampaigns",
        start_date="2025-01-01", end_date="2025-01-31",
        submitted_at="2026-02-20T10:00:00",
    ))

    with patch("amazon_ads.commands.reports_cmd._get_queue", return_value=queue):
        result = runner.invoke(app, ["clean", "--all"])
    assert result.exit_code == 0
    assert len(queue.load()) == 0
