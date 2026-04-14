"""`huly upgrade` — check PyPI for the latest version and upgrade in-place."""

from __future__ import annotations

import shutil
import subprocess
import sys

import httpx
import typer

from huly_cli import __version__
from huly_cli.output import console, print_error, print_success

PYPI_URL = "https://pypi.org/pypi/huly-cli/json"
PACKAGE_NAME = "huly-cli"


def _parse_version(v: str) -> tuple[int, ...]:
    """Parse a version string like '0.1.3' into a comparable tuple.

    Non-integer suffixes (e.g. 'rc1', 'dev0') are stripped conservatively so
    the comparison falls back to the numeric prefix. Unparsable segments are
    treated as -1 so they sort below any real release.
    """
    parts: list[int] = []
    for segment in v.split("."):
        digits = ""
        for ch in segment:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else -1)
    return tuple(parts)


def _fetch_latest_version() -> str:
    """Fetch the latest version of huly-cli from PyPI.

    Raises:
        httpx.HTTPError: on connection issues, timeouts, non-2xx responses.
        KeyError / ValueError: on malformed PyPI response.
    """
    response = httpx.get(PYPI_URL, timeout=10.0, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    return str(payload["info"]["version"])


def _detect_installer() -> str:
    """Detect whether huly-cli was installed via pipx or pip.

    Returns:
        "pipx" if the current interpreter lives under a pipx venvs directory,
        "pip" otherwise.
    """
    exec_path = (sys.executable or "").replace("\\", "/")
    if "pipx/venvs" in exec_path or "/pipx/" in exec_path:
        return "pipx"
    # Secondary signal: if pipx exists AND the executable lives under the user's
    # local share (where pipx typically installs), call it pipx.
    pipx_bin = shutil.which("pipx")
    if pipx_bin and ("/.local/" in exec_path or "/Application Support/pipx" in exec_path):
        return "pipx"
    return "pip"


def _build_upgrade_command(installer: str) -> list[str]:
    if installer == "pipx":
        pipx_bin = shutil.which("pipx") or "pipx"
        return [pipx_bin, "upgrade", PACKAGE_NAME]
    return [sys.executable, "-m", "pip", "install", "--upgrade", PACKAGE_NAME]


def upgrade() -> None:
    """Check PyPI for a newer version and upgrade huly-cli in place."""
    current = __version__
    console.print("Checking for updates...")

    try:
        latest = _fetch_latest_version()
    except httpx.HTTPError as e:
        print_error(
            f"Could not reach PyPI to check for updates: {e}",
            hint="Check your internet connection and try again.",
        )
        raise typer.Exit(1) from e
    except (KeyError, ValueError) as e:
        print_error(
            f"Unexpected response from PyPI: {e}",
            hint="PyPI may be temporarily misbehaving. Try again shortly.",
        )
        raise typer.Exit(1) from e

    if _parse_version(current) >= _parse_version(latest):
        console.print(f"huly-cli {current} is already up to date.")
        return

    installer = _detect_installer()
    cmd = _build_upgrade_command(installer)
    console.print(
        f"Upgrading huly-cli [bold]{current}[/bold] → [bold]{latest}[/bold] via {installer}..."
    )

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print_error(
            f"Upgrade command failed (exit code {e.returncode}).",
            hint=f"Tried: {' '.join(cmd)}",
        )
        raise typer.Exit(1) from e
    except FileNotFoundError as e:
        print_error(
            f"Could not find the upgrade tool: {e}",
            hint=f"Install {installer} or run the command manually: {' '.join(cmd)}",
        )
        raise typer.Exit(1) from e

    print_success(f"Upgraded huly-cli {current} → {latest}")
