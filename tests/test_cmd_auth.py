"""CLI tests for auth command group."""
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from amazon_ads.commands.auth_cmd import app
from amazon_ads.models.auth import TokenStatus

runner = CliRunner()


def _mock_auth_and_config():
    """Patch get_config and AuthManager for auth commands."""
    config = MagicMock()
    auth = MagicMock()
    return config, auth


# ── login ────────────────────────────────────────────────────────────

def test_login_success():
    config = MagicMock()
    auth = MagicMock()
    auth.get_access_token.return_value = "tok-abc"
    auth.get_status.return_value = TokenStatus(
        has_token=True, is_expired=False,
        expires_at=datetime.now() + timedelta(hours=1),
        seconds_remaining=3600,
    )

    with patch("amazon_ads.commands.auth_cmd.get_config", return_value=config), \
         patch("amazon_ads.commands.auth_cmd.AuthManager", return_value=auth):
        result = runner.invoke(app, ["login", "--region", "US", "--output", "json"])
    assert result.exit_code == 0
    auth.get_access_token.assert_called_once()


# ── status ───────────────────────────────────────────────────────────

def test_status():
    config = MagicMock()
    auth = MagicMock()
    auth.get_status.return_value = TokenStatus(has_token=False, is_expired=True)

    with patch("amazon_ads.commands.auth_cmd.get_config", return_value=config), \
         patch("amazon_ads.commands.auth_cmd.AuthManager", return_value=auth):
        result = runner.invoke(app, ["status", "--output", "json"])
    assert result.exit_code == 0


# ── refresh error ────────────────────────────────────────────────────

def test_refresh_failure():
    config = MagicMock()
    auth = MagicMock()
    auth.get_access_token.side_effect = RuntimeError("Token refresh failed")

    with patch("amazon_ads.commands.auth_cmd.get_config", return_value=config), \
         patch("amazon_ads.commands.auth_cmd.AuthManager", return_value=auth):
        result = runner.invoke(app, ["refresh", "--region", "US"])
    assert result.exit_code == 1
