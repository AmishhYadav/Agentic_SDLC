"""StateGraph construction — config -> conditional branch -> plan -> review -> push.

Returns the UNCOMPILED builder. Compilation with the checkpointer happens in
main.py's lifespan (Pattern 1) so the checkpointer is never rebuilt per-request.

The conditional edge after ingest_config (REPO-01, D-09) routes on
smoke_test_passed first (a failed smoke-test is a dead end at END, never
reaching doc-fetch/plan-generation — Plan 01's blocked_smoke_test_failed
status derivation already surfaces this), then on repo_mode. Both the
greenfield and brownfield legs converge into generate_plan — the real
GLM-backed plan generator (Plan 04), which itself short-circuits on
blocked_reason for the brownfield-placeholder/no-docs cases.
"""

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.generate_plan import generate_plan
from app.graph.nodes.human_review import human_review
from app.graph.nodes.ingest_brownfield_stub import ingest_brownfield_stub
from app.graph.nodes.ingest_config import ingest_config
from app.graph.nodes.push_to_ado import push_to_ado
from app.graph.nodes.read_docs_greenfield import read_docs_greenfield
from app.graph.state import RunState


def route_after_config(state: RunState) -> str:
    """Route after ingest_config: blocked -> brownfield stub -> greenfield (default).

    A failed smoke-test always routes to "blocked" regardless of repo_mode
    (CONN-03's blocking gate takes priority). Otherwise routes on repo_mode,
    defaulting to "read_docs_greenfield" when repo_mode is unset/missing —
    mirrors ingest_config's own greenfield default (D-08 safety net).
    """
    if state.get("smoke_test_passed") is False:
        return "blocked"
    if state.get("repo_mode") == "brownfield":
        return "ingest_brownfield_stub"
    return "read_docs_greenfield"


def build_graph() -> StateGraph:
    builder = StateGraph(RunState)

    builder.add_node("ingest_config", ingest_config)
    builder.add_node("read_docs_greenfield", read_docs_greenfield)
    builder.add_node("ingest_brownfield_stub", ingest_brownfield_stub)
    builder.add_node("generate_plan", generate_plan)
    builder.add_node("human_review", human_review)
    builder.add_node("push_to_ado", push_to_ado)

    builder.add_edge(START, "ingest_config")
    builder.add_conditional_edges(
        "ingest_config",
        route_after_config,
        {
            "blocked": END,
            "read_docs_greenfield": "read_docs_greenfield",
            "ingest_brownfield_stub": "ingest_brownfield_stub",
        },
    )
    builder.add_edge("read_docs_greenfield", "generate_plan")
    builder.add_edge("ingest_brownfield_stub", "generate_plan")
    builder.add_edge("generate_plan", "human_review")
    builder.add_edge("human_review", "push_to_ado")
    builder.add_edge("push_to_ado", END)

    return builder
