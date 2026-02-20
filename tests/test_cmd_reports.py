"""CLI tests for reports command group."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.reports_cmd import app

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
