"""POST /runs, GET /runs/{run_id}, POST /runs/{run_id}/resume.

Status is always derived from graph.aget_state(config) — the single source of
truth for "is this run paused" (per research's "Don't Hand-Roll" guidance) —
never a hand-rolled status field synced separately from the graph.
"""

import asyncio
import logging
import os
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from langgraph.types import Command
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.db import team_roster
from app.db.run_metadata import create_run_record
from app.models.plan import Plan, PushReport
from app.services.plan_edit import apply_instruction, diff_plans
from app.services.risk import compute_risk

router = APIRouter()


class ResumeRequest(BaseModel):
    approved: bool


class EditRequest(BaseModel):
    instruction: str


class ApplyRequest(BaseModel):
    plan: Plan


def _config_for(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


async def _derive_status(graph, run_id: str) -> dict:
    """Single shared status-derivation helper used by all three routes.

    smoke_test/smoke_test_passed (CONN-03/D-02/D-03) are surfaced on every
    branch except not_found, following the same "None there" convention as
    plan/push_report. When the smoke-test failed, the derived status is
    overridden to "blocked_smoke_test_failed" — this is the run-blocking
    behavior D-02 requires; the surfaced detail is what makes it satisfy
    D-03's "not an opaque run blocked" requirement.
    """
    config = _config_for(run_id)
    snapshot = await graph.aget_state(config)

    if not snapshot.values:
        return {
            "run_id": run_id,
            "status": "not_found",
            "plan": None,
            "push_report": None,
            "smoke_test": None,
            "smoke_test_passed": None,
            "repo_mode": None,
            "risk": None,
            "team_count": 0,
            "demo_mode": False,
            "onboarding_summary": None,
        }

    smoke_test = snapshot.values.get("smoke_test")
    smoke_test_passed = snapshot.values.get("smoke_test_passed")
    repo_mode = snapshot.values.get("repo_mode")
    risk = snapshot.values.get("risk")
    team_count = snapshot.values.get("team_count")
    demo_mode = snapshot.values.get("demo_mode", False)
    onboarding_summary = snapshot.values.get("onboarding_summary")

    # A failed smoke-test blocks the run — UNLESS DEMO_MODE let it proceed to
    # planning without a valid PAT (the loop stays demoable; push is skipped).
    if smoke_test_passed is False and not demo_mode:
        return {
            "run_id": run_id,
            "status": "blocked_smoke_test_failed",
            "plan": snapshot.values.get("plan"),
            "push_report": None,
            "smoke_test": smoke_test,
            "smoke_test_passed": smoke_test_passed,
            "repo_mode": repo_mode,
            "risk": risk,
            "team_count": team_count,
            "demo_mode": demo_mode,
            "onboarding_summary": onboarding_summary,
        }

    # A genuine human-review pause is an active INTERRUPT at human_review — not
    # merely "some node is pending". Because the graph now runs in the
    # background (POST /runs returns immediately), _derive_status can observe
    # intermediate states where snapshot.next points at a node that just hasn't
    # executed yet (e.g. ingest_config on a brand-new run); those are "running",
    # not "awaiting_review". Detect the real interrupt via snapshot interrupts /
    # the pending human_review task.
    interrupted = bool(getattr(snapshot, "interrupts", None)) or any(
        getattr(task, "interrupts", None) for task in (getattr(snapshot, "tasks", None) or ())
    )
    if interrupted or "human_review" in (getattr(snapshot, "next", None) or ()):
        plan: Plan | None = snapshot.values.get("plan")
        return {
            "run_id": run_id,
            "status": "awaiting_review",
            "plan": plan,
            "push_report": None,
            "smoke_test": smoke_test,
            "smoke_test_passed": smoke_test_passed,
            "repo_mode": repo_mode,
            "risk": risk,
            "team_count": team_count,
            "demo_mode": demo_mode,
            "onboarding_summary": onboarding_summary,
        }

    if snapshot.values.get("pushed") is True:
        push_report: PushReport | None = snapshot.values.get("push_report")
        return {
            "run_id": run_id,
            "status": "completed",
            "plan": snapshot.values.get("plan"),
            "push_report": push_report,
            "smoke_test": smoke_test,
            "smoke_test_passed": smoke_test_passed,
            "repo_mode": repo_mode,
            "risk": risk,
            "team_count": team_count,
            "demo_mode": demo_mode,
            "onboarding_summary": onboarding_summary,
        }

    # snapshot.next truthy but not interrupted -> the background graph is still
    # executing a node (ingest/doc-fetch/embed/LLM). Otherwise the run has
    # settled without pushing (e.g. blocked at END). Both surface as "running"
    # from the client's polling perspective.
    return {
        "run_id": run_id,
        "status": "running",
        "plan": snapshot.values.get("plan"),
        "push_report": snapshot.values.get("push_report"),
        "smoke_test": smoke_test,
        "smoke_test_passed": smoke_test_passed,
        "repo_mode": repo_mode,
        "risk": risk,
        "team_count": team_count,
        "demo_mode": demo_mode,
        "onboarding_summary": onboarding_summary,
    }


@router.post("/runs")
async def start_run(request: Request):
    run_id = uuid.uuid4().hex
    lead_email = os.environ.get("LEAD_EMAIL", "")
    create_run_record(run_id, lead_email)

    graph = request.app.state.graph
    config = _config_for(run_id)

    # The graph runs to the human-review interrupt before returning — for the
    # brownfield path that means real RAG ingestion + embeddings + LLM calls,
    # which can take minutes. Run it in the background and return immediately so
    # the client (which polls GET /runs/{id}) never blocks on a long request.
    async def _run() -> None:
        try:
            await graph.ainvoke({"run_id": run_id}, config)
        except Exception:  # noqa: BLE001 — a run failure must not kill the task silently
            logger.exception("run %s failed during graph invocation", run_id)

    asyncio.create_task(_run())

    # Wait briefly for the first checkpoint so we can return a meaningful status
    # (running/awaiting_review/blocked) instead of a transient not_found.
    for _ in range(50):
        snapshot = await graph.aget_state(config)
        if snapshot.values:
            break
        await asyncio.sleep(0.1)

    return await _derive_status(graph, run_id)


@router.get("/runs/{run_id}")
async def get_run(run_id: str, request: Request):
    graph = request.app.state.graph
    return await _derive_status(graph, run_id)


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, body: ResumeRequest, request: Request):
    graph = request.app.state.graph
    config = _config_for(run_id)
    await graph.ainvoke(Command(resume={"approved": body.approved}), config)
    return await _derive_status(graph, run_id)


