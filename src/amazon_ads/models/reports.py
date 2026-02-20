"""Report data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


# Default campaign report columns matching the legacy script
DEFAULT_CAMPAIGN_COLUMNS = [
    "date",
    "campaignName",
    "campaignId",
    "impressions",
    "clicks",
    "cost",
    "sales1d",
    "purchases1d",
    "unitsSoldClicks1d",
    "attributedSalesSameSku1d",
    "unitsSoldSameSku1d",
    "clickThroughRate",
    "costPerClick",
    "campaignStatus",
]

# Summary report columns (for performance summaries)
SUMMARY_COLUMNS = [
    "campaignId",
    "campaignName",
    "impressions",
    "clicks",
    "cost",
    "sales1d",
]

# Keyword-level report columns
KEYWORD_COLUMNS = [
    "date",
    "campaignName",
    "campaignId",
    "adGroupName",
    "adGroupId",
    "keywordId",
    "keyword",
    "matchType",
    "impressions",
    "clicks",
    "cost",
    "sales1d",
    "purchases1d",
    "clickThroughRate",
    "costPerClick",
    "keywordBid",
    "keywordStatus",
]

# Search term report columns
SEARCH_TERM_COLUMNS = [
    "date",
    "campaignName",
    "campaignId",
    "adGroupName",
    "adGroupId",
    "keywordId",
    "keyword",
    "matchType",
    "searchTerm",
    "impressions",
    "clicks",
    "cost",
    "sales1d",
    "purchases1d",
    "clickThroughRate",
    "costPerClick",
]

# Targeting report columns (product/category targets)
TARGET_COLUMNS = [
    "date",
    "campaignName",
    "campaignId",
    "adGroupName",
    "adGroupId",
    "targetId",
    "targetingExpression",
    "targetingType",
    "impressions",
    "clicks",
    "cost",
    "sales1d",
    "purchases1d",
    "clickThroughRate",
    "costPerClick",
]

# Advertised product report columns
ADVERTISED_PRODUCT_COLUMNS = [
    "date",
    "campaignName",
    "campaignId",
    "adGroupName",
    "adGroupId",
    "advertisedAsin",
    "advertisedSku",
    "impressions",
    "clicks",
    "cost",
    "sales1d",
    "purchases1d",
    "unitsSoldClicks1d",
    "clickThroughRate",
    "costPerClick",
]

# Mapping from reportTypeId → (columns, groupBy)
REPORT_TYPE_DEFAULTS: dict[str, tuple[list[str], list[str]]] = {
    "spCampaigns": (DEFAULT_CAMPAIGN_COLUMNS, ["campaign"]),
    "spKeywords": (KEYWORD_COLUMNS, ["keyword"]),
    "spSearchTerm": (SEARCH_TERM_COLUMNS, ["searchTerm"]),
    "spTargeting": (TARGET_COLUMNS, ["targeting"]),
    "spAdvertisedProduct": (ADVERTISED_PRODUCT_COLUMNS, ["advertiser"]),
}


class ReportConfiguration(BaseModel):
    """Report configuration for Amazon Ads async reports."""
    ad_product: str = Field(default="SPONSORED_PRODUCTS", alias="adProduct")
    group_by: list[str] = Field(default=["campaign"], alias="groupBy")
    columns: list[str] = Field(default_factory=lambda: DEFAULT_CAMPAIGN_COLUMNS)
    report_type_id: str = Field(default="spCampaigns", alias="reportTypeId")
    time_unit: str = Field(default="DAILY", alias="timeUnit")  # DAILY or SUMMARY
    format: str = "GZIP_JSON"

    model_config = {"populate_by_name": True}


class CreateReportRequest(BaseModel):
    """Request to create an async report."""
    name: str
    start_date: str = Field(alias="startDate")
    end_date: str = Field(alias="endDate")
    configuration: ReportConfiguration = Field(default_factory=ReportConfiguration)

    model_config = {"populate_by_name": True}
