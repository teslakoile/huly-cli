"""Authentication logic for Huly CLI."""

from __future__ import annotations

import time
from urllib.parse import urlparse

import httpx

from huly_cli.config import AuthCache, HulyConfig, load_auth, save_auth
from huly_cli.errors import AuthError


def _is_cloud(config: HulyConfig) -> bool:
    """Return True if the configured URL points at Huly cloud (huly.app)."""
    parsed = urlparse(config.url)
    return bool(parsed.hostname and parsed.hostname.endswith(".huly.app"))


def _accounts_url(config: HulyConfig) -> str:
    """Return the accounts RPC endpoint for the given Huly instance.

    Huly cloud (huly.app) uses a dedicated ``account`` subdomain.
    Self-hosted instances expose the account service at ``/_accounts``
    via an nginx reverse-proxy.
    """
    if _is_cloud(config):
        parsed = urlparse(config.url)
        return f"{parsed.scheme or 'https'}://account.huly.app"
    return f"{config.url}/_accounts"


def _params(config: HulyConfig, *, cloud: dict, self_hosted: list) -> dict | list:
    """Return request params in the format expected by the target instance.

    Cloud accepts named params (dict); self-hosted expects positional params (list).
    """
    return cloud if _is_cloud(config) else self_hosted


async def _rpc(
    http: httpx.AsyncClient,
    url: str,
    method: str,
    params: dict | list,
    *,
    token: str | None = None,
    request_id: str = "1",
) -> dict:
    """Send a JSON-RPC request to the Huly accounts service."""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = await http.post(
        url,
        headers=headers,
        json={"id": request_id, "method": method, "params": params},
    )
    resp.raise_for_status()
    body = resp.json()
    if "error" in body and body["error"] is not None:
        raise AuthError(f"{method} failed: {body['error']}")
    return body


def _require_result_dict(body: dict, method: str) -> dict:
    result = body.get("result")
    if not isinstance(result, dict):
        raise AuthError(
            f"{method} failed: unexpected response from accounts API "
            "(missing or invalid 'result' field). The server may be "
            "incompatible or a proxy may be intercepting the request."
        )
    return result


def _require_str(result: dict, key: str, method: str) -> str:
    value = result.get(key)
    if not value or not isinstance(value, str):
        raise AuthError(
            f"{method} failed: response did not include a '{key}' "
            "in the 'result' payload."
        )
    return value


async def login(config: HulyConfig) -> AuthCache:
    """Perform full password auth flow and cache tokens.

    Steps:
    1. POST accounts → login → account_token
    2. POST accounts with account_token → selectWorkspace → workspace_token
    3. POST accounts with account_token → getUserWorkspaces → workspace_uuid
    4. GET transactor/api/v1/account/{workspace_id} → account_id
    5. Verify with ping
    """
    if not config.email:
        raise AuthError("Email is required for login. Set HULY_EMAIL env var.")
    if not config.password:
        raise AuthError("Password is required for login. Set HULY_PASSWORD env var.")
    if not config.workspace:
        raise AuthError("Workspace is required for login. Set HULY_WORKSPACE env var.")

    accounts_url = _accounts_url(config)
    transactor_base = f"{config.url}/_transactor"

    async with httpx.AsyncClient(timeout=30.0) as http:
        login_params = _params(
            config,
            cloud={"email": config.email, "password": config.password},
            self_hosted=[config.email, config.password],
        )
        body = await _rpc(http, accounts_url, "login", login_params)
        result = _require_result_dict(body, "Login")
        account_token = _require_str(result, "token", "Login")

        return await _complete_login(
            http, config, accounts_url, transactor_base, account_token,
        )


async def login_otp(config: HulyConfig, code: str) -> AuthCache:
    """Perform OTP (email code) auth flow and cache tokens.

    Caller is responsible for sending the OTP first via ``send_otp`` and
    collecting the code (e.g. from a prompt or ``--code`` flag).
    """
    if not config.email:
        raise AuthError("Email is required for OTP login. Set HULY_EMAIL env var.")
    if not config.workspace:
        raise AuthError("Workspace is required for login. Set HULY_WORKSPACE env var.")
    if not code:
        raise AuthError("OTP code required. Check your email and pass --code.")

    accounts_url = _accounts_url(config)
    transactor_base = f"{config.url}/_transactor"

    async with httpx.AsyncClient(timeout=30.0) as http:
        otp_params = _params(
            config,
            cloud={"email": config.email, "code": code},
            self_hosted=[config.email, code],
        )
        body = await _rpc(http, accounts_url, "validateOtp", otp_params)
        result = _require_result_dict(body, "OTP login")
        account_token = _require_str(result, "token", "OTP login")

        return await _complete_login(
            http, config, accounts_url, transactor_base, account_token,
        )


async def send_otp(config: HulyConfig) -> None:
    """Request an OTP code to be sent to the user's email."""
    if not config.email:
        raise AuthError("Email is required. Set HULY_EMAIL env var.")

    accounts_url = _accounts_url(config)
    async with httpx.AsyncClient(timeout=30.0) as http:
        params = _params(
            config,
            cloud={"email": config.email},
            self_hosted=[config.email],
        )
        await _rpc(http, accounts_url, "loginOtp", params)


