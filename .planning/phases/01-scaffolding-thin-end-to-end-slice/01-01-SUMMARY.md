---
phase: 01-scaffolding-thin-end-to-end-slice
plan: 01
subsystem: api
tags: [langgraph, fastapi, sqlite, pydantic, interrupt-resume, checkpointing]

# Dependency graph
requires: []
provides:
  - "Shared Plan/Epic/Task/PushReport/PushResultItem Pydantic schema (backend/app/models/plan.py) — the single source of truth for plan data"
  - "RunState TypedDict (backend/app/graph/state.py) shared across all graph nodes"
  - "Four-node LangGraph straight-line spine: ingest_config -> stub_plan -> human_review -> push_to_ado"
  - "FastAPI app with AsyncSqliteSaver opened once in lifespan, graph compiled once, stored on app.state.graph"
  - "POST /runs, GET /runs/{id}, POST /runs/{id}/resume routes with a single shared status-derivation helper"
  - "Proven interrupt/resume + restart-survival integration point (ORCH-01 partial, ORCH-02)"
affects: [01-02-push-to-ado, 01-03-frontend]

# Tech tracking
tech-stack:
  added: ["fastapi[standard]==0.139.0", "langgraph==1.2.8", "langgraph-checkpoint-sqlite==3.1.0", "httpx==0.28.1", "pydantic==2.13.4", "python-dotenv==1.2.2"]
  patterns:
    - "AsyncSqliteSaver opened exactly once in FastAPI lifespan, compiled graph stored on app.state.graph — never per-request"
    - "interrupt() isolated in a side-effect-free node (human_review); no plan mutation or ADO calls before/around it"
    - "push_to_ado gated by a pushed:bool flag so re-invocation after completion is a no-op (defends against double-resume)"
    - "Status for all three run routes derived from graph.aget_state(config).next / .values, never a hand-rolled parallel status field"

key-files:
  created:
    - backend/app/models/plan.py
    - backend/app/graph/state.py
    - backend/app/graph/build.py
    - backend/app/graph/nodes/ingest_config.py
    - backend/app/graph/nodes/stub_plan.py
    - backend/app/graph/nodes/human_review.py
    - backend/app/graph/nodes/push_to_ado.py
    - backend/app/main.py
    - backend/app/routers/runs.py
    - backend/app/db/run_metadata.py
    - backend/requirements.txt
    - backend/.env.example
    - .gitignore
  modified: []

key-decisions:
  - "Used Python 3.13 (Homebrew) for the backend venv since the system python3 was 3.9.6, below the project's 3.12+ floor — no code impact, purely environment setup"
  - "Confirmed AsyncSqliteSaver.setup() takes no arguments and is idempotent (guarded by an internal is_setup flag) by reading the installed package source directly, resolving research Assumption A2 with no deviation needed"
  - "Left the langgraph-checkpoint msgpack deprecation warning for Pydantic model types unresolved (non-blocking today; from_conn_string doesn't expose a serde override) — documented as a known follow-up rather than adding checkpointer construction complexity out of scope for this thin slice"

patterns-established:
  - "Pattern 1: AsyncSqliteSaver opened once in lifespan, never per-request"
  - "Pattern 2: interrupt() inside human_review, node re-executes from its top on resume — no side effects before/around the call"
  - "Pattern 3: push_to_ado gated by a pushed flag so it runs exactly once even across a double-resume"

requirements-completed: [ORCH-01, ORCH-02]

# Metrics
duration: ~20min
completed: 2026-07-10
---

# Phase 01 Plan 01: Scaffolding + LangGraph Interrupt/Resume Spine Summary

**Four-node LangGraph spine (`ingest_config -> stub_plan -> human_review -> push_to_ado`) wired into FastAPI with a durable file-backed `AsyncSqliteSaver` checkpointer — verified live that a run pauses at human review, survives a real backend process restart, and resumes to a stubbed completion without double-firing on a repeated approve.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-10T01:04:00+05:30 (approx, first commit 01:06:13+05:30)
- **Completed:** 2026-07-10T01:09:33+05:30
- **Tasks:** 3 completed
- **Files modified:** 19 created (13 backend source/config files + 6 `__init__.py` package markers)

## Accomplishments
- Shared `Plan`/`Epic`/`Task`/`PushReport`/`PushResultItem` Pydantic schema is the single source of truth, imported by both graph nodes and (eventually) API response models — no parallel plan representation exists anywhere in the codebase.
- The four-node straight-line spine compiles and runs end-to-end with `interrupt()` fully isolated in `human_review` (no side effects before or around the call) and `push_to_ado` gated by a `pushed` flag.
- Live-verified against a real running `uvicorn` process (not just unit-level): started a run, confirmed `awaiting_review`, **killed and restarted the backend process**, and confirmed the same `run_id` still returned `awaiting_review` with the plan intact — this is the ORCH-02 restart-survival proof running against the actual file-backed SQLite checkpoint, not a mock.
- Confirmed double-resume idempotency against the live server: calling `POST /runs/{id}/resume` a second time on an already-completed thread returned the identical `completed` status and `push_report` with no error and no re-push.

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold backend project, gitignore, and the shared Plan/RunState schema** - `d0aed6f` (feat)
2. **Task 2: Build the four graph nodes and the StateGraph spine** - `e5bfb20` (feat)
3. **Task 3: Wire FastAPI app with AsyncSqliteSaver lifespan and the three run routes** - `c032a9d` (feat)

