"""Azure DevOps REST client — create, link, and verify work items.

All calls target api-version=7.1 using direct httpx REST calls (per CLAUDE.md
"Azure DevOps API gotchas" and STACK.md — never the azure-devops SDK, which is
stale). Every write is followed by a read-back verification (D-09/D-10):
ADO returns 200/201 even when System.AssignedTo silently fails to resolve, so
"the API call succeeded" and "the assignment worked" are two different facts
that must be checked separately.

Auth: Basic with an empty username, PAT as the password
(`Authorization: Basic {base64(":" + ADO_PAT)}`) — read once from os.environ,
never logged, never echoed back to the frontend.

Content-Type for every create/update call MUST be exactly
`application/json-patch+json` — this is the single most common point of
failure per CLAUDE.md.
"""

import base64
import os
from typing import Any, Literal

import httpx

from app.models.plan import Plan, PushReport, PushResultItem

_TIMEOUT_SECONDS = 15.0
_API_VERSION = "7.1"


def _auth_header() -> dict[str, str]:
    """Basic auth header with an empty username and the PAT as password.

    Never logs the PAT. Read fresh from os.environ on every call so this
    module has no import-time dependency on .env already being loaded.
    """
    pat = os.environ.get("ADO_PAT", "")
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def _org_project() -> tuple[str, str]:
    return os.environ.get("ADO_ORG", ""), os.environ.get("ADO_PROJECT", "")


def _base_url() -> str:
    org, project = _org_project()
    return f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems"


def build_patch_op(op: str, path: str, value: Any) -> dict[str, Any]:
    """Small typed helper for one JSON-Patch operation.

    Used everywhere instead of ad-hoc dict literals scattered across call
    sites (research "Don't Hand-Roll" guidance / Pitfall 4).
    """
    return {"op": op, "path": path, "value": value}


def _relation_add_op(parent_id: int) -> dict[str, Any]:
    """Build the /relations/- add-op linking a child (task) to its parent (epic).

    System.LinkTypes.Hierarchy-Reverse goes on the CHILD, pointing UP to the
    parent — "Reverse" is relative to the natural parent->child hierarchy
    direction, not an intuitive label. Do not reverse this (research
    "Direction gotcha").
    """
    org, project = _org_project()
    parent_url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workItems/{parent_id}"
    return build_patch_op(
        "add",
        "/relations/-",
        {
            "rel": "System.LinkTypes.Hierarchy-Reverse",
            "url": parent_url,
            "attributes": {"comment": "linking to parent epic"},
        },
    )


def _check_json_response(response: httpx.Response) -> tuple[bool, Any]:
    """Check Content-Type is JSON before parsing.

    An expired/invalid PAT can return a 203 with an HTML login page body
    rather than a clean 401 — parsing that blindly as JSON throws a
    confusing decode exception (research "Response format gotcha").
    Returns (is_json, parsed_body_or_none).
    """
    content_type = response.headers.get("content-type", "")
    if "application/json" not in content_type:
        return False, None
    try:
        return True, response.json()
    except ValueError:
        return False, None


async def create_work_item(
    work_item_type: Literal["Epic", "Task"],
    fields: dict[str, Any],
    parent_id: int | None,
) -> tuple[int, dict[str, Any]]:
    """POST a new work item, optionally linked to a parent epic in the same call.

    fields is a dict of {reference_name: value}, e.g. {"System.Title": "..."}.
    Returns (new_work_item_id, raw_response_json).
    Raises RuntimeError on a create failure (non-2xx or non-JSON response) —
    callers (push_plan) catch this per-item so one bad item does not abort
    the whole push (D-09).
    """
    ops: list[dict[str, Any]] = [
        build_patch_op("add", f"/fields/{name}", value) for name, value in fields.items()
    ]
    if parent_id is not None:
        ops.append(_relation_add_op(parent_id))

    url = f"{_base_url()}/${work_item_type}?api-version={_API_VERSION}"
    headers = {
        "Content-Type": "application/json-patch+json",
        **_auth_header(),
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers, json=ops)

    is_json, body = _check_json_response(response)
    if not is_json:
        raise RuntimeError(
            f"create_work_item({work_item_type}) got a non-JSON response "
            f"(status={response.status_code}); PAT may be invalid/expired"
        )
    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"create_work_item({work_item_type}) failed: "
            f"status={response.status_code} body={body}"
        )

    new_id = body.get("id")
    if new_id is None:
        raise RuntimeError(
            f"create_work_item({work_item_type}) response missing 'id': {body}"
        )
    return new_id, body


