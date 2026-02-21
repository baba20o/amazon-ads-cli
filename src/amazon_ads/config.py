"""Configuration management for Amazon Ads CLI.

Loads credentials from .env and region profiles from profiles.yaml.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv


class RegionProfile(BaseModel):
    """A single region's API configuration."""
    profile_id: str
    api_endpoint: str
    auth_endpoint: str
    auth_region: str  # NA, EU, or FE


class Settings(BaseModel):
    """Application settings loaded from environment variables."""
    client_id: str = Field(description="Amazon Ads OAuth client ID")
    client_secret: str = Field(description="Amazon Ads OAuth client secret")
    refresh_token: str = Field(description="OAuth refresh token (NA/FE)")
    refresh_token_eu: str = Field(default="", description="OAuth refresh token (EU)")
    backup_dir: str = Field(default="./backups", description="Directory for bid backups")
    cache_ttl: int = Field(default=300, description="API response cache TTL in seconds")
    cache_enabled: bool = Field(default=True, description="Enable API response caching")
    queue_dir: str = Field(default="./data", description="Directory for report queue and downloads")


class Config(BaseModel):
    """Full application configuration."""
    settings: Settings
    regions: dict[str, RegionProfile]

    def get_region(self, region: str) -> RegionProfile:
        """Get region profile by country code (e.g. US, GB, DE)."""
        region = region.upper()
        if region not in self.regions:
            available = ", ".join(sorted(self.regions.keys()))
            raise ValueError(f"Unknown region '{region}'. Available: {available}")
        return self.regions[region]

    def get_refresh_token(self, region: str) -> str:
        """Get the appropriate refresh token for a region."""
        profile = self.get_region(region)
        if profile.auth_region == "EU":
            return self.settings.refresh_token_eu
        return self.settings.refresh_token

    @property
    def all_regions(self) -> list[str]:
        """List all configured region codes."""
        return sorted(self.regions.keys())


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (where config/ lives)."""
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / "config" / "profiles.yaml").exists():
            return parent
    # Fallback: cwd
    return Path.cwd()


def _load_profiles(project_root: Path) -> dict[str, RegionProfile]:
    """Load region profiles from profiles.yaml."""
    profiles_path = project_root / "config" / "profiles.yaml"
    if not profiles_path.exists():
        raise FileNotFoundError(f"Profiles config not found at {profiles_path}")

    with open(profiles_path) as f:
        data = yaml.safe_load(f)

    regions = {}
    for code, profile_data in data.get("regions", {}).items():
        regions[code.upper()] = RegionProfile(**profile_data)
    return regions


def _env(*keys: str, default: str = "") -> str:
    """Try multiple env var names, return the first one found."""
    for key in keys:
        val = os.environ.get(key, "")
        if val:
            return val.strip().strip('"')
    return default


def _load_settings() -> Settings:
    """Load settings from environment variables.

    Supports both AMAZON_ADS_* and legacy camelCase names from .env.
    """
    return Settings(
        client_id=_env("AMAZON_ADS_CLIENT_ID", "clientId"),
        client_secret=_env("AMAZON_ADS_CLIENT_SECRET", "clientSecret"),
        refresh_token=_env("AMAZON_ADS_REFRESH_TOKEN", "refreshToken"),
        refresh_token_eu=_env("AMAZON_ADS_REFRESH_TOKEN_EU", "refreshTokenEU"),
        backup_dir=_env("AMAZON_ADS_BACKUP_DIR", default="./backups"),
        cache_ttl=int(_env("AMAZON_ADS_CACHE_TTL", default="300")),
        cache_enabled=_env("AMAZON_ADS_CACHE_ENABLED", default="true").lower() in ("true", "1", "yes"),
        queue_dir=_env("AMAZON_ADS_QUEUE_DIR", default="./data"),
    )


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Load and cache the full application configuration."""
    project_root = _find_project_root()

    # Load .env from project root if it exists
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    settings = _load_settings()
    regions = _load_profiles(project_root)

    return Config(settings=settings, regions=regions)
