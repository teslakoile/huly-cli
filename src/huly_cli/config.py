"""Configuration management for Huly CLI."""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w
from dotenv import load_dotenv

from huly_cli.errors import ConfigError

CONFIG_DIR = Path.home() / ".config" / "huly"
CONFIG_FILE = CONFIG_DIR / "config.toml"
AUTH_FILE = CONFIG_DIR / "auth.json"


@dataclass
class HulyConfig:
    url: str
    workspace: str
    email: str | None = None
    password: str | None = None


@dataclass
class AuthCache:
    account_token: str
    workspace_token: str
    workspace_id: str  # e.g. "w-example-abc12345-..."
    workspace_uuid: str  # e.g. "46573ece-3150-4b3a-..."
    email: str
    workspace_slug: str
    account_id: str  # for modifiedBy in write ops
    cached_at: float  # unix timestamp
    transactor_base: str = ""  # REST base URL for transactor


def _load_toml_config() -> dict[str, Any]:
    """Load config.toml if it exists.

    Raises ConfigError (a HulyError subclass) on malformed TOML so the top-level
    handler in main.py can render a clean message instead of a raw traceback.
    """
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(
            f"Invalid config file {CONFIG_FILE}: {e}. Fix or remove the file and try again."
        ) from e


def load_config(
    url_override: str | None = None,
    workspace_override: str | None = None,
) -> HulyConfig:
    """Load config with priority: CLI flags > env > .env in cwd > config.toml."""
    # Load .env from cwd (does NOT override already-set env vars)
    load_dotenv(dotenv_path=Path.cwd() / ".env")

    toml = _load_toml_config()

    url = (
        url_override or os.environ.get("HULY_URL") or toml.get("url") or "https://huly.example.com"
    )
    workspace = (
        workspace_override or os.environ.get("HULY_WORKSPACE") or toml.get("workspace") or ""
    )
    email = os.environ.get("HULY_EMAIL") or toml.get("email")
    password = os.environ.get("HULY_PASSWORD")  # NEVER saved to toml

    return HulyConfig(
        url=url.rstrip("/"),
        workspace=workspace,
        email=email,
        password=password,
    )


def save_config(config: HulyConfig) -> None:
    """Save url + workspace to TOML. NEVER saves password."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    if config.url:
        data["url"] = config.url
    if config.workspace:
        data["workspace"] = config.workspace
    if config.email:
        data["email"] = config.email
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)


def load_auth() -> AuthCache | None:
    """Read cached auth tokens. Returns None if not present or malformed."""
    if not AUTH_FILE.exists():
        return None
    try:
        with open(AUTH_FILE) as f:
            data = json.load(f)
        return AuthCache(
            account_token=data["account_token"],
            workspace_token=data["workspace_token"],
            workspace_id=data["workspace_id"],
            workspace_uuid=data["workspace_uuid"],
            email=data["email"],
            workspace_slug=data["workspace_slug"],
            account_id=data["account_id"],
            cached_at=data["cached_at"],
            transactor_base=data.get("transactor_base", ""),
        )
    except (KeyError, json.JSONDecodeError, OSError):
        return None


def save_auth(auth: AuthCache) -> None:
    """Write auth tokens with 0o600 permissions."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "account_token": auth.account_token,
        "workspace_token": auth.workspace_token,
        "workspace_id": auth.workspace_id,
        "workspace_uuid": auth.workspace_uuid,
        "email": auth.email,
        "workspace_slug": auth.workspace_slug,
        "account_id": auth.account_id,
        "cached_at": auth.cached_at,
        "transactor_base": auth.transactor_base,
    }
    AUTH_FILE.write_text(json.dumps(data, indent=2))
    AUTH_FILE.chmod(0o600)
