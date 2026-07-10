"""Real GLM-backed plan-generation node — replaces stub_plan (PLAN-01/02/03/04).

Checks state["blocked_reason"] first (set by either read_docs_greenfield's
D-12 no-docs case or ingest_brownfield's no-source-files case) and
short-circuits with an empty-but-valid Plan without ever calling the LLM —
per 02-RESEARCH.md's explicit guidance, generate_plan must not attempt real
planning from empty/placeholder context. Otherwise, calls the real GLM-via-
NVIDIA-NIM structured-output + validate/repair loop when an API key is
configured (llm_available()), or falls back to the deterministic offline
planner when it isn't — so the demo works end-to-end with zero API keys.
"""

from app.graph.state import RunState
from app.models.plan import Plan
from app.models.skills import SKILL_TAXONOMY
from app.services.llm import build_chat_llm, generate_plan_with_repair, llm_available
from app.services.offline_planner import generate_plan_offline


async def generate_plan(state: RunState) -> dict:
    if state.get("blocked_reason") is not None:
        return {"plan": Plan(epics=[])}

    docs_text = state.get("docs_text") or ""

    if llm_available():
        try:
            llm = build_chat_llm()
            plan = generate_plan_with_repair(llm, docs_text, SKILL_TAXONOMY)
        except Exception:  # noqa: BLE001 — demo resilience: a live LLM failure
            # (deprecated model id, transient NIM error, repair-loop exhaustion)
            # must never abort the run — fall back to the deterministic planner.
            plan = generate_plan_offline(docs_text, SKILL_TAXONOMY)
    else:
        plan = generate_plan_offline(docs_text, SKILL_TAXONOMY)
    return {"plan": plan}
