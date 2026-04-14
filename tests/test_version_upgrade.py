"""Regression tests for `huly --version` and `huly upgrade`."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
from typer.testing import CliRunner

from huly_cli import __version__
from huly_cli.main import app

runner = CliRunner()


# ── --version flag ────────────────────────────────────────────────────────────


def test_version_flag_prints_package_and_version():
    """`huly --version` exits 0 and prints 'huly-cli <version>'."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert "huly-cli" in result.output
    assert __version__ in result.output


def test_version_flag_output_format():
    """`huly --version` output matches exactly 'huly-cli <version>'."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == f"huly-cli {__version__}"


# ── huly upgrade ──────────────────────────────────────────────────────────────


def _make_pypi_response(version: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock(return_value=None)
    resp.json = MagicMock(return_value={"info": {"version": version}})
    return resp


def test_upgrade_already_up_to_date():
    """When installed version == PyPI version, print a friendly message and exit 0."""
    fake_get = MagicMock(return_value=_make_pypi_response(__version__))
    subprocess_mock = MagicMock()

    with (
        patch("huly_cli.commands.upgrade.httpx.get", fake_get),
        patch("huly_cli.commands.upgrade.subprocess.run", subprocess_mock),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 0, result.output
    assert "already up to date" in result.output.lower()
    subprocess_mock.assert_not_called()
    fake_get.assert_called_once()


def test_upgrade_runs_pip_when_upgrade_available():
    """When PyPI has a newer version, run the upgrade subprocess and report success."""
    higher = "999.999.999"
    fake_get = MagicMock(return_value=_make_pypi_response(higher))
    subprocess_run = MagicMock()

    with (
        patch("huly_cli.commands.upgrade.httpx.get", fake_get),
        patch("huly_cli.commands.upgrade.subprocess.run", subprocess_run),
        patch("huly_cli.commands.upgrade._detect_installer", return_value="pip"),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 0, result.output
    assert "Upgrading" in result.output
    assert __version__ in result.output
    assert higher in result.output
    subprocess_run.assert_called_once()
    # The command should target this Python interpreter's pip and huly-cli
    cmd = subprocess_run.call_args.args[0]
    assert "pip" in cmd
    assert "install" in cmd
    assert "--upgrade" in cmd
    assert "huly-cli" in cmd


def test_upgrade_runs_pipx_when_detected():
    """When pipx is detected, use `pipx upgrade huly-cli` instead of pip."""
    higher = "999.999.999"
    fake_get = MagicMock(return_value=_make_pypi_response(higher))
    subprocess_run = MagicMock()

    with (
        patch("huly_cli.commands.upgrade.httpx.get", fake_get),
        patch("huly_cli.commands.upgrade.subprocess.run", subprocess_run),
        patch("huly_cli.commands.upgrade._detect_installer", return_value="pipx"),
        patch("huly_cli.commands.upgrade.shutil.which", return_value="/usr/local/bin/pipx"),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code == 0, result.output
    subprocess_run.assert_called_once()
    cmd = subprocess_run.call_args.args[0]
    assert "pipx" in " ".join(cmd)
    assert "upgrade" in cmd
    assert "huly-cli" in cmd


def test_upgrade_handles_pypi_unreachable():
    """Network errors reaching PyPI should print a clean error and exit non-zero."""
    fake_get = MagicMock(side_effect=httpx.ConnectError("network down"))
    subprocess_run = MagicMock()

    with (
        patch("huly_cli.commands.upgrade.httpx.get", fake_get),
        patch("huly_cli.commands.upgrade.subprocess.run", subprocess_run),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code != 0
    combined = (result.output or "") + (result.stderr or "")
    assert "PyPI" in combined or "reach" in combined.lower()
    subprocess_run.assert_not_called()


def test_upgrade_handles_http_error():
    """Non-2xx HTTP responses should also fail cleanly without crashing."""
    resp = MagicMock()
    resp.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock(status_code=500)
        )
    )
    fake_get = MagicMock(return_value=resp)
    subprocess_run = MagicMock()

    with (
        patch("huly_cli.commands.upgrade.httpx.get", fake_get),
        patch("huly_cli.commands.upgrade.subprocess.run", subprocess_run),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code != 0
    subprocess_run.assert_not_called()


def test_upgrade_subprocess_failure_exits_nonzero():
    """If the upgrade subprocess itself fails, surface a clean non-zero exit."""
    import subprocess as _sp

    higher = "999.999.999"
    fake_get = MagicMock(return_value=_make_pypi_response(higher))
    subprocess_run = MagicMock(side_effect=_sp.CalledProcessError(1, ["pip"]))

    with (
        patch("huly_cli.commands.upgrade.httpx.get", fake_get),
        patch("huly_cli.commands.upgrade.subprocess.run", subprocess_run),
        patch("huly_cli.commands.upgrade._detect_installer", return_value="pip"),
    ):
        result = runner.invoke(app, ["upgrade"])

    assert result.exit_code != 0
    subprocess_run.assert_called_once()
