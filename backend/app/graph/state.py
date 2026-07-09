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
