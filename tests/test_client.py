"""Async tests for HulyClient using respx to mock httpx."""

from __future__ import annotations

import json
import urllib.parse

import pytest
import respx

from huly_cli.client import HulyClient
from huly_cli.errors import AuthError, RateLimitError, ServerError

# ── find_all ───────────────────────────────────────────────────────────────────


async def test_find_all(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json={"value": [{"_id": "i1", "title": "Issue One"}], "total": -1}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.find_all("tracker:class:Issue")
    assert len(result) == 1
    assert result[0]["title"] == "Issue One"


async def test_find_all_with_query(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json={"value": [{"_id": "i2", "identifier": "DEMO-1"}], "total": -1}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.find_all("tracker:class:Issue", query={"identifier": "DEMO-1"})
    assert result[0]["identifier"] == "DEMO-1"


async def test_find_all_empty_result(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json={"value": [], "total": 0}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.find_all("tracker:class:Issue")
    assert result == []


async def test_find_all_with_options(fake_config, fake_auth):
    with respx.mock:
        route = respx.post(
            "https://test.example.com/_transactor/api/v1/find-all/w-test-123"
        ).respond(json={"value": [], "total": 0})
        async with HulyClient(fake_config, fake_auth) as client:
            await client.find_all("tracker:class:Issue", options={"limit": 10})
        sent_body = json.loads(route.calls[0].request.content)
        assert sent_body["options"]["limit"] == 10


# ── tx ─────────────────────────────────────────────────────────────────────────


async def test_tx_adds_modified_fields(fake_config, fake_auth):
    with respx.mock:
        route = respx.post("https://test.example.com/_transactor/api/v1/tx/w-test-123").respond(
            json={"result": "ok"}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            await client.tx({"_class": "core:class:TxUpdateDoc", "operations": {"title": "new"}})
        body = json.loads(route.calls[0].request.content)
        assert body["modifiedBy"] == "acc-test-789"
        assert "modifiedOn" in body


async def test_tx_does_not_override_existing_modified_by(fake_config, fake_auth):
    with respx.mock:
        route = respx.post("https://test.example.com/_transactor/api/v1/tx/w-test-123").respond(
            json={}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            await client.tx(
                {
                    "_class": "core:class:TxUpdateDoc",
                    "modifiedBy": "custom-user",
                    "operations": {},
                }
            )
        body = json.loads(route.calls[0].request.content)
        # setdefault should not override the provided modifiedBy
        assert body["modifiedBy"] == "custom-user"


# ── ping ───────────────────────────────────────────────────────────────────────


async def test_ping_success(fake_config, fake_auth):
    with respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/ping/w-test-123").respond(200)
        async with HulyClient(fake_config, fake_auth) as client:
            assert await client.ping() is True


async def test_ping_failure(fake_config, fake_auth):
    with respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/ping/w-test-123").respond(500)
        async with HulyClient(fake_config, fake_auth) as client:
            assert await client.ping() is False


async def test_ping_non_200_is_false(fake_config, fake_auth):
    with respx.mock:
        respx.get("https://test.example.com/_transactor/api/v1/ping/w-test-123").respond(404)
        async with HulyClient(fake_config, fake_auth) as client:
            assert await client.ping() is False


# ── Error handling ─────────────────────────────────────────────────────────────


async def test_auth_error_on_401(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(401)
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(AuthError):
                await client.find_all("tracker:class:Issue")


async def test_auth_error_on_403(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(403)
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(AuthError):
                await client.find_all("tracker:class:Issue")


async def test_rate_limit_on_429(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            429, headers={"Retry-After": "30"}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.find_all("tracker:class:Issue")
        assert exc_info.value.retry_after == 30.0


async def test_server_error_on_500(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            500, text="Internal Error"
        )
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(ServerError):
                await client.find_all("tracker:class:Issue")


async def test_server_error_on_503(fake_config, fake_auth):
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            503, text="Service Unavailable"
        )
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(ServerError):
                await client.find_all("tracker:class:Issue")


# ── get_description / set_description ─────────────────────────────────────────


async def test_get_description(fake_config, fake_auth):
    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    with respx.mock:
        respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").respond(
            json={"content": {"description": {"type": "doc", "content": []}}}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.get_description("issue1", "blob-ref-123")
    assert result is not None
    parsed = json.loads(result)
    assert parsed["type"] == "doc"


async def test_create_description(fake_config, fake_auth):
    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    with respx.mock:
        route = respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").respond(
            json={"content": {"description": "blob-ref-456"}}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.create_description("issue1", '{"type":"doc","content":[]}')
    assert result == "blob-ref-456"
    body = json.loads(route.calls[0].request.content)
    assert body["method"] == "createContent"
    assert body["payload"]["content"]["description"] == '{"type":"doc","content":[]}'


async def test_create_content_falls_back_to_update_content(fake_config, fake_auth):
    """Regression for #31/#32: when createContent fails, fall back to updateContent."""
    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        body = json.loads(request.content)
        if body["method"] == "createContent":
            return respx.MockResponse(500, text='{"error":"The specified bucket does not exist"}')
        # updateContent fallback succeeds
        return respx.MockResponse(200, json={})

    with respx.mock:
        respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").mock(
            side_effect=side_effect
        )
        async with HulyClient(fake_config, fake_auth) as client:
            # Disable retry delay for test speed
            import huly_cli.client as client_mod

            original_delay = client_mod._RETRY_BASE_DELAY
            client_mod._RETRY_BASE_DELAY = 0.01
            try:
                result = await client.create_description(
                    "issue1", '{"type":"doc","content":[]}', warn_on_error=False
                )
            finally:
                client_mod._RETRY_BASE_DELAY = original_delay

    assert result is not None
    assert result.startswith("issue1-description-")


async def test_set_description(fake_config, fake_auth):
    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    with respx.mock:
        route = respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").respond(
            200, json={}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            ok = await client.set_description(
                "issue1",
                "blob-ref-123",
                '{"type":"doc","content":[]}',
            )
    assert ok is True
    body = json.loads(route.calls[0].request.content)
    assert body["method"] == "updateContent"
    assert body["payload"]["source"] == "blob-ref-123"
    assert body["payload"]["content"]["description"] == '{"type":"doc","content":[]}'


# ── Collaborator RPC retry ───────────────────────────────────────────────────


async def test_collaborator_rpc_retries_on_500(fake_config, fake_auth, monkeypatch):
    """set_description retries on 500 and succeeds on the second attempt."""
    import huly_cli.client as client_mod

    monkeypatch.setattr(client_mod, "_RETRY_BASE_DELAY", 0.01)

    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return respx.MockResponse(500, text='{"error":"Failed to save document"}')
        return respx.MockResponse(200, json={})

    with respx.mock:
        respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").mock(
            side_effect=side_effect
        )
        async with HulyClient(fake_config, fake_auth) as client:
            ok = await client.set_description("issue1", "blob-ref-123", '{"type":"doc"}')
    assert ok is True
    assert call_count == 2


async def test_collaborator_rpc_fails_after_max_retries(fake_config, fake_auth, monkeypatch):
    """set_description returns False after exhausting all retries on 500."""
    import huly_cli.client as client_mod

    monkeypatch.setattr(client_mod, "_RETRY_BASE_DELAY", 0.01)

    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    with respx.mock:
        route = respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").respond(
            500, text='{"error":"Failed to save document"}'
        )
        async with HulyClient(fake_config, fake_auth) as client:
            ok = await client.set_description("issue1", "blob-ref-123", '{"type":"doc"}')
    assert ok is False
    assert len(route.calls) == 3  # 3 attempts total


async def test_collaborator_rpc_no_retry_on_4xx(fake_config, fake_auth, monkeypatch):
    """Non-5xx errors (e.g. 400) are not retried."""
    import huly_cli.client as client_mod

    monkeypatch.setattr(client_mod, "_RETRY_BASE_DELAY", 0.01)

    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    with respx.mock:
        route = respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").respond(
            400, text="Bad Request"
        )
        async with HulyClient(fake_config, fake_auth) as client:
            ok = await client.set_description("issue1", "blob-ref-123", '{"type":"doc"}')
    assert ok is False
    assert len(route.calls) == 1  # no retry


async def test_collaborator_rpc_retries_create_content(fake_config, fake_auth, monkeypatch):
    """create_description also retries on 500."""
    import huly_cli.client as client_mod

    monkeypatch.setattr(client_mod, "_RETRY_BASE_DELAY", 0.01)

    doc_id = urllib.parse.quote("uuid-test-456|tracker:class:Issue|issue1|description", safe="")
    call_count = 0

    def side_effect(request, route):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return respx.MockResponse(500, text="error")
        return respx.MockResponse(200, json={"content": {"description": "blob-new"}})

    with respx.mock:
        respx.post(f"https://test.example.com/_collaborator/rpc/{doc_id}").mock(
            side_effect=side_effect
        )
        async with HulyClient(fake_config, fake_auth) as client:
            ref = await client.create_description("issue1", '{"type":"doc"}')
    assert ref == "blob-new"
    assert call_count == 3


# ── Retry-After header handling (Bug A) ──────────────────────────────────────


async def test_rate_limit_retry_after_large_seconds_not_converted(fake_config, fake_auth):
    """Retry-After: 1500 is valid seconds per RFC 7231, must NOT be divided by 1000.

    Regression test for Issue #20 Bug A: the `> 1000` heuristic silently converted
    a legitimate 1500-second wait into 1.5 seconds.
    """
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            429, headers={"Retry-After": "1500"}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.find_all("tracker:class:Issue")
    # Must be treated as seconds per RFC 7231, not milliseconds.
    assert exc_info.value.retry_after == 1500.0


async def test_rate_limit_retry_after_small_seconds_unchanged(fake_config, fake_auth):
    """Retry-After: 500 is 500 seconds, must NOT be reinterpreted as ms."""
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            429, headers={"Retry-After": "500"}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.find_all("tracker:class:Issue")
    assert exc_info.value.retry_after == 500.0


# ── find_all filters non-dict rows (Bug B) ───────────────────────────────────


async def test_find_all_drops_null_rows(fake_config, fake_auth):
    """Non-dict rows (e.g. null) in the server response must be filtered out.

    Regression test for Issue #20 Bug B: the normalisation loop used `continue`
    to skip non-dicts but left them in the returned list, causing
    Model.model_validate(None) ValidationError downstream.
    """
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json={"value": [None, {"_id": "x", "name": "real"}], "total": -1}
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.find_all("tracker:class:Issue")
    # Only the dict row should survive — the `None` must be dropped, not kept.
    assert len(result) == 1
    assert all(isinstance(row, dict) for row in result)
    assert result[0]["_id"] == "x"


async def test_find_all_drops_mixed_non_dict_rows(fake_config, fake_auth):
    """Mixed non-dict items (null, string, int) must all be filtered out."""
    with respx.mock:
        respx.post("https://test.example.com/_transactor/api/v1/find-all/w-test-123").respond(
            json={
                "value": [None, "stray-string", 42, {"_id": "keep", "name": "real"}],
                "total": -1,
            }
        )
        async with HulyClient(fake_config, fake_auth) as client:
            result = await client.find_all("tracker:class:Issue")
    assert len(result) == 1
    assert result[0]["_id"] == "keep"