def _identity_matches(identity_field: Any, expected_assignee: str) -> bool:
    """Case-insensitively compare an ADO identity object against expected_assignee.

    fields["System.AssignedTo"] is an identity object (not a bare string) in
    GET responses, exposing uniqueName/displayName/email-shaped keys
    depending on org configuration.
    """
    if not isinstance(identity_field, dict):
        return False
    expected = expected_assignee.strip().lower()
    for key in ("uniqueName", "displayName", "mailAddress", "id"):
        val = identity_field.get(key)
        if isinstance(val, str) and val.strip().lower() == expected:
            return True
    return False


async def verify_work_item(
    work_item_id: int,
    expected_assignee: str,
    expected_parent_id: int | None,
) -> dict[str, Any]:
    """GET the work item with $expand=relations and check assignment + parent link.

    Returns a dict shaped like the checks push_plan needs:
        {"assignment_resolved": bool, "link_resolved": bool | None, "raw": dict | None, "error": str | None}
    expected_parent_id=None means "no parent link expected to be checked" (e.g.
    the epic itself, or Script A's standalone task) -> link_resolved is None.
    Never raises; all failures are captured in "error" so callers can build a
    partial-success PushResultItem without an unhandled exception (D-09).
    """
    org, project = _org_project()
    url = (
        f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/"
        f"{work_item_id}?$expand=relations&api-version={_API_VERSION}"
    )
    headers = _auth_header()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return {
            "assignment_resolved": False,
            "link_resolved": None,
            "raw": None,
            "error": f"verify_work_item request failed: {exc}",
        }

    is_json, body = _check_json_response(response)
    if not is_json:
        return {
            "assignment_resolved": False,
            "link_resolved": None,
            "raw": None,
            "error": (
                f"verify_work_item got a non-JSON response "
                f"(status={response.status_code}); PAT may be invalid/expired"
            ),
        }
    if response.status_code != 200:
        return {
            "assignment_resolved": False,
            "link_resolved": None,
            "raw": body,
            "error": f"verify_work_item failed: status={response.status_code}",
        }

    fields = body.get("fields", {})
    assigned_to = fields.get("System.AssignedTo")
    assignment_resolved = _identity_matches(assigned_to, expected_assignee)

    link_resolved: bool | None = None
    if expected_parent_id is not None:
        relations = body.get("relations", []) or []
        org_, project_ = _org_project()
        expected_parent_url_suffix = f"/workItems/{expected_parent_id}"
        link_resolved = any(
            rel.get("rel") == "System.LinkTypes.Hierarchy-Reverse"
            and str(rel.get("url", "")).rstrip("/").endswith(expected_parent_url_suffix)
            for rel in relations
        )

    return {
        "assignment_resolved": assignment_resolved,
        "link_resolved": link_resolved,
        "raw": body,
        "error": None,
    }


