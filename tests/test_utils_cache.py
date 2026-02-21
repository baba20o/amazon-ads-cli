"""Tests for utils/cache.py — TTL cache with region-scoped invalidation."""
import time
from unittest.mock import patch

from amazon_ads.utils.cache import ResponseCache


# ── is_cacheable_request ─────────────────────────────────────────────

def test_get_is_cacheable():
    assert ResponseCache.is_cacheable_request("GET", "/sp/campaigns") is True


def test_post_list_is_cacheable():
    assert ResponseCache.is_cacheable_request("POST", "/sp/campaigns/list") is True


def test_post_create_not_cacheable():
    assert ResponseCache.is_cacheable_request("POST", "/sp/campaigns") is False


def test_post_delete_not_cacheable():
    assert ResponseCache.is_cacheable_request("POST", "/sp/campaigns/delete") is False


def test_put_not_cacheable():
    assert ResponseCache.is_cacheable_request("PUT", "/sp/campaigns") is False


def test_delete_not_cacheable():
    assert ResponseCache.is_cacheable_request("DELETE", "/sp/campaigns") is False


# ── is_write_request ─────────────────────────────────────────────────

def test_put_is_write():
    assert ResponseCache.is_write_request("PUT", "/sp/campaigns") is True


def test_delete_is_write():
    assert ResponseCache.is_write_request("DELETE", "/sp/campaigns") is True


def test_post_create_is_write():
    assert ResponseCache.is_write_request("POST", "/sp/campaigns") is True


def test_post_delete_is_write():
    assert ResponseCache.is_write_request("POST", "/sp/campaigns/delete") is True


def test_post_list_not_write():
    assert ResponseCache.is_write_request("POST", "/sp/campaigns/list") is False


def test_get_not_write():
    assert ResponseCache.is_write_request("GET", "/sp/campaigns") is False


# ── make_key ─────────────────────────────────────────────────────────

def test_same_input_same_key():
    cache = ResponseCache()
    k1 = cache.make_key("POST", "/sp/campaigns/list", "US", {"maxResults": 100})
    k2 = cache.make_key("POST", "/sp/campaigns/list", "US", {"maxResults": 100})
    assert k1 == k2


def test_different_region_different_key():
    cache = ResponseCache()
    k1 = cache.make_key("POST", "/sp/campaigns/list", "US", {})
    k2 = cache.make_key("POST", "/sp/campaigns/list", "DE", {})
    assert k1 != k2


def test_different_body_different_key():
    cache = ResponseCache()
    k1 = cache.make_key("POST", "/sp/campaigns/list", "US", {"maxResults": 100})
    k2 = cache.make_key("POST", "/sp/campaigns/list", "US", {"maxResults": 200})
    assert k1 != k2


def test_dict_key_order_irrelevant():
    cache = ResponseCache()
    k1 = cache.make_key("POST", "/path", "US", {"a": 1, "b": 2})
    k2 = cache.make_key("POST", "/path", "US", {"b": 2, "a": 1})
    assert k1 == k2


def test_none_body():
    cache = ResponseCache()
    k1 = cache.make_key("GET", "/path", "US", None)
    k2 = cache.make_key("GET", "/path", "US", None)
    assert k1 == k2


# ── get / put ────────────────────────────────────────────────────────

def test_put_then_get():
    cache = ResponseCache(ttl=60)
    cache.put("key1", {"data": "value"}, "US")
    assert cache.get("key1") == {"data": "value"}


def test_miss_returns_none():
    cache = ResponseCache(ttl=60)
    assert cache.get("nonexistent") is None


def test_expired_returns_none():
    cache = ResponseCache(ttl=1)
    cache.put("key1", {"data": "value"}, "US")
    with patch("amazon_ads.utils.cache.time.time", return_value=time.time() + 2):
        assert cache.get("key1") is None


def test_disabled_cache_returns_none():
    cache = ResponseCache(enabled=False)
    cache.put("key1", {"data": "value"}, "US")
    assert cache.get("key1") is None


def test_size_property():
    cache = ResponseCache()
    assert cache.size == 0
    cache.put("k1", "v1", "US")
    cache.put("k2", "v2", "US")
    assert cache.size == 2


# ── invalidation ─────────────────────────────────────────────────────

def test_invalidate_region():
    cache = ResponseCache()
    cache.put("k1", "v1", "US")
    cache.put("k2", "v2", "US")
    cache.put("k3", "v3", "DE")
    count = cache.invalidate_region("US")
    assert count == 2
    assert cache.get("k1") is None
    assert cache.get("k2") is None
    assert cache.get("k3") == "v3"


def test_invalidate_all():
    cache = ResponseCache()
    cache.put("k1", "v1", "US")
    cache.put("k2", "v2", "DE")
    count = cache.invalidate_all()
    assert count == 2
    assert cache.size == 0


def test_invalidate_empty_region():
    cache = ResponseCache()
    count = cache.invalidate_region("US")
    assert count == 0
