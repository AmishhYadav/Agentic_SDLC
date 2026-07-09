"""Side-effect-free interrupt node (D-03).

The ENTIRE body of this function is: read the already-computed plan, pause via
interrupt(), and merge the resume payload. LangGraph re-executes this node from
its top on every resume — so no statement here may perform a side effect
(network call, plan mutation, logging intended to fire once). This is the
ORCH-01 interrupt/resume half; the greenfield/brownfield branch half is
deferred to Phase 2 (D-02).
"""

from langgraph.types import interrupt

from app.graph.state import RunState


def human_review(state: RunState) -> dict:
    decision = interrupt({"plan": state["plan"]})
    return {"approved": decision.get("approved", False)}
