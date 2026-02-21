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


# ── audit ────────────────────────────────────────────────────────────

_MOCK_CAMPAIGNS = [
    {"campaignId": "c1", "name": "Book-AUTOMATIC", "targetingType": "AUTO"},
    {"campaignId": "c2", "name": "Book-MANUAL", "targetingType": "MANUAL"},
]

_MOCK_AD_GROUPS = [
    {"adGroupId": "ag1", "campaignId": "c1", "defaultBid": 0.35},
]

_MOCK_TARGETS = [
    {
        "targetId": "t1",
        "campaignId": "c1",
        "adGroupId": "ag1",
        "bid": 1.20,
        "expression": [{"type": "QUERY_HIGH_REL_MATCHES"}],
    },
    {
        "targetId": "t2",
        "campaignId": "c1",
        "adGroupId": "ag1",
        "bid": 0.35,
        "expression": [{"type": "QUERY_BROAD_REL_MATCHES"}],
    },
]


def _audit_patches(mock_camp_svc, mock_ag_svc, mock_tgt_svc):
    """Return a context manager stack that patches all audit dependencies."""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(
        patch("amazon_ads.commands.bids_cmd._build_client", return_value=_mock_build(MagicMock()))
    )
    stack.enter_context(
        patch("amazon_ads.commands.bids_cmd.CampaignService", return_value=mock_camp_svc)
    )
    stack.enter_context(
        patch("amazon_ads.commands.bids_cmd.AdGroupService", return_value=mock_ag_svc)
    )
    stack.enter_context(
        patch("amazon_ads.commands.bids_cmd.TargetingService", return_value=mock_tgt_svc)
    )
    return stack


def _make_audit_mocks():
    camp_svc = MagicMock()
    camp_svc.list.return_value = _MOCK_CAMPAIGNS

    ag_svc = MagicMock()
    ag_svc.list.return_value = _MOCK_AD_GROUPS

    tgt_svc = MagicMock()
    tgt_svc.list.return_value = _MOCK_TARGETS

    return camp_svc, ag_svc, tgt_svc


def test_audit_finds_overrides():
    camp_svc, ag_svc, tgt_svc = _make_audit_mocks()

    with _audit_patches(camp_svc, ag_svc, tgt_svc):
        result = runner.invoke(app, [
            "audit", "--region", "US", "--output", "json",
        ])
    assert result.exit_code == 0
    # Should find t1 (1.20 vs 0.35 = +0.85) but not t2 (0.35 vs 0.35 = 0)
    assert "Close Match" in result.output
    assert "1.2" in result.output
    tgt_svc.update.assert_not_called()


def test_audit_fix_dry_run():
    camp_svc, ag_svc, tgt_svc = _make_audit_mocks()

    with _audit_patches(camp_svc, ag_svc, tgt_svc):
        result = runner.invoke(app, [
            "audit", "--region", "US", "--fix", "--dry-run", "--output", "json",
        ])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output
    tgt_svc.update.assert_not_called()


def test_audit_fix_applies():
    camp_svc, ag_svc, tgt_svc = _make_audit_mocks()

    with _audit_patches(camp_svc, ag_svc, tgt_svc):
        result = runner.invoke(app, [
            "audit", "--region", "US", "--fix", "--output", "json",
        ])
    assert result.exit_code == 0
    tgt_svc.update.assert_called_once()
    # Verify the update was called with the correct target ID and default bid
    call_args = tgt_svc.update.call_args
    assert call_args[0][0] == "US"  # region
    updates = call_args[0][1]
    assert len(updates) == 1
    assert updates[0].target_id == "t1"
    assert updates[0].bid == 0.35
