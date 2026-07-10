"""Assignment + risk-scoring node — inserted between generate_plan and human_review.

Loads the current team roster (D-04: global roster, never per-run state),
runs the deterministic assign_plan/compute_risk services (never the LLM —
CLAUDE.md's non-negotiable risk-score constraint), and returns the assigned
plan plus the risk report for the lead to review before approving.
"""

from app.db import team_roster
from app.graph.state import RunState
from app.services.assignment import assign_plan
from app.services.risk import compute_risk


async def assign_and_score(state: RunState) -> dict:
    team = team_roster.list_members()
    plan = state["plan"]

    if not plan.epics:
        return {"team_count": len(team), "risk": compute_risk(plan, team)}

    assigned = assign_plan(plan, team)
    risk = compute_risk(assigned, team)
    return {"plan": assigned, "risk": risk, "team_count": len(team)}
