"""Tests for huly_cli.config — especially error handling for malformed TOML."""

from __future__ import annotations

from pathlib import Path

import pytest

from huly_cli import config as config_module
from huly_cli.config import _load_toml_config, load_config
from huly_cli.errors import ConfigError, HulyError


def test_load_toml_config_raises_configerror_on_malformed_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed config.toml should surface as a ConfigError (HulyError subclass),
    not a raw tomllib.TOMLDecodeError."""
    bad_toml = tmp_path / "config.toml"
    bad_toml.write_text("key = [unclosed\n")

    monkeypatch.setattr(config_module, "CONFIG_FILE", bad_toml)

    with pytest.raises(ConfigError) as exc_info:
        _load_toml_config()

    # Verify it's in the HulyError hierarchy (so main.py's handler catches it)
    assert isinstance(exc_info.value, HulyError)
    # Error message should include the offending file path so the user knows what to fix
    assert str(bad_toml) in exc_info.value.message


def test_load_config_raises_configerror_on_malformed_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """load_config() should propagate the ConfigError from the TOML loader
    instead of crashing with an uncaught TOMLDecodeError."""
    bad_toml = tmp_path / "config.toml"
    bad_toml.write_text('name = "unterminated\n')

    monkeypatch.setattr(config_module, "CONFIG_FILE", bad_toml)
    # Ensure cwd .env doesn't accidentally contribute to the test
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError):
        load_config()


def test_load_toml_config_returns_empty_when_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sanity baseline: if CONFIG_FILE does not exist, loader returns {}."""
    missing = tmp_path / "does-not-exist.toml"
    monkeypatch.setattr(config_module, "CONFIG_FILE", missing)

    assert _load_toml_config() == {}


def test_load_toml_config_parses_valid_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sanity baseline: valid TOML still loads correctly after the fix."""
    good_toml = tmp_path / "config.toml"
    good_toml.write_text(
        'url = "https://huly.example.com"\nworkspace = "ws-abc"\nemail = "user@example.com"\n'
    )
    monkeypatch.setattr(config_module, "CONFIG_FILE", good_toml)

    data = _load_toml_config()
    assert data == {
        "url": "https://huly.example.com",
        "workspace": "ws-abc",
        "email": "user@example.com",
    }
