"""CLI tests for sync command group."""
import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.sync_cmd import app

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── export ───────────────────────────────────────────────────────────

def test_export_structure():
    svc = MagicMock()
    svc.export_structure.return_value = [
        {"campaignId": "c1", "campaignName": "Test", "adGroups": []},
    ]

    with patch("amazon_ads.commands.sync_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "export", "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    assert "Test" in result.stdout


# ── replicate dry-run ────────────────────────────────────────────────

def test_replicate_dry_run(tmp_path):
    source_data = [
        {"campaignName": "Test", "targetingType": "MANUAL", "adGroups": []},
    ]
    source_file = tmp_path / "source.json"
    source_file.write_text(json.dumps(source_data))

    svc = MagicMock()

    with patch("amazon_ads.commands.sync_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "replicate", "--from-file", str(source_file),
            "--target", "DE", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.replicate.assert_not_called()


# ── sync keywords dry-run ────────────────────────────────────────────

def test_sync_keywords_dry_run():
    svc = MagicMock()

    with patch("amazon_ads.commands.sync_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "keywords", "--source", "US", "--target", "DE",
            "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.sync_keywords.assert_not_called()


# ── export error ─────────────────────────────────────────────────────

def test_export_error():
    svc = MagicMock()
    svc.export_structure.side_effect = RuntimeError("API error")

    with patch("amazon_ads.commands.sync_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, ["export", "--region", "US"])
    assert result.exit_code == 1
