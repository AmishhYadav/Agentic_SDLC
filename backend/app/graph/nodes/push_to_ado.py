"""Real ADO push node — gated so it runs exactly once (Pattern 3).

Wired to the real ado_client.push_plan implementation. The "check pushed
first" gate and the "approved is not True" early-return are unchanged from
the original stub — only the push body changed. With no/expired PAT,
ado_client.push_plan returns create_failed items gracefully rather than
raising — that is the intended honest behavior (D-09).
"""

from app.graph.state import RunState
from app.models.plan import PushReport, PushResultItem
from app.services import ado_client

_DEMO_SKIP_DETAIL = (
    "ADO push skipped — running in DEMO_MODE (no valid PAT). "
    "Add a valid ADO_PAT and set DEMO_MODE=false to push for real."
)


def _demo_skip_report(state: RunState) -> PushReport:
    """Build an honest, per-item 'skipped' report without touching ADO.

    Reuses the 'not_implemented' status (the only non-success terminal status
    that isn't an actual API failure) so the frontend renders it unchanged;
    the detail string carries the real reason.
    """
    plan = state["plan"]
    items: list[PushResultItem] = []
    for epic in plan.epics:
        items.append(
            PushResultItem(item_id=epic.id, status="not_implemented", detail=_DEMO_SKIP_DETAIL)
        )
        for task in epic.tasks:
            items.append(
                PushResultItem(item_id=task.id, status="not_implemented", detail=_DEMO_SKIP_DETAIL)
            )
    return PushReport(items=items, all_succeeded=False)


async def push_to_ado(state: RunState) -> dict:
    if state.get("pushed") is True:
        return {}

    if state.get("approved") is not True:
        return {
            "push_report": PushReport(items=[], all_succeeded=False),
            "pushed": False,
        }

    # DEMO_MODE (or a run that only got past the smoke-test because of it):
    # never hammer ADO with an invalid/expired PAT — report an honest skip.
    if state.get("demo_mode") and state.get("smoke_test_passed") is not True:
        return {"push_report": _demo_skip_report(state), "pushed": True}

    report = await ado_client.push_plan(state["plan"])
    return {"push_report": report, "pushed": True}