async def check_project_access() -> dict[str, Any]:
    """Cheap, read-only probe: can this PAT see this org/project at all?

    Distinguishes "PAT invalid/expired" (non-JSON/203 response — see
    _check_json_response's docstring) from "auth rejected" (401) from
    "no access to this project" (403), per Pitfall 2's ordered-probe design.
    Never raises.
    """
    org, project = _org_project()
    url = (
        f"https://dev.azure.com/{org}/{project}/_apis/wit/workitemtypes"
        f"?api-version={_API_VERSION}"
    )
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=_auth_header())
    except httpx.HTTPError as exc:
        # No network route / DNS failure / timeout reaching ADO. Honor the
        # "never raises" contract: report a graceful failure so run_smoke_test
        # returns passed=False and DEMO_MODE can still carry the run forward,
        # instead of an uncaught error killing the whole graph run.
        return {
            "check": "project_access",
            "passed": False,
            "reason": f"could not reach Azure DevOps ({type(exc).__name__})",
        }

    is_json, _ = _check_json_response(response)
    if not is_json:
        return {
            "check": "project_access",
            "passed": False,
            "reason": "PAT invalid or expired (non-JSON/203 response)",
        }
    if response.status_code == 401:
        return {"check": "project_access", "passed": False, "reason": "PAT auth rejected (401)"}
    if response.status_code == 403:
        return {
            "check": "project_access",
            "passed": False,
            "reason": "PAT lacks access to this project (403)",
        }
    if response.status_code != 200:
        return {
            "check": "project_access",
            "passed": False,
            "reason": f"unexpected status {response.status_code}",
        }
    return {"check": "project_access", "passed": True, "reason": None}


async def check_write_scope(lead_email: str) -> dict[str, Any]:
    """Confirm work-item WRITE scope by creating a real throwaway work item.

    There is no read-only "can I write" ADO call (Pitfall 2) — create-and-leave
    is the only reliable mechanism; acceptable clutter for a single-lead local
    MVP (threat T-02-03, disposition: accept). Never raises — RuntimeError
    from create_work_item is caught here.
    """
    try:
        await create_work_item(
            "Task",
            {
                "System.Title": "ADO smoke-test — safe to delete",
                "System.AssignedTo": lead_email,
            },
            parent_id=None,
        )
    except RuntimeError as exc:
        return {"check": "write_scope", "passed": False, "reason": str(exc)}
    except httpx.HTTPError as exc:
        # Same network-unreachable guard as check_project_access — never raise.
        return {
            "check": "write_scope",
            "passed": False,
            "reason": f"could not reach Azure DevOps ({type(exc).__name__})",
        }
    return {"check": "write_scope", "passed": True, "reason": None}


async def check_expiry_best_effort() -> dict[str, Any]:
    """Best-effort PAT expiry lookup — never fails the overall smoke-test.

    Per Pitfall 1 / Open Question 1, whether `_apis/tokens/pats` accepts plain
    PAT Basic auth for self-introspection is genuinely unresolved; this probe
    is enrichment only. Any non-200/non-JSON response degrades gracefully to
    "unknown" rather than failing the check.
    """
    org, _ = _org_project()
    url = f"https://vssps.dev.azure.com/{org}/_apis/tokens/pats?api-version=7.1-preview.1"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=_auth_header())
    except httpx.HTTPError:
        return {
            "check": "expiry",
            "passed": True,
            "reason": "unknown (best-effort check unavailable)",
        }

    is_json, body = _check_json_response(response)
    if not is_json or response.status_code != 200:
        return {
            "check": "expiry",
            "passed": True,
            "reason": "unknown (best-effort check unavailable)",
        }

    valid_to: str | None = None
    patTokens = body.get("patTokens") if isinstance(body, dict) else None
    if isinstance(patTokens, list):
        for entry in patTokens:
            if isinstance(entry, dict) and entry.get("validTo"):
                valid_to = entry["validTo"]
                break

    return {
        "check": "expiry",
        "passed": True,
        "reason": valid_to or "unknown (best-effort check unavailable)",
    }


