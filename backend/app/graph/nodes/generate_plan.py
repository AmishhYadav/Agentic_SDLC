"""Real GLM-backed plan-generation node — replaces stub_plan (PLAN-01/02/03/04).

Checks state["blocked_reason"] first (set by either read_docs_greenfield's
D-12 no-docs case or ingest_brownfield_stub's D-09 placeholder) and
short-circuits with an empty-but-valid Plan without ever calling the LLM —
per 02-RESEARCH.md's explicit guidance, generate_plan must not attempt real
planning from empty/placeholder context. Otherwise, calls the real GLM-via-
NVIDIA-NIM structured-output + validate/repair loop.
"""

from app.graph.state import RunState
from app.models.plan import Plan
from app.models.skills import SKILL_TAXONOMY
from app.services.llm import build_chat_llm, generate_plan_with_repair


async def generate_plan(state: RunState) -> dict:
    if state.get("blocked_reason") is not None:
        return {"plan": Plan(epics=[])}

    llm = build_chat_llm()
    plan = generate_plan_with_repair(llm, state["docs_text"], SKILL_TAXONOMY)
    return {"plan": plan}
