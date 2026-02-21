"""Tests for client.py — retry logic, header construction, convenience methods."""
from unittest.mock import MagicMock, patch, call

import httpx
import pytest

from amazon_ads.client import AmazonAdsClient, CONTENT_TYPES


@pytest.fixture
def mock_auth():
    auth = MagicMock()
    auth.get_access_token.return_value = "test-token"
    auth.close = MagicMock()
    return auth


@pytest.fixture
def client(fake_config, mock_auth):
    """Client with retry_delay=0.0 to avoid real waits in tests."""
    c = AmazonAdsClient(fake_config, mock_auth, max_retries=3, retry_delay=0.0)
    c._http = MagicMock()
    return c


def _resp(status_code=200, json_data=None, text=""):
    """Build a fake httpx.Response."""
    r = MagicMock(spec=httpx.Response)
    r.status_code = status_code
    r.text = text
    r.json.return_value = json_data or {}
    return r


# ── Header construction ──────────────────────────────────────────────

def test_headers_include_auth(client):
    client._http.request.return_value = _resp(200)
    client.get("/sp/campaigns/list", "US")

    headers = client._http.request.call_args[1]["headers"]
    assert headers["Authorization"] == "Bearer test-token"


def test_headers_include_client_id(client):
    client._http.request.return_value = _resp(200)
    client.get("/sp/campaigns/list", "US")

    headers = client._http.request.call_args[1]["headers"]
    assert headers["Amazon-Advertising-API-ClientId"] == "test-client-id"


def test_headers_include_profile_scope(client):
    client._http.request.return_value = _resp(200)
    client.get("/sp/campaigns/list", "US")

    headers = client._http.request.call_args[1]["headers"]
    assert headers["Amazon-Advertising-API-Scope"] == "111111"


def test_headers_custom_content_type(client):
    client._http.request.return_value = _resp(200)
    client.post("/sp/campaigns", "US", content_type="application/custom+json")

    headers = client._http.request.call_args[1]["headers"]
    assert headers["Content-Type"] == "application/custom+json"


def test_headers_accept(client):
    client._http.request.return_value = _resp(200)
    client.get("/sp/campaigns", "US", accept="text/csv")

    headers = client._http.request.call_args[1]["headers"]
    assert headers["Accept"] == "text/csv"


def test_headers_extra(client):
    client._http.request.return_value = _resp(200)
    client.get("/test", "US", extra_headers={"X-Custom": "val"})

    headers = client._http.request.call_args[1]["headers"]
    assert headers["X-Custom"] == "val"


# ── 401 — refresh and retry ─────────────────────────────────────────

def test_401_triggers_refresh_and_retry(client, mock_auth):
    client._http.request.side_effect = [
        _resp(401, text="Unauthorized"),
        _resp(200, json_data={"result": "ok"}),
    ]

    resp = client.get("/test", "US")
    assert resp.status_code == 200
    mock_auth.get_access_token.assert_any_call("US", force_refresh=True)


def test_401_exhausted_raises(client):
    """Three consecutive 401s → RuntimeError."""
    client._http.request.side_effect = [
        _resp(401, text="Unauthorized"),
        _resp(401, text="Unauthorized"),
        _resp(401, text="Unauthorized"),
    ]

    with pytest.raises(RuntimeError, match="API error.*401"):
        client.get("/test", "US")


# ── 429 — rate limit backoff ────────────────────────────────────────

def test_429_retries(client):
    client._http.request.side_effect = [
        _resp(429, text="Too Many Requests"),
        _resp(200, json_data={"ok": True}),
    ]

    resp = client.get("/test", "US")
    assert resp.status_code == 200
    assert client._http.request.call_count == 2


def test_429_exhausted_raises(client):
    client._http.request.side_effect = [
        _resp(429, text="Too Many Requests"),
        _resp(429, text="Too Many Requests"),
        _resp(429, text="Too Many Requests"),
    ]

    with pytest.raises(RuntimeError, match="API error.*429"):
        client.get("/test", "US")


# ── 5xx — server error backoff ──────────────────────────────────────

def test_500_retries(client):
    client._http.request.side_effect = [
        _resp(500, text="Internal Server Error"),
        _resp(200),
    ]

    resp = client.get("/test", "US")
    assert resp.status_code == 200


def test_503_exhausted_raises(client):
    client._http.request.side_effect = [
        _resp(503),
        _resp(503),
        _resp(503),
    ]

    with pytest.raises(RuntimeError, match="API error.*503"):
        client.get("/test", "US")


# ── 4xx (non-retryable) — immediate raise ───────────────────────────

def test_400_raises_immediately(client):
    client._http.request.return_value = _resp(400, text="Bad Request")

    with pytest.raises(RuntimeError, match="API error.*400"):
        client.post("/test", "US", body={"bad": "data"})
    assert client._http.request.call_count == 1


def test_403_raises_immediately(client):
    client._http.request.return_value = _resp(403, text="Forbidden")

    with pytest.raises(RuntimeError, match="API error.*403"):
        client.get("/test", "US")
    assert client._http.request.call_count == 1


