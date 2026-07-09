"""Trivial passthrough node — reads the lead's email from the environment.

Per D-01, no branch logic (greenfield/brownfield detection) exists in Phase 1;
this node exists only so the graph spine has a first node to run before
stub_plan builds the hardcoded Plan.
"""

import os

from app.graph.state import RunState


def ingest_config(state: RunState) -> dict:
    lead_email = os.environ.get("LEAD_EMAIL", "")
    return {"lead_email": lead_email}
