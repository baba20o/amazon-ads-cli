"""Tests for Pydantic model serialization — alias mapping, defaults, exclude_none."""
from amazon_ads.models.campaigns import (
    CampaignBudget, CreateCampaignRequest, DynamicBidding, UpdateCampaignRequest,
)
from amazon_ads.models.keywords import (
    CreateKeywordRequest, UpdateKeywordRequest,
    CreateNegativeKeywordRequest, CreateCampaignNegativeKeywordRequest,
)
from amazon_ads.models.ad_groups import CreateAdGroupRequest, UpdateAdGroupRequest
from amazon_ads.models.product_ads import CreateProductAdRequest
from amazon_ads.models.reports import ReportConfiguration, CreateReportRequest
from amazon_ads.models.auth import TokenResponse, TokenStatus


# ── Campaign models ───────────────────────────────────────────────────

def test_create_campaign_alias():
    req = CreateCampaignRequest(targetingType="MANUAL", name="Test")
    dumped = req.model_dump(by_alias=True, exclude_none=True)
    assert "targetingType" in dumped
    assert "targeting_type" not in dumped


def test_create_campaign_defaults():
    req = CreateCampaignRequest(targetingType="AUTO", name="Test")
    assert req.state == "ENABLED"
    assert req.budget.budget == 100.0
    assert req.budget.budget_type == "DAILY"


def test_campaign_budget_alias():
    dumped = CampaignBudget(budget=50.0).model_dump(by_alias=True)
    assert dumped["budgetType"] == "DAILY"


def test_update_campaign_exclude_none():
    req = UpdateCampaignRequest(campaignId="123", state="PAUSED")
    dumped = req.model_dump(by_alias=True, exclude_none=True)
    assert "campaignId" in dumped
    assert "name" not in dumped
    assert "endDate" not in dumped


def test_dynamic_bidding_exclude_none():
    dumped = DynamicBidding().model_dump(by_alias=True, exclude_none=True)
    assert "strategy" in dumped
    assert "placementBidding" not in dumped


# ── Keyword models ────────────────────────────────────────────────────

def test_create_keyword_alias():
    req = CreateKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="test", matchType="BROAD",
    )
    dumped = req.model_dump(by_alias=True, exclude_none=True)
    assert dumped["campaignId"] == "c1"
    assert dumped["keywordText"] == "test"
    assert "nativeLanguageLocale" not in dumped


def test_create_keyword_populate_by_name():
    req = CreateKeywordRequest(
        campaign_id="c1", ad_group_id="a1", keyword_text="test", match_type="EXACT",
    )
    assert req.campaign_id == "c1"


def test_create_keyword_defaults():
    req = CreateKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="test", matchType="BROAD",
    )
    assert req.state == "ENABLED"
    assert req.bid == 0.30


def test_update_keyword_minimal():
    dumped = UpdateKeywordRequest(keywordId="k1").model_dump(by_alias=True, exclude_none=True)
    assert dumped == {"keywordId": "k1"}


def test_update_keyword_with_bid():
    dumped = UpdateKeywordRequest(keywordId="k1", bid=0.55).model_dump(by_alias=True, exclude_none=True)
    assert dumped["bid"] == 0.55


def test_negative_keyword_alias():
    req = CreateNegativeKeywordRequest(
        campaignId="c1", adGroupId="a1", keywordText="bad", matchType="NEGATIVE_EXACT",
    )
    dumped = req.model_dump(by_alias=True)
    assert dumped["matchType"] == "NEGATIVE_EXACT"


def test_campaign_negative_keyword_no_ad_group():
    req = CreateCampaignNegativeKeywordRequest(
        campaignId="c1", keywordText="bad", matchType="NEGATIVE_PHRASE",
    )
    dumped = req.model_dump(by_alias=True)
    assert "adGroupId" not in dumped


# ── Ad group models ──────────────────────────────────────────────────

def test_create_ad_group_defaults():
    req = CreateAdGroupRequest(campaignId="c1", name="AG1")
    dumped = req.model_dump(by_alias=True)
    assert dumped["defaultBid"] == 0.45
    assert dumped["state"] == "ENABLED"


def test_update_ad_group_exclude_none():
    dumped = UpdateAdGroupRequest(adGroupId="a1", state="PAUSED").model_dump(
        by_alias=True, exclude_none=True,
    )
    assert "defaultBid" not in dumped


# ── Product ad models ────────────────────────────────────────────────

def test_create_product_ad_alias():
    dumped = CreateProductAdRequest(
        campaignId="c1", adGroupId="a1", asin="B00TEST",
    ).model_dump(by_alias=True)
    assert dumped["asin"] == "B00TEST"
    assert dumped["state"] == "ENABLED"


# ── Report models ────────────────────────────────────────────────────

def test_report_config_alias():
    dumped = ReportConfiguration(
        adProduct="SPONSORED_PRODUCTS", reportTypeId="spCampaigns", timeUnit="DAILY",
    ).model_dump(by_alias=True)
    assert dumped["adProduct"] == "SPONSORED_PRODUCTS"
    assert dumped["reportTypeId"] == "spCampaigns"


def test_create_report_request_alias():
    dumped = CreateReportRequest(
        name="test", startDate="2025-01-01", endDate="2025-01-31",
    ).model_dump(by_alias=True)
    assert dumped["startDate"] == "2025-01-01"


# ── Auth models ──────────────────────────────────────────────────────

def test_token_response_defaults():
    tr = TokenResponse(access_token="abc")
    assert tr.token_type == "bearer"
    assert tr.expires_in == 3600


def test_token_status_no_token():
    ts = TokenStatus(has_token=False, is_expired=True)
    assert ts.expires_at is None
    assert ts.seconds_remaining is None
