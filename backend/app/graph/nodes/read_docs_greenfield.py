"""Real greenfield doc-reading node (REPO-02).

Reads GITHUB_REPO/GITHUB_TOKEN fresh from os.environ (config, not run data,
per D-04 — mirrors ingest_config's own "read fresh from env" pattern; these
are never threaded through RunState). Calls github_client.fetch_greenfield_docs
and sets docs_text/blocked_reason per D-12's exact no-docs wording.
"""

import os

from app.graph.state import RunState
from app.services import github_client
from app.services.sample_brief import SAMPLE_PROJECT_BRIEF


async def read_docs_greenfield(state: RunState) -> dict:
    github_token = os.environ.get("GITHUB_TOKEN", "")
    github_repo = os.environ.get("GITHUB_REPO", "")

    # A real configured repo always takes precedence. Guard the network call so
    # an empty/misconfigured repo never crashes the node.
    result = None
    if github_repo.strip():
        try:
            result = github_client.fetch_greenfield_docs(github_token, github_repo)
        except Exception:  # noqa: BLE001 — never let a fetch error abort the run
            result = None

    if result is not None:
        return {"docs_text": result, "blocked_reason": None}

    # DEMO_MODE fallback: no real docs available, but the demo must still plan —
    # use the built-in sample brief. Non-demo runs honestly block (D-12).
    if state.get("demo_mode"):
        return {"docs_text": SAMPLE_PROJECT_BRIEF, "blocked_reason": None}

    return {
        "docs_text": None,
        "blocked_reason": "No project docs found — add a README to plan",
    }