## Files Created/Modified
- `.gitignore` - Excludes `.env`, venvs, `__pycache__`, sqlite checkpoint files, and frontend build artifacts
- `backend/requirements.txt` - Pins fastapi/langgraph/langgraph-checkpoint-sqlite/httpx/pydantic/python-dotenv to the exact versions in CLAUDE.md's stack table
- `backend/.env.example` - Empty placeholders for ADO_ORG/ADO_PROJECT/ADO_PAT/GITHUB_TOKEN/ANTHROPIC_API_KEY/DATABASE_URL plus LEAD_EMAIL and CHECKPOINT_DB_PATH
- `backend/app/models/plan.py` - Task/Epic/Plan/PushResultItem/PushReport Pydantic classes — the one shared plan shape
- `backend/app/graph/state.py` - RunState TypedDict (run_id, lead_email, plan, approved, pushed, push_report)
- `backend/app/graph/nodes/ingest_config.py` - Trivial passthrough reading LEAD_EMAIL from env
- `backend/app/graph/nodes/stub_plan.py` - Builds a real Plan instance: 1 epic, 3 tasks, all self-assigned to lead_email
- `backend/app/graph/nodes/human_review.py` - Side-effect-free interrupt() node
- `backend/app/graph/nodes/push_to_ado.py` - Stub push node gated by pushed/approved flags; Plan 01-02 replaces the body only
- `backend/app/graph/build.py` - Builds the uncompiled StateGraph with the straight-line spine
- `backend/app/main.py` - FastAPI app; lifespan opens AsyncSqliteSaver once, compiles graph, stores on app.state
- `backend/app/routers/runs.py` - POST /runs, GET /runs/{id}, POST /runs/{id}/resume with a single shared `_derive_status` helper
- `backend/app/db/run_metadata.py` - sqlite3-based run_id -> lead_email/created_at table in the same file as the checkpointer

## Decisions Made
- System `python3` was 3.9.6 (below the project's 3.12+ floor); used Homebrew's `python3.13` to create the backend venv instead. No code impact — purely a local environment choice, not a deviation from the plan's architecture.
- Verified `AsyncSqliteSaver.setup()`'s actual signature/behavior directly against the installed `langgraph-checkpoint-sqlite==3.1.0` package (per research Assumption A2's instruction): it takes no arguments and is idempotent via an internal `is_setup` guard flag. No adaptation needed — implemented exactly as researched.

## Deviations from Plan

None - plan executed exactly as written. The one behavior worth flagging (not a deviation, an observed runtime characteristic) is documented below under Issues Encountered.

## Issues Encountered

- **`langgraph-checkpoint` msgpack deprecation warning:** Deserializing the custom `Plan`/`PushReport` Pydantic types from a checkpoint logs `"Deserializing unregistered type ... This will be blocked in a future version"`. This is non-blocking today (verified restart-survival works correctly with the warning present) — the permissive default (`allowed_msgpack_modules=True`) is what current `langgraph-checkpoint==4.1.1` uses unless `LANGGRAPH_STRICT_MSGPACK=true` is set. `AsyncSqliteSaver.from_conn_string()` does not expose a `serde=` override, so silencing this cleanly would require manually constructing the checkpointer instead of using the documented factory — judged out of scope for this thin slice. **Flagging as a known follow-up**: if `langgraph-checkpoint` flips its default to strict mode in a future release, this checkpointer wiring will need an explicit `JsonPlusSerializer(allowed_msgpack_modules=[("app.models.plan", "Plan"), ("app.models.plan", "PushReport"), ("app.models.plan", "Epic"), ("app.models.plan", "Task"), ("app.models.plan", "PushResultItem")])` passed through a manually constructed `AsyncSqliteSaver` instance.

## User Setup Required

None for this plan — no external service configuration required. (Real ADO org/project/PAT provisioning is a precondition for Plan 01-02, not this plan; `push_to_ado` in this plan is a deliberate no-op stub.)

## Next Phase Readiness

- The graph spine, shared Plan schema, and FastAPI route contract are all in place and proven durable across a real process restart — Plan 01-02 can replace `push_to_ado`'s stub body with the real ADO REST implementation without touching the node's place in the graph or its function signature.
- Plan 01-03 (frontend) can build directly against the `POST /runs` / `GET /runs/{id}` / `POST /runs/{id}/resume` contract exactly as documented in this plan's `<interfaces>` block — verified live against all three routes.
- No blockers. The ADO precondition (real org/project/PAT/lead identity, D-11/D-12) still needs to be provisioned before Plan 01-02's `push_to_ado` implementation and Script A can run — this is unchanged from before this plan and is Plan 01-02's concern, not a blocker introduced here.

---
*Phase: 01-scaffolding-thin-end-to-end-slice*
*Completed: 2026-07-10*

## Self-Check: PASSED

All 14 claimed files verified present on disk; all 4 commit hashes (d0aed6f, e5bfb20, c032a9d, 9957006) verified present in git log.
