"""Unit coverage for the grown ingest_config node (CONN-01/02/03, D-08) and
the runs.py _derive_status smoke_test surfacing contract.
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.graph.nodes.ingest_config import ingest_config


@pytest.mark.asyncio
async def test_ingest_config_returns_failed_smoke_test(mock_ado_env, monkeypatch):
    monkeypatch.setenv("LEAD_EMAIL", "lead@example.com")
    failing_result = {
        "passed": False,
        "checks": [{"check": "project_access", "passed": False, "reason": "PAT auth rejected (401)"}],
    }
    with patch(
        "app.graph.nodes.ingest_config.ado_client.run_smoke_test",
        AsyncMock(return_value=failing_result),
    ):
        state = await ingest_config({})

    assert state["smoke_test_passed"] is False
    assert state["smoke_test"] == failing_result


@pytest.mark.asyncio
async def test_ingest_config_returns_passed_smoke_test_and_reads_repo_mode(mock_ado_env, monkeypatch):
    monkeypatch.setenv("LEAD_EMAIL", "lead@example.com")
    monkeypatch.setenv("REPO_MODE", "brownfield")
    passing_result = {"passed": True, "checks": []}
    with patch(
        "app.graph.nodes.ingest_config.ado_client.run_smoke_test",
        AsyncMock(return_value=passing_result),
    ):
        state = await ingest_config({})

    assert state["smoke_test_passed"] is True
    assert state["repo_mode"] == "brownfield"


@pytest.mark.asyncio
async def test_ingest_config_defaults_repo_mode_to_greenfield(mock_ado_env, monkeypatch):
    monkeypatch.setenv("LEAD_EMAIL", "lead@example.com")
    monkeypatch.delenv("REPO_MODE", raising=False)
    passing_result = {"passed": True, "checks": []}
    with patch(
        "app.graph.nodes.ingest_config.ado_client.run_smoke_test",
        AsyncMock(return_value=passing_result),
    ):
        state = await ingest_config({})

    assert state["repo_mode"] == "greenfield"


@pytest.mark.asyncio
async def test_derive_status_surfaces_smoke_test_and_overrides_status_on_failure():
    from app.routers.runs import _derive_status

    class FakeSnapshot:
        values = {
            "smoke_test_passed": False,
            "smoke_test": {"passed": False, "checks": [{"check": "project_access", "passed": False, "reason": "PAT auth rejected (401)"}]},
        }
        next = ()

    class FakeGraph:
        async def aget_state(self, config):
            return FakeSnapshot()

    result = await _derive_status(FakeGraph(), "run-123")

    assert result["status"] == "blocked_smoke_test_failed"
    assert result["smoke_test_passed"] is False
    assert result["smoke_test"]["checks"][0]["reason"] == "PAT auth rejected (401)"


@pytest.mark.asyncio
async def test_derive_status_not_found_has_smoke_test_none():
    from app.routers.runs import _derive_status

    class FakeSnapshot:
        values = {}
        next = ()

    class FakeGraph:
        async def aget_state(self, config):
            return FakeSnapshot()

    result = await _derive_status(FakeGraph(), "run-404")

    assert result["status"] == "not_found"
    assert result["smoke_test"] is None
