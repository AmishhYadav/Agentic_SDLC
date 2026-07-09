"""POST /runs, GET /runs/{run_id}, POST /runs/{run_id}/resume.

Status is always derived from graph.aget_state(config) — the single source of
truth for "is this run paused" (per research's "Don't Hand-Roll" guidance) —
never a hand-rolled status field synced separately from the graph.
"""

import os
import uuid

from fastapi import APIRouter, Request
from langgraph.types import Command
from pydantic import BaseModel

from app.db.run_metadata import create_run_record
from app.models.plan import Plan, PushReport

router = APIRouter()


class ResumeRequest(BaseModel):
    approved: bool


def _config_for(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


async def _derive_status(graph, run_id: str) -> dict:
    """Single shared status-derivation helper used by all three routes."""
    config = _config_for(run_id)
    snapshot = await graph.aget_state(config)

    if not snapshot.values:
        return {
            "run_id": run_id,
            "status": "not_found",
            "plan": None,
            "push_report": None,
        }

    if snapshot.next:
        # Pending task present (interrupt not yet resolved) -> awaiting review
        plan: Plan | None = snapshot.values.get("plan")
        return {
            "run_id": run_id,
            "status": "awaiting_review",
            "plan": plan,
            "push_report": None,
        }

    if snapshot.values.get("pushed") is True:
        push_report: PushReport | None = snapshot.values.get("push_report")
        return {
            "run_id": run_id,
            "status": "completed",
            "plan": snapshot.values.get("plan"),
            "push_report": push_report,
        }

    return {
        "run_id": run_id,
        "status": "running",
        "plan": snapshot.values.get("plan"),
        "push_report": snapshot.values.get("push_report"),
    }


@router.post("/runs")
async def start_run(request: Request):
    run_id = uuid.uuid4().hex
    lead_email = os.environ.get("LEAD_EMAIL", "")
    create_run_record(run_id, lead_email)

    graph = request.app.state.graph
    config = _config_for(run_id)
    await graph.ainvoke({"run_id": run_id}, config)

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
