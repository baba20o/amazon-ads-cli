"""Ad group data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateAdGroupRequest(BaseModel):
    campaign_id: str = Field(alias="campaignId")
    name: str
    state: str = "ENABLED"
    default_bid: float = Field(default=0.45, alias="defaultBid")

    model_config = {"populate_by_name": True}


class UpdateAdGroupRequest(BaseModel):
    ad_group_id: str = Field(alias="adGroupId")
    state: str | None = None
    name: str | None = None
    default_bid: float | None = Field(default=None, alias="defaultBid")

    model_config = {"populate_by_name": True}
