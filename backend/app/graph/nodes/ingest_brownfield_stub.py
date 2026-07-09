"""Guarded brownfield placeholder node (D-09).

Synchronous, zero-network, never-crashing placeholder. Real brownfield
codebase RAG ingestion arrives in Phase 5 — this node never attempts real
ingestion and never silently falls back to greenfield; it sets a distinct,
checkable blocked_reason that downstream plan generation short-circuits on.
"""

from app.graph.state import RunState


def ingest_brownfield_stub(state: RunState) -> dict:
    return {
        "docs_text": None,
        "blocked_reason": (
            "Brownfield planning arrives in Phase 5 — this run cannot generate a plan yet."
        ),
    }
