"""Tests for utils/errors.py — error code classification and hint matching."""
import json

from amazon_ads.utils.errors import _get_hint, handle_error


# ── _get_hint tests ───────────────────────────────────────────────────

def test_hint_401():
    assert _get_hint("HTTP 401 Unauthorized") is not None


def test_hint_token():
    assert "refresh" in _get_hint("invalid token error").lower()


def test_hint_unauthorized():
    assert "refresh" in _get_hint("Unauthorized access").lower()


def test_hint_429():
    assert "rate" in _get_hint("HTTP 429 Too Many Requests").lower()


def test_hint_rate_limit():
    assert "rate" in _get_hint("Rate limit exceeded").lower()


def test_hint_throttled():
    assert "rate" in _get_hint("Request was throttled").lower()


def test_hint_entity_not_found():
    assert _get_hint("ENTITY_NOT_FOUND for campaign") is not None


def test_hint_invalid_argument():
    assert _get_hint("INVALID_ARGUMENT: bid must be positive") is not None


def test_hint_malformed_request():
    assert _get_hint("MALFORMED_REQUEST: missing field") is not None


def test_hint_timeout():
    assert "timed out" in _get_hint("Connection timeout occurred").lower()


def test_hint_connection():
    assert "network" in _get_hint("Connection refused").lower()


def test_hint_profile():
    assert "profiles.yaml" in _get_hint("could not find profile").lower()


def test_hint_no_match():
    assert _get_hint("some random error") is None


# ── handle_error JSON output ──────────────────────────────────────────

def test_handle_error_auth_code(capsys):
    handle_error(RuntimeError("HTTP 401 Unauthorized"))
    data = json.loads(capsys.readouterr().out)
    assert data["error"] is True
    assert data["code"] == "AUTH_ERROR"
    assert "hint" in data


def test_handle_error_rate_limited_code(capsys):
    handle_error(RuntimeError("429 Too Many Requests"))
    assert json.loads(capsys.readouterr().out)["code"] == "RATE_LIMITED"


def test_handle_error_timeout_code(capsys):
    handle_error(RuntimeError("request timeout"))
    assert json.loads(capsys.readouterr().out)["code"] == "TIMEOUT"


def test_handle_error_connection_code(capsys):
    handle_error(RuntimeError("connection refused"))
    assert json.loads(capsys.readouterr().out)["code"] == "CONNECTION_ERROR"


def test_handle_error_not_found_code(capsys):
    handle_error(RuntimeError("ENTITY_NOT_FOUND"))
    assert json.loads(capsys.readouterr().out)["code"] == "NOT_FOUND"


def test_handle_error_invalid_argument_code(capsys):
    handle_error(RuntimeError("INVALID_ARGUMENT"))
    assert json.loads(capsys.readouterr().out)["code"] == "INVALID_ARGUMENT"


def test_handle_error_generic_code(capsys):
    handle_error(RuntimeError("something went wrong"))
    data = json.loads(capsys.readouterr().out)
    assert data["code"] == "RUNTIME_ERROR"
    assert "hint" not in data
