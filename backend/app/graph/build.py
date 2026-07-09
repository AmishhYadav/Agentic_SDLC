"""StateGraph construction — the 4-node straight-line spine (D-01).

Returns the UNCOMPILED builder. Compilation with the checkpointer happens in
main.py's lifespan (Pattern 1) so the checkpointer is never rebuilt per-request.
"""

from langgraph.graph import END, START, StateGraph

from app.graph.nodes.human_review import human_review
from app.graph.nodes.ingest_config import ingest_config
from app.graph.nodes.push_to_ado import push_to_ado
from app.graph.nodes.stub_plan import stub_plan
from app.graph.state import RunState


def build_graph() -> StateGraph:
    builder = StateGraph(RunState)

    builder.add_node("ingest_config", ingest_config)
    builder.add_node("stub_plan", stub_plan)
    builder.add_node("human_review", human_review)
    builder.add_node("push_to_ado", push_to_ado)

    builder.add_edge(START, "ingest_config")
    builder.add_edge("ingest_config", "stub_plan")
    builder.add_edge("stub_plan", "human_review")
    builder.add_edge("human_review", "push_to_ado")
    builder.add_edge("push_to_ado", END)

    return builder
