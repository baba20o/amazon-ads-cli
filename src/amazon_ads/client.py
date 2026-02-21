"""Base API client for Amazon Advertising API.

Handles header injection, retry logic, rate limiting, and token refresh.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx

from amazon_ads.auth import AuthManager
from amazon_ads.config import Config
from amazon_ads.utils.cache import ResponseCache

logger = logging.getLogger(__name__)


# Versioned content types for SP API entities
CONTENT_TYPES = {
    "campaigns": "application/vnd.spCampaign.v3+json",
    "ad_groups": "application/vnd.spAdGroup.v3+json",
    "keywords": "application/vnd.spKeyword.v3+json",
    "negative_keywords": "application/vnd.spNegativeKeyword.v3+json",
    "campaign_negative_keywords": "application/vnd.spCampaignNegativeKeyword.v3+json",
    "product_ads": "application/vnd.spProductAd.v3+json",
    "targets": "application/vnd.spTargetingClause.v3+json",
    "negative_targets": "application/vnd.spNegativeTargetingClause.v3+json",
    "bid_recommendations": "application/vnd.spthemebasedbidrecommendation.v3+json",
    "reports_request": "application/vnd.createasyncreportrequest.v3+json",
    "reports_response": "application/vnd.getasyncreportresponse.v3+json",
}


class _CachedResponse:
    """Minimal response wrapper for cached data, duck-type compatible with httpx.Response."""

    def __init__(self, data: Any) -> None:
        self._data = data
        self.status_code = 200

    def json(self) -> Any:
        return self._data

    @property
    def text(self) -> str:
        return json.dumps(self._data)

    def raise_for_status(self) -> None:
        pass


class AmazonAdsClient:
    """HTTP client for Amazon Advertising API with retry and auth handling."""

    def __init__(
        self,
        config: Config,
        auth: AuthManager,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        verbose: bool = False,
    ) -> None:
        self._config = config
        self._auth = auth
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._verbose = verbose
        self._http = httpx.Client(timeout=60.0)
        self._cache = ResponseCache(
            ttl=config.settings.cache_ttl,
            enabled=config.settings.cache_enabled,
        )

    def request(
        self,
        method: str,
        path: str,
        region: str = "US",
        *,
        body: dict[str, Any] | list | None = None,
        content_type: str | None = None,
        accept: str | None = None,
        extra_headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Make an authenticated API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: API path (e.g. "/sp/campaigns/list"). Appended to region endpoint.
            region: Country code (US, GB, etc.).
            body: JSON request body.
            content_type: Override Content-Type header.
            accept: Override Accept header.
            extra_headers: Additional headers to include.
            params: Query parameters.

        Returns:
            The httpx.Response object.

        Raises:
            RuntimeError: If all retries are exhausted.
        """
        profile = self._config.get_region(region)
        url = profile.api_endpoint + path

        # Cache: check for cached response on read operations
        cacheable = self._cache.enabled and ResponseCache.is_cacheable_request(method, path)
        cache_key = ""
        if cacheable:
            cache_key = self._cache.make_key(method, path, region, body)
            cached = self._cache.get(cache_key)
            if cached is not None:
                return _CachedResponse(cached)

        # Cache: invalidate on write operations
        if self._cache.enabled and ResponseCache.is_write_request(method, path):
            self._cache.invalidate_region(region)

        for attempt in range(1, self._max_retries + 1):
            headers = self._build_headers(region, content_type, accept, extra_headers)

            if self._verbose:
                logger.info(f"[Attempt {attempt}/{self._max_retries}] {method} {url}")
                if body:
                    logger.info(f"Body: {body}")

            try:
                response = self._http.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body,
                    params=params,
                )
            except httpx.HTTPError as e:
                if attempt == self._max_retries:
                    raise RuntimeError(f"Request failed after {self._max_retries} attempts: {e}")
                wait = self._backoff(attempt)
                logger.warning(f"HTTP error: {e}. Retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue

            if self._verbose:
                logger.info(f"Response: {response.status_code}")

            # 401 — refresh token and retry
            if response.status_code == 401 and attempt < self._max_retries:
                logger.warning("Got 401, refreshing token and retrying...")
                self._auth.get_access_token(region, force_refresh=True)
                time.sleep(self._retry_delay)
                continue

            # 429 — rate limited, exponential backoff
            if response.status_code == 429 and attempt < self._max_retries:
                wait = self._backoff(attempt)
                logger.warning(f"Rate limited (429). Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            # 5xx — server error, exponential backoff
            if 500 <= response.status_code < 600 and attempt < self._max_retries:
                wait = self._backoff(attempt)
                logger.warning(f"Server error ({response.status_code}). Waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            # Raise for any non-retryable error
            if response.status_code >= 400:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get("message", error_json.get("details", response.text))
                except Exception:
                    pass
                raise RuntimeError(
                    f"API error (HTTP {response.status_code}): {error_detail}"
                )

            # Cache: store successful read responses
            if cacheable and cache_key:
                try:
                    self._cache.put(cache_key, response.json(), region)
                except Exception:
                    pass

            return response

        raise RuntimeError(f"Request to {url} failed after {self._max_retries} attempts")

    def get(self, path: str, region: str = "US", **kwargs: Any) -> httpx.Response:
        """Convenience method for GET requests."""
        return self.request("GET", path, region, **kwargs)

    def post(self, path: str, region: str = "US", **kwargs: Any) -> httpx.Response:
        """Convenience method for POST requests."""
        return self.request("POST", path, region, **kwargs)

    def put(self, path: str, region: str = "US", **kwargs: Any) -> httpx.Response:
        """Convenience method for PUT requests."""
        return self.request("PUT", path, region, **kwargs)

    def delete(self, path: str, region: str = "US", **kwargs: Any) -> httpx.Response:
        """Convenience method for DELETE requests."""
        return self.request("DELETE", path, region, **kwargs)

    def _build_headers(
        self,
        region: str,
        content_type: str | None = None,
        accept: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Build request headers with auth and profile scope."""
        profile = self._config.get_region(region)
        token = self._auth.get_access_token(region)

        headers = {
            "Authorization": f"Bearer {token}",
            "Amazon-Advertising-API-ClientId": self._config.settings.client_id,
            "Amazon-Advertising-API-Scope": profile.profile_id,
            "Content-Type": content_type or "application/json",
        }

        if accept:
            headers["Accept"] = accept

        if extra_headers:
            headers.update(extra_headers)

        return headers

    def _backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay."""
        return self._retry_delay * (2 ** (attempt - 1))

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._http.close()
        self._auth.close()
