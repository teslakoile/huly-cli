"""HTTP client for Huly Transactor + Collaborator APIs."""

from __future__ import annotations

import asyncio
import json as json_mod
import time
import urllib.parse
from typing import Any

import httpx

from huly_cli.config import AuthCache, HulyConfig
from huly_cli.errors import AuthError, RateLimitError, ServerError
from huly_cli.output import print_warning

# Retry settings for Collaborator RPC (server 500s)
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles each attempt


class HulyClient:
    def __init__(self, config: HulyConfig, auth: AuthCache) -> None:
        self._config = config
        self._auth = auth
        self._transactor_base = auth.transactor_base or f"{config.url}/_transactor"
        self._http = httpx.AsyncClient(
            base_url=self._transactor_base,
            headers={"Authorization": f"Bearer {auth.workspace_token}"},
            timeout=30.0,
        )

    async def find_all(
        self,
        class_id: str,
        query: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Query documents via POST /api/v1/find-all/{workspace_id}."""
        query = query or {}
        body = {
            "_class": class_id,
            "query": query,
            "options": options or {},
        }
        resp = await self._http.post(
            f"/api/v1/find-all/{self._auth.workspace_id}",
            json=body,
        )
        data = self._handle_response(resp)
        return self._normalize_find_all_result(class_id, query, data)

    async def tx(self, transaction: dict[str, Any]) -> dict[str, Any]:
        """Execute a transaction via POST /api/v1/tx/{workspace_id}."""
        transaction = dict(transaction)
        transaction.setdefault("modifiedBy", self._auth.account_id)
        transaction.setdefault("modifiedOn", int(time.time() * 1000))
        resp = await self._http.post(
            f"/api/v1/tx/{self._auth.workspace_id}",
            json=transaction,
        )
        return self._handle_response(resp)

    async def ping(self) -> bool:
        """GET /api/v1/ping/{workspace_id} — returns True if server responds OK."""
        try:
            resp = await self._http.get(f"/api/v1/ping/{self._auth.workspace_id}")
            return resp.status_code == 200
        except Exception:
            return False

    async def get_account(self) -> dict[str, Any]:
        """GET /api/v1/account/{workspace_id} — current user account info."""
        resp = await self._http.get(f"/api/v1/account/{self._auth.workspace_id}")
        return self._handle_response(resp)

    # ── Collaborator RPC ──────────────────────────────────────────────────────

    async def _collaborator_rpc(
        self,
        class_id: str,
        object_id: str,
        field: str,
        method: str,
        payload: dict[str, Any],
    ) -> httpx.Response | None:
        """Send a Collaborator RPC request with automatic retry on 5xx errors.

        Returns the successful httpx.Response, or None after all retries are
        exhausted.
        """
        doc_id = self._build_doc_id(class_id, object_id, field)
        url = f"{self._config.url}/_collaborator/rpc/{doc_id}"
        headers = {
            "Authorization": f"Bearer {self._auth.workspace_token}",
            "Content-Type": "application/json",
        }
        body = {"method": method, "payload": payload}

        last_error: Exception | None = None
        last_status: int | None = None
        last_body: str = ""

        for attempt in range(_RETRY_MAX_ATTEMPTS):
            try:
                async with httpx.AsyncClient(timeout=15.0) as http:
                    resp = await http.post(url, headers=headers, json=body)
                if resp.status_code == 200:
                    return resp
                last_status = resp.status_code
                last_body = resp.text[:200]
                # Only retry on server errors (5xx)
                if resp.status_code < 500:
                    break
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_error = exc

            if attempt < _RETRY_MAX_ATTEMPTS - 1:
                delay = _RETRY_BASE_DELAY * (2**attempt)
                await asyncio.sleep(delay)

        # All retries exhausted — store details for caller
        self._last_rpc_status = last_status
        self._last_rpc_body = last_body
        self._last_rpc_error = last_error
        return None

    async def get_content(
        self, class_id: str, object_id: str, field: str, blob_ref: str
    ) -> str | None:
        """Fetch entity content ProseMirror JSON via Collaborator RPC.

        Works for any entity class and field, e.g.:
          - class_id="tracker:class:Issue", field="description"
          - class_id="document:class:Document", field="content"
        """
        resp = await self._collaborator_rpc(
            class_id,
            object_id,
            field,
            method="getContent",
            payload={"source": blob_ref},
        )
        if resp is None:
            self._warn_rpc_failure("getContent")
            return None
        data = resp.json()
        content = data.get("content", {}).get(field)
        if content is None:
            return None
        if isinstance(content, (dict, list)):
            return json_mod.dumps(content)
        return str(content)

    async def create_content(
        self,
        class_id: str,
        object_id: str,
        field: str,
        markup_json: str,
        *,
        warn_on_error: bool = True,
    ) -> str | None:
        """Create entity content via Collaborator RPC and return its blob ref."""
        resp = await self._collaborator_rpc(
            class_id,
            object_id,
            field,
            method="createContent",
            payload={"content": {field: markup_json}},
        )
        if resp is None:
            if warn_on_error:
                self._warn_rpc_failure("createContent")
            return None
        data = resp.json()
        blob_ref = data.get("content", {}).get(field)
        if blob_ref is None:
            return None
        return str(blob_ref)

    async def set_content(
        self,
        class_id: str,
        object_id: str,
        field: str,
        blob_ref: str,
        markup_json: str,
        *,
        warn_on_error: bool = True,
    ) -> bool:
        """Update entity content via Collaborator RPC.

        Works for any entity class and field.
        """
        resp = await self._collaborator_rpc(
            class_id,
            object_id,
            field,
            method="updateContent",
            payload={"source": blob_ref, "content": {field: markup_json}},
        )
        if resp is None:
            if warn_on_error:
                self._warn_rpc_failure("updateContent")
            return False
        return True

    def _warn_rpc_failure(self, method: str) -> None:
        """Emit a warning with details from the last failed RPC attempt."""
        status = getattr(self, "_last_rpc_status", None)
        body = getattr(self, "_last_rpc_body", "")
        error = getattr(self, "_last_rpc_error", None)
        if error:
            print_warning(f"{method} error after {_RETRY_MAX_ATTEMPTS} attempts: {error}")
        elif status:
            print_warning(f"{method} failed (HTTP {status}): {body}")
        else:
            print_warning(f"{method} failed after {_RETRY_MAX_ATTEMPTS} attempts")

    async def get_description(self, issue_id: str, blob_ref: str) -> str | None:
        """Fetch issue description ProseMirror JSON via Collaborator RPC.

        Thin wrapper around get_content for tracker:class:Issue / description.
        """
        return await self.get_content("tracker:class:Issue", issue_id, "description", blob_ref)

    async def create_description(
        self,
        issue_id: str,
        markup_json: str,
        *,
        warn_on_error: bool = True,
    ) -> str | None:
        """Create issue description content and return the blob ref."""
        return await self.create_content(
            "tracker:class:Issue",
            issue_id,
            "description",
            markup_json,
            warn_on_error=warn_on_error,
        )

    async def set_description(
        self,
        issue_id: str,
        blob_ref: str,
        markup_json: str,
        *,
        warn_on_error: bool = True,
    ) -> bool:
        """Update issue description via Collaborator RPC.

        Thin wrapper around set_content for tracker:class:Issue / description.
        """
        return await self.set_content(
            "tracker:class:Issue",
            issue_id,
            "description",
            blob_ref,
            markup_json,
            warn_on_error=warn_on_error,
        )

    def _build_doc_id(self, class_id: str, object_id: str, field: str) -> str:
        """URL-encode the collaborator document ID for any entity class and field."""
        raw = f"{self._auth.workspace_uuid}|{class_id}|{object_id}|{field}"
        return urllib.parse.quote(raw, safe="")

    # ── Response handling ─────────────────────────────────────────────────────

    def _handle_response(self, resp: httpx.Response) -> dict[str, Any]:
        if resp.status_code in (401, 403):
            raise AuthError(
                f"Authentication failed (HTTP {resp.status_code}). Run 'huly auth login'."
            )
        if resp.status_code == 429:
            # RFC 7231: `Retry-After` is in seconds (or an HTTP-date, unsupported
            # here). Only the explicitly millisecond-based `Retry-After-ms`
            # header should be converted — never guess based on magnitude.
            retry_after_header = resp.headers.get("Retry-After")
            if retry_after_header is not None:
                try:
                    retry_after = float(retry_after_header)
                except ValueError:
                    retry_after = 0.0
            else:
                try:
                    retry_after = float(resp.headers.get("Retry-After-ms", 0)) / 1000.0
                except ValueError:
                    retry_after = 0.0
            raise RateLimitError("Rate limit exceeded.", retry_after=retry_after)
        if resp.status_code >= 500:
            raise ServerError(f"Server error (HTTP {resp.status_code}): {resp.text[:200]}")
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            return {}

    def _normalize_find_all_result(
        self,
        class_id: str,
        query: dict[str, Any],
        data: dict[str, Any] | list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Mirror the upstream REST client normalization for `find-all`.

        The platform client restores scalar query values that may be omitted in
        filtered results and resolves lookup references using the response's
        `lookupMap`.
        """
        if isinstance(data, dict):
            lookup_map = data.pop("lookupMap", None)
            rows = data.get("value", [])
        else:
            lookup_map = None
            rows = data

        if not isinstance(rows, list):
            return []

        # Filter out any non-dict entries (e.g. ``None``) up front so callers
        # never see them. Keeping them in the list caused
        # ``Model.model_validate`` to raise ``ValidationError`` on null rows.
        rows = [row for row in rows if isinstance(row, dict)]

        if isinstance(lookup_map, dict):
            for row in rows:
                lookup = row.get("$lookup")
                if not isinstance(lookup, dict):
                    continue
                for key, value in list(lookup.items()):
                    if isinstance(value, list):
                        lookup[key] = [lookup_map.get(item) for item in value]
                    else:
                        lookup[key] = lookup_map.get(value)

        for row in rows:
            if row.get("_class") is None:
                row["_class"] = class_id
            for key, value in query.items():
                if isinstance(value, (str, int, bool)) and row.get(key) is None:
                    row[key] = value

        return rows

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> HulyClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self._http.aclose()
