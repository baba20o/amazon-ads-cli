"""Keyword data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateKeywordRequest(BaseModel):
    campaign_id: str = Field(alias="campaignId")
    ad_group_id: str = Field(alias="adGroupId")
    keyword_text: str = Field(alias="keywordText")
    match_type: str = Field(alias="matchType")  # BROAD, PHRASE, EXACT
    state: str = "ENABLED"
    bid: float = 0.30
    native_language_keyword: str | None = Field(default=None, alias="nativeLanguageKeyword")
    native_language_locale: str | None = Field(default=None, alias="nativeLanguageLocale")

    model_config = {"populate_by_name": True}


class UpdateKeywordRequest(BaseModel):
    keyword_id: str = Field(alias="keywordId")
    state: str | None = None
    bid: float | None = None

    model_config = {"populate_by_name": True}


class CreateNegativeKeywordRequest(BaseModel):
    """Negative keyword at the ad group level."""
    campaign_id: str = Field(alias="campaignId")
    ad_group_id: str = Field(alias="adGroupId")
    keyword_text: str = Field(alias="keywordText")
    match_type: str = Field(alias="matchType")  # NEGATIVE_EXACT, NEGATIVE_PHRASE
    state: str = "ENABLED"

    model_config = {"populate_by_name": True}


class CreateCampaignNegativeKeywordRequest(BaseModel):
    """Negative keyword at the campaign level."""
    campaign_id: str = Field(alias="campaignId")
    keyword_text: str = Field(alias="keywordText")
    match_type: str = Field(alias="matchType")  # NEGATIVE_EXACT, NEGATIVE_PHRASE
    state: str = "ENABLED"

    model_config = {"populate_by_name": True}


class UpdateProductTargetRequest(BaseModel):
    """Update a product/category targeting clause (bid and/or state)."""
    target_id: str = Field(alias="targetId")
    state: str | None = None
    bid: float | None = None

    model_config = {"populate_by_name": True}


class CreateProductTargetRequest(BaseModel):
    """Product/category targeting expression."""
    campaign_id: str = Field(alias="campaignId")
    ad_group_id: str = Field(alias="adGroupId")
    state: str = "ENABLED"
    bid: float = 0.30
    expression: list[dict] = Field(alias="expression")
    expression_type: str = Field(default="manual", alias="expressionType")

    model_config = {"populate_by_name": True}


class CreateNegativeTargetRequest(BaseModel):
    """Negative product targeting expression."""
    campaign_id: str = Field(alias="campaignId")
    ad_group_id: str = Field(alias="adGroupId")
    state: str = "ENABLED"
    expression: list[dict] = Field(alias="expression")
    expression_type: str = Field(default="manual", alias="expressionType")

    model_config = {"populate_by_name": True}
