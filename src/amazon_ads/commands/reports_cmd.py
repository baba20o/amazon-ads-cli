"""CLI commands for reporting."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated

import typer
from rich.console import Console

from amazon_ads.auth import AuthManager
from amazon_ads.client import AmazonAdsClient
from amazon_ads.config import get_config
from amazon_ads.models.reports import REPORT_TYPE_DEFAULTS
from amazon_ads.services.report_queue import QueueEntry, ReportQueue
from amazon_ads.services.reporting import ReportingService
from amazon_ads.utils.errors import handle_error
from amazon_ads.utils.output import OutputFormat, print_output

console = Console(stderr=True)
app = typer.Typer(name="reports", help="Create and download Amazon Ads reports.")

ALL_REGIONS = ["US", "CA", "GB", "DE", "FR", "ES", "IT", "AU"]
DEFAULT_REPORT_TYPES = ["spCampaigns", "spKeywords", "spSearchTerm", "spTargeting"]


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
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", help="Filter by campaign ID(s), comma-separated")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", help="Filter by ad group ID(s), comma-separated")] = None,
    columns: Annotated[str | None, typer.Option("--columns", help="Comma-separated column list")] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help="Wait for report completion and download")] = False,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Create an async report. Use --wait to poll and download automatically."""
    client, service = _build_client(verbose)
    try:
        campaign_ids = [c.strip() for c in campaign_id.split(",") if c.strip()] if campaign_id else None
        ad_group_ids = [a.strip() for a in ad_group_id.split(",") if a.strip()] if ad_group_id else None
        column_list = [c.strip() for c in columns.split(",") if c.strip()] if columns else None

        console.print(f"Creating {report_type} report for {region} ({start_date} to {end_date})...")

        report_id = service.create_report(
            region=region,
            start_date=start_date,
            end_date=end_date,
            time_unit=time_unit.upper(),
            report_type=report_type,
            campaign_ids=campaign_ids,
            ad_group_ids=ad_group_ids,
            columns=column_list,
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


# ── Queue commands ────────────────────────────────────────────────────


def _get_queue() -> ReportQueue:
    config = get_config()
    return ReportQueue(queue_dir=config.settings.queue_dir)


@app.command("submit")
def submit_reports(
    region: Annotated[str, typer.Option("--region", "-r", help="Region (or 'ALL')")] = "US",
    start_date: Annotated[str, typer.Option("--start-date", help="Start date (YYYY-MM-DD)")] = ...,
    end_date: Annotated[str, typer.Option("--end-date", help="End date (YYYY-MM-DD)")] = ...,
    report_type: Annotated[str | None, typer.Option("--report-type", help="Report type (default: all 4)")] = None,
    campaign_id: Annotated[str | None, typer.Option("--campaign-id", help="Filter by campaign ID(s), comma-separated")] = None,
    ad_group_id: Annotated[str | None, typer.Option("--ad-group-id", help="Filter by ad group ID(s), comma-separated")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Submit report(s) to the queue without waiting. Tracks them for later download."""
    regions = ALL_REGIONS if region.upper() == "ALL" else [region.upper()]
    types = [report_type] if report_type else DEFAULT_REPORT_TYPES

    campaign_ids = [c.strip() for c in campaign_id.split(",") if c.strip()] if campaign_id else None
    ad_group_ids = [a.strip() for a in ad_group_id.split(",") if a.strip()] if ad_group_id else None

    client, service = _build_client(verbose)
    queue = _get_queue()
    submitted = []

    try:
        for reg in regions:
            for rtype in types:
                console.print(f"Submitting {rtype} for {reg}...")
                rid = service.create_report(
                    region=reg,
                    start_date=start_date,
                    end_date=end_date,
                    report_type=rtype,
                    campaign_ids=campaign_ids,
                    ad_group_ids=ad_group_ids,
                )
                entry = QueueEntry(
                    report_id=rid,
                    region=reg,
                    report_type=rtype,
                    start_date=start_date,
                    end_date=end_date,
                    submitted_at=datetime.now().isoformat(),
                    filters={"campaign_ids": campaign_ids, "ad_group_ids": ad_group_ids},
                )
                queue.add(entry)
                submitted.append({
                    "reportId": rid[:12] + "...",
                    "region": reg,
                    "type": rtype,
                    "status": "SUBMITTED",
                })
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()

    console.print(f"\n[bold green]{len(submitted)} report(s) submitted to queue.[/bold green]")
    print_output(submitted, output, title="Submitted Reports")


@app.command("queue")
def list_queue(
    status_filter: Annotated[str | None, typer.Option("--status", "-s", help="Filter by status")] = None,
    region: Annotated[str | None, typer.Option("--region", "-r", help="Filter by region")] = None,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
) -> None:
    """List all tracked reports in the queue."""
    queue = _get_queue()
    entries = queue.get_all(status=status_filter, region=region)

    if not entries:
        console.print("Queue is empty.")
        raise typer.Exit(0)

    rows = []
    for e in entries:
        rows.append({
            "reportId": e.report_id[:12] + "...",
            "region": e.region,
            "type": e.report_type,
            "dates": f"{e.start_date} to {e.end_date}",
            "status": e.status,
            "submitted": e.submitted_at[:19] if e.submitted_at else "",
            "rows": e.row_count or "",
        })
    print_output(rows, output, title="Report Queue")


@app.command("poll")
def poll_reports(
    region: Annotated[str | None, typer.Option("--region", "-r", help="Only poll reports for this region")] = None,
    download: Annotated[bool, typer.Option("--download/--no-download", help="Auto-download completed reports")] = True,
    output: Annotated[OutputFormat, typer.Option("--output", "-o")] = OutputFormat.TABLE,
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Check status of all pending reports. Downloads completed ones by default."""
    queue = _get_queue()
    pending = queue.get_pending()
    if region:
        pending = [e for e in pending if e.region.upper() == region.upper()]

    if not pending:
        console.print("No pending reports in queue.")
        raise typer.Exit(0)

    client, service = _build_client(verbose)
    results = []

    try:
        for entry in pending:
            console.print(f"Checking {entry.report_type} ({entry.region})...")
            try:
                api_status = service.get_report_status(entry.region, entry.report_id)
                state = api_status.get("status", "UNKNOWN")

                if state == "COMPLETED" and download:
                    url = api_status.get("url")
                    if url:
                        rows = service._download_and_decompress(url)
                        dl_path = queue.download_path(entry)
                        with open(dl_path, "w") as f:
                            json.dump(rows, f, indent=2, default=str)
                        queue.update_status(
                            entry.report_id, "DOWNLOADED",
                            completed_at=datetime.now().isoformat(),
                            download_path=str(dl_path),
                            row_count=len(rows),
                        )
                        state = "DOWNLOADED"
                        console.print(f"  Downloaded {len(rows)} rows -> {dl_path}")
                    else:
                        queue.update_status(entry.report_id, state)
                elif state in ("FAILURE", "CANCELLED"):
                    queue.update_status(entry.report_id, state)
                else:
                    queue.update_status(entry.report_id, state)

                results.append({
                    "reportId": entry.report_id[:12] + "...",
                    "region": entry.region,
                    "type": entry.report_type,
                    "status": state,
                })
            except RuntimeError as e:
                console.print(f"  Error: {e}")
                results.append({
                    "reportId": entry.report_id[:12] + "...",
                    "region": entry.region,
                    "type": entry.report_type,
                    "status": "ERROR",
                })
    finally:
        client.close()

    print_output(results, output, title="Poll Results")


@app.command("download")
def download_report(
    report_id: Annotated[str, typer.Option("--report-id", help="Report ID to download")] = ...,
    region: Annotated[str, typer.Option("--region", "-r")] = "US",
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Download a specific completed report by ID."""
    queue = _get_queue()
    entry = queue.get_by_id(report_id)

    client, service = _build_client(verbose)
    try:
        api_status = service.get_report_status(region, report_id)
        state = api_status.get("status", "UNKNOWN")

        if state != "COMPLETED":
            console.print(f"Report is not ready: {state}")
            raise typer.Exit(1)

        url = api_status.get("url")
        if not url:
            console.print("Report completed but no download URL provided.")
            raise typer.Exit(1)

        rows = service._download_and_decompress(url)

        if entry:
            dl_path = queue.download_path(entry)
        else:
            # Not in queue — use a generic path
            config = get_config()
            from pathlib import Path
            dl_dir = Path(config.settings.queue_dir) / "reports"
            dl_dir.mkdir(parents=True, exist_ok=True)
            dl_path = dl_dir / f"{region}-{report_id[:8]}.json"

        with open(dl_path, "w") as f:
            json.dump(rows, f, indent=2, default=str)

        if entry:
            queue.update_status(
                report_id, "DOWNLOADED",
                completed_at=datetime.now().isoformat(),
                download_path=str(dl_path),
                row_count=len(rows),
            )

        console.print(f"Downloaded {len(rows)} rows -> {dl_path}")
    except RuntimeError as e:
        handle_error(e)
        raise typer.Exit(1)
    finally:
        client.close()


@app.command("clean")
def clean_queue(
    days: Annotated[int, typer.Option("--days", help="Remove entries older than N days")] = 30,
    all_entries: Annotated[bool, typer.Option("--all", help="Clear entire queue")] = False,
) -> None:
    """Remove old or completed entries from the report queue."""
    queue = _get_queue()

    if all_entries:
        removed = queue.clear()
    else:
        removed = queue.remove_older_than(days)

    console.print(f"Removed {removed} queue entries.")
