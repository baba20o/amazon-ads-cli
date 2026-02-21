"""Tests for services/reporting.py — report creation, polling, ACoS calc."""
from unittest.mock import MagicMock, patch
import gzip
import json

import pytest

from amazon_ads.services.reporting import ReportingService


def _json_resp(data):
    return MagicMock(json=MagicMock(return_value=data))


# ── create_report ────────────────────────────────────────────────────

def test_create_report_returns_id(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt-123"})
    svc = ReportingService(mock_client)

    report_id = svc.create_report("US", "2025-01-01", "2025-01-31")
    assert report_id == "rpt-123"


def test_create_report_posts_body(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt"})
    svc = ReportingService(mock_client)

    svc.create_report("US", "2025-01-01", "2025-01-31", time_unit="SUMMARY")
    body = mock_client.post.call_args[1]["body"]
    assert body["startDate"] == "2025-01-01"
    assert body["configuration"]["timeUnit"] == "SUMMARY"


# ── get_report_status ────────────────────────────────────────────────

def test_get_report_status(mock_client):
    mock_client.get.return_value = _json_resp({"status": "COMPLETED", "url": "https://dl.example.com"})
    svc = ReportingService(mock_client)

    status = svc.get_report_status("US", "rpt-123")
    assert status["status"] == "COMPLETED"


# ── wait_and_download ────────────────────────────────────────────────

def test_wait_completed_immediately(mock_client):
    mock_client.get.return_value = _json_resp({"status": "COMPLETED", "url": "https://dl.example.com/report.gz"})

    svc = ReportingService(mock_client)
    report_data = [{"campaign": "c1", "cost": 10}]
    compressed = gzip.compress(json.dumps(report_data).encode())

    with patch("amazon_ads.services.reporting.httpx.Client") as MockHTTP:
        dl_resp = MagicMock()
        dl_resp.content = compressed
        dl_resp.raise_for_status = MagicMock()
        mock_http_instance = MagicMock()
        mock_http_instance.get.return_value = dl_resp
        mock_http_instance.__enter__ = MagicMock(return_value=mock_http_instance)
        mock_http_instance.__exit__ = MagicMock(return_value=False)
        MockHTTP.return_value = mock_http_instance

        result = svc.wait_and_download("US", "rpt-123")
        assert result == report_data


def test_wait_failure_raises(mock_client):
    mock_client.get.return_value = _json_resp({"status": "FAILURE"})
    svc = ReportingService(mock_client)

    with pytest.raises(RuntimeError, match="failed with status"):
        svc.wait_and_download("US", "rpt-fail")


def test_wait_timeout_raises(mock_client):
    mock_client.get.return_value = _json_resp({"status": "PROCESSING"})
    svc = ReportingService(mock_client)

    with patch("amazon_ads.services.reporting.time.sleep"):
        with pytest.raises(RuntimeError, match="timed out"):
            svc.wait_and_download("US", "rpt-slow", poll_interval=1, max_wait=2)


# ── ACoS calculation via get_performance_summary ─────────────────────

def test_acos_calculation(mock_client):
    # Simulate report creation + polling + download
    mock_client.post.return_value = _json_resp({"reportId": "rpt"})
    mock_client.get.return_value = _json_resp({"status": "COMPLETED", "url": "https://dl.example.com/r.gz"})

    rows = [
        {"cost": "10.0", "sales1d": "100.0", "impressions": "1000", "clicks": "50"},
        {"cost": "5.0", "sales1d": "50.0", "impressions": "500", "clicks": "25"},
    ]
    compressed = gzip.compress(json.dumps(rows).encode())

    svc = ReportingService(mock_client)

    with patch("amazon_ads.services.reporting.httpx.Client") as MockHTTP:
        dl_resp = MagicMock()
        dl_resp.content = compressed
        dl_resp.raise_for_status = MagicMock()
        mock_http_instance = MagicMock()
        mock_http_instance.get.return_value = dl_resp
        mock_http_instance.__enter__ = MagicMock(return_value=mock_http_instance)
        mock_http_instance.__exit__ = MagicMock(return_value=False)
        MockHTTP.return_value = mock_http_instance

        summary = svc.get_performance_summary("US", timeframe="custom", start_date="2025-01-01", end_date="2025-01-31")

    assert summary["totalCost"] == 15.0
    assert summary["totalSales"] == 150.0
    assert summary["acos"] == 10.0  # (15 / 150) * 100
    assert summary["totalImpressions"] == 1500
    assert summary["totalClicks"] == 75


def test_acos_zero_sales(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt"})
    mock_client.get.return_value = _json_resp({"status": "COMPLETED", "url": "https://dl.example.com/r.gz"})

    rows = [{"cost": "10.0", "sales1d": "0", "impressions": "100", "clicks": "5"}]
    compressed = gzip.compress(json.dumps(rows).encode())

    svc = ReportingService(mock_client)

    with patch("amazon_ads.services.reporting.httpx.Client") as MockHTTP:
        dl_resp = MagicMock()
        dl_resp.content = compressed
        dl_resp.raise_for_status = MagicMock()
        mock_http_instance = MagicMock()
        mock_http_instance.get.return_value = dl_resp
        mock_http_instance.__enter__ = MagicMock(return_value=mock_http_instance)
        mock_http_instance.__exit__ = MagicMock(return_value=False)
        MockHTTP.return_value = mock_http_instance

        summary = svc.get_performance_summary("US", timeframe="custom", start_date="2025-01-01", end_date="2025-01-31")

    assert summary["acos"] == 0.0


# ── Report filters ────────────────────────────────────────────────────

def test_create_report_with_campaign_filter(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt-f1"})
    svc = ReportingService(mock_client)

    svc.create_report("US", "2025-01-01", "2025-01-31", campaign_ids=["111", "222"])

    body = mock_client.post.call_args[1]["body"]
    filters = body["configuration"]["filters"]
    assert len(filters) == 1
    assert filters[0]["field"] == "campaignId"
    assert filters[0]["values"] == ["111", "222"]


def test_create_report_with_ad_group_filter(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt-f2"})
    svc = ReportingService(mock_client)

    svc.create_report("US", "2025-01-01", "2025-01-31", ad_group_ids=["ag1"])

    body = mock_client.post.call_args[1]["body"]
    filters = body["configuration"]["filters"]
    assert len(filters) == 1
    assert filters[0]["field"] == "adGroupId"


def test_create_report_no_filters_omits_field(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt-nf"})
    svc = ReportingService(mock_client)

    svc.create_report("US", "2025-01-01", "2025-01-31")

    body = mock_client.post.call_args[1]["body"]
    assert "filters" not in body["configuration"]


def test_create_report_custom_columns(mock_client):
    mock_client.post.return_value = _json_resp({"reportId": "rpt-cc"})
    svc = ReportingService(mock_client)

    svc.create_report("US", "2025-01-01", "2025-01-31", columns=["campaignId", "cost", "clicks"])

    body = mock_client.post.call_args[1]["body"]
    assert body["configuration"]["columns"] == ["campaignId", "cost", "clicks"]
