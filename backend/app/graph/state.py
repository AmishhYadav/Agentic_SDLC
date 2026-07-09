"""RunState TypedDict shared across all graph nodes.

Checkpointed to SQLite on every node transition via AsyncSqliteSaver.
"""

from typing import TypedDict

from app.models.plan import Plan, PushReport


class RunState(TypedDict, total=False):
    run_id: str
    lead_email: str  # used for self-assignment in Plan 01-02
    plan: Plan
    approved: bool
    pushed: bool
    push_report: PushReport
    repo_mode: str  # "greenfield" | "brownfield" — D-08 manual toggle, defaults to greenfield
    smoke_test_passed: bool  # CONN-03 blocking gate result, set by ingest_config
    smoke_test: dict  # full per-check detail (project_access/write_scope/expiry), D-03
