"""Tests for services/keywords.py — EU locale injection, chunking, filters."""
from unittest.mock import MagicMock

import pytest

from amazon_ads.services.keywords import KeywordService, _EU_NATIVE_LOCALE_REGIONS
from amazon_ads.models.keywords import CreateKeywordRequest, UpdateKeywordRequest


def _mock_post_response(data=None):
    """Build a MagicMock that returns json data."""
    return MagicMock(
        json=MagicMock(return_value=data or {"keywords": {"success": [], "error": []}})
    )


# ── EU locale injection ─────────────────────────────────────────────

def test_eu_locale_injected_for_de(mock_client):
    mock_client.post.return_value = _mock_post_response()
    svc = KeywordService(mock_client)

    kw = CreateKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="test", matchType="BROAD",
    )
    svc.create("DE", [kw])

    body = mock_client.post.call_args[1]["body"]
    assert body["keywords"][0]["nativeLanguageLocale"] == "en_GB"


def test_eu_locale_injected_for_fr(mock_client):
    mock_client.post.return_value = _mock_post_response()
    svc = KeywordService(mock_client)

    kw = CreateKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="test", matchType="BROAD",
    )
    svc.create("FR", [kw])

    body = mock_client.post.call_args[1]["body"]
    assert body["keywords"][0]["nativeLanguageLocale"] == "en_GB"


def test_no_locale_for_us(mock_client):
    mock_client.post.return_value = _mock_post_response()
    svc = KeywordService(mock_client)

    kw = CreateKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="test", matchType="BROAD",
    )
    svc.create("US", [kw])

    body = mock_client.post.call_args[1]["body"]
    assert "nativeLanguageLocale" not in body["keywords"][0]


def test_no_locale_for_gb(mock_client):
    mock_client.post.return_value = _mock_post_response()
    svc = KeywordService(mock_client)

    kw = CreateKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="test", matchType="BROAD",
    )
    svc.create("GB", [kw])

    body = mock_client.post.call_args[1]["body"]
    assert "nativeLanguageLocale" not in body["keywords"][0]


def test_eu_native_locale_regions_set():
    assert _EU_NATIVE_LOCALE_REGIONS == {"DE", "FR", "IT", "ES"}


# ── Chunking ─────────────────────────────────────────────────────────

def test_create_chunks(mock_client):
    """Creating 3 keywords with chunk_size=2 should make 2 API calls."""
    mock_client.post.return_value = _mock_post_response()
    svc = KeywordService(mock_client)

    keywords = [
        CreateKeywordRequest(
            campaignId="c1", adGroupId="a1", keywordText=f"kw{i}", matchType="BROAD",
        )
        for i in range(3)
    ]
    results = svc.create("US", keywords, chunk_size=2)
    assert mock_client.post.call_count == 2
    assert len(results) == 2


# ── List filters ─────────────────────────────────────────────────────

def test_list_with_campaign_filter(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"keywords": []})
    )
    svc = KeywordService(mock_client)
    svc.list("US", campaign_id="c1")

    body = mock_client.post.call_args[1]["body"]
    assert body["campaignIdFilter"]["include"] == ["c1"]


def test_list_with_match_type_filter(mock_client):
    mock_client.post.return_value = MagicMock(
        json=MagicMock(return_value={"keywords": []})
    )
    svc = KeywordService(mock_client)
    svc.list("US", match_type="exact")

    body = mock_client.post.call_args[1]["body"]
    assert body["matchTypeFilter"]["include"] == ["EXACT"]