@router.post("/runs/{run_id}/edit")
async def edit_run(run_id: str, body: EditRequest, request: Request):
    """Apply an offline natural-language edit instruction to the current plan.

    Does not mutate the checkpointed state — returns current_plan,
    proposed_plan, a unified diff, an edit note, and the recomputed risk for
    the proposed plan so the lead can preview before accepting via /apply.
    """
    graph = request.app.state.graph
    config = _config_for(run_id)
    snapshot = await graph.aget_state(config)

    current_plan_raw = snapshot.values.get("plan") if snapshot.values else None
    if current_plan_raw is None:
        return JSONResponse(status_code=400, content={"detail": "no plan to edit"})

    plan_obj = Plan.model_validate(current_plan_raw)
    team = team_roster.list_members()

    new_plan, note = apply_instruction(plan_obj, team, body.instruction)
    risk = compute_risk(new_plan, team)

    return {
        "current_plan": plan_obj,
        "proposed_plan": new_plan,
        "diff": diff_plans(plan_obj, new_plan),
        "note": note,
        "risk": risk,
    }


@router.post("/runs/{run_id}/apply")
async def apply_run(run_id: str, body: ApplyRequest, request: Request):
    """Write an edited plan (proposed via /edit or authored directly) back into the checkpoint.

    Recomputes risk against the current team roster so the checkpointed
    risk stays consistent with the checkpointed plan; used for both
    chat-accept and direct edits before the lead approves/resumes the run.
    """
    graph = request.app.state.graph
    config = _config_for(run_id)

    team = team_roster.list_members()
    risk = compute_risk(body.plan, team)

    await graph.aupdate_state(config, {"plan": body.plan, "risk": risk})
    return await _derive_status(graph, run_id)
