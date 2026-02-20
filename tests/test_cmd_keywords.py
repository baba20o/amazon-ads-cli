"""CLI tests for keywords command group."""
import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.keywords_cmd import app

runner = CliRunner()


def _mock_build(mock_service):
    client = MagicMock()
    return client, mock_service


# ── list ─────────────────────────────────────────────────────────────

def test_list_keywords():
    svc = MagicMock()
    svc.list.return_value = [{"keywordId": "k1", "keywordText": "test"}]

    with patch("amazon_ads.commands.keywords_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, ["list", "--region", "US", "--output", "json"])
    assert result.exit_code == 0
    assert "k1" in result.stdout


# ── create single ────────────────────────────────────────────────────

def test_create_single_keyword_dry_run():
    svc = MagicMock()

    with patch("amazon_ads.commands.keywords_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--keyword-text", "test keyword", "--campaign-id", "c1",
            "--ad-group-id", "a1", "--region", "US", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.create.assert_not_called()


def test_create_single_keyword():
    svc = MagicMock()
    svc.create.return_value = [{"keywords": {"success": [{"keywordId": "k1"}]}}]

    with patch("amazon_ads.commands.keywords_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--keyword-text", "test keyword", "--campaign-id", "c1",
            "--ad-group-id", "a1", "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    svc.create.assert_called_once()


# ── create from stdin ────────────────────────────────────────────────

def test_create_from_stdin():
    svc = MagicMock()
    svc.create.return_value = [{"keywords": {"success": []}}]

    keywords = json.dumps([
        {"keywordText": "kw1", "matchType": "BROAD", "campaignId": "c1", "adGroupId": "a1"},
    ])

    with patch("amazon_ads.commands.keywords_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, [
            "create", "--from-stdin", "--region", "US", "--output", "json",
        ], input=keywords)
    assert result.exit_code == 0
    svc.create.assert_called_once()


# ── generate ─────────────────────────────────────────────────────────

def test_generate_dry_run():
    result = runner.invoke(app, [
        "generate", "--title", "Test Book", "--region", "US", "--dry-run", "--output", "json",
    ])
    assert result.exit_code == 0


def test_generate_invalid_provider():
    result = runner.invoke(app, [
        "generate", "--title", "Test", "--api-key", "fake",
        "--provider", "invalid", "--output", "json",
    ])
    assert result.exit_code == 1


# ── error handling ───────────────────────────────────────────────────

def test_list_error_handled():
    svc = MagicMock()
    svc.list.side_effect = RuntimeError("API error")

    with patch("amazon_ads.commands.keywords_cmd._build_client", return_value=_mock_build(svc)):
        result = runner.invoke(app, ["list", "--region", "US"])
    assert result.exit_code == 1
