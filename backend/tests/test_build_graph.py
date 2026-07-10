"""Unit + integration coverage for REPO-01's conditional edge wiring.

route_after_config is tested as a pure function (unit), and the compiled
graph is exercised end-to-end via a stubbed ingest_config (monkeypatched
ado_client.run_smoke_test) to confirm it actually reaches the correct node
for each repo_mode / smoke-test outcome, per 02-03-PLAN.md Task 2 behavior.
"""

from unittest.mock import AsyncMock, patch

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.graph.build import build_graph, route_after_config


def test_route_after_config_returns_blocked_when_smoke_test_failed():
    state = {"smoke_test_passed": False, "repo_mode": "greenfield"}
    assert route_after_config(state) == "blocked"


def test_route_after_config_returns_blocked_regardless_of_repo_mode():
    state = {"smoke_test_passed": False, "repo_mode": "brownfield"}
    assert route_after_config(state) == "blocked"


def test_route_after_config_returns_ingest_brownfield_when_passed_and_brownfield():
    state = {"smoke_test_passed": True, "repo_mode": "brownfield"}
    assert route_after_config(state) == "ingest_brownfield"


def test_route_after_config_returns_greenfield_when_passed_and_greenfield():
    state = {"smoke_test_passed": True, "repo_mode": "greenfield"}
    assert route_after_config(state) == "read_docs_greenfield"


def test_route_after_config_defaults_to_greenfield_when_repo_mode_missing():
    state = {"smoke_test_passed": True}
    assert route_after_config(state) == "read_docs_greenfield"


@pytest.mark.asyncio
async def test_compiled_graph_reaches_read_docs_greenfield_for_greenfield_state(mock_ado_env, monkeypatch):
    monkeypatch.setenv("LEAD_EMAIL", "lead@example.com")
    monkeypatch.setenv("REPO_MODE", "greenfield")
    monkeypatch.setenv("GITHUB_REPO", "acme/widgets")
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    passing_result = {"passed": True, "checks": []}
    from app.models.plan import Plan

    with (
        patch(
            "app.graph.nodes.ingest_config.ado_client.run_smoke_test",
            AsyncMock(return_value=passing_result),
        ),
        patch(
            "app.graph.nodes.read_docs_greenfield.github_client.fetch_greenfield_docs",
            return_value="some docs",
        ),
        patch("app.graph.nodes.generate_plan.build_chat_llm", return_value=object()),
        patch(
            "app.graph.nodes.generate_plan.generate_plan_with_repair",
            return_value=Plan(epics=[]),
        ),
    ):
        graph = build_graph().compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-greenfield"}}
        result = await graph.ainvoke({}, config=config)

    assert result["docs_text"] == "some docs"
    assert result["blocked_reason"] is None


@pytest.mark.asyncio
async def test_compiled_graph_reaches_ingest_brownfield_for_brownfield_state(mock_ado_env, monkeypatch, tmp_path):
    monkeypatch.setenv("LEAD_EMAIL", "lead@example.com")
    monkeypatch.setenv("REPO_MODE", "brownfield")
    # Force the offline embedding/LLM fallbacks so this stays hermetic.
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)
    monkeypatch.setenv("GITHUB_REPO", "")

    sample_file = tmp_path / "main.py"
    sample_file.write_text("def main():\n    print('hello world')\n")
    monkeypatch.setenv("BROWNFIELD_PATH", str(tmp_path))

    passing_result = {"passed": True, "checks": []}
    from app.models.plan import Plan

    with (
        patch(
            "app.graph.nodes.ingest_config.ado_client.run_smoke_test",
            AsyncMock(return_value=passing_result),
        ),
        patch("app.graph.nodes.generate_plan.build_chat_llm", return_value=object()),
        patch(
            "app.graph.nodes.generate_plan.generate_plan_with_repair",
            return_value=Plan(epics=[]),
        ),
    ):
        graph = build_graph().compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-brownfield"}}
        result = await graph.ainvoke({}, config=config)

    assert result["blocked_reason"] is None
    assert result["docs_text"]
    assert result["onboarding_summary"]


@pytest.mark.asyncio
async def test_compiled_graph_dead_ends_at_end_when_smoke_test_fails(mock_ado_env, monkeypatch):
    monkeypatch.setenv("LEAD_EMAIL", "lead@example.com")
    failing_result = {
        "passed": False,
        "checks": [{"check": "project_access", "passed": False, "reason": "PAT auth rejected (401)"}],
    }

    with patch(
        "app.graph.nodes.ingest_config.ado_client.run_smoke_test",
        AsyncMock(return_value=failing_result),
    ):
        graph = build_graph().compile(checkpointer=InMemorySaver())
        config = {"configurable": {"thread_id": "test-blocked"}}
        result = await graph.ainvoke({}, config=config)

    # Never reaches doc-fetch or plan generation.
    assert result["smoke_test_passed"] is False
    assert "docs_text" not in result
    assert "plan" not in result
