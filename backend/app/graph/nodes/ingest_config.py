"""Real config intake and blocking ADO PAT smoke-test (CONN-01/02/03).

Reads ADO_ORG/ADO_PROJECT/ADO_PAT/GITHUB_REPO/REPO_MODE from os.environ per
run (D-04: config lives in .env, no per-run snapshot — ado_client/github_client
read os.environ fresh on every call, so those values are not stored in
RunState directly). Runs the CONN-03 smoke-test and returns its detailed
pass/fail result so runs.py can surface it and block the run on failure
(D-02/D-03).

Note: this node only detects and surfaces a failed smoke-test via the state
fields below. It intentionally does NOT halt graph execution before
generate_plan runs — that requires a conditional edge in build.py,
which Plan 03 owns (see 02-01-PLAN.md's "Note on blocking").
"""

import os

from app.graph.state import RunState
from app.services import ado_client


def _demo_mode_enabled() -> bool:
    """DEMO_MODE lets the run proceed through planning even when the ADO PAT
    smoke-test fails (no/expired PAT), so the plan/assign/risk/edit loop is
    demoable without a live PAT. The real ADO push is skipped in this mode.

    Enabled when DEMO_MODE is truthy in .env, OR auto-enabled when ADO_PAT is
    absent/empty (so the tool "just works" before a PAT is provisioned). Set
    DEMO_MODE=false and provide a valid ADO_PAT to restore real blocking + push.
    """
    flag = os.environ.get("DEMO_MODE", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return True
    if flag in ("0", "false", "no", "off"):
        return False
    # Unset: auto-enable only when there is no PAT to try at all.
    return not os.environ.get("ADO_PAT", "").strip()


async def ingest_config(state: RunState) -> dict:
    lead_email = os.environ.get("LEAD_EMAIL", "")
    repo_mode = os.environ.get("REPO_MODE") or "greenfield"
    demo_mode = _demo_mode_enabled()

    smoke_test = await ado_client.run_smoke_test(lead_email)

    return {
        "lead_email": lead_email,
        "repo_mode": repo_mode,
        "demo_mode": demo_mode,
        "smoke_test_passed": smoke_test["passed"],
        "smoke_test": smoke_test,
    }
