"""Unit coverage for CONN-03's ADO PAT smoke-test (ado_client.run_smoke_test).

httpx.AsyncClient.get/.post are mocked via unittest.mock.patch — no respx or
other HTTP-mocking dependency added, per 02-RESEARCH.md's Wave 0 test map.
Mock responses mirror the shape _check_json_response expects: a
headers.get("content-type") call and a .json() call.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import ado_client


def _mock_response(status_code: int, json_body=None, content_type="application/json"):
    response = MagicMock()
    response.status_code = status_code
    response.headers = {"content-type": content_type}
    if json_body is not None:
        response.json.return_value = json_body
    else:
        response.json.side_effect = ValueError("no body")
    return response


def _patched_async_client(get_response=None, post_response=None):
    """Build a mock httpx.AsyncClient context manager returning canned responses."""
    client_instance = MagicMock()
    client_instance.get = AsyncMock(return_value=get_response)
    client_instance.post = AsyncMock(return_value=post_response)

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=client_instance)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


@pytest.mark.asyncio
async def test_project_access_passes_on_200_json(mock_ado_env):
    resp = _mock_response(200, json_body={"value": []})
    with patch("httpx.AsyncClient", return_value=_patched_async_client(get_response=resp)):
        result = await ado_client.check_project_access()
    assert result == {"check": "project_access", "passed": True, "reason": None}


@pytest.mark.asyncio
async def test_project_access_fails_on_203_non_json(mock_ado_env):
    resp = _mock_response(203, json_body=None, content_type="text/html")
    with patch("httpx.AsyncClient", return_value=_patched_async_client(get_response=resp)):
        result = await ado_client.check_project_access()
    assert result["passed"] is False
    assert "PAT invalid or expired" in result["reason"]


@pytest.mark.asyncio
async def test_project_access_fails_on_401(mock_ado_env):
    resp = _mock_response(401, json_body={"message": "unauthorized"})
    with patch("httpx.AsyncClient", return_value=_patched_async_client(get_response=resp)):
        result = await ado_client.check_project_access()
    assert result["passed"] is False
    assert "401" in result["reason"]


@pytest.mark.asyncio
async def test_project_access_fails_on_403(mock_ado_env):
    resp = _mock_response(403, json_body={"message": "forbidden"})
    with patch("httpx.AsyncClient", return_value=_patched_async_client(get_response=resp)):
        result = await ado_client.check_project_access()
    assert result["passed"] is False
    assert "403" in result["reason"]


@pytest.mark.asyncio
async def test_run_smoke_test_short_circuits_on_project_access_failure(mock_ado_env):
    resp = _mock_response(401, json_body={"message": "unauthorized"})
    with patch("httpx.AsyncClient", return_value=_patched_async_client(get_response=resp)):
        result = await ado_client.run_smoke_test("lead@example.com")
    assert result["passed"] is False
    assert len(result["checks"]) == 1
    assert result["checks"][0]["check"] == "project_access"


@pytest.mark.asyncio
async def test_run_smoke_test_fails_when_write_scope_raises(mock_ado_env):
    access_resp = _mock_response(200, json_body={"value": []})

    async def fake_check_write_scope(lead_email):
        return {"check": "write_scope", "passed": False, "reason": "create_work_item failed: status=403"}

    async def fake_check_expiry_best_effort():
        return {"check": "expiry", "passed": True, "reason": "unknown (best-effort check unavailable)"}

    with (
        patch.object(ado_client, "check_project_access", AsyncMock(return_value={
            "check": "project_access", "passed": True, "reason": None,
        })),
        patch.object(ado_client, "check_write_scope", fake_check_write_scope),
        patch.object(ado_client, "check_expiry_best_effort", fake_check_expiry_best_effort),
    ):
        result = await ado_client.run_smoke_test("lead@example.com")

    assert result["passed"] is False
    assert len(result["checks"]) == 3
    assert result["checks"][1]["check"] == "write_scope"
    assert result["checks"][1]["passed"] is False


@pytest.mark.asyncio
async def test_run_smoke_test_passes_with_all_three_checks_even_if_expiry_probe_fails(mock_ado_env):
    async def fake_check_project_access():
        return {"check": "project_access", "passed": True, "reason": None}

    async def fake_check_write_scope(lead_email):
        return {"check": "write_scope", "passed": True, "reason": None}

    # Force a non-200 on the expiry (pats) endpoint — run_smoke_test must
    # never raise and must still report overall passed=True.
    expiry_resp = _mock_response(403, json_body=None, content_type="text/html")

    with (
        patch.object(ado_client, "check_project_access", fake_check_project_access),
        patch.object(ado_client, "check_write_scope", fake_check_write_scope),
        patch("httpx.AsyncClient", return_value=_patched_async_client(get_response=expiry_resp)),
    ):
        result = await ado_client.run_smoke_test("lead@example.com")

    assert result["passed"] is True
    assert len(result["checks"]) == 3
    assert result["checks"][2]["check"] == "expiry"
    assert result["checks"][2]["passed"] is True
    assert result["checks"][2]["reason"] == "unknown (best-effort check unavailable)"
