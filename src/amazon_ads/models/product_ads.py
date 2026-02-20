"""Product ad data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateProductAdRequest(BaseModel):
    campaign_id: str = Field(alias="campaignId")
    ad_group_id: str = Field(alias="adGroupId")
    asin: str
    state: str = "ENABLED"

    model_config = {"populate_by_name": True}
