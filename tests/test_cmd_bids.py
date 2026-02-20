"""CLI tests for bids command group."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.bids_cmd import app

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── update dry-run ───────────────────────────────────────────────────

def test_update_bids_dry_run():
    svc = MagicMock()
    svc.list.return_value = [
        {"keywordId": "k1", "bid": 0.50, "keywordText": "test"},
    ]

    with patch("amazon_ads.commands.bids_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "update", "--region", "US", "--target-bid", "0.75", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.update.assert_not_called()


# ── backup ───────────────────────────────────────────────────────────

def test_backup_bids(tmp_path):
    svc = MagicMock()
    svc.list.return_value = [
        {"keywordId": "k1", "bid": 0.50, "keywordText": "test"},
    ]

    with patch("amazon_ads.commands.bids_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "backup", "--region", "US", "--dir", str(tmp_path), "--output", "json",
        ])
    assert result.exit_code == 0


# ── restore dry-run ──────────────────────────────────────────────────

def test_restore_bids_dry_run(tmp_path):
    import json
    backup_file = tmp_path / "backup.json"
    backup_file.write_text(json.dumps([{"keywordId": "k1", "bid": "0.50"}]))

    svc = MagicMock()

    with patch("amazon_ads.commands.bids_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "restore", "--file", str(backup_file), "--region", "US",
            "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.update.assert_not_called()
