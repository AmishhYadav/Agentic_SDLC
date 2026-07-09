---
phase: 02-config-team-greenfield-planning
plan: 01
subsystem: api
tags: [ado, smoke-test, langgraph, pytest, config]

# Dependency graph
requires:
  - phase: 01-scaffolding-thin-end-to-end-slice
    provides: ado_client.py's auth/response-parsing helpers (_auth_header, _org_project, _check_json_response, create_work_item), the RunState TypedDict, and the ingest_config passthrough node this plan replaces
provides:
  - "ado_client.run_smoke_test() — ordered CONN-03 probe sequence (project access -> write scope + best-effort expiry), never raises"
  - "ingest_config grown into a real, blocking config-load + smoke-test entry point (CONN-01/02/03)"
  - "RunState fields (repo_mode, smoke_test_passed, smoke_test) ready for Plan 03's conditional edge"
  - "runs.py surfaces smoke_test detail and overrides status to blocked_smoke_test_failed on failure"
  - "First pytest scaffold for the backend (pytest.ini, tests/conftest.py, 12 passing tests)"
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: [pytest==9.1.1, pytest-asyncio==1.4.0]
  patterns: ["Ordered capability-probe smoke-test (no single introspection call) — project_access short-circuits before write_scope/expiry", "unittest.mock.patch on httpx.AsyncClient for HTTP-call unit tests (no respx dependency)"]

key-files:
  created:
    - backend/pytest.ini
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_ado_smoketest.py
    - backend/tests/test_ingest_config.py
  modified:
    - backend/app/services/ado_client.py
    - backend/app/graph/nodes/ingest_config.py
    - backend/app/graph/state.py
    - backend/app/routers/runs.py
    - backend/requirements.txt
    - backend/.env.example

key-decisions:
  - "Used pytest==9.1.1 / pytest-asyncio==1.4.0 (current top versions per pip index versions) instead of the plan's suggested 8.4.2/1.2.0, per the plan's own 'verify before pinning' instruction"
  - "Expiry best-effort probe (_apis/tokens/pats) degrades to 'unknown (best-effort check unavailable)' on any non-200/non-JSON response, and is never allowed to fail the overall smoke-test, per Pitfall 1/Open Question 1's unresolved PAT-introspection ambiguity"
  - "build.py deliberately left untouched — this plan only makes smoke_test_passed/smoke_test/repo_mode available on RunState; the conditional edge that actually halts graph execution on failure is Plan 03's scope"

patterns-established:
  - "Smoke-test probes live in ado_client.py and reuse _auth_header/_org_project/_check_json_response rather than duplicating auth/parsing logic"
  - "_derive_status in runs.py surfaces new state fields following the existing 'None for not_found' convention, and can override the derived status string for a blocking condition"

requirements-completed: [CONN-01, CONN-02, CONN-03]

# Metrics
duration: 20min
completed: 2026-07-10
---

# Phase 2 Plan 1: Config & ADO Smoke-Test Summary

**Grew `ingest_config` from a Phase 1 passthrough into a real, blocking CONN-01/02/03 entry point with an ordered ADO PAT smoke-test (project access, write scope, best-effort expiry) surfaced in detail through `GET /runs/{id}`.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-09T21:01:58Z (per STATE.md session start)
- **Completed:** 2026-07-10 (session date)
- **Tasks:** 2 completed
- **Files modified:** 10 (5 created, 5 modified — excluding SUMMARY/STATE/ROADMAP)

## Accomplishments
- Built the first pytest scaffold for the backend (`pytest.ini`, `conftest.py`) with 12 passing unit tests, zero new HTTP-mocking dependencies
- Implemented the ordered ADO PAT smoke-test (`run_smoke_test`) per Pitfall 2's capability-probe design — distinguishes auth failure, missing write scope, and no project access with specific, non-opaque reasons
- Grew `ingest_config` into a real config-load + blocking smoke-test node, and extended `RunState`/`runs.py` to surface the result without breaking existing status derivation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pytest scaffold and ADO smoke-test probe sequence with unit tests** - `aeabc72` (feat)
2. **Task 2: Wire blocking smoke-test + real config load into ingest_config** - `9f36382` (test, RED) then `f0dbfa3` (feat, GREEN)

**Plan metadata:** _pending — this SUMMARY's own commit_

_Note: Task 2 was tdd="true" and followed RED/GREEN — no REFACTOR commit was needed._

