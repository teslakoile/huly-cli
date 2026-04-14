"""Unit tests for `huly_cli.auth` covering malformed API responses.

Regression tests for issue #18: the login flow previously raised
a raw ``KeyError: 'result'`` when the accounts API returned an
unexpected ``200 OK`` body. These tests assert that a descriptive
``AuthError`` is raised instead.
"""

from __future__ import annotations

import pytest
import respx

from huly_cli import auth as auth_module
from huly_cli.errors import AuthError

ACCOUNTS_URL = "https://test.example.com/_accounts"


async def test_login_raises_auth_error_when_result_missing(fake_config):
    """Login 200 response without a 'result' key should raise AuthError, not KeyError."""
    with respx.mock:
        respx.post(ACCOUNTS_URL).respond(json={})

        with pytest.raises(AuthError) as exc_info:
            await auth_module.login(fake_config)

    message = str(exc_info.value)
    assert "result" in message.lower()
    assert "KeyError" not in type(exc_info.value).__name__


async def test_login_raises_auth_error_when_result_has_no_token(fake_config):
    """Login 200 response where result lacks 'token' should raise AuthError, not KeyError."""
    with respx.mock:
        respx.post(ACCOUNTS_URL).respond(json={"result": {}})

        with pytest.raises(AuthError) as exc_info:
            await auth_module.login(fake_config)

    message = str(exc_info.value)
    assert "token" in message.lower()


async def test_login_raises_auth_error_when_error_null_and_no_result(fake_config):
    """An {'error': null} 200 body is still a malformed login response → AuthError."""
    with respx.mock:
        respx.post(ACCOUNTS_URL).respond(json={"error": None})

        with pytest.raises(AuthError):
            await auth_module.login(fake_config)


async def test_login_raises_auth_error_when_select_workspace_missing_token(fake_config):
    """selectWorkspace response missing 'token' should raise AuthError, not KeyError."""
    with respx.mock:
        # respx matches routes in registration order and returns the first match;
        # we use a side_effect to return different bodies for successive calls.
        call_count = {"n": 0}

        def handler(request):
            import httpx as _httpx

            call_count["n"] += 1
            if call_count["n"] == 1:
                # login succeeds
                return _httpx.Response(200, json={"result": {"token": "acct-tok"}})
            # selectWorkspace returns body without token/workspaceId
            return _httpx.Response(200, json={"result": {}})

        respx.post(ACCOUNTS_URL).mock(side_effect=handler)

        with pytest.raises(AuthError) as exc_info:
            await auth_module.login(fake_config)

    message = str(exc_info.value).lower()
    assert "token" in message or "workspaceid" in message or "workspace" in message


async def test_login_raises_auth_error_when_select_workspace_missing_result(fake_config):
    """selectWorkspace response without 'result' should raise AuthError, not KeyError."""
    with respx.mock:
        call_count = {"n": 0}

        def handler(request):
            import httpx as _httpx

            call_count["n"] += 1
            if call_count["n"] == 1:
                return _httpx.Response(200, json={"result": {"token": "acct-tok"}})
            # selectWorkspace: no 'result' key
            return _httpx.Response(200, json={})

        respx.post(ACCOUNTS_URL).mock(side_effect=handler)

        with pytest.raises(AuthError) as exc_info:
            await auth_module.login(fake_config)

    assert "result" in str(exc_info.value).lower()
