"""Unit tests for Huly cloud support and OTP login in `huly_cli.auth`.

Covers:
- `_accounts_url` endpoint selection (cloud vs self-hosted)
- Param-format detection: cloud accepts named params (dict), self-hosted
  requires positional params (list) for login, selectWorkspace,
  getUserWorkspaces, validateOtp, and loginOtp.
- `_rpc` error handling edge cases ({"error": null} must NOT raise).
- OTP flow: `send_otp` and `login_otp`.
- Cloud `endpoint` override for transactor base URL.
"""

from __future__ import annotations

import pytest
import respx
import httpx

from huly_cli import auth as auth_module
from huly_cli.config import HulyConfig
from huly_cli.errors import AuthError

SELF_HOSTED_ACCOUNTS_URL = "https://test.example.com/_accounts"
CLOUD_ACCOUNTS_URL = "https://account.huly.app"


@pytest.fixture
def cloud_config():
    return HulyConfig(
        url="https://app.huly.app",
        workspace="acme",
        email="u@example.com",
        password="pw",
    )


# ── endpoint + cloud detection ───────────────────────────────────────────────


def test_accounts_url_self_hosted(fake_config):
    assert auth_module._accounts_url(fake_config) == SELF_HOSTED_ACCOUNTS_URL


def test_accounts_url_cloud(cloud_config):
    assert auth_module._accounts_url(cloud_config) == CLOUD_ACCOUNTS_URL


def test_is_cloud_detection(fake_config, cloud_config):
    assert auth_module._is_cloud(cloud_config) is True
    assert auth_module._is_cloud(fake_config) is False


def test_params_helper_shape(cloud_config, fake_config):
    cloud = auth_module._params(
        cloud_config,
        cloud={"email": "x"},
        self_hosted=["x"],
    )
    assert cloud == {"email": "x"}

    self_hosted = auth_module._params(
        fake_config,
        cloud={"email": "x"},
        self_hosted=["x"],
    )
    assert self_hosted == ["x"]


# ── _rpc behavior ────────────────────────────────────────────────────────────


async def test_rpc_null_error_does_not_raise():
    """{"error": null} is valid — _rpc must not raise on it."""
    with respx.mock:
        respx.post(SELF_HOSTED_ACCOUNTS_URL).respond(
            json={"error": None, "result": {"ok": True}}
        )
        async with httpx.AsyncClient() as http:
            body = await auth_module._rpc(
                http, SELF_HOSTED_ACCOUNTS_URL, "login", {}
            )
        assert body["result"] == {"ok": True}


async def test_rpc_non_null_error_raises():
    with respx.mock:
        respx.post(SELF_HOSTED_ACCOUNTS_URL).respond(
            json={"error": "bad creds"}
        )
        async with httpx.AsyncClient() as http:
            with pytest.raises(AuthError) as exc:
                await auth_module._rpc(
                    http, SELF_HOSTED_ACCOUNTS_URL, "login", {}
                )
        assert "bad creds" in str(exc.value)


# ── self-hosted: positional params ───────────────────────────────────────────


async def test_self_hosted_login_sends_positional_params(fake_config):
    """Self-hosted login must send params as a list, not a dict."""
    captured = {}

    def handler(request):
        body = request.content
        import json as _json
        parsed = _json.loads(body)
        captured.setdefault("login_params", []).append(parsed["params"])
        method = parsed["method"]
        if method == "login":
            return httpx.Response(200, json={"result": {"token": "acct-tok"}})
        if method == "selectWorkspace":
            return httpx.Response(200, json={
                "result": {"token": "ws-tok", "workspaceId": "w-1"}
            })
        if method == "getUserWorkspaces":
            return httpx.Response(200, json={
                "result": [{"workspaceUrl": "test-ws", "uuid": "uuid-1"}]
            })
        return httpx.Response(500)

    with respx.mock:
        respx.post(SELF_HOSTED_ACCOUNTS_URL).mock(side_effect=handler)
        respx.get(
            "https://test.example.com/_transactor/api/v1/account/w-1"
        ).respond(json={"_id": "acc-1"})
        respx.get(
            "https://test.example.com/_transactor/api/v1/ping/w-1"
        ).respond(200)

        # save_auth writes to disk; patch it out.
        import unittest.mock as mock
        with mock.patch("huly_cli.auth.save_auth"):
            await auth_module.login(fake_config)

    # First call is login → must be list form
    assert isinstance(captured["login_params"][0], list)
    assert captured["login_params"][0] == ["test@test.com", "testpass"]
    # Second call is selectWorkspace → list form
    assert isinstance(captured["login_params"][1], list)
    assert captured["login_params"][1] == ["test-ws", "external"]
    # Third call is getUserWorkspaces → empty list
    assert captured["login_params"][2] == []


# ── cloud: named params ──────────────────────────────────────────────────────


