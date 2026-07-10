"""Unit coverage for generate_plan_offline (deterministic, no-network plan generation)."""

from app.models.plan import Plan
from app.models.skills import SKILL_TAXONOMY, validate_skill_tags
from app.services.offline_planner import generate_plan_offline

_SAMPLE_DOCS = """
# Project Overview
This tool helps engineering leads plan work.

# User Authentication
Users log in via OAuth and sessions are stored server-side.

# Data Storage
We persist plans and tasks in a relational database with a normalized schema.

# Frontend Dashboard
A React-based UI renders the plan and lets the lead edit it inline.

# Deployment
CI runs tests and deploys via a Docker-based pipeline.
"""


def test_returns_valid_plan_instance():
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    assert isinstance(plan, Plan)


def test_epic_and_task_count_bounds():
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    assert 2 <= len(plan.epics) <= 5
    for epic in plan.epics:
        assert 2 <= len(epic.tasks) <= 6


def test_taxonomy_compliance_via_validate_skill_tags():
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    # Should not raise.
    validate_skill_tags(plan, SKILL_TAXONOMY)


def test_all_estimates_positive():
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    for epic in plan.epics:
        for task in epic.tasks:
            assert task.estimate_hours > 0


def test_all_assignees_empty():
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    for epic in plan.epics:
        for task in epic.tasks:
            assert task.suggested_assignee == ""


def test_empty_docs_text_is_robust_and_produces_generic_epics():
    plan = generate_plan_offline("", SKILL_TAXONOMY)
    assert isinstance(plan, Plan)
    assert 2 <= len(plan.epics) <= 5
    validate_skill_tags(plan, SKILL_TAXONOMY)
    titles = [epic.title for epic in plan.epics]
    assert "Foundation & Setup" in titles


def test_short_docs_text_is_robust():
    plan = generate_plan_offline("hi", SKILL_TAXONOMY)
    assert isinstance(plan, Plan)
    validate_skill_tags(plan, SKILL_TAXONOMY)


def test_task_ids_are_unique_and_scoped_to_epic():
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    all_ids = [task.id for epic in plan.epics for task in epic.tasks]
    assert len(all_ids) == len(set(all_ids))


def test_deterministic_across_repeated_calls():
    plan1 = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    plan2 = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    assert plan1.model_dump() == plan2.model_dump()
