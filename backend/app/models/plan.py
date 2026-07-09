"""Shared Plan/Epic/Task/PushReport/PushResultItem schema.

This is the ONE shared shape for plan data across the entire backend.
Both LangGraph nodes and FastAPI API responses import these classes directly
— no parallel/duplicate plan representation may be introduced elsewhere.
"""

from typing import Literal

from pydantic import BaseModel


class Task(BaseModel):
    id: str
    title: str
    description: str
    suggested_assignee: str  # email/UPN string; ADO resolves it server-side
    estimate_hours: float
    skill_tag: str | None = None  # Phase 1: unused/None; Phase 2+ populates
    depends_on: list[str] = []  # display-only, no enforcement


class Epic(BaseModel):
    id: str
    title: str
    description: str
    tasks: list[Task]


class Plan(BaseModel):
    epics: list[Epic]


class PushResultItem(BaseModel):
    item_id: str
    ado_work_item_id: int | None = None
    status: Literal[
        "created",
        "assignment_unresolved",
        "create_failed",
        "link_failed",
        "not_implemented",
    ]
    detail: str | None = None


class PushReport(BaseModel):
    items: list[PushResultItem]
    all_succeeded: bool
