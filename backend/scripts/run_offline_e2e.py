"""Offline end-to-end smoke/demo script — no API keys, no ADO PAT required.

Run with:
    .venv/bin/python -m scripts.run_offline_e2e

Proves the "no LLM key configured" demo path works end to end by driving the
individual deterministic services directly (offline plan generation ->
assignment -> risk scoring -> a chat-style plan edit + diff), the same
functions app/graph/nodes/generate_plan.py, assign_and_score.py, and
routers/runs.py's /edit endpoint call. This is a smoke/demo artifact, not a
test — it prints human-readable output for a quick manual sanity check.
"""

import json

from app.models.skills import SKILL_TAXONOMY
from app.models.team import TeamMember
from app.services.assignment import assign_plan
from app.services.offline_planner import generate_plan_offline
from app.services.plan_edit import apply_instruction, diff_plans
from app.services.risk import compute_risk

_SAMPLE_DOCS = """
# Project Overview
An AI project-planning tool for engineering leads, connecting Azure DevOps
and GitHub to generate an implementation plan.

# User Authentication
Team members authenticate via the org's existing ADO login; no new auth
surface is built here.

# Data Storage
Plans and team rosters persist in a local SQLite database.

# Frontend Dashboard
A React dashboard renders the plan, risk score, and lets the lead edit it.

# Deployment Pipeline
CI runs the test suite and deploys the backend via a simple Docker pipeline.
"""

_TEAM = [
    TeamMember(
        name="Ada Lovelace",
        email="ada@example.com",
        designation="Senior Backend Engineer",
        skills="Backend, API design, Python",
        experience_level="senior",
    ),
    TeamMember(
        name="Grace Hopper",
        email="grace@example.com",
        designation="Frontend Engineer",
        skills="Frontend, React, UX",
        experience_level="mid",
    ),
    TeamMember(
        name="Alan Turing",
        email="alan@example.com",
        designation="QA / DevOps Engineer",
        skills="Testing, DevOps, CI",
        experience_level="lead",
    ),
]


def _print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _print_plan_summary(plan) -> None:
    for epic in plan.epics:
        print(f"  Epic {epic.id}: {epic.title}")
        for task in epic.tasks:
            print(
                f"    - {task.id}: {task.title!r} "
                f"[{task.skill_tag}] {task.estimate_hours}h -> "
                f"{task.suggested_assignee or '(unassigned)'}"
            )


def main() -> None:
    _print_header("STEP 1: Offline plan generation (no NVIDIA_API_KEY needed)")
    plan = generate_plan_offline(_SAMPLE_DOCS, SKILL_TAXONOMY)
    print(f"Generated {len(plan.epics)} epics.")
    _print_plan_summary(plan)

    _print_header("STEP 2: Skill-aware, load-balanced assignment")
    assigned_plan = assign_plan(plan, _TEAM)
    _print_plan_summary(assigned_plan)

    _print_header("STEP 3: Deterministic risk scoring (plain Python, no LLM)")
    risk = compute_risk(assigned_plan, _TEAM)
    print(f"Risk score: {risk.score}/100 ({risk.level})")
    print(f"Narrative: {risk.narrative}")
    if risk.items:
        print("Risk items:")
        for item in risk.items:
            print(f"  - {item.skill}: {item.hours_at_risk}h at risk ({item.severity})")
    else:
        print("No coverage gaps found.")

    _print_header("STEP 4: Conversational plan edit (offline, no LLM)")
    instruction = "reassign integration tests to Alan"
    # Pick a real task title to edit against, so the demo instruction matches.
    first_task_title = assigned_plan.epics[0].tasks[0].title
    instruction = f"assign {first_task_title} to Alan"
    print(f"Instruction: {instruction!r}")

    edited_plan, note = apply_instruction(assigned_plan, _TEAM, instruction)
    print(f"Edit note: {note}")

    diff_text = diff_plans(assigned_plan, edited_plan)
    print("Diff (current vs proposed):")
    if diff_text:
        for line in diff_text.splitlines()[:20]:
            print(f"  {line}")
    else:
        print("  (no diff)")

    edited_risk = compute_risk(edited_plan, _TEAM)
    print(f"Risk after edit: {edited_risk.score}/100 ({edited_risk.level})")

    _print_header("SUMMARY")
    print(
        json.dumps(
            {
                "epics": len(edited_plan.epics),
                "tasks": sum(len(e.tasks) for e in edited_plan.epics),
                "risk_score": edited_risk.score,
                "risk_level": edited_risk.level,
                "edit_note": note,
            },
            indent=2,
        )
    )
    print()
    print("Offline end-to-end demo completed successfully.")


if __name__ == "__main__":
    main()
