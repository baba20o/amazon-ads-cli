"""Reporting service for Amazon Ads async reports."""

from __future__ import annotations

import gzip
import time
from datetime import date, datetime
from typing import Any

import httpx
from rich.console import Console

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES
from amazon_ads.models.reports import (
    CreateReportRequest,
    ReportConfiguration,
    ReportFilter,
    REPORT_TYPE_DEFAULTS,
    SUMMARY_COLUMNS,
)

console = Console(stderr=True)

REPORT_CT_REQUEST = CONTENT_TYPES["reports_request"]
REPORT_CT_RESPONSE = CONTENT_TYPES["reports_response"]


class ReportingService:
    """Service for creating, polling, and downloading Amazon Ads reports."""

    def __init__(self, client: AmazonAdsClient) -> None:
        self._client = client

    def create_report(
        self,
        region: str,
        start_date: str,
        end_date: str,
        columns: list[str] | None = None,
        time_unit: str = "DAILY",
        report_type: str = "spCampaigns",
        group_by: list[str] | None = None,
        campaign_ids: list[str] | None = None,
        ad_group_ids: list[str] | None = None,
    ) -> str:
        """Create an async report and return the report ID.

        Args:
            region: Country code.
            start_date: Start date (YYYY-MM-DD).
            end_date: End date (YYYY-MM-DD).
            columns: Report columns. Defaults to campaign columns.
            time_unit: DAILY or SUMMARY.
            report_type: Report type ID (spCampaigns, spKeywords, etc.).
            group_by: Grouping dimensions.
            campaign_ids: Filter by campaign ID(s).
            ad_group_ids: Filter by ad group ID(s).

        Returns:
            The report ID string.
        """
        # Auto-select columns and groupBy based on report type if not provided
        default_columns, default_group_by = REPORT_TYPE_DEFAULTS.get(
            report_type, (SUMMARY_COLUMNS, ["campaign"])
        )

        # Build filters
        filters: list[ReportFilter] = []
        if campaign_ids:
            filters.append(ReportFilter(field="campaignId", values=campaign_ids))
        if ad_group_ids:
            filters.append(ReportFilter(field="adGroupId", values=ad_group_ids))

        config = ReportConfiguration(
            adProduct="SPONSORED_PRODUCTS",
            groupBy=group_by or default_group_by,
            columns=columns or default_columns,
            reportTypeId=report_type,
            timeUnit=time_unit,
            filters=filters if filters else None,
            format="GZIP_JSON",
        )
        request = CreateReportRequest(
            name=f"report-{region}-{start_date}",
            startDate=start_date,
            endDate=end_date,
            configuration=config,
        )
        body = request.model_dump(by_alias=True, exclude_none=True)
        response = self._client.post(
            "/reporting/reports",
            region,
            body=body,
            content_type=REPORT_CT_REQUEST,
            accept=REPORT_CT_REQUEST,
        )
        data = response.json()
        return data["reportId"]

    def get_report_status(self, region: str, report_id: str) -> dict[str, Any]:
        """Check the status of an async report.

        Returns:
            Dict with 'status', 'url' (if completed), etc.
        """
        response = self._client.get(
            f"/reporting/reports/{report_id}",
            region,
            content_type=REPORT_CT_RESPONSE,
            accept=REPORT_CT_RESPONSE,
        )
        return response.json()

    def wait_and_download(
        self,
        region: str,
        report_id: str,
        poll_interval: int = 30,
        max_wait: int = 600,
    ) -> list[dict[str, Any]]:
        """Poll until report is ready, then download and decompress.

        Args:
            region: Country code.
            report_id: The report ID to poll.
            poll_interval: Seconds between status checks.
            max_wait: Max seconds to wait before timing out.

        Returns:
            List of report row dicts.
        """
        elapsed = 0
        while elapsed < max_wait:
            status = self.get_report_status(region, report_id)
            state = status.get("status", "UNKNOWN")

            if state == "COMPLETED":
                url = status.get("url")
                if not url:
                    raise RuntimeError("Report completed but no download URL provided")
                return self._download_and_decompress(url)

            if state in ("FAILURE", "CANCELLED"):
                raise RuntimeError(f"Report {report_id} failed with status: {state}")

            console.print(f"Report status: {state}. Waiting {poll_interval}s...")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise RuntimeError(f"Report {report_id} timed out after {max_wait}s")

    def get_performance_summary(
        self,
        region: str,
        timeframe: str = "daily",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Get a performance summary with ACoS calculation.

        Args:
            region: Country code.
            timeframe: daily, monthly, yearly, or custom.
            start_date: Required if timeframe is custom.
            end_date: Required if timeframe is custom.

        Returns:
            Summary dict with totals and ACoS.
        """
        today = date.today()
        if timeframe == "daily":
            start = today.isoformat()
            end = start
        elif timeframe == "monthly":
            start = today.replace(day=1).isoformat()
            end = today.isoformat()
        elif timeframe == "yearly":
            start = today.replace(month=1, day=1).isoformat()
            end = today.isoformat()
        elif timeframe == "custom":
            if not start_date or not end_date:
                raise ValueError("start_date and end_date required for custom timeframe")
            start = start_date
            end = end_date
        else:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        report_id = self.create_report(
            region=region,
            start_date=start,
            end_date=end,
            columns=SUMMARY_COLUMNS,
            time_unit="SUMMARY",
            report_type="spCampaigns",
        )

        rows = self.wait_and_download(region, report_id)

        # Calculate totals
        total_cost = sum(float(r.get("cost", 0)) for r in rows)
        total_sales = sum(float(r.get("sales1d", 0)) for r in rows)
        total_impressions = sum(int(r.get("impressions", 0)) for r in rows)
        total_clicks = sum(int(r.get("clicks", 0)) for r in rows)
        acos = round((total_cost / total_sales) * 100, 2) if total_sales > 0 else 0.0

        return {
            "region": region,
            "startDate": start,
            "endDate": end,
            "timeframe": timeframe,
            "totalCost": round(total_cost, 2),
            "totalSales": round(total_sales, 2),
            "totalImpressions": total_impressions,
            "totalClicks": total_clicks,
            "acos": acos,
            "campaignCount": len(rows),
        }

    def _download_and_decompress(self, url: str) -> list[dict[str, Any]]:
        """Download a GZIP report and decompress to JSON."""
        with httpx.Client(timeout=120.0) as http:
            response = http.get(url)
            response.raise_for_status()

        decompressed = gzip.decompress(response.content)
        import json
        return json.loads(decompressed)
