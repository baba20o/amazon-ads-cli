"""Tests for services/sync.py — _extract_id helper."""
import pytest
from amazon_ads.services.sync import _extract_id


def test_extract_id_success_list():
    resp = {"campaigns": {"success": [{"campaignId": "c123"}]}}
    assert _extract_id(resp, "campaigns", "campaignId") == "c123"


def test_extract_id_empty_success():
    resp = {"campaigns": {"success": []}}
    assert _extract_id(resp, "campaigns", "campaignId") is None


def test_extract_id_flat_list_raises():
    """Flat list (no 'success' wrapper) hits .get() on a list — current code raises."""
    resp = {"campaigns": [{"campaignId": "c456"}]}
    with pytest.raises(AttributeError):
        _extract_id(resp, "campaigns", "campaignId")


def test_extract_id_missing_entity_key():
    assert _extract_id({"other": "data"}, "campaigns", "campaignId") is None


def test_extract_id_missing_id_key():
    resp = {"campaigns": {"success": [{"name": "test"}]}}
    assert _extract_id(resp, "campaigns", "campaignId") == ""
