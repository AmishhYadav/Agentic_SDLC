"""RunState TypedDict shared across all graph nodes.

Checkpointed to SQLite on every node transition via AsyncSqliteSaver.
"""

from typing import TypedDict

from app.models.plan import Plan, PushReport
from app.models.risk import RiskReport


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
    docs_text: str | None  # concatenated README + docs/**/*.md text (greenfield), or None
    onboarding_summary: str | None  # brownfield RAG-grounded onboarding summary (Phase 5), or None
    blocked_reason: str | None  # D-12 no-docs / D-09 brownfield-placeholder message, or None
    risk: RiskReport  # deterministic risk score/narrative, set by assign_and_score
    team_count: int  # len(team_roster.list_members()) at assign_and_score time
    demo_mode: bool  # DEMO_MODE: proceed through planning even if ADO smoke-test fails; skip real push
