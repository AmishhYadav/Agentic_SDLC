---
phase: 02-config-team-greenfield-planning
plan: 03
subsystem: api
tags: [langgraph, pygithub, conditional-edge, greenfield, repo-mode]

# Dependency graph
requires:
  - phase: 02-config-team-greenfield-planning
    plan: 01
    provides: "RunState fields repo_mode/smoke_test_passed/smoke_test, blocking ingest_config"
provides:
  - "github_client.fetch_greenfield_docs() — README + docs/**/*.md tree-enumeration + targeted-fetch, capped at max_chars"
  - "route_after_config(state) — pure routing function: blocked (failed smoke-test) -> brownfield stub -> greenfield (default)"
  - "read_docs_greenfield / ingest_brownfield_stub graph nodes, both converging into stub_plan"
  - "RunState.docs_text / RunState.blocked_reason fields for Plan 04's generate_plan to consume"
affects: [02-04]

# Tech tracking
tech-stack:
  added: [PyGithub==2.9.1]
  patterns:
    - "Pure path-matching (_match_doc_paths) + injectable get_contents_fn keep github_client.py unit-testable without network calls"
    - "Conditional-edge routing function (route_after_config) lives in build.py as a plain function, not a graph node, mirroring 02-RESEARCH.md Pattern 1"

key-files:
  created:
    - backend/app/services/github_client.py
    - backend/app/graph/nodes/read_docs_greenfield.py
    - backend/app/graph/nodes/ingest_brownfield_stub.py
    - backend/tests/test_github_client.py
    - backend/tests/test_build_graph.py
  modified:
    - backend/app/graph/build.py
    - backend/app/graph/state.py
    - backend/requirements.txt

key-decisions:
  - "fnmatch avoided entirely per Pitfall 5 — _match_doc_paths uses explicit path.lower().startswith('docs/')/.endswith('.md') and a root-only 'no slash + startswith readme' check instead of glob patterns"
  - "fetch_greenfield_docs accepts optional tree_paths/get_contents_fn injection points so the pure matching/concatenation logic is testable without a real Github() client or network access; falls back to a real PyGithub client when both are omitted"
  - "route_after_config checks smoke_test_passed before repo_mode, giving the CONN-03 blocking gate priority over the greenfield/brownfield branch, per the plan's exact three-way spec"
  - "A failed smoke-test routes directly to END via the conditional-edges mapping (no dedicated 'blocked' node) — Plan 01's blocked_smoke_test_failed status derivation already surfaces this from state, so no further node processing is needed"

patterns-established:
  - "Greenfield/brownfield legs both return docs_text/blocked_reason and converge into the same downstream node (stub_plan for now, generate_plan in Plan 04) rather than branching further downstream"

requirements-completed: [REPO-01, REPO-02]

# Metrics
duration: 24min
completed: 2026-07-09
---

# Phase 2 Plan 3: Conditional Edge Wiring & Greenfield Doc Fetch Summary

**Replaced the straight-line `ingest_config -> stub_plan` edge with a real conditional branch that blocks on a failed smoke-test, reads real README/docs/**/*.md content on the greenfield path via PyGithub tree enumeration, and takes a guarded, honest placeholder on the brownfield path — both converging into `stub_plan` for Plan 04 to replace next.**

## Performance

- **Duration:** ~24 min
- **Started:** 2026-07-09T21:00:00Z (session start, per STATE.md)
- **Completed:** 2026-07-09
- **Tasks:** 2 completed
- **Files modified:** 8 (5 created, 3 modified — excluding SUMMARY/STATE/ROADMAP)

## Accomplishments
- Built `github_client.fetch_greenfield_docs()` with tree-enumeration + targeted-fetch, explicit (non-fnmatch) doc-path matching per Pitfall 5, and a hard `max_chars` cap that truncates and stops early rather than over-fetching
- Replaced `build.py`'s straight-line `ingest_config -> stub_plan` edge with a real `add_conditional_edges` call routing on `smoke_test_passed` (priority) then `repo_mode`
- Added `read_docs_greenfield` (real greenfield doc-fetch node) and `ingest_brownfield_stub` (guarded, zero-network, never-crashing D-09 placeholder), both converging into `stub_plan`
- A failed smoke-test now dead-ends the compiled graph at `END` without reaching doc-fetch or plan-generation, verified via an integration-level compiled-graph test

## Task Commits

Each task was committed atomically:

1. **Task 1: github_client doc-fetch service with tree enumeration + size cap** - `9f082f3` (test, RED) then `e72124a` (feat, GREEN)
2. **Task 2: Conditional edge wiring — smoke-test gate, repo_mode branch, brownfield placeholder** - `1924fb2` (test, RED) then `67a4e96` (feat, GREEN)

**Plan metadata:** _pending — this SUMMARY's own commit_

_Note: Both tasks were tdd="true" and followed RED/GREEN — no REFACTOR commit was needed for either._