async def _complete_login(
    http: httpx.AsyncClient,
    config: HulyConfig,
    accounts_url: str,
    transactor_base: str,
    account_token: str,
) -> AuthCache:
    """Complete login after obtaining an account token (from password or OTP)."""
    select_params = _params(
        config,
        cloud={"workspaceUrl": config.workspace, "kind": "external"},
        self_hosted=[config.workspace, "external"],
    )
    body = await _rpc(
        http, accounts_url, "selectWorkspace", select_params,
        token=account_token, request_id="2",
    )
    ws_result = _require_result_dict(body, "Select workspace")
    workspace_token = _require_str(ws_result, "token", "Select workspace")
    workspace_id = ws_result.get("workspaceId") or ws_result.get("workspace", "")
    if not isinstance(workspace_id, str) or not workspace_id:
        raise AuthError(
            "Select workspace failed: response did not include a 'workspaceId' "
            "in the 'result' payload."
        )

    # Cloud returns a per-region transactor endpoint (e.g. wss://europe-tr1.huly.app).
    # Use it for REST calls instead of the default /_transactor path. Self-hosted
    # instances reach the transactor through the nginx /_transactor reverse-proxy,
    # so leave the base URL alone even if the response carries an `endpoint` field.
    if _is_cloud(config):
        endpoint = ws_result.get("endpoint", "")
        if endpoint:
            transactor_base = endpoint.replace("wss://", "https://").replace("ws://", "http://")

    ws_list_params = _params(config, cloud={}, self_hosted=[])
    body = await _rpc(
        http, accounts_url, "getUserWorkspaces", ws_list_params,
        token=account_token, request_id="3",
    )
    workspaces = body.get("result") or []
    if not isinstance(workspaces, list):
        raise AuthError(
            "getUserWorkspaces failed: unexpected response shape (expected list)."
        )
    workspace_uuid = ""
    for ws in workspaces:
        if not isinstance(ws, dict):
            continue
        if ws.get("workspaceUrl") == config.workspace or ws.get("url") == config.workspace:
            workspace_uuid = ws.get("uuid", "")
            break
    if not workspace_uuid:
        raise AuthError(
            f"Could not find UUID for workspace '{config.workspace}' in getUserWorkspaces response."
        )

    resp = await http.get(
        f"{transactor_base}/api/v1/account/{workspace_id}",
        headers={"Authorization": f"Bearer {workspace_token}"},
    )
    resp.raise_for_status()
    account_data = resp.json()
    account_id: str = account_data.get("_id", account_data.get("id", ""))

    ping_resp = await http.get(
        f"{transactor_base}/api/v1/ping/{workspace_id}",
        headers={"Authorization": f"Bearer {workspace_token}"},
    )
    ping_resp.raise_for_status()

    auth = AuthCache(
        account_token=account_token,
        workspace_token=workspace_token,
        workspace_id=workspace_id,
        workspace_uuid=workspace_uuid,
        email=config.email or "",
        workspace_slug=config.workspace,
        account_id=account_id,
        cached_at=time.time(),
        transactor_base=transactor_base,
    )
    save_auth(auth)
    return auth


async def _ping(config: HulyConfig, auth: AuthCache) -> bool:
    """Ping the transactor to verify the cached token is still valid."""
    transactor_base = auth.transactor_base or f"{config.url}/_transactor"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(
                f"{transactor_base}/api/v1/ping/{auth.workspace_id}",
                headers={"Authorization": f"Bearer {auth.workspace_token}"},
            )
            return resp.status_code == 200
    except Exception:
        return False


async def ensure_auth(config: HulyConfig) -> AuthCache:
    """Return valid auth — use cache if fresh, otherwise re-login."""
    cached = load_auth()
    if cached is not None:
        if await _ping(config, cached):
            return cached
        if not config.email or not config.password:
            raise AuthError(
                "Cached token is invalid and no credentials available to re-authenticate. "
                "Run 'huly auth login'."
            )
    elif not config.email or not config.password:
        raise AuthError("Not authenticated. Run 'huly auth login'.")

    return await login(config)


async def check_auth_status(config: HulyConfig) -> dict:
    """Return a dict describing current auth status."""
    import time as time_mod

    cached = load_auth()
    if cached is None:
        return {"authenticated": False, "email": None, "workspace": None, "token_age": None}

    is_valid = await _ping(config, cached)
    age_seconds = time_mod.time() - cached.cached_at
    return {
        "authenticated": is_valid,
        "email": cached.email,
        "workspace": cached.workspace_slug,
        "workspace_id": cached.workspace_id,
        "workspace_uuid": cached.workspace_uuid,
        "token_age_seconds": int(age_seconds),
        "token_age_human": _humanize_age(age_seconds),
    }


def _humanize_age(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h"
    return f"{int(seconds // 86400)}d"
