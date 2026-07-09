"""Stub push node — gated so it runs exactly once (Pattern 3).

This is a DELIBERATE no-op stub for Phase 1: it returns a "not yet
implemented" PushReport and sets pushed=True so the full graph compiles and
runs end-to-end. Plan 01-02 REPLACES this function's body with the real ADO
REST push implementation — the signature and the "check pushed first" gate
must remain identical so 01-02 only changes the body, not the node's place in
the graph.
"""

from app.graph.state import RunState
from app.models.plan import PushReport, PushResultItem


async def push_to_ado(state: RunState) -> dict:
    if state.get("pushed") is True:
        return {}

    if state.get("approved") is not True:
        return {
            "push_report": PushReport(items=[], all_succeeded=False),
            "pushed": False,
        }

    plan = state["plan"]
    items: list[PushResultItem] = []
    for epic in plan.epics:
        items.append(
            PushResultItem(
                item_id=epic.id,
                status="not_implemented",
                detail="push_to_ado not yet wired to real ADO client (see Plan 01-02)",
            )
        )
        for task in epic.tasks:
            items.append(
                PushResultItem(
                    item_id=task.id,
                    status="not_implemented",
                    detail="push_to_ado not yet wired to real ADO client (see Plan 01-02)",
                )
            )

    report = PushReport(items=items, all_succeeded=False)
    return {"push_report": report, "pushed": True}
