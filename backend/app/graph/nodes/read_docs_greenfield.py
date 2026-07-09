"""Real greenfield doc-reading node (REPO-02).

Reads GITHUB_REPO/GITHUB_TOKEN fresh from os.environ (config, not run data,
per D-04 — mirrors ingest_config's own "read fresh from env" pattern; these
are never threaded through RunState). Calls github_client.fetch_greenfield_docs
and sets docs_text/blocked_reason per D-12's exact no-docs wording.
"""

import os

from app.graph.state import RunState
from app.services import github_client


async def read_docs_greenfield(state: RunState) -> dict:
    github_token = os.environ.get("GITHUB_TOKEN", "")
    github_repo = os.environ.get("GITHUB_REPO", "")

    result = github_client.fetch_greenfield_docs(github_token, github_repo)

    if result is None:
        return {
            "docs_text": None,
            "blocked_reason": "No project docs found — add a README to plan",
        }

    return {"docs_text": result, "blocked_reason": None}
