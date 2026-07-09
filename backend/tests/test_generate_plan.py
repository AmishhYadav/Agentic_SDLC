"""Unit coverage for PLAN-01/02/03/04's generate_plan_with_repair loop.

Mocks structured_llm.invoke (the ChatOpenAI.with_structured_output(...)
return value's .invoke) so no real network/NVIDIA NIM call is made. Covers:
first-try success (no retry), parse-error retry-then-succeed, taxonomy-
violation retry-then-succeed, exhausted-retries RuntimeError, and the
defensive suggested_assignee="" force-blank (D-14).
"""

from unittest.mock import MagicMock

import pytest

from app.models.plan import Epic, Plan, Task
from app.models.skills import SKILL_TAXONOMY
from app.services.llm import generate_plan_with_repair


def _valid_plan(skill_tag: str = "Backend", suggested_assignee: str = "") -> Plan:
    return Plan(
        epics=[
            Epic(
                id="epic-1",
                title="Epic 1",
                description="desc",
                tasks=[
                    Task(
                        id="task-1",
                        title="Task 1",
                        description="desc",
                        suggested_assignee=suggested_assignee,
                        estimate_hours=4.0,
                        skill_tag=skill_tag,
                    )
                ],
            )
        ]
    )


def _structured_result(parsed, parsing_error=None):
    return {"raw": MagicMock(), "parsed": parsed, "parsing_error": parsing_error}


def _mock_llm_with_structured_invoke(invoke_side_effects):
    """Build a mock llm whose .with_structured_output(...).invoke has the given side_effect."""
    structured_llm = MagicMock()
    structured_llm.invoke.side_effect = invoke_side_effects
    llm = MagicMock()
    llm.with_structured_output.return_value = structured_llm
    return llm, structured_llm


def test_first_try_success_returns_immediately_no_retry():
    valid_plan = _valid_plan()
    llm, structured_llm = _mock_llm_with_structured_invoke(
        [_structured_result(valid_plan, parsing_error=None)]
    )

    result = generate_plan_with_repair(llm, "some docs", SKILL_TAXONOMY)

    assert result.epics[0].tasks[0].id == "task-1"
    assert structured_llm.invoke.call_count == 1


def test_parse_error_then_success_retries_once():
    valid_plan = _valid_plan()
    llm, structured_llm = _mock_llm_with_structured_invoke(
        [
            _structured_result(None, parsing_error=Exception("malformed tool-call JSON")),
            _structured_result(valid_plan, parsing_error=None),
        ]
    )

    result = generate_plan_with_repair(llm, "some docs", SKILL_TAXONOMY)

    assert result.epics[0].tasks[0].id == "task-1"
    assert structured_llm.invoke.call_count == 2


def test_taxonomy_violation_then_success_retries_once():
    invalid_plan = _valid_plan(skill_tag="NotARealSkill")
    valid_plan = _valid_plan(skill_tag="Backend")
    llm, structured_llm = _mock_llm_with_structured_invoke(
        [
            _structured_result(invalid_plan, parsing_error=None),
            _structured_result(valid_plan, parsing_error=None),
        ]
    )

    result = generate_plan_with_repair(llm, "some docs", SKILL_TAXONOMY)

    assert result.epics[0].tasks[0].skill_tag == "Backend"
    assert structured_llm.invoke.call_count == 2


def test_exhausted_retries_raises_runtime_error_after_exactly_max_attempts():
    llm, structured_llm = _mock_llm_with_structured_invoke(
        [
            _structured_result(None, parsing_error=Exception("bad json 1")),
            _structured_result(None, parsing_error=Exception("bad json 2")),
            _structured_result(None, parsing_error=Exception("bad json 3")),
        ]
    )

    with pytest.raises(RuntimeError):
        generate_plan_with_repair(llm, "some docs", SKILL_TAXONOMY, max_attempts=3)

    assert structured_llm.invoke.call_count == 3


def test_suggested_assignee_force_blanked_on_success():
    valid_plan = _valid_plan(suggested_assignee="someone@example.com")
    llm, structured_llm = _mock_llm_with_structured_invoke(
        [_structured_result(valid_plan, parsing_error=None)]
    )

    result = generate_plan_with_repair(llm, "some docs", SKILL_TAXONOMY)

    for epic in result.epics:
        for task in epic.tasks:
            assert task.suggested_assignee == ""
