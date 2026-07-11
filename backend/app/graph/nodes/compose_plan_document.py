"""Plan-document composition node — runs after assign_and_score, before human_review.

Turns the finalized, assigned Plan (source of truth) plus the Python-computed
risk into a professional markdown document for the lead to read/download. Runs
after assignment so the document reflects real owners; runs before human_review
so it's ready when the lead pauses to review.

The composition is fully synchronous (a blocking LLM call, with a deterministic
markdown fallback) — offloaded to a worker thread via asyncio.to_thread so it
never pins the event loop (the freeze that made runs look hung; see
generate_plan for the same guard).
"""

import asyncio

from app.db import team_roster
from app.graph.state import RunState
from app.services.plan_document import compose_plan_document as _compose


async def compose_plan_document(state: RunState) -> dict:
    plan = state["plan"]
    risk = state.get("risk")
    docs_text = state.get("docs_text")
    team = team_roster.list_members()

    document = await asyncio.to_thread(_compose, plan, docs_text, risk, team)
    return {"plan_document": document}
