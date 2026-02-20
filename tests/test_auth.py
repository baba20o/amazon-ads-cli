"""Tests for auth.py — token refresh, caching, expiry, status."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from amazon_ads.auth import AuthManager, EXPIRY_BUFFER
from amazon_ads.config import Config
from amazon_ads.models.auth import TokenStatus


def _make_token_response(access_token="tok-abc", expires_in=3600):
    """Build a fake httpx.Response for token endpoint."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": expires_in,
    }
    return resp


# ── Token refresh ────────────────────────────────────────────────────

def test_refresh_sets_token(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response("my-token")

    token = auth.get_access_token("US")
    assert token == "my-token"
    auth._http.post.assert_called_once()


def test_refresh_posts_to_auth_endpoint(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response()

    auth.get_access_token("US")
    call_args = auth._http.post.call_args
    assert call_args[0][0] == "https://api.amazon.com/auth/o2/token"


def test_refresh_sends_correct_body(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response()

    auth.get_access_token("US")
    body = auth._http.post.call_args[1]["data"]
    assert body["grant_type"] == "refresh_token"
    assert body["client_id"] == "test-client-id"
    assert body["refresh_token"] == "test-refresh-token-na"


def test_eu_region_uses_eu_token(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response()

    auth.get_access_token("DE")
    body = auth._http.post.call_args[1]["data"]
    assert body["refresh_token"] == "test-refresh-token-eu"


# ── Caching ──────────────────────────────────────────────────────────

def test_caches_token(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response("cached-tok")

    # First call: refreshes
    auth.get_access_token("US")
    assert auth._http.post.call_count == 1

    # Second call: uses cache (token is valid for 3600s)
    token = auth.get_access_token("US")
    assert auth._http.post.call_count == 1
    assert token == "cached-tok"


def test_force_refresh_bypasses_cache(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response("fresh-tok")

    auth.get_access_token("US")
    auth.get_access_token("US", force_refresh=True)
    assert auth._http.post.call_count == 2


# ── Expiry buffer ────────────────────────────────────────────────────

def test_expired_token_triggers_refresh(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response("new-tok")

    # Manually set an expired token
    auth._access_token = "old-tok"
    auth._token_expiry = datetime.now() - timedelta(minutes=1)

    token = auth.get_access_token("US")
    assert token == "new-tok"
    auth._http.post.assert_called_once()


def test_token_within_buffer_triggers_refresh(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    auth._http.post.return_value = _make_token_response("refreshed")

    # Token expires in 2 minutes (within 5-min buffer)
    auth._access_token = "about-to-expire"
    auth._token_expiry = datetime.now() + timedelta(minutes=2)

    token = auth.get_access_token("US")
    assert token == "refreshed"


# ── get_status ───────────────────────────────────────────────────────

def test_status_no_token(fake_config):
    auth = AuthManager(fake_config)
    status = auth.get_status()
    assert status.has_token is False
    assert status.is_expired is True
    assert status.seconds_remaining is None


def test_status_valid_token(fake_config):
    auth = AuthManager(fake_config)
    auth._access_token = "tok"
    auth._token_expiry = datetime.now() + timedelta(hours=1)

    status = auth.get_status()
    assert status.has_token is True
    assert status.is_expired is False
    assert status.seconds_remaining > 0


def test_status_expired_token(fake_config):
    auth = AuthManager(fake_config)
    auth._access_token = "tok"
    auth._token_expiry = datetime.now() - timedelta(hours=1)

    status = auth.get_status()
    assert status.has_token is True
    assert status.is_expired is True


# ── Error handling ───────────────────────────────────────────────────

def test_refresh_failure_raises(fake_config):
    auth = AuthManager(fake_config)
    auth._http = MagicMock()
    err_resp = MagicMock()
    err_resp.status_code = 400
    err_resp.text = "invalid_grant"
    err_resp.json.return_value = {"error_description": "Token has been revoked"}
    auth._http.post.return_value = err_resp

    with pytest.raises(RuntimeError, match="Token refresh failed"):
        auth.get_access_token("US")


def test_missing_refresh_token_raises(fake_settings, fake_regions):
    """EU refresh token is empty string — should raise ValueError."""
    fake_settings.refresh_token_eu = ""
    config = Config(settings=fake_settings, regions=fake_regions)
    auth = AuthManager(config)
    auth._http = MagicMock()

    with pytest.raises(ValueError, match="No refresh token configured"):
        auth.get_access_token("DE")
