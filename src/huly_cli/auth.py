"""Authentication logic for Huly CLI."""

from __future__ import annotations

import time

import httpx

from huly_cli.config import AuthCache, HulyConfig, load_auth, save_auth
from huly_cli.errors import AuthError


async def login(config: HulyConfig) -> AuthCache:
    """Perform full auth flow and cache tokens.

    Steps:
    1. POST /_accounts → login → account_token
    2. POST /_accounts with account_token → selectWorkspace → workspace_token + workspace_id
    3. POST /_accounts with account_token → getUserWorkspaces → workspace_uuid
    4. GET /_transactor/api/v1/account/{workspace_id} → account_id
    5. Verify with ping
    """
    if not config.email:
        raise AuthError("Email is required for login. Set HULY_EMAIL env var.")
    if not config.password:
        raise AuthError("Password is required for login. Set HULY_PASSWORD env var.")
    if not config.workspace:
        raise AuthError("Workspace is required for login. Set HULY_WORKSPACE env var.")

    accounts_url = f"{config.url}/_accounts"
    transactor_base = f"{config.url}/_transactor"

    async with httpx.AsyncClient(timeout=30.0) as http:
        # Step 1: Login
        resp = await http.post(
            accounts_url,
            json={"id": "1", "method": "login", "params": [config.email, config.password]},
        )
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise AuthError(f"Login failed: {body['error']}")
        account_token: str = body["result"]["token"]

        # Step 2: Select workspace
        resp = await http.post(
            accounts_url,
            headers={"Authorization": f"Bearer {account_token}"},
            json={
                "id": "2",
                "method": "selectWorkspace",
                "params": [config.workspace, "external"],
            },
        )
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise AuthError(f"Select workspace failed: {body['error']}")
        ws_result = body["result"]
        workspace_token: str = ws_result["token"]
        workspace_id: str = ws_result["workspaceId"]

        # Step 3: Get workspace UUID via getUserWorkspaces
        resp = await http.post(
            accounts_url,
            headers={"Authorization": f"Bearer {account_token}"},
            json={"id": "3", "method": "getUserWorkspaces", "params": []},
        )
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise AuthError(f"getUserWorkspaces failed: {body['error']}")
        workspace_uuid = ""
        for ws in body.get("result", []):
            if ws.get("workspaceUrl") == config.workspace:
                workspace_uuid = ws.get("uuid", "")
                break
        if not workspace_uuid:
            raise AuthError(
                f"Could not find UUID for workspace '{config.workspace}' in getUserWorkspaces response."
            )

        # Step 4: Get account ID
        resp = await http.get(
            f"{transactor_base}/api/v1/account/{workspace_id}",
            headers={"Authorization": f"Bearer {workspace_token}"},
        )
        resp.raise_for_status()
        account_data = resp.json()
        # account endpoint returns the account object; _id is the account ID
        account_id: str = account_data.get("_id", account_data.get("id", ""))

        # Step 5: Ping to verify
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
        email=config.email,
        workspace_slug=config.workspace,
        account_id=account_id,
        cached_at=time.time(),
    )
    save_auth(auth)
    return auth


async def _ping(config: HulyConfig, auth: AuthCache) -> bool:
    """Ping the transactor to verify the cached token is still valid."""
    transactor_base = f"{config.url}/_transactor"
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
        # Token stale — re-login if we have credentials
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
