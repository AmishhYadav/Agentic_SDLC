"""Script A (CLAUDE.md Setup checklist): create + self-assign one ADO work item via the PAT.

Standalone smoke test — does NOT start FastAPI or the LangGraph graph. Must
run and PASS against the real ADO target BEFORE its logic (via ado_client) is
wired into push_to_ado (D-12 sequencing).

Run with either:
    python backend/scripts/script_a_ado_smoke_test.py
    cd backend && PYTHONPATH=. python scripts/script_a_ado_smoke_test.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv


def _load_env() -> None:
    # Resolve .env relative to this file's location (backend/.env) so the
    # script works regardless of the caller's current working directory.
    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(here)
    env_path = os.path.join(backend_dir, ".env")
    load_dotenv(dotenv_path=env_path)


async def _run() -> bool:
    # Import after env is loaded and after sys.path is adjusted, so
    # ado_client's os.environ reads see real values regardless of run mode.
    from app.services import ado_client

    lead_email = os.environ.get("LEAD_EMAIL", "")
    if not lead_email:
        print("FAIL: LEAD_EMAIL is not set in backend/.env")
        return False

    print(f"Creating one ADO Task work item, self-assigned to {lead_email}...")
    try:
        work_item_id, raw = await ado_client.create_work_item(
            "Task",
            {
                "System.Title": "Script A smoke test — safe to delete",
                "System.Description": (
                    "Created by backend/scripts/script_a_ado_smoke_test.py "
                    "(Plan 01-02 Task 1) to prove ADO auth + create + "
                    "self-assign works before push_to_ado is wired to the "
                    "real client."
                ),
                "System.AssignedTo": lead_email,
            },
            parent_id=None,
        )
    except RuntimeError as exc:
        print(f"FAIL: work item creation failed: {exc}")
        return False

    org = os.environ.get("ADO_ORG", "")
    project = os.environ.get("ADO_PROJECT", "")
    work_item_url = f"https://dev.azure.com/{org}/{project}/_workitems/edit/{work_item_id}"
    print(f"Created work item id={work_item_id} url={work_item_url}")

    print("Reading it back to verify System.AssignedTo resolved...")
    verification = await ado_client.verify_work_item(
        work_item_id,
        expected_assignee=lead_email,
        expected_parent_id=None,
    )

    if verification["error"] is not None:
        print(f"FAIL: verification request failed: {verification['error']}")
        return False

    if not verification["assignment_resolved"]:
        print(
            f"FAIL: work item {work_item_id} created but System.AssignedTo "
            f"did NOT resolve to '{lead_email}'. Check that this email is a "
            f"member of {org}/{project} (D-11 precondition)."
        )
        return False

    print(
        f"PASS: work item id={work_item_id} created at {work_item_url} and "
        f"System.AssignedTo resolved to '{lead_email}'."
    )
    return True


def main() -> None:
    _load_env()
    # Ensure `app` package is importable whether invoked as
    # `python backend/scripts/script_a_ado_smoke_test.py` (cwd = repo root)
    # or `python scripts/script_a_ado_smoke_test.py` (cwd = backend/).
    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(here)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    passed = asyncio.run(_run())
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
