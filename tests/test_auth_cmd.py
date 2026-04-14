"""Regression tests for `huly auth login` and `huly auth status`."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from huly_cli.config import AuthCache, HulyConfig
from huly_cli.errors import AuthError
from huly_cli.main import app

runner = CliRunner()


FAKE_AUTH = AuthCache(
    account_token="acct-tok",
    workspace_token="ws-tok",
    workspace_id="w-fake",
    workspace_uuid="uuid-fake",
    email="user@example.com",
    workspace_slug="fake-ws",
    account_id="acc-fake",
    cached_at=1700000000.0,
)


# ── auth login ────────────────────────────────────────────────────────────────


def test_auth_login_uses_cli_credentials_and_saves_config():
    """auth login with --email/--password/--workspace stores tokens and persists config."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
        email=None,
        password=None,
    )
    load_config_mock = MagicMock(return_value=fake_config)
    save_config_mock = MagicMock()
    login_mock = AsyncMock(return_value=FAKE_AUTH)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", load_config_mock),
        patch("huly_cli.commands.auth_cmd.save_config", save_config_mock),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(
            app,
            ["auth", "login", "--email", "user@example.com", "--password", "secret"],
        )

    assert result.exit_code == 0, result.output
    assert "Logged in as" in result.output
    assert "user@example.com" in result.output
    assert "fake-ws" in result.output
    login_mock.assert_awaited_once()
    save_config_mock.assert_called_once()
    saved_config = save_config_mock.call_args.args[0]
    assert saved_config.email == "user@example.com"
    assert saved_config.password == "secret"


def test_auth_login_uses_config_credentials_when_flags_omitted():
    """auth login should fall back to config-resident credentials when no flags are passed."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
        email="env-user@example.com",
        password="env-pass",
    )
    login_mock = AsyncMock(return_value=FAKE_AUTH)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.save_config", MagicMock()),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 0, result.output
    login_mock.assert_awaited_once()


def test_auth_login_errors_when_email_missing_in_non_tty():
    """auth login without email and without TTY should exit with code 2."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
        email=None,
        password=None,
    )
    login_mock = AsyncMock(return_value=FAKE_AUTH)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.save_config", MagicMock()),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(app, ["auth", "login"])

    # CliRunner stdin is not a tty, so missing email should raise AuthError
    assert result.exit_code != 0
    login_mock.assert_not_awaited()


def test_auth_login_errors_when_password_missing_in_non_tty():
    """auth login with email but no password (non-tty) should exit non-zero."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
        email="u@example.com",
        password=None,
    )
    login_mock = AsyncMock(return_value=FAKE_AUTH)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.save_config", MagicMock()),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code != 0
    login_mock.assert_not_awaited()


def test_auth_login_errors_when_workspace_missing_in_non_tty():
    """auth login with email/password but no workspace (non-tty) should exit non-zero."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="",
        email=None,
        password=None,
    )
    login_mock = AsyncMock(return_value=FAKE_AUTH)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.save_config", MagicMock()),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(
            app,
            ["auth", "login", "--email", "u@example.com", "--password", "pw"],
        )

    assert result.exit_code != 0
    login_mock.assert_not_awaited()


def test_auth_login_propagates_auth_error_with_exit_code_2():
    """AuthError raised from login() surfaces as exit code 2."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
        email="u@example.com",
        password="pw",
    )
    login_mock = AsyncMock(side_effect=AuthError("Bad credentials"))

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.save_config", MagicMock()),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 2
    login_mock.assert_awaited_once()


def test_auth_login_propagates_generic_error_with_exit_code_1():
    """A non-AuthError exception during login surfaces as exit code 1."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
        email="u@example.com",
        password="pw",
    )
    login_mock = AsyncMock(side_effect=RuntimeError("network down"))

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.save_config", MagicMock()),
        patch("huly_cli.commands.auth_cmd.login", login_mock),
    ):
        result = runner.invoke(app, ["auth", "login"])

    assert result.exit_code == 1
    login_mock.assert_awaited_once()


# ── auth status ───────────────────────────────────────────────────────────────


def test_auth_status_authenticated():
    """auth status reports authenticated when check_auth_status returns a positive payload."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
    )
    status_payload = {
        "authenticated": True,
        "email": "user@example.com",
        "workspace": "fake-ws",
        "workspace_id": "w-fake",
        "workspace_uuid": "uuid-fake",
        "token_age_seconds": 42,
        "token_age_human": "42s",
    }
    check_mock = AsyncMock(return_value=status_payload)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.check_auth_status", check_mock),
    ):
        result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0, result.output
    assert "user@example.com" in result.output
    check_mock.assert_awaited_once()


def test_auth_status_unauthenticated_stale_cache():
    """auth status surfaces an unauthenticated payload (stale/missing cache)."""
    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
    )
    status_payload = {
        "authenticated": False,
        "email": None,
        "workspace": None,
        "token_age": None,
    }
    check_mock = AsyncMock(return_value=status_payload)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.check_auth_status", check_mock),
    ):
        result = runner.invoke(app, ["auth", "status"])

    assert result.exit_code == 0, result.output
    assert "False" in result.output or "false" in result.output
    check_mock.assert_awaited_once()


def test_auth_status_json_mode():
    """auth status emits JSON envelope when --json is set."""
    import json as json_mod

    fake_config = HulyConfig(
        url="https://huly.example.com",
        workspace="fake-ws",
    )
    status_payload = {
        "authenticated": True,
        "email": "user@example.com",
        "workspace": "fake-ws",
        "workspace_id": "w-fake",
        "workspace_uuid": "uuid-fake",
        "token_age_seconds": 1,
        "token_age_human": "1s",
    }
    check_mock = AsyncMock(return_value=status_payload)

    with (
        patch("huly_cli.commands.auth_cmd.load_config", MagicMock(return_value=fake_config)),
        patch("huly_cli.commands.auth_cmd.check_auth_status", check_mock),
    ):
        result = runner.invoke(app, ["--json", "auth", "status"])

    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["ok"] is True
    assert data["data"]["authenticated"] is True
    assert data["data"]["email"] == "user@example.com"
