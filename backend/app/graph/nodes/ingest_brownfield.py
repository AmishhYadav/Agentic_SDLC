"""Real brownfield codebase RAG ingestion node — replaces ingest_brownfield_stub (Phase 5).

Resolves a source directory (cloned repo / configured local path / this
project's own root as a zero-config demo default), chunks + embeds it into an
in-memory vector store, retrieves representative context, and produces an
onboarding summary that feeds generate_plan's docs_text — so brownfield plans
are grounded in the real codebase exactly like read_docs_greenfield's
docs_text grounds greenfield plans.

Never crashes the graph: every failure mode (no source files, clone failure,
embedding/LLM failure) is caught and turned into a distinct blocked_reason or
a safe fallback, matching read_docs_greenfield's and generate_plan's own
never-let-a-failure-abort-the-run posture.
"""

import shutil

from app.graph.state import RunState
from app.services.code_ingest import resolve_source_dir
from app.services.onboarding import build_onboarding
from app.services.rag_store import build_store_from_dir


async def ingest_brownfield(state: RunState) -> dict:
    is_temp = False
    try:
        root, is_temp = resolve_source_dir()
        store, stats = build_store_from_dir(root)

        if stats["chunk_count"] == 0:
            return {
                "docs_text": None,
                "onboarding_summary": None,
                "blocked_reason": "Brownfield ingestion found no source files to analyze.",
            }

        summary, grounding = build_onboarding(store, stats)
        return {"docs_text": grounding, "onboarding_summary": summary, "blocked_reason": None}
    except Exception as exc:  # noqa: BLE001 — never let ingestion abort the run
        return {
            "docs_text": None,
            "onboarding_summary": None,
            "blocked_reason": f"Brownfield ingestion failed: {exc}",
        }
    finally:
        if is_temp:
            shutil.rmtree(root, ignore_errors=True)
