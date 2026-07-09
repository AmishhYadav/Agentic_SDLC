# Walking Skeleton — AI Project Planning & Onboarding Dashboard

**Phase:** 1
**Generated:** 2026-07-09

## Capability Proven End-to-End

A lead can click Start in the browser, watch a run pause for human review (a hardcoded stub plan), click Approve, and see the resulting Azure DevOps epic + tasks created with correct parent/child hierarchy and confirmed assignment — with the whole run surviving a backend restart mid-review.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Orchestration | Single LangGraph `StateGraph`, straight-line spine `ingest_config -> stub_plan -> human_review -> push_to_ado`, one `thread_id = run_id` | D-01/D-03: minimal spine only, no branch node this phase; `interrupt()` isolated in its own side-effect-free node (research Pattern 2, Pitfall 1) |
| Checkpointer | `AsyncSqliteSaver` (langgraph-checkpoint-sqlite), file-backed, opened once in FastAPI lifespan, stored on `app.state` | D-04 overrides CLAUDE.md's `InMemorySaver` table entry — required for ORCH-02 (restart survival); never `MemorySaver` (Pitfall 2) |
| Backend framework | FastAPI 0.139.0, async routes, `httpx` for outbound ADO calls | Already locked project-wide; async-native, matches `AsyncSqliteSaver`'s native async methods |
| Plan schema | Single shared Pydantic model (`Plan`/`Epic`/`Task`/`PushReport`/`PushResultItem`) in `backend/app/models/plan.py`, imported by graph nodes AND API response models | D-06 + CLAUDE.md file/folder rule: one source-of-truth shape, no ad-hoc dicts, no duplicate representations |
| Frontend framework | React 19 + Vite, plain fetch/`@tanstack/react-query` polling (no SSE) | D-07/D-08, resolving CLAUDE.md's internal Next.js/React contradiction (research A4) in favor of the more specific, locked CONTEXT.md decision |
| ADO integration | Direct REST via `httpx`, `api-version=7.1`, `Content-Type: application/json-patch+json`, Basic auth with empty username | CLAUDE.md gotchas + research; `azure-devops` SDK explicitly rejected (stale, beta) |
| Run metadata storage | Same SQLite file as the checkpointer, separate table (`runs`) | Claude's discretion per CONTEXT.md; avoids managing two DB files for a 2-day MVP |
| Directory layout | `backend/app/{routers,graph/nodes,services,models,db}`, `backend/scripts/`, `frontend/src/{pages,lib}` | Per `.planning/research/ARCHITECTURE.md` "Recommended Project Structure," scoped down to Phase 1 needs |

## Stack Touched in Phase 1

- [x] Project scaffold (backend `venv` + FastAPI app skeleton; frontend Vite + React-TS scaffold; root `.gitignore` covering `.env`)
- [x] Routing — `POST /runs`, `GET /runs/{id}`, `POST /runs/{id}/resume` (real routes, not stubs)
- [x] Database — `AsyncSqliteSaver` checkpoint writes (LangGraph state) AND `runs` metadata table read/write (both real SQLite reads/writes)
- [x] UI — Start button (POST), polling status display (GET), Approve button (POST) wired to the real API, no mocked data
- [x] Deployment — documented local full-stack run command (`uvicorn` + `npm run dev`); no hosted deployment target for this 2-day local MVP (out of scope per CLAUDE.md — no auth, single local lead)

## Out of Scope (Deferred to Later Slices)

- Greenfield/brownfield branch node — Phase 2 (D-01/D-02)
- Real ADO/GitHub config intake forms, team roster CRUD — Phase 2
- LLM plan generation (`generate_plan` node) — Phase 2
- Risk scoring (deterministic engine + LLM explanation) — Phase 3
- Direct plan editing UI, chat-driven edits, diff preview — Phase 4
- Brownfield RAG ingestion, onboarding summary — Phase 5
- SSE streaming for run status (polling only this phase) — noted as a post-MVP scaling option in ARCHITECTURE.md
- Any styling/visual polish on the React page — D-08

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: Replace `ingest_config`'s hardcoded passthrough with real ADO+GitHub connection config and team roster intake; add the greenfield/brownfield branch node; replace `stub_plan` with a real LLM-generated plan (still the same `Plan`/`Epic`/`Task` schema from Phase 1)
- Phase 3: Add skill/load-aware assignment and deterministic risk scoring on top of the same plan/team shape
- Phase 4: Add direct plan editing and LLM chat-driven editing with diff preview, reusing this phase's `interrupt()`/`update_state` pattern a second time
- Phase 5: Add brownfield codebase RAG ingestion and onboarding summary generation, feeding into the same `generate_plan` path from Phase 2