## Files Created/Modified
- `backend/pytest.ini` - pytest config (asyncio_mode=auto, testpaths=tests)
- `backend/tests/__init__.py` - test package marker
- `backend/tests/conftest.py` - shared `mock_ado_env` fixture (monkeypatch ADO_ORG/PROJECT/PAT)
- `backend/tests/test_ado_smoketest.py` - 7 unit tests for `run_smoke_test`/`check_project_access`/`check_write_scope`/`check_expiry_best_effort`
- `backend/tests/test_ingest_config.py` - 5 unit tests for the grown `ingest_config` node and `_derive_status`'s smoke_test surfacing
- `backend/app/services/ado_client.py` - added `check_project_access`, `check_write_scope`, `check_expiry_best_effort`, `run_smoke_test`
- `backend/app/graph/nodes/ingest_config.py` - rewritten: real `.env` config load, blocking smoke-test call, `repo_mode` read with greenfield default
- `backend/app/graph/state.py` - added `repo_mode`, `smoke_test_passed`, `smoke_test` fields to `RunState`
- `backend/app/routers/runs.py` - `_derive_status` surfaces `smoke_test`/`smoke_test_passed` on every branch, overrides status to `blocked_smoke_test_failed` on failure
- `backend/requirements.txt` - added `pytest==9.1.1`, `pytest-asyncio==1.4.0`
- `backend/.env.example` - added `GITHUB_REPO=` and `REPO_MODE=greenfield`

## Decisions Made
- Pinned pytest/pytest-asyncio to their current top PyPI versions (9.1.1/1.4.0) rather than the plan's suggested 8.4.2/1.2.0, per the plan's explicit "verify via pip index versions before pinning" instruction — confirmed no compatibility issues (all 12 tests pass under Python 3.13.11 in `backend/.venv`).
- Left `build.py` untouched as directed — `ingest_config` becoming async requires no build.py change since LangGraph's `add_node` accepts async functions transparently; the conditional edge that halts the graph on a failed smoke-test is explicitly Plan 03's scope.

## Deviations from Plan

None - plan executed exactly as written. The pytest version pin substitution (8.4.2/1.2.0 -> 9.1.1/1.4.0) was explicitly directed by the plan's own action text ("verify these are the current top versions... if a newer patch exists, use that instead"), not a deviation from intent.

## Issues Encountered

None blocking. Manual verification against a real ADO org (`phase1-pilot-demo`) with an intentionally wrong project name and a fake PAT correctly produced `smoke_test_passed: False` with a `project_access` check reason (`"PAT invalid or expired (non-JSON/203 response)"`), confirming the plan's `<verification>` requirement. Note: STATE.md's carried-forward blocker (expired real `ADO_PAT`) was not re-tested against a valid PAT in this plan — that remains an open item for whenever push_to_ado (already built in Phase 1) needs to be exercised against live ADO again; it does not block this plan's CONN-01/02/03 scope, which is fully covered by the unit test suite and the wrong-project-name manual check above.

## Verification Evidence

- `cd backend && pytest -x` -> 12 passed (full suite, all new tests)
- `grep -c "async def run_smoke_test" backend/app/services/ado_client.py` -> 1
- `grep -c "async def check_project_access" backend/app/services/ado_client.py` -> 1
- `grep -n "pytest==" / "pytest-asyncio=="` in requirements.txt -> both present
- Manual check: wrong `ADO_PROJECT` + fake `ADO_PAT` -> `smoke_test_passed=False`, `project_access` reason surfaced (see Issues Encountered)

## TDD Gate Compliance

Task 2 (tdd="true"): RED commit `9f36382` (`test(02-01): add failing tests...`, 5 tests failing as expected) precedes GREEN commit `f0dbfa3` (`feat(02-01): wire blocking ADO smoke-test...`, all 5 passing). Gate sequence satisfied — no warning needed.

## Known Stubs

None. All code paths in this plan's scope (`run_smoke_test` and its three sub-checks, `ingest_config`, `_derive_status`'s smoke_test surfacing) are fully implemented, not placeholders.

## Threat Flags

None. This plan's new surface (ADO smoke-test probes, `smoke_test` detail crossing the FastAPI->frontend boundary) was already anticipated in the plan's own `<threat_model>` (T-02-01/02/03) and no additional surface was introduced beyond what that threat model covers. Verified: no `reason=` string literal in `ado_client.py` interpolates the raw `ADO_PAT` value (see Self-Check below).

## Next Steps
- Plan 02-02/02-03/02-04 (team roster, greenfield doc fetch, plan generation) can now assume `RunState["repo_mode"]`/`["smoke_test_passed"]`/`["smoke_test"]` exist and are correctly populated by `ingest_config`.
- Plan 03 (per 02-CONTEXT.md/02-RESEARCH.md's architecture map) owns adding the `route_repo_mode` conditional edge in `build.py`, which must check `state.get("smoke_test_passed")` first and route to a blocked/terminal path when False, before the greenfield/brownfield branch.

## Self-Check: PASSED

All 12 created/modified files confirmed present on disk; all 3 task commit hashes (`aeabc72`, `9f36382`, `f0dbfa3`) confirmed in `git log --oneline --all`.
