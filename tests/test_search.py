"""Command-layer tests for ``huly search`` and ``huly issues search``.

Uses ``respx`` to mock the fulltext endpoint end-to-end (including a
truncated-JSON response body), and ``CliRunner`` to exercise the Typer
command wiring. The truncated-body test is the single most important one in
this module: if the upstream-workaround regex ever regresses, it re-breaks
the whole feature.
"""

from __future__ import annotations

import json
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import respx
from typer.testing import CliRunner

from huly_cli.config import AuthCache, HulyConfig
from huly_cli.main import app

runner = CliRunner()

FAKE_CONFIG = HulyConfig(
    url="https://test.example.com",
    workspace="test-ws",
    email="test@test.com",
    password="testpass",
)

FAKE_AUTH = AuthCache(
    account_token="t",
    workspace_token="t",
    workspace_id="w",
    workspace_uuid="u",
    email="test@test.com",
    workspace_slug="test",
    account_id="a",
    cached_at=1.0,
)

# A body that intentionally trails off mid-token — mirrors real Huly behavior
# where Content-Length is declared but the tail is cut at ``"total":N``.
TRUNCATED_SEARCH_BODY = (
    '{"docs":['
    '{"id":"i1","title":"Fix login","doc":'
    '{"_id":"i1","_class":"tracker:class:Issue"},'
    '"score":100.5,"iconComponent":"x"},'
    '{"id":"d1","title":"Onboarding","doc":'
    '{"_id":"d1","_class":"document:class:Document"},'
    '"score":42.0,"iconComponent":"x"}'
    '],"total":1'  # ← no closing ``}``.
)


@contextmanager
def _auth_patch():
    """Mock auth + config across every module that uses them directly.

    Patching ``load_config`` is necessary because the search commands go
    through the real HTTP path (only auth is mocked); without it, the client
    would build URLs against whatever URL the dev environment resolves.
    """
    auth_mock = AsyncMock(return_value=FAKE_AUTH)
    config_mock = MagicMock(return_value=FAKE_CONFIG)
    modules = [
        "huly_cli.auth",
        "huly_cli.commands.search",
        "huly_cli.commands.issues",
    ]
    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.ensure_auth", new=auth_mock))
        stack.enter_context(patch("huly_cli.commands.search.load_config", config_mock))
        yield auth_mock


# ── Sanity check on the fixture ───────────────────────────────────────────────


def test_truncated_fixture_is_actually_invalid_json():
    """Guard against the fixture silently becoming valid JSON.

    If this assert ever flips, the truncation test below no longer exercises
    the workaround — it would be testing stock ``json.loads`` on valid input.
    """
    import pytest

    with pytest.raises(json.JSONDecodeError):
        json.loads(TRUNCATED_SEARCH_BODY)


# ── huly search ───────────────────────────────────────────────────────────────


def test_search_happy_path():
    """Table output includes class, id, title for each hit."""
    body = (
        '{"docs":['
        '{"id":"i1","title":"Fix login","doc":'
        '{"_id":"i1","_class":"tracker:class:Issue"},'
        '"score":100.5,"iconComponent":"x"}'
        '],"total":1'
    )
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=body
        )
        result = runner.invoke(app, ["search", "login"])
    assert result.exit_code == 0, result.output
    assert "Fix login" in result.output
    assert "tracker:class:Issue" in result.output
    assert "i1" in result.output


def test_search_parses_truncated_response():
    """THE load-bearing command-layer test: the workaround survives end-to-end."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(app, ["search", "anything"])
    assert result.exit_code == 0, result.output
    assert "Fix login" in result.output
    assert "Onboarding" in result.output
    assert "tracker:class:Issue" in result.output
    assert "document:class:Document" in result.output


def test_search_limit_flag_forwarded_to_server():
    """``--limit`` shows up as a ``limit=`` query parameter."""
    with _auth_patch(), respx.mock:
        route = respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text='{"docs":[],"total":0'
        )
        result = runner.invoke(app, ["search", "q", "--limit", "7"])
    assert result.exit_code == 0, result.output
    assert route.calls[0].request.url.params["limit"] == "7"


def test_search_single_class_filter_applied_client_side():
    """A single ``--class`` restricts the table to just that class."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(app, ["search", "q", "--class", "tracker:class:Issue"])
    assert result.exit_code == 0, result.output
    assert "Fix login" in result.output
    # The doc hit must not appear in the output at all.
    assert "Onboarding" not in result.output
    assert "document:class:Document" not in result.output


def test_search_multiple_class_filters():
    """Multiple ``--class`` flags union the filter — both classes pass."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(
            app,
            [
                "search",
                "q",
                "--class",
                "tracker:class:Issue",
                "--class",
                "document:class:Document",
            ],
        )
    assert result.exit_code == 0, result.output
    assert "Fix login" in result.output
    assert "Onboarding" in result.output


def test_search_json_output_mode():
    """``--json`` emits a structured envelope with id/class/title/score."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(app, ["search", "q", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert len(payload["data"]) == 2
    first = payload["data"][0]
    assert set(first.keys()) == {"id", "class", "title", "score"}
    assert first["id"] == "i1"
    assert first["class"] == "tracker:class:Issue"
    assert first["score"] == 100.5


def test_search_empty_docs_array():
    """An empty ``docs`` array returns exit 0 with no rows rendered."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text='{"docs":[],"total":0'
        )
        result = runner.invoke(app, ["search", "no-hits"])
    assert result.exit_code == 0, result.output


# ── huly issues search wrapper ───────────────────────────────────────────────


def test_issues_search_filters_to_issue_class():
    """The wrapper prefills the Issue class so non-issue hits drop out."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(app, ["issues", "search", "login"])
    assert result.exit_code == 0, result.output
    assert "Fix login" in result.output
    # Document hit must not appear.
    assert "Onboarding" not in result.output


def test_issues_search_parses_truncated_response():
    """Wrapper must inherit the truncation workaround."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(app, ["issues", "search", "login"])
    assert result.exit_code == 0, result.output


def test_issues_search_json_output_mode():
    """``--json`` on the wrapper emits the same structured envelope."""
    with _auth_patch(), respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/search-fulltext/w").respond(
            200, text=TRUNCATED_SEARCH_BODY
        )
        result = runner.invoke(app, ["issues", "search", "q", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True
    # Only the issue hit survives.
    assert len(payload["data"]) == 1
    assert payload["data"][0]["class"] == "tracker:class:Issue"
