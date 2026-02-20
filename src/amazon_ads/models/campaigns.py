"""Campaign data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CampaignBudget(BaseModel):
    budget_type: str = Field(default="DAILY", alias="budgetType")
    budget: float = 100.0

    model_config = {"populate_by_name": True}


class DynamicBiddingStrategy(BaseModel):
    strategy: str = "LEGACY_FOR_SALES"


class PlacementBid(BaseModel):
    placement: str  # PLACEMENT_TOP, PLACEMENT_PRODUCT_PAGE, PLACEMENT_REST_OF_SEARCH
    percentage: float


class DynamicBidding(BaseModel):
    strategy: str = "LEGACY_FOR_SALES"
    placement_bidding: list[PlacementBid] | None = Field(default=None, alias="placementBidding")

    model_config = {"populate_by_name": True}


class CreateCampaignRequest(BaseModel):
    name: str
    targeting_type: str = Field(alias="targetingType")  # AUTO or MANUAL
    state: str = "ENABLED"
    budget: CampaignBudget = CampaignBudget()
    dynamic_bidding: DynamicBidding = Field(
        default_factory=lambda: DynamicBidding(), alias="dynamicBidding"
    )
    start_date: str | None = Field(default=None, alias="startDate")
    end_date: str | None = Field(default=None, alias="endDate")
    portfolio_id: str | None = Field(default=None, alias="portfolioId")

    model_config = {"populate_by_name": True}


class UpdateCampaignRequest(BaseModel):
    campaign_id: str = Field(alias="campaignId")
    state: str | None = None
    name: str | None = None
    budget: CampaignBudget | None = None
    dynamic_bidding: DynamicBidding | None = Field(default=None, alias="dynamicBidding")
    end_date: str | None = Field(default=None, alias="endDate")
    portfolio_id: str | None = Field(default=None, alias="portfolioId")

    model_config = {"populate_by_name": True}
