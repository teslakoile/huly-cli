"""HTTP client for Huly Transactor + Collaborator APIs."""

from __future__ import annotations

import json as json_mod
import time
import urllib.parse
from typing import Any

import httpx

from huly_cli.config import AuthCache, HulyConfig
from huly_cli.errors import AuthError, RateLimitError, ServerError
from huly_cli.output import print_warning


class HulyClient:
    def __init__(self, config: HulyConfig, auth: AuthCache) -> None:
        self._config = config
        self._auth = auth
        self._transactor_base = f"{config.url}/_transactor"
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

    async def get_content(
        self, class_id: str, object_id: str, field: str, blob_ref: str
    ) -> str | None:
        """Fetch entity content ProseMirror JSON via Collaborator RPC.

        Works for any entity class and field, e.g.:
          - class_id="tracker:class:Issue", field="description"
          - class_id="document:class:Document", field="content"
        """
        doc_id = self._build_doc_id(class_id, object_id, field)
        url = f"{self._config.url}/_collaborator/rpc/{doc_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._auth.workspace_token}",
                        "Content-Type": "application/json",
                    },
                    json={"method": "getContent", "payload": {"source": blob_ref}},
                )
                if resp.status_code != 200:
                    print_warning(f"getContent returned HTTP {resp.status_code}: {resp.text[:200]}")
                    return None
                data = resp.json()
                content = data.get("content", {}).get(field)
                if content is None:
                    return None
                if isinstance(content, (dict, list)):
                    return json_mod.dumps(content)
                return str(content)
        except Exception as e:
            print_warning(f"getContent error: {e}")
            return None

    async def create_content(
        self, class_id: str, object_id: str, field: str, markup_json: str
    ) -> str | None:
        """Create entity content via Collaborator RPC and return its blob ref."""
        doc_id = self._build_doc_id(class_id, object_id, field)
        url = f"{self._config.url}/_collaborator/rpc/{doc_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._auth.workspace_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "method": "createContent",
                        "payload": {
                            "content": {field: json_mod.loads(markup_json)},
                        },
                    },
                )
                if resp.status_code != 200:
                    print_warning(
                        f"createContent failed (HTTP {resp.status_code}): {resp.text[:200]}"
                    )
                    return None
                data = resp.json()
                blob_ref = data.get("content", {}).get(field)
                if blob_ref is None:
                    return None
                return str(blob_ref)
        except Exception as e:
            print_warning(f"createContent error: {e}")
            return None

    async def set_content(
        self, class_id: str, object_id: str, field: str, blob_ref: str, markup_json: str
    ) -> bool:
        """Update entity content via Collaborator RPC.

        Works for any entity class and field.
        """
        doc_id = self._build_doc_id(class_id, object_id, field)
        url = f"{self._config.url}/_collaborator/rpc/{doc_id}"
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {self._auth.workspace_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "method": "updateContent",
                        "payload": {
                            "source": blob_ref,
                            "content": {field: json_mod.loads(markup_json)},
                        },
                    },
                )
                if resp.status_code != 200:
                    print_warning(
                        f"updateContent failed (HTTP {resp.status_code}): {resp.text[:200]}"
                    )
                    return False
                return True
        except Exception as e:
            print_warning(f"updateContent error: {e}")
            return False

    async def get_description(self, issue_id: str, blob_ref: str) -> str | None:
        """Fetch issue description ProseMirror JSON via Collaborator RPC.

        Thin wrapper around get_content for tracker:class:Issue / description.
        """
        return await self.get_content("tracker:class:Issue", issue_id, "description", blob_ref)

    async def create_description(self, issue_id: str, markup_json: str) -> str | None:
        """Create issue description content and return the blob ref."""
        return await self.create_content(
            "tracker:class:Issue", issue_id, "description", markup_json
        )

    async def set_description(self, issue_id: str, blob_ref: str, markup_json: str) -> bool:
        """Update issue description via Collaborator RPC.

        Thin wrapper around set_content for tracker:class:Issue / description.
        """
        return await self.set_content(
            "tracker:class:Issue", issue_id, "description", blob_ref, markup_json
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
            retry_after = float(
                resp.headers.get("Retry-After") or resp.headers.get("Retry-After-ms", 0)
            )
            if retry_after > 1000:
                retry_after /= 1000  # convert ms to seconds
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

        if isinstance(lookup_map, dict):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                lookup = row.get("$lookup")
                if not isinstance(lookup, dict):
                    continue
                for key, value in list(lookup.items()):
                    if isinstance(value, list):
                        lookup[key] = [lookup_map.get(item) for item in value]
                    else:
                        lookup[key] = lookup_map.get(value)

        for row in rows:
            if not isinstance(row, dict):
                continue
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
