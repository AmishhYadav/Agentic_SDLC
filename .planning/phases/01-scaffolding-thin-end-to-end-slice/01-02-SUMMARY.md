---
phase: 01-scaffolding-thin-end-to-end-slice
plan: 02
subsystem: api
tags: [azure-devops, httpx, rest, json-patch, work-items]

# Dependency graph
requires:
  - phase: 01-scaffolding-thin-end-to-end-slice (Plan 01-01)
    provides: "Shared Plan/Epic/Task/PushReport/PushResultItem schema, RunState, push_to_ado stub node"
provides:
  - "ado_client.py service: create_work_item, verify_work_item, push_plan, build_patch_op (httpx, json-patch+json, api-version 7.1, Basic auth, read-back verification)"
  - "Standalone Script A smoke test (backend/scripts/script_a_ado_smoke_test.py) proving/disproving ADO connectivity independent of FastAPI/LangGraph"
affects: [01-02-push-to-ado-wiring (blocked, see below)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Every ADO write followed by a read-back GET with $expand=relations before reporting success (D-10) — never trust 200/201 alone"
    - "Content-Type checked as application/json before parsing any ADO response — a 401/203 with an expired/invalid PAT returns text/html, not JSON (T-01-08)"
    - "build_patch_op single shared helper for all JSON-Patch op construction — no ad-hoc dict literals at call sites (research 'Don't Hand-Roll')"
    - "push_plan uses partial-success reporting: one item's create/verify failure does not abort the loop or raise past push_plan's boundary (D-09)"

key-files:
  created:
    - backend/app/services/__init__.py
    - backend/app/services/ado_client.py
    - backend/scripts/__init__.py
    - backend/scripts/script_a_ado_smoke_test.py
  modified: []

key-decisions:
  - "Stopped execution after Task 1 per plan's explicit D-12 sequencing instruction: Script A must PASS against the real ADO target before push_to_ado's real body is wired. Script A FAILED (PAT expired) — Task 2 was NOT started, and push_to_ado.py is untouched (still Plan 01-01's stub)."
  - "Confirmed the failure is a precondition/credential problem, not a code defect, by cross-verifying with a standalone diagnostic GET against a read-only ADO endpoint (project properties) — same 401 with 'Access Denied: The Personal Access Token used has expired.' HTML body, independent of ado_client.py entirely."

patterns-established:
  - "Pattern: verify_work_item/create_work_item never raise past a caller expecting partial-success reporting where applicable (push_plan catches RuntimeError per item); Script A itself surfaces PASS/FAIL via a clean exit code (0/1) rather than an uncaught traceback."

requirements-completed: []

# Metrics
duration: ~12min
completed: 2026-07-10
---

# Phase 01 Plan 02: ADO Client Service + Script A Smoke Test (BLOCKED before Task 2) Summary

**Built and unit-verified `ado_client.py` (create/verify/push_plan/build_patch_op) and a standalone Script A smoke test; running Script A against the real ADO org confirmed the previously-provisioned PAT has since expired — Task 2 (wiring `push_to_ado`) was correctly NOT started per the plan's mandatory D-12 sequencing gate.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-10 (session start)
- **Completed:** 2026-07-10
- **Tasks:** 1 of 2 completed (Task 2 blocked; Task 0 checkpoint pre-cleared by orchestrator)
- **Files modified:** 4 created

## Accomplishments
- `backend/app/services/ado_client.py` implements all four required exports (`create_work_item`, `verify_work_item`, `push_plan`, `build_patch_op`) exactly per the REST shapes in `01-RESEARCH.md`'s "ADO REST Call Reference": `Content-Type: application/json-patch+json`, `api-version=7.1`, Basic auth with empty username, `System.LinkTypes.Hierarchy-Reverse` on the child pointing to the parent, and a mandatory read-back (`$expand=relations`) after every task create.
- Every outbound call has an explicit 15s `httpx` timeout (research Security Mistakes table: "no timeout on outbound calls").
- `verify_work_item` and `create_work_item` check response `Content-Type` is JSON before parsing — this guard is what correctly caught the real PAT-expiry failure below as a clean, diagnosable `RuntimeError`/`FAIL` line instead of an opaque JSON-decode exception.
- `push_plan` implements partial-success reporting (D-09): a failed epic create marks all its child tasks `create_failed` with a clear `detail` string rather than raising or silently dropping them; per-task failures (`create_failed`, `assignment_unresolved`, `link_failed`) are isolated per item.
- `backend/scripts/script_a_ado_smoke_test.py` is a standalone, directly-runnable script (`python backend/scripts/script_a_ado_smoke_test.py` or `PYTHONPATH=. python scripts/script_a_ado_smoke_test.py` from `backend/`) that reuses `ado_client.create_work_item`/`verify_work_item` internally rather than duplicating request logic, per CLAUDE.md's "Don't Hand-Roll" spirit.
- All static acceptance-criteria greps pass:
  - `ado_client.py` exports `create_work_item`, `verify_work_item`, `push_plan`, `build_patch_op` — confirmed via `grep -n "^async def \|^def "`.
  - `grep -c "application/json-patch+json"` → 2 (present).
  - `grep -c "System.LinkTypes.Hierarchy-Reverse"` → 3 (present).
  - `grep -v '^\s*#' ... | grep -c "Basic "` → 4 (Basic auth header present, non-comment lines).

## Task Commits

Each task was committed atomically:

1. **Task 1: Build the ADO client service and Script A, run Script A against the real target** - `5388fd7` (feat)

Task 2 (wiring `push_to_ado`) was NOT executed — see "Script A Result" below.

## Script A Result — REAL RUN AGAINST LIVE ADO TARGET

Command run: `cd backend && PYTHONPATH=. .venv/bin/python3 scripts/script_a_ado_smoke_test.py`

Output:
```
Creating one ADO Task work item, self-assigned to aisdlclogin@outlook.com...
FAIL: work item creation failed: create_work_item(Task) got a non-JSON response (status=401); PAT may be invalid/expired
```
Exit code: 1 (FAIL)

**Root-cause confirmation (independent of `ado_client.py`):** A separate, minimal diagnostic script issued a raw read-only `GET https://dev.azure.com/{org}/_apis/projects/{project}?api-version=7.1` with the same Basic-auth header built directly from `backend/.env`'s `ADO_PAT`. It returned the identical `401` with `Content-Type: text/html` and body:

```
Access Denied: The Personal Access Token used has expired.
```

This confirms the failure is **not** a bug in `ado_client.py`'s request construction (auth header shape, endpoint URL, json-patch body) — it is the ADO org rejecting the PAT itself as expired. The diagnostic script was deleted after use (scratchpad-only, not committed).

**No ADO work item was created** by this run (the request failed before any write occurred), so there is nothing to verify in the ADO Boards UI for Task 1's "manually opening the created work item" acceptance criterion — this criterion cannot be satisfied until Script A passes with a fresh PAT.

## Files Created/Modified
- `backend/app/services/__init__.py` - Empty package marker
- `backend/app/services/ado_client.py` - `build_patch_op`, `create_work_item`, `verify_work_item`, `push_plan`; Basic auth, json-patch+json, api-version 7.1, Content-Type-before-parse guard, 15s timeouts
- `backend/scripts/__init__.py` - Empty package marker
- `backend/scripts/script_a_ado_smoke_test.py` - Standalone PASS/FAIL smoke test creating + self-assigning one ADO Task via the PAT

`backend/.env.example` was NOT modified — Task 1's action said "confirm, don't duplicate," and it already lists `ADO_ORG`, `ADO_PROJECT`, `ADO_PAT`, `LEAD_EMAIL` from Plan 01-01.

## Decisions Made
- Per the plan's explicit instruction ("If it FAILS, stop and fix the ado_client implementation or the ADO precondition ... before proceeding to Task 2 — do not wire an unverified client into the graph node"), execution stopped immediately after Script A's FAIL result. `backend/app/graph/nodes/push_to_ado.py` was not read-first-then-edited and remains exactly Plan 01-01's stub (`status="not_implemented"` for every item, `pushed=True`/`all_succeeded=False`).
- Diagnosed the failure as a PAT-expiry precondition problem (not a code defect) using a throwaway diagnostic script hitting a read-only ADO endpoint directly — this was scoped as investigation only, discarded after use, and is not part of the committed deliverable.

## Deviations from Plan

None — plan executed exactly as written through Task 1, including its explicit instruction to halt before Task 2 on a Script A failure. No Rule 1/2/3 auto-fixes were applicable: the failure is external (an expired credential), not a bug, missing functionality, or blocking issue inside code this plan controls.

## Issues Encountered

- **ADO PAT expired between Task 0's checkpoint clearance and Task 1's execution (or was already expired when provisioned).** The `.env` file's `ADO_ORG`/`ADO_PROJECT`/`ADO_PAT`/`LEAD_EMAIL` are all non-empty (verified via `python-dotenv` load, without printing values), and the orchestrator confirmed the user's account is a project member. However, the PAT itself returns a "Access Denied: The Personal Access Token used has expired" error from Azure DevOps on every authenticated call, including a bare read-only project-properties GET. This is unrelated to code correctness — `ado_client.py`'s auth header construction, endpoint shape, and json-patch body are unchanged from the researched-and-verified REST call reference and were never actually exercised against a live, valid credential.

## User Setup Required

**A fresh, non-expired Azure DevOps Personal Access Token is required before this plan can proceed to Task 2.**

Steps for the user:
1. Go to Azure DevOps → User Settings → Personal Access Tokens.
2. Create a **new** PAT (the existing one has expired) scoped to **Work Items (Read & Write)** at minimum.
3. Set an expiry that comfortably covers the rest of this build+demo window (not the short default) — this was called out as Pitfall 6 in `01-RESEARCH.md` and is exactly what happened here.
4. Update `ADO_PAT=` in `backend/.env` with the new token value.
5. Confirm `ADO_ORG`, `ADO_PROJECT`, and `LEAD_EMAIL` in `backend/.env` are still correct (unchanged from Task 0's provisioning — only the PAT needs replacing based on the diagnostic evidence above).

**Verification command the user (or a resumed executor) should run after updating the PAT:**
```bash
cd backend && PYTHONPATH=. .venv/bin/python3 scripts/script_a_ado_smoke_test.py
```
Expect a `PASS: work item id=... created at https://dev.azure.com/{org}/{project}/_workitems/edit/{id} and System.AssignedTo resolved to '...'` line. If this prints PASS, Task 2 (wiring `push_to_ado` to `ado_client.push_plan`) can proceed safely.

**Browser-verification items for the user once Script A passes (not yet applicable — no work item was created this run):**
- Once Script A passes, open `https://dev.azure.com/{org}/{project}/_workitems/edit/{id}` (id printed by Script A's PASS line) and confirm it shows assigned to the lead, not "Unassigned" — this is Task 1's remaining manual acceptance criterion.
- Task 2's manual acceptance criteria (epic→task nesting in ADO Boards, before/after item counts across a double-resume) cannot be attempted until Task 2 itself is executed, which is gated on Script A passing first.

## Next Phase Readiness

- **Blocked.** `push_to_ado.py` remains Plan 01-01's stub. Task 2 of this plan (replacing the stub body with `ado_client.push_plan`) cannot start until Script A passes against a valid, non-expired PAT, per this plan's own D-12 sequencing requirement.
- Once the PAT is refreshed and Script A passes, resume this plan at Task 2. No other blockers: the `ado_client.py` implementation itself is complete, matches all static acceptance criteria, and its error-handling correctly surfaced the real-world failure it was built to catch (T-01-08).
- Recommend the orchestrator/user treat this as a `checkpoint:human-action` (PAT renewal) before re-invoking this plan's execution to complete Task 2.

---
*Phase: 01-scaffolding-thin-end-to-end-slice*
*Completed: 2026-07-10 (partial — Task 2 blocked)*

## Self-Check: PASSED

All 4 claimed created files verified present on disk; both commit hashes (5388fd7, 93a2049) verified present in git log.
