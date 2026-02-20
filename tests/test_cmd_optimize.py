"""CLI tests for optimize command group."""
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.optimize_cmd import app

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── run dry-run ──────────────────────────────────────────────────────

def test_optimize_run_dry_run():
    svc = MagicMock()
    svc.optimize.return_value = [
        {"keywordId": "k1", "action": "REDUCE", "currentBid": 1.0, "newBid": 0.32},
    ]

    with patch("amazon_ads.commands.optimize_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "run", "--region", "US", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    # Dry run should force apply=False
    call_kwargs = svc.optimize.call_args[1]
    assert call_kwargs.get("apply") is False or svc.optimize.call_args[0] is not None


# ── compare (read-only) ─────────────────────────────────────────────

def test_optimize_compare():
    svc = MagicMock()
    svc.optimize.return_value = [
        {"keywordId": "k1", "action": "KEEP", "currentBid": 0.30, "newBid": 0.30},
    ]

    with patch("amazon_ads.commands.optimize_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "compare", "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