## Files Created/Modified
- `backend/app/services/github_client.py` - `fetch_greenfield_docs()` (tree-enumeration + targeted fetch, capped) and `_match_doc_paths()` (pure, unit-testable path filter)
- `backend/app/graph/nodes/read_docs_greenfield.py` - real greenfield node, reads `GITHUB_REPO`/`GITHUB_TOKEN` fresh from env, calls `github_client`, sets `docs_text`/`blocked_reason`
- `backend/app/graph/nodes/ingest_brownfield_stub.py` - synchronous, zero-network guarded placeholder returning the D-09 "Phase 5" message
- `backend/tests/test_github_client.py` - 6 unit tests covering doc-path matching, concatenation, truncation, and no-match `None` return
- `backend/tests/test_build_graph.py` - 5 unit tests for `route_after_config` + 3 integration tests on the compiled graph (greenfield reach, brownfield reach, blocked dead-end)
- `backend/app/graph/build.py` - added `route_after_config`, registered the two new nodes, replaced the straight edge with `add_conditional_edges`
- `backend/app/graph/state.py` - added `docs_text: str | None`, `blocked_reason: str | None` to `RunState`
- `backend/requirements.txt` - added `PyGithub==2.9.1` (verified current top version via `pip index versions`)

## Decisions Made
- Verified `PyGithub==2.9.1` is still the current top PyPI version before committing to it (matches 02-RESEARCH.md's finding from one day prior) — no drift.
- Kept `fetch_greenfield_docs`'s signature flexible (`tree_paths`/`get_contents_fn` optional injection points) rather than requiring a real `Github` client in every call, so the plan's Task 1 Test 1-4 behaviors are exercisable without network access, per the plan's own "Claude's discretion on exact signature split" note.
- Routed the failed-smoke-test case directly to `END` via the conditional-edges mapping rather than adding a dedicated "blocked" node, exactly as the plan specified — `runs.py`'s existing `blocked_smoke_test_failed` status override (built in Plan 01) already surfaces this from state with no further processing needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None blocking. All behaviors specified in the plan's `<behavior>` sections were implemented and verified exactly as described.

## Verification Evidence

- `cd backend && pytest tests/test_github_client.py tests/test_build_graph.py -x` -> 14 passed
- `cd backend && pytest -x` (full suite) -> 35 passed, no regressions to Plan 01/02's tests
- `grep -c "def fetch_greenfield_docs" backend/app/services/github_client.py` -> 1
- `grep -c "fetch_greenfield_docs" backend/app/graph/nodes/read_docs_greenfield.py` -> 2
- `grep -c "blocked_reason" backend/app/graph/nodes/ingest_brownfield_stub.py` -> 2
- `grep -c "add_conditional_edges" backend/app/graph/build.py` -> 1
- Confirmed `add_conditional_edges("ingest_config", route_after_config, ...)` present in `build.py` (multi-line call, matched by direct read)

## TDD Gate Compliance

Task 1 (tdd="true"): RED commit `9f082f3` (`test(02-03): add failing tests for github_client doc-fetch service`, 6 tests failing on import error) precedes GREEN commit `e72124a` (`feat(02-03): implement github_client doc-fetch...`, all 6 passing). Gate sequence satisfied.

Task 2 (tdd="true"): RED commit `1924fb2` (`test(02-03): add failing tests for conditional edge wiring`, 8 tests failing on import error) precedes GREEN commit `67a4e96` (`feat(02-03): wire conditional edge for smoke-test gate + repo_mode branch`, all 8 passing). Gate sequence satisfied.

## Known Stubs

`ingest_brownfield_stub.py` is an intentional, documented placeholder per D-09 — it is not an unintentional stub. It returns a clear, honest "Brownfield planning arrives in Phase 5" message, never attempts real ingestion, never crashes, and never silently falls back to greenfield. Phase 5 replaces this node with real brownfield RAG ingestion. This is explicitly in-scope-as-a-placeholder per the plan's objective and 02-CONTEXT.md D-09, not a gap to flag for the verifier.

`stub_plan.py`'s body is unchanged and still ignores `docs_text`/`blocked_reason` — this is expected and explicitly out of scope for this plan (Plan 04 replaces `stub_plan` with `generate_plan`, which is the node that will actually consume these fields and short-circuit on `blocked_reason`).

## Threat Flags

None. This plan's new surface (GitHub doc content flowing toward a future LLM prompt, `GITHUB_TOKEN` outbound calls) was already anticipated in the plan's own `<threat_model>` (T-02-06/07/08) and no additional surface was introduced beyond what that threat model covers:
- T-02-07 (DoS via unbounded doc concatenation) — mitigated by the `max_chars` cap, verified by Task 1's truncation test.
- T-02-08 (GITHUB_TOKEN disclosure) — mitigated by reading the token fresh from `os.environ` inside `read_docs_greenfield`, never stored in `RunState` or logged.
- T-02-06 (prompt injection via malicious docs) — accepted per the threat model's own disposition; `docs_text` is passed through as opaque data by this plan, with no prompt construction happening yet (that's Plan 04's responsibility, already flagged as a constraint on that plan in the threat register).

## Next Steps
- Plan 04 (real `generate_plan`) replaces `stub_plan` as the terminal node for both the greenfield and brownfield legs, consumes `RunState["docs_text"]`, and must check `RunState["blocked_reason"]` first and short-circuit with a clear error/status when it is not `None` (covers both D-12's no-docs case and D-09's brownfield-placeholder case) rather than attempting to generate a plan from empty context.
- `GITHUB_TOKEN`/`GITHUB_REPO` real-world verification against a live repo was not performed in this plan (all tests use mocked/injected fixtures) — the same "PAT/token needs live verification" caveat noted in Plan 01's summary applies here too; recommend a manual smoke check with a real `GITHUB_TOKEN` before the Phase 2 demo.

## Self-Check: PASSED

All 8 created/modified files confirmed present on disk; all 4 task commit hashes (`9f082f3`, `e72124a`, `1924fb2`, `67a4e96`) confirmed in `git log --oneline --all`.