def test_404_raises_immediately(client):
    client._http.request.return_value = _resp(
        404, json_data={"message": "Not found"}
    )

    with pytest.raises(RuntimeError, match="Not found"):
        client.get("/test", "US")


# ── httpx exception retry ───────────────────────────────────────────

def test_httpx_exception_retries(client):
    client._http.request.side_effect = [
        httpx.ConnectError("connection refused"),
        _resp(200),
    ]

    resp = client.get("/test", "US")
    assert resp.status_code == 200


def test_httpx_exception_exhausted(client):
    client._http.request.side_effect = httpx.ConnectError("connection refused")

    with pytest.raises(RuntimeError, match="failed after 3 attempts"):
        client.get("/test", "US")


# ── Convenience methods ──────────────────────────────────────────────

def test_get_calls_request(client):
    client._http.request.return_value = _resp(200)
    client.get("/path", "DE")

    args = client._http.request.call_args[1]
    assert args["method"] == "GET"
    assert "advertising-api-eu.amazon.com" in args["url"]


def test_post_calls_request(client):
    client._http.request.return_value = _resp(200)
    client.post("/path", "US", body={"key": "val"})

    args = client._http.request.call_args[1]
    assert args["method"] == "POST"
    assert args["json"] == {"key": "val"}


def test_put_calls_request(client):
    client._http.request.return_value = _resp(200)
    client.put("/path", "US", body={"update": True})

    args = client._http.request.call_args[1]
    assert args["method"] == "PUT"


def test_delete_calls_request(client):
    client._http.request.return_value = _resp(200)
    client.delete("/path", "US")

    args = client._http.request.call_args[1]
    assert args["method"] == "DELETE"


# ── Backoff calculation ──────────────────────────────────────────────

def test_backoff_exponential(client):
    assert client._backoff(1) == 0.0   # 0.0 * 2^0
    assert client._backoff(2) == 0.0   # 0.0 * 2^1  (retry_delay=0.0)


def test_backoff_with_real_delay(fake_config, mock_auth):
    c = AmazonAdsClient(fake_config, mock_auth, retry_delay=1.0)
    assert c._backoff(1) == 1.0
    assert c._backoff(2) == 2.0
    assert c._backoff(3) == 4.0


# ── URL construction ─────────────────────────────────────────────────

def test_url_constructed_from_region(client):
    client._http.request.return_value = _resp(200)
    client.get("/sp/campaigns/list", "US")

    url = client._http.request.call_args[1]["url"]
    assert url == "https://advertising-api.amazon.com/sp/campaigns/list"


def test_eu_url(client):
    client._http.request.return_value = _resp(200)
    client.get("/sp/campaigns/list", "DE")

    url = client._http.request.call_args[1]["url"]
    assert url == "https://advertising-api-eu.amazon.com/sp/campaigns/list"


# ── Cache integration ────────────────────────────────────────────────

from amazon_ads.utils.cache import ResponseCache


def test_post_list_is_cached(client):
    """POST to /list endpoints should be cached on second call."""
    cache = ResponseCache(ttl=60)
    client._cache = cache
    client._http.request.return_value = _resp(200, json_data={"campaigns": []})

    client.post("/sp/campaigns/list", "US", body={"maxResults": 100})
    client.post("/sp/campaigns/list", "US", body={"maxResults": 100})

    assert client._http.request.call_count == 1


def test_post_create_not_cached(client):
    """POST without /list should NOT be cached."""
    cache = ResponseCache(ttl=60)
    client._cache = cache
    client._http.request.return_value = _resp(200, json_data={"campaigns": {}})

    client.post("/sp/campaigns", "US", body={"campaigns": [{}]})
    client.post("/sp/campaigns", "US", body={"campaigns": [{}]})

    assert client._http.request.call_count == 2


def test_put_invalidates_region_cache(client):
    """PUT should invalidate all cached entries for that region."""
    cache = ResponseCache(ttl=60)
    client._cache = cache
    client._http.request.return_value = _resp(200, json_data={"campaigns": []})

    client.post("/sp/campaigns/list", "US", body={"maxResults": 100})
    assert cache.size == 1

    client.put("/sp/campaigns", "US", body={"campaigns": [{}]})
    assert cache.size == 0


def test_write_does_not_invalidate_other_region(client):
    """A write to US should not invalidate DE cache."""
    cache = ResponseCache(ttl=60)
    client._cache = cache
    client._http.request.return_value = _resp(200, json_data={"data": []})

    client.post("/sp/campaigns/list", "US", body={"maxResults": 100})
    client.post("/sp/campaigns/list", "DE", body={"maxResults": 100})
    assert cache.size == 2

    client.put("/sp/campaigns", "US", body={})
    assert cache.size == 1


def test_disabled_cache_passes_through(client):
    """When cache is disabled, every request hits the network."""
    cache = ResponseCache(enabled=False)
    client._cache = cache
    client._http.request.return_value = _resp(200, json_data={})

    client.get("/test", "US")
    client.get("/test", "US")

    assert client._http.request.call_count == 2
