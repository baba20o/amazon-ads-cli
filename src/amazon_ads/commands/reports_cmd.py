"""CLI commands for reporting."""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.reports import REPORT_TYPE_DEFAULTS
from amazon_ads.services.reporting import ReportingService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="reports", help="Create and download Amazon Ads reports.")

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]


def _build_client(verbose: bool = False) -> tuple[AmazonAdsClient, ReportingService]:
    config = get_config()
    auth = AuthManager(config)
    client = AmazonAdsClient(config, auth, verbose=verbose)
    return client, ReportingService(client)


@app.command("create")
def create_report(
    region: Annotated[str, typer.Option("--region", "-r", help="Region")] = "US",
    start_date: Annotated[str, typer.Option("--start-date", help="Start date (YYYY-MM-DD)")] = ...,
    end_date: Annotated[str, typer.Option("--end-date", help="End date (YYYY-MM-DD)")] = ...,
    time_unit: Annotated[str, typer.Option("--time-unit", help="DAILY or SUMMARY")] = "DAILY",
    report_type: Annotated[str, typer.Option("--report-type", help="spCampaigns, spKeywords, etc.")] = "spCampaigns",
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for report completion and download")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create an async report. Use --wait to poll and download automatically."""
    client, service = _build_client(verbose)
    try:
        console.print(f"Creating {report_type} report for {region} ({start_date} to {end_date})...")

        report_id = service.create_report(
            region=region,
            start_date=start_date,
            end_date=end_date,
            time_unit=time_unit.upper(),
            report_type=report_type,
        )

        if not wait:
            result = {"reportId": report_id, "region": region, "status": "SUBMITTED"}
            print_output(result, output, title="Report Created")
            return

        console.print(f"Report submitted: {report_id}. Polling for completion...")
        rows = service.wait_and_download(region, report_id)
        console.print(f"Report downloaded: {len(rows)} rows")
        print_output(rows, output, title=f"Report ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("status")
def report_status(
    report_id: Annotated[str, typer.Option("--report-id", help="Report ID to check")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait and download when ready")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Check report status. Use --wait to poll until complete and download."""
    client, service = _build_client(verbose)
    try:
        if not wait:
            status = service.get_report_status(region, report_id)
            print_output(status, output, title="Report Status")
            return

        console.print(f"Waiting for report {report_id}...")
        rows = service.wait_and_download(region, report_id)
        console.print(f"Report downloaded: {len(rows)} rows")
        print_output(rows, output, title=f"Report ({region})")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("summary")
def performance_summary(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL' for all regions)")] = "US",
    timeframe: Annotated[str, typer.Option("--timeframe", "-t", help="daily, monthly, yearly, or custom")] = "daily",
    start_date: Annotated[str | None, typer.Option("--start-date", help="Start date for custom timeframe")] = None,
    end_date: Annotated[str | None, typer.Option("--end-date", help="End date for custom timeframe")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Get performance summary with ACoS calculation."""
    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]
    client, service = _build_client(verbose)

    try:
        summaries = []
        for reg in regions:
            console.print(f"Generating {timeframe} summary for {reg}...")
            summary = service.get_performance_summary(
                region=reg,
                timeframe=timeframe.lower(),
                start_date=start_date,
                end_date=end_date,
            )
            summaries.append(summary)

        columns = [
            "region", "startDate", "endDate", "totalCost", "totalSales",
            "totalImpressions", "totalClicks", "acos", "campaignCount",
        ]
        print_output(summaries, output, columns=columns, title="Performance Summary")
    except (RuntimeError, ValueError) as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()
