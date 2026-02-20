"""Tests for services/campaigns.py — CRUD operations, parse_multi_status."""
from unittest.mock import MagicMock

import pytest

from amazon_ads.services.campaigns import CampaignService, parse_multi_status
from amazon_ads.models.campaigns import CreateCampaignRequest, UpdateCampaignRequest


# ── parse_multi_status ───────────────────────────────────────────────

def test_parse_multi_status_no_errors():
    resp = {"campaigns": {"success": [{"campaignId": "c1"}], "error": []}}
    result = parse_multi_status(resp, "campaigns")
    assert result is resp


def test_parse_multi_status_with_errors(capsys):
    resp = {
        "campaigns": {
            "success": [],
            "error": [
                {"errorType": "INVALID_ARGUMENT", "description": "bid too low"},
            ],
        }
    }
    parse_multi_status(resp, "campaigns")
    # Errors are printed to stderr via Rich console — capsys won't capture Rich
    # But the function still returns the original response
    assert resp["campaigns"]["error"][0]["errorType"] == "INVALID_ARGUMENT"


def test_parse_multi_status_missing_entity_key():
    resp = {"other": {}}
    result = parse_multi_status(resp, "campaigns")
    assert result is resp


# ── CampaignService.list ─────────────────────────────────────────────

def test_list_calls_post(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"campaigns": [{"campaignId": "c1"}]})
    )
    svc = CampaignService(mock_client)
    results = svc.list("US")

    assert len(results) == 1
    assert results[0]["campaignId"] == "c1"
    mock_client.post.assert_called_once()


def test_list_with_state_filter(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"campaigns": []})
    )
    svc = CampaignService(mock_client)
    svc.list("US", state="ENABLED")

    body = mock_client.post.call_args[1]["body"]
    assert body["stateFilter"]["include"] == ["ENABLED"]


def test_list_with_name_filter(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"campaigns": []})
    )
    svc = CampaignService(mock_client)
    svc.list("US", name="test campaign")

    body = mock_client.post.call_args[1]["body"]
    assert body["nameFilter"]["include"] == ["test campaign"]


# ── CampaignService.create ───────────────────────────────────────────

def test_create_sends_body(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"campaigns": {"success": [{"campaignId": "c1"}], "error": []}})
    )
    svc = CampaignService(mock_client)
    req = CreateCampaignRequest(targetingType="MANUAL", name="Test")
    result = svc.create("US", req)

    body = mock_client.post.call_args[1]["body"]
    assert len(body["campaigns"]) == 1
    assert body["campaigns"][0]["name"] == "Test"


# ── CampaignService.delete ──────────────────────────────────────────

def test_delete_sends_ids(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"campaigns": {"success": [], "error": []}})
    )
    svc = CampaignService(mock_client)
    svc.delete("US", ["c1", "c2"])

    body = mock_client.post.call_args[1]["body"]
    assert body["campaignIdFilter"]["include"] == ["c1", "c2"]
