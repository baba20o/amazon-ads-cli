"""Tests for services/optimization.py — compare_bids pure function, match type mapping."""
from amazon_ads.services.optimization import OptimizationService, _MATCH_TYPE_MAP


# ── _MATCH_TYPE_MAP ──────────────────────────────────────────────────

def test_match_type_map_broad():
    assert _MATCH_TYPE_MAP["BROAD"] == "KEYWORD_BROAD_MATCH"


def test_match_type_map_exact():
    assert _MATCH_TYPE_MAP["EXACT"] == "KEYWORD_EXACT_MATCH"


def test_match_type_map_phrase():
    assert _MATCH_TYPE_MAP["PHRASE"] == "KEYWORD_PHRASE_MATCH"


# ── compare_bids ─────────────────────────────────────────────────────

def _kw(keyword_id="k1", text="test", match="BROAD", bid=0.50):
    return {
        "keywordId": keyword_id, "keywordText": text, "matchType": match,
        "campaignId": "c1", "adGroupId": "a1", "bid": bid,
    }


def test_overbid_flagged(mock_client):
    svc = OptimizationService(mock_client)
    bid_map = {"KEYWORD_BROAD_MATCH_test": {"low": 0.20, "suggested": 0.30, "high": 0.40}}
    result = svc.compare_bids([_kw(bid=1.00)], bid_map, offset=0.02)
    assert len(result) == 1
    assert result[0]["action"] == "REDUCE"
    assert result[0]["newBid"] == 0.32


def test_within_range_keep(mock_client):
    svc = OptimizationService(mock_client)
    bid_map = {"KEYWORD_BROAD_MATCH_test": {"low": 0.20, "suggested": 0.30, "high": 0.40}}
    result = svc.compare_bids([_kw(bid=0.30)], bid_map, offset=0.02)
    assert result[0]["action"] == "KEEP"


def test_no_suggestion_skipped(mock_client):
    svc = OptimizationService(mock_client)
    result = svc.compare_bids([_kw()], {}, offset=0.02)
    assert len(result) == 0


def test_unknown_match_type_skipped(mock_client):
    svc = OptimizationService(mock_client)
    result = svc.compare_bids([_kw(match="UNKNOWN")], {}, offset=0.02)
    assert len(result) == 0


def test_offset_zero(mock_client):
    svc = OptimizationService(mock_client)
    bid_map = {"KEYWORD_EXACT_MATCH_test": {"low": 0.20, "suggested": 0.35, "high": 0.50}}
    result = svc.compare_bids([_kw(match="EXACT", bid=0.35)], bid_map, offset=0.0)
    assert result[0]["action"] == "KEEP"
    assert result[0]["newBid"] == 0.35


def test_returns_all_bid_levels(mock_client):
    svc = OptimizationService(mock_client)
    bid_map = {"KEYWORD_PHRASE_MATCH_test": {"low": 0.10, "suggested": 0.25, "high": 0.40}}
    result = svc.compare_bids([_kw(match="PHRASE", bid=0.50)], bid_map)
    assert result[0]["suggestedBidLow"] == 0.10
    assert result[0]["suggestedBid"] == 0.25
    assert result[0]["suggestedBidHigh"] == 0.40
