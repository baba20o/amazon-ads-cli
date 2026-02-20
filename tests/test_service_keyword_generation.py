"""Tests for services/keyword_generation.py — _extract_json, record construction."""
import pytest

from amazon_ads.services.keyword_generation import (
    _extract_json, generate_keywords, MATCH_TYPES, _DEFAULT_PROMPT, _PROVIDERS,
)


# ── _extract_json ────────────────────────────────────────────────────

def test_extract_raw_object():
    assert _extract_json('{"keywords": ["a", "b"]}') == {"keywords": ["a", "b"]}


def test_extract_raw_array():
    assert _extract_json('["a", "b"]') == ["a", "b"]


def test_extract_markdown_fenced():
    text = 'Here:\n```json\n{"keywords": ["x"]}\n```'
    assert _extract_json(text) == {"keywords": ["x"]}


def test_extract_markdown_no_tag():
    text = 'Result:\n```\n{"keywords": ["y"]}\n```'
    assert _extract_json(text) == {"keywords": ["y"]}


def test_extract_embedded_object():
    text = 'Text before {"keywords": ["z"]} and after'
    assert _extract_json(text) == {"keywords": ["z"]}


def test_extract_embedded_array():
    assert _extract_json('Here: ["a", "b"] done') == ["a", "b"]


def test_extract_invalid_raises():
    with pytest.raises(ValueError, match="Could not extract JSON"):
        _extract_json("no json here")


def test_extract_whitespace():
    assert _extract_json('  \n  {"keywords": ["trimmed"]}  \n  ') == {"keywords": ["trimmed"]}


# ── Record construction ──────────────────────────────────────────────

def test_expands_match_types(monkeypatch):
    monkeypatch.setitem(
        _PROVIDERS, "anthropic",
        lambda *a: '{"keywords": ["test keyword"]}',
    )
    results = generate_keywords(
        title="Test", api_key="fake", provider="anthropic", expand_match_types=True,
    )
    assert len(results) == 3
    assert {r["matchType"] for r in results} == {"BROAD", "PHRASE", "EXACT"}


def test_no_expansion(monkeypatch):
    monkeypatch.setitem(
        _PROVIDERS, "anthropic",
        lambda *a: '{"keywords": ["test"]}',
    )
    results = generate_keywords(
        title="Test", api_key="fake", provider="anthropic", expand_match_types=False,
    )
    assert len(results) == 1
    assert results[0]["matchType"] == "BROAD"


def test_attaches_ids_and_bid(monkeypatch):
    monkeypatch.setitem(
        _PROVIDERS, "anthropic",
        lambda *a: '{"keywords": ["kw"]}',
    )
    results = generate_keywords(
        title="T", api_key="fake", provider="anthropic",
        campaign_id="c1", ad_group_id="a1", bid=0.50, expand_match_types=False,
    )
    assert results[0]["campaignId"] == "c1"
    assert results[0]["adGroupId"] == "a1"
    assert results[0]["bid"] == 0.50


def test_skips_empty_strings(monkeypatch):
    monkeypatch.setitem(
        _PROVIDERS, "anthropic",
        lambda *a: '{"keywords": ["valid", "", "  "]}',
    )
    results = generate_keywords(
        title="T", api_key="fake", provider="anthropic", expand_match_types=False,
    )
    assert len(results) == 1


def test_bare_list_response(monkeypatch):
    monkeypatch.setitem(
        _PROVIDERS, "anthropic",
        lambda *a: '["alpha", "beta"]',
    )
    results = generate_keywords(
        title="T", api_key="fake", provider="anthropic", expand_match_types=False,
    )
    assert len(results) == 2


def test_invalid_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        generate_keywords(title="T", api_key="k", provider="invalid")


def test_state_is_enabled(monkeypatch):
    monkeypatch.setitem(
        _PROVIDERS, "anthropic",
        lambda *a: '{"keywords": ["kw"]}',
    )
    results = generate_keywords(
        title="T", api_key="fake", provider="anthropic", expand_match_types=False,
    )
    assert results[0]["state"] == "ENABLED"


def test_default_prompt_has_placeholders():
    assert "{title}" in _DEFAULT_PROMPT
    assert "{region}" in _DEFAULT_PROMPT
    formatted = _DEFAULT_PROMPT.format(title="My Book", region="US")
    assert "My Book" in formatted
    assert "US" in formatted
