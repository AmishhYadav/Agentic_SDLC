"""StateGraph construction — config -> conditional branch -> plan -> review -> push.

Returns the UNCOMPILED builder. Compilation with the checkpointer happens in
main.py's lifespan (Pattern 1) so the checkpointer is never rebuilt per-request.

The conditional edge after ingest_config (REPO-01, D-09) routes on
smoke_test_passed first (a failed smoke-test is a dead end at END, never
reaching doc-fetch/plan-generation — Plan 01's blocked_smoke_test_failed
status derivation already surfaces this), then on repo_mode. Both the
greenfield and brownfield legs converge into generate_plan — the real
GLM-backed plan generator (Plan 04), which itself short-circuits on
blocked_reason for the no-source/no-docs cases. Brownfield ingestion (Phase 5)
performs real RAG ingestion of the target codebase and produces an onboarding
summary that feeds generate_plan's docs_text, grounding the brownfield plan
in the real repo exactly like read_docs_greenfield does for greenfield.
"""

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.assign_and_score import assign_and_score
from app.graph.nodes.compose_plan_document import compose_plan_document
from app.graph.nodes.generate_plan import generate_plan
from app.graph.nodes.human_review import human_review
from app.graph.nodes.ingest_brownfield import ingest_brownfield
from app.graph.nodes.ingest_config import ingest_config
from app.graph.nodes.push_to_ado import push_to_ado
from app.graph.nodes.read_docs_greenfield import read_docs_greenfield
from app.graph.state import RunState


def route_after_config(state: RunState) -> str:
    """Route after ingest_config: blocked -> brownfield ingestion -> greenfield (default).

    A failed smoke-test always routes to "blocked" regardless of repo_mode
    (CONN-03's blocking gate takes priority). Otherwise routes on repo_mode,
    defaulting to "read_docs_greenfield" when repo_mode is unset/missing —
    mirrors ingest_config's own greenfield default (D-08 safety net).

    Exception: in DEMO_MODE the run proceeds to planning even if the smoke-test
    failed (no/expired PAT), so the plan/assign/risk/edit loop stays demoable
    without a live PAT; push_to_ado then skips the real ADO write.
    """
    if state.get("smoke_test_passed") is False and not state.get("demo_mode"):
        return "blocked"
    if state.get("repo_mode") == "brownfield":
        return "ingest_brownfield"
    return "read_docs_greenfield"


def build_graph() -> StateGraph:
    builder = StateGraph(RunState)

    builder.add_node("ingest_config", ingest_config)
    builder.add_node("read_docs_greenfield", read_docs_greenfield)
    builder.add_node("ingest_brownfield", ingest_brownfield)
    builder.add_node("generate_plan", generate_plan)
    builder.add_node("assign_and_score", assign_and_score)
    builder.add_node("compose_plan_document", compose_plan_document)
    builder.add_node("human_review", human_review)
    builder.add_node("push_to_ado", push_to_ado)

    builder.add_edge(START, "ingest_config")
    builder.add_conditional_edges(
        "ingest_config",
        route_after_config,
        {
            "blocked": END,
            "read_docs_greenfield": "read_docs_greenfield",
            "ingest_brownfield": "ingest_brownfield",
        },
    )
    builder.add_edge("read_docs_greenfield", "generate_plan")
    builder.add_edge("ingest_brownfield", "generate_plan")
    builder.add_edge("generate_plan", "assign_and_score")
    builder.add_edge("assign_and_score", "compose_plan_document")
    builder.add_edge("compose_plan_document", "human_review")
    builder.add_edge("human_review", "push_to_ado")
    builder.add_edge("push_to_ado", END)

    return builder
