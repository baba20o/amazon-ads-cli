"""CLI tests for onboard command group."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.onboard_cmd import app

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── dry-run ──────────────────────────────────────────────────────────

def test_onboard_dry_run():
    svc = MagicMock()

    with patch("amazon_ads.commands.onboard_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "--title", "Test Book", "--asin", "B00TEST",
            "--region", "US", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.onboard_product.assert_not_called()


# ── service call ─────────────────────────────────────────────────────

def test_onboard_calls_service():
    svc = MagicMock()
    svc.onboard_product.return_value = [{"campaign": "Test", "status": "SUCCESS"}]

    with patch("amazon_ads.commands.onboard_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "--title", "Test Book", "--asin", "B00TEST",
            "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.onboard_product.assert_called_once()
