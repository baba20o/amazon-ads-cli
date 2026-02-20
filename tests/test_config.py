"""Tests for config.py — region lookup, refresh token routing, env helpers."""
import pytest

from amazon_ads.config import Config, RegionProfile, Settings, _env, _load_settings


# ── get_region ───────────────────────────────────────────────────────

def test_get_region_upper(fake_config):
    """Accepts lowercase and still resolves correctly."""
    assert fake_config.get_region("us").profile_id == "111111"


def test_get_region_found(fake_config):
    assert fake_config.get_region("DE").profile_id == "222222"


def test_get_region_unknown(fake_config):
    with pytest.raises(ValueError, match="Unknown region 'XX'"):
        fake_config.get_region("XX")


# ── get_refresh_token ────────────────────────────────────────────────

def test_refresh_token_na(fake_config):
    assert fake_config.get_refresh_token("US") == "test-refresh-token-na"


def test_refresh_token_eu(fake_config):
    assert fake_config.get_refresh_token("DE") == "test-refresh-token-eu"


def test_refresh_token_eu_gb(fake_config):
    """GB is also EU auth region."""
    assert fake_config.get_refresh_token("GB") == "test-refresh-token-eu"


# ── all_regions ──────────────────────────────────────────────────────

def test_all_regions_sorted(fake_config):
    assert fake_config.all_regions == ["DE", "GB", "US"]


# ── _env helper ──────────────────────────────────────────────────────

def test_env_first_key(monkeypatch):
    monkeypatch.setenv("FOO", "bar")
    assert _env("FOO", "BAZ") == "bar"


def test_env_fallback_key(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.setenv("BAZ", "qux")
    assert _env("FOO", "BAZ") == "qux"


def test_env_default(monkeypatch):
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAZ", raising=False)
    assert _env("FOO", "BAZ", default="fallback") == "fallback"


def test_env_strips_quotes(monkeypatch):
    monkeypatch.setenv("FOO", '"hello"')
    assert _env("FOO") == "hello"


def test_env_strips_whitespace(monkeypatch):
    monkeypatch.setenv("FOO", "  hello  ")
    assert _env("FOO") == "hello"


# ── _load_settings ───────────────────────────────────────────────────

def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("AMAZON_ADS_CLIENT_ID", "cid")
    monkeypatch.setenv("AMAZON_ADS_CLIENT_SECRET", "csec")
    monkeypatch.setenv("AMAZON_ADS_REFRESH_TOKEN", "rtok")
    monkeypatch.setenv("AMAZON_ADS_REFRESH_TOKEN_EU", "rtok_eu")
    settings = _load_settings()
    assert settings.client_id == "cid"
    assert settings.client_secret == "csec"
    assert settings.refresh_token == "rtok"
    assert settings.refresh_token_eu == "rtok_eu"


def test_load_settings_legacy_names(monkeypatch):
    """Falls back to camelCase .env names."""
    monkeypatch.delenv("AMAZON_ADS_CLIENT_ID", raising=False)
    monkeypatch.delenv("AMAZON_ADS_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("AMAZON_ADS_REFRESH_TOKEN", raising=False)
    monkeypatch.setenv("clientId", "legacy-id")
    monkeypatch.setenv("clientSecret", "legacy-sec")
    monkeypatch.setenv("refreshToken", "legacy-tok")
    settings = _load_settings()
    assert settings.client_id == "legacy-id"
