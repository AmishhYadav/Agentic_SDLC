"""Builds the hardcoded stub Plan (D-05/D-06).

1 epic, 2-3 tasks, all self-assigned to the lead's own ADO identity. Zero LLM
involvement — a real Plan instance, not an ad-hoc dict, so later phases can
swap this stub generator for the real one without reshaping downstream nodes.
"""

from app.graph.state import RunState
from app.models.plan import Epic, Plan, Task


def stub_plan(state: RunState) -> dict:
    lead_email = state["lead_email"]
    plan = Plan(
        epics=[
            Epic(
                id="epic-1",
                title="Stub Epic: Scaffolding Slice",
                description=(
                    "Hardcoded epic proving the ingest_config -> stub_plan -> "
                    "human_review -> push_to_ado spine end to end (Phase 1)."
                ),
                tasks=[
                    Task(
                        id="task-1",
                        title="Stub Task 1: Wire the graph spine",
                        description=(
                            "Prove the four-node straight-line spine compiles "
                            "and runs, pausing at human_review for approval."
                        ),
                        suggested_assignee=lead_email,
                        estimate_hours=4,
                    ),
                    Task(
                        id="task-2",
                        title="Stub Task 2: Verify checkpoint restart survival",
                        description=(
                            "Prove a run paused at human_review survives a "
                            "backend process restart via AsyncSqliteSaver."
                        ),
                        suggested_assignee=lead_email,
                        estimate_hours=6,
                    ),
                    Task(
                        id="task-3",
                        title="Stub Task 3: Approve and reach completion",
                        description=(
                            "Prove resuming the run after approval progresses "
                            "through to the (stubbed) push_to_ado completion."
                        ),
                        suggested_assignee=lead_email,
                        estimate_hours=2,
                    ),
                ],
            )
        ]
    )
    return {"plan": plan}
