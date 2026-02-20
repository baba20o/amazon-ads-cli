"""CLI tests for campaigns command group."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.campaigns_cmd import app

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── list ─────────────────────────────────────────────────────────────

def test_list_campaigns():
    svc = MagicMock()
    svc.list.return_value = [{"campaignId": "c1", "name": "Test"}]

    with patch("amazon_ads.commands.campaigns_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, ["list", "--region", "US", "--output", "json"])
    assert result.exit_code == 0
    assert "c1" in result.stdout


def test_list_with_state_filter():
    svc = MagicMock()
    svc.list.return_value = []

    with patch("amazon_ads.commands.campaigns_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, ["list", "--region", "US", "--state", "PAUSED", "--output", "json"])
    assert result.exit_code == 0
    svc.list.assert_called_once_with("US", state="PAUSED", name=None, portfolio_id=None)


# ── create ───────────────────────────────────────────────────────────

def test_create_dry_run():
    svc = MagicMock()

    with patch("amazon_ads.commands.campaigns_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--name", "Test Campaign", "--region", "US", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.create.assert_not_called()


def test_create_calls_service():
    svc = MagicMock()
    svc.create.return_value = {"campaigns": {"success": [{"campaignId": "c1"}], "error": []}}

    with patch("amazon_ads.commands.campaigns_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--name", "Real Campaign", "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.create.assert_called_once()


# ── delete ───────────────────────────────────────────────────────────

def test_delete_dry_run():
    svc = MagicMock()

    with patch("amazon_ads.commands.campaigns_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "delete", "--campaign-id", "c1", "--campaign-id", "c2",
            "--region", "US", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.delete.assert_not_called()


# ── error handling ───────────────────────────────────────────────────

def test_list_error_handled():
    svc = MagicMock()
    svc.list.side_effect = RuntimeError("API error")

    with patch("amazon_ads.commands.campaigns_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, ["list", "--region", "US"])
    assert result.exit_code == 1