async def test_cloud_login_sends_named_params(cloud_config):
    """Cloud login must send params as a dict."""
    captured = []

    def handler(request):
        import json as _json
        parsed = _json.loads(request.content)
        captured.append((parsed["method"], parsed["params"]))
        method = parsed["method"]
        if method == "login":
            return httpx.Response(200, json={"result": {"token": "acct"}})
        if method == "selectWorkspace":
            return httpx.Response(200, json={
                "result": {
                    "token": "ws",
                    "workspaceId": "w-1",
                    "endpoint": "wss://europe-tr1.huly.app",
                }
            })
        if method == "getUserWorkspaces":
            return httpx.Response(200, json={
                "result": [{"workspaceUrl": "acme", "uuid": "uuid-1"}]
            })
        return httpx.Response(500)

    with respx.mock:
        respx.post(CLOUD_ACCOUNTS_URL).mock(side_effect=handler)
        respx.get(
            "https://europe-tr1.huly.app/api/v1/account/w-1"
        ).respond(json={"_id": "acc-1"})
        respx.get(
            "https://europe-tr1.huly.app/api/v1/ping/w-1"
        ).respond(200)

        import unittest.mock as mock
        with mock.patch("huly_cli.auth.save_auth") as save:
            auth = await auth_module.login(cloud_config)

    methods = [c[0] for c in captured]
    assert methods[:3] == ["login", "selectWorkspace", "getUserWorkspaces"]
    assert captured[0][1] == {"email": "u@example.com", "password": "pw"}
    assert captured[1][1] == {"workspaceUrl": "acme", "kind": "external"}
    assert captured[2][1] == {}
    # transactor_base was overridden by cloud endpoint
    assert auth.transactor_base == "https://europe-tr1.huly.app"
    save.assert_called_once()


# ── OTP flow ─────────────────────────────────────────────────────────────────


async def test_send_otp_cloud_uses_named_params(cloud_config):
    captured = []

    def handler(request):
        import json as _json
        captured.append(_json.loads(request.content)["params"])
        return httpx.Response(200, json={"result": None})

    with respx.mock:
        respx.post(CLOUD_ACCOUNTS_URL).mock(side_effect=handler)
        await auth_module.send_otp(cloud_config)

    assert captured == [{"email": "u@example.com"}]


async def test_send_otp_self_hosted_uses_positional_params(fake_config):
    captured = []

    def handler(request):
        import json as _json
        captured.append(_json.loads(request.content)["params"])
        return httpx.Response(200, json={"result": None})

    with respx.mock:
        respx.post(SELF_HOSTED_ACCOUNTS_URL).mock(side_effect=handler)
        await auth_module.send_otp(fake_config)

    assert captured == [["test@test.com"]]


async def test_login_otp_validates_and_completes(cloud_config):
    cloud_config.otp_code = "123456"

    def handler(request):
        import json as _json
        parsed = _json.loads(request.content)
        method = parsed["method"]
        if method == "validateOtp":
            # Ensure named params were sent
            assert parsed["params"] == {
                "email": "u@example.com",
                "code": "123456",
            }
            return httpx.Response(200, json={"result": {"token": "acct"}})
        if method == "selectWorkspace":
            return httpx.Response(200, json={
                "result": {
                    "token": "ws",
                    "workspaceId": "w-1",
                    "endpoint": "wss://europe-tr1.huly.app",
                }
            })
        if method == "getUserWorkspaces":
            return httpx.Response(200, json={
                "result": [{"workspaceUrl": "acme", "uuid": "uuid-1"}]
            })
        return httpx.Response(500)

    with respx.mock:
        respx.post(CLOUD_ACCOUNTS_URL).mock(side_effect=handler)
        respx.get(
            "https://europe-tr1.huly.app/api/v1/account/w-1"
        ).respond(json={"_id": "acc-1"})
        respx.get(
            "https://europe-tr1.huly.app/api/v1/ping/w-1"
        ).respond(200)

        import unittest.mock as mock
        with mock.patch("huly_cli.auth.save_auth"):
            auth = await auth_module.login_otp(cloud_config)

    assert auth.account_token == "acct"
    assert auth.workspace_token == "ws"


async def test_login_otp_requires_code(cloud_config):
    cloud_config.otp_code = None
    with pytest.raises(AuthError):
        await auth_module.login_otp(cloud_config)


# ── result hardening ─────────────────────────────────────────────────────────


async def test_select_workspace_missing_token_raises_auth_error(cloud_config):
    def handler(request):
        import json as _json
        method = _json.loads(request.content)["method"]
        if method == "login":
            return httpx.Response(200, json={"result": {"token": "acct"}})
        # selectWorkspace returns no token
        return httpx.Response(200, json={"result": {}})

    with respx.mock:
        respx.post(CLOUD_ACCOUNTS_URL).mock(side_effect=handler)
        with pytest.raises(AuthError) as exc:
            await auth_module.login(cloud_config)

    assert "token" in str(exc.value).lower()


async def test_cloud_getuserworkspaces_missing_workspace_raises(cloud_config):
    def handler(request):
        import json as _json
        method = _json.loads(request.content)["method"]
        if method == "login":
            return httpx.Response(200, json={"result": {"token": "acct"}})
        if method == "selectWorkspace":
            return httpx.Response(200, json={
                "result": {"token": "ws", "workspaceId": "w-1"}
            })
        # workspace list does not contain the requested slug
        return httpx.Response(200, json={"result": [
            {"workspaceUrl": "other-ws", "uuid": "other-uuid"}
        ]})

    with respx.mock:
        respx.post(CLOUD_ACCOUNTS_URL).mock(side_effect=handler)
        with pytest.raises(AuthError) as exc:
            await auth_module.login(cloud_config)

    assert "acme" in str(exc.value)