async def run_smoke_test(lead_email: str) -> dict[str, Any]:
    """Ordered CONN-03 probe sequence: project access -> write scope + expiry.

    Short-circuits after project_access if it fails — write-scope is
    meaningless without project access (Pitfall 2). Returns
    {"passed": bool, "checks": [dict, ...]}. Never raises.
    """
    project_access_result = await check_project_access()
    if not project_access_result["passed"]:
        return {"passed": False, "checks": [project_access_result]}

    write_scope_result = await check_write_scope(lead_email)
    expiry_result = await check_expiry_best_effort()

    return {
        "passed": project_access_result["passed"] and write_scope_result["passed"],
        "checks": [project_access_result, write_scope_result, expiry_result],
    }


async def push_plan(plan: Plan) -> PushReport:
    """Create the epic, then each task (with parent link + assignee), verifying every write.

    Partial-success reporting (D-09): one bad item does not abort the loop.
    Every item gets a PushResultItem with a status reflecting an actual
    read-back check, never an assumed success from the create call's HTTP
    status alone (PUSH-03).
    """
    items: list[PushResultItem] = []

    for epic in plan.epics:
        epic_ado_id: int | None = None
        try:
            epic_ado_id, _ = await create_work_item(
                "Epic",
                {
                    "System.Title": epic.title,
                    "System.Description": epic.description,
                },
                parent_id=None,
            )
        except RuntimeError as exc:
            items.append(
                PushResultItem(
                    item_id=epic.id,
                    ado_work_item_id=None,
                    status="create_failed",
                    detail=str(exc),
                )
            )
            # Cannot create any child tasks without the parent epic id —
            # record every task under this epic as create_failed too, rather
            # than silently skipping them (D-09: nothing silently swallowed).
            for task in epic.tasks:
                items.append(
                    PushResultItem(
                        item_id=task.id,
                        ado_work_item_id=None,
                        status="create_failed",
                        detail=f"parent epic '{epic.id}' failed to create: {exc}",
                    )
                )
            continue

        items.append(
            PushResultItem(
                item_id=epic.id,
                ado_work_item_id=epic_ado_id,
                status="created",
                detail=None,
            )
        )

        for task in epic.tasks:
            try:
                task_ado_id, _ = await create_work_item(
                    "Task",
                    {
                        "System.Title": task.title,
                        "System.Description": task.description,
                        "System.AssignedTo": task.suggested_assignee,
                        "Microsoft.VSTS.Scheduling.OriginalEstimate": task.estimate_hours,
                    },
                    parent_id=epic_ado_id,
                )
            except RuntimeError as exc:
                items.append(
                    PushResultItem(
                        item_id=task.id,
                        ado_work_item_id=None,
                        status="create_failed",
                        detail=str(exc),
                    )
                )
                continue

            verification = await verify_work_item(
                task_ado_id,
                expected_assignee=task.suggested_assignee,
                expected_parent_id=epic_ado_id,
            )

            if verification["error"] is not None:
                items.append(
                    PushResultItem(
                        item_id=task.id,
                        ado_work_item_id=task_ado_id,
                        status="create_failed",
                        detail=verification["error"],
                    )
                )
            elif not verification["assignment_resolved"]:
                items.append(
                    PushResultItem(
                        item_id=task.id,
                        ado_work_item_id=task_ado_id,
                        status="assignment_unresolved",
                        detail=(
                            f"System.AssignedTo did not resolve to "
                            f"'{task.suggested_assignee}'"
                        ),
                    )
                )
            elif verification["link_resolved"] is False:
                items.append(
                    PushResultItem(
                        item_id=task.id,
                        ado_work_item_id=task_ado_id,
                        status="link_failed",
                        detail=f"Hierarchy-Reverse link to parent epic {epic_ado_id} not found",
                    )
                )
            else:
                items.append(
                    PushResultItem(
                        item_id=task.id,
                        ado_work_item_id=task_ado_id,
                        status="created",
                        detail=None,
                    )
                )

    all_succeeded = all(item.status == "created" for item in items)
    return PushReport(items=items, all_succeeded=all_succeeded)
