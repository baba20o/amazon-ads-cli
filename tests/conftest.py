"""Shared fixtures for the amazon-ads test suite."""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from amazon_ads.config import Config, RegionProfile, Settings


@pytest.fixture
def fake_settings() -> Settings:
    return Settings(
        client_id="test-client-id",
        client_secret="test-client-secret",
        refresh_token="test-refresh-token-na",
        refresh_token_eu="test-refresh-token-eu",
        backup_dir="./test-backups",
        cache_ttl=300,
        cache_enabled=True,
        queue_dir="./test-data",
    )


@pytest.fixture
def fake_regions() -> dict[str, RegionProfile]:
    return {
        "US": RegionProfile(
            profile_id="111111",
            api_endpoint="https://advertising-api.amazon.com",
            auth_endpoint="https://api.amazon.com/auth/o2/token",
            auth_region="NA",
        ),
        "DE": RegionProfile(
            profile_id="222222",
            api_endpoint="https://advertising-api-eu.amazon.com",
            auth_endpoint="https://api.amazon.co.uk/auth/o2/token",
            auth_region="EU",
        ),
        "GB": RegionProfile(
            profile_id="333333",
            api_endpoint="https://advertising-api-eu.amazon.com",
            auth_endpoint="https://api.amazon.co.uk/auth/o2/token",
            auth_region="EU",
        ),
    }


@pytest.fixture
def fake_config(fake_settings, fake_regions) -> Config:
    return Config(settings=fake_settings, regions=fake_regions)


@pytest.fixture
def mock_client():
    """MagicMock standing in for AmazonAdsClient."""
    client = MagicMock()
    client.get = MagicMock()
    client.post = MagicMock()
    client.put = MagicMock()
    client.delete = MagicMock()
    client.close = MagicMock()
    return client
