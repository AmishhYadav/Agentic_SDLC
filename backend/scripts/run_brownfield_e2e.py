"""Brownfield end-to-end demo script — real RAG ingestion + grounded plan generation.

Run with:
    .venv/bin/python -m scripts.run_brownfield_e2e

Proves the brownfield path works end to end by driving the individual
services directly (resolve_source_dir -> build_store_from_dir ->
build_onboarding -> generate_plan_with_repair/generate_plan_offline), the
same functions app/graph/nodes/ingest_brownfield.py and generate_plan.py
call. This is a smoke/demo artifact, not a test — it prints human-readable
output for a quick manual sanity check.

Uses the real NVIDIA NIM key/embeddings if NVIDIA_API_KEY/NVIDIA_EMBED_MODEL
are configured (loaded from .env); otherwise falls back to the deterministic
offline embedding/planner paths automatically, same as the graph does.
"""

import json

from dotenv import load_dotenv

load_dotenv()

from app.models.skills import SKILL_TAXONOMY  # noqa: E402
from app.services.code_ingest import resolve_source_dir  # noqa: E402
from app.services.llm import build_chat_llm, generate_plan_with_repair, llm_available  # noqa: E402
from app.services.offline_planner import generate_plan_offline  # noqa: E402
from app.services.onboarding import build_onboarding  # noqa: E402
from app.services.rag_store import build_store_from_dir  # noqa: E402


def _print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _print_plan_summary(plan) -> None:
    for epic in plan.epics:
        print(f"  Epic {epic.id}: {epic.title}")
        for task in epic.tasks:
            print(
                f"    - {task.id}: {task.title!r} "
                f"[{task.skill_tag}] {task.estimate_hours}h"
            )


def main() -> None:
    _print_header("STEP 1: Resolve brownfield source directory")
    root, is_temp = resolve_source_dir()
    print(f"Source dir: {root}")
    print(f"Temp clone: {is_temp}")

    try:
        _print_header("STEP 2: Ingest + chunk + embed the codebase")
        store, stats = build_store_from_dir(root)
        print(json.dumps(stats, indent=2))

        if stats["chunk_count"] == 0:
            print("No source files found — nothing further to demo.")
            return

        _print_header("STEP 3: Retrieve context + build onboarding summary")
        summary, grounding = build_onboarding(store, stats)
        print(summary)
        print(f"\n(grounding_docs_text length: {len(grounding)} chars)")

        _print_header("STEP 4: Generate a brownfield plan grounded in the codebase")
        if llm_available():
            try:
                llm = build_chat_llm()
                plan = generate_plan_with_repair(llm, grounding, SKILL_TAXONOMY)
                print("(used real GLM-via-NVIDIA-NIM plan generation)")
            except Exception as exc:  # noqa: BLE001 — demo resilience
                print(f"(LLM plan generation failed: {exc} — falling back to offline planner)")
                plan = generate_plan_offline(grounding, SKILL_TAXONOMY)
        else:
            print("(NVIDIA_API_KEY not configured — using offline planner)")
            plan = generate_plan_offline(grounding, SKILL_TAXONOMY)

        _print_plan_summary(plan)

        _print_header("SUMMARY")
        print(
            json.dumps(
                {
                    "file_count": stats["file_count"],
                    "chunk_count": stats["chunk_count"],
                    "languages": stats["languages"],
                    "epics": len(plan.epics),
                    "tasks": sum(len(e.tasks) for e in plan.epics),
                },
                indent=2,
            )
        )
        print()
        print("Brownfield end-to-end demo completed successfully.")
    finally:
        if is_temp:
            import shutil

            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
