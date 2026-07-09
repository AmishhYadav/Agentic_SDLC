# Phase 1: Scaffolding + Thin End-to-End Slice - Research

**Researched:** 2026-07-09
**Domain:** LangGraph durable interrupt/resume (AsyncSqliteSaver) + FastAPI async orchestration + Azure DevOps REST work-item push (JSON-Patch, hierarchy links, assignment verification)
**Confidence:** HIGH (LangGraph interrupt/checkpoint semantics and ADO REST shapes verified against official docs; MEDIUM on `AsyncSqliteSaver.setup()` exact signature — not fully documented, verify against installed package at implementation time)

## Summary

Phase 1 has zero real feature logic — its entire job is to de-risk two integration points before Phase 2 builds anything on top of them. The plumbing is well-documented but has sharp edges that are easy to get subtly wrong in ways that "look done" in a demo and then fail exactly when it matters (double-fired ADO writes on resume, lost review state on a dev server reload, unassigned work items that return 200 OK).

The LangGraph side requires exactly the shape CONTEXT.md already locked in (D-01/D-03/D-04): a minimal 4-node straight-line spine, `interrupt()` isolated in its own side-effect-free node, and `AsyncSqliteSaver` — never `MemorySaver`/`InMemorySaver` — wired through FastAPI's lifespan so the connection outlives individual requests. The critical mental model correction for the planner: **on resume, LangGraph re-executes the interrupted node from its top, not from the `interrupt()` line.** This is documented, expected behavior, not a bug — every side effect (the ADO push) must live in a node that only runs *after* the interrupt node returns control, gated so it fires exactly once.

The ADO side requires a small number of precise REST calls (create epic, create task, link task→epic via `System.LinkTypes.Hierarchy-Reverse` on the child, read back to verify) using `Content-Type: application/json-patch+json`, Basic auth with an empty username, and api-version `7.1`. Every write must be followed by a read-back — ADO returns 200/201 even when `System.AssignedTo` silently fails to resolve, so "the API call succeeded" and "the assignment worked" are two different facts that must be checked separately.

**Primary recommendation:** Build the graph as `ingest_config → stub_plan → human_review → push_to_ado`, compiled once at FastAPI startup with `AsyncSqliteSaver` opened in the app's lifespan (not per-request), and build/run the two standalone verification scripts (Script A: ADO create+self-assign; a LangGraph interrupt/resume smoke script analogous to "Script A" for the graph side) before wiring either concern into the real node functions.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Run orchestration (graph sequencing, interrupt/resume) | API / Backend (LangGraph in-process) | — | LangGraph graph lives inside the FastAPI process; no separate orchestration service in a 2-day local MVP |
| Durable checkpoint storage | Database / Storage (SQLite file) | — | `AsyncSqliteSaver` writes to a local `.sqlite` file; this IS the durability mechanism for ORCH-02 |
| Run status / plan display | Browser / Client (React) | API / Backend (poll endpoint) | Client polls a read-only status endpoint; no business logic in the browser |
| Approve action | Browser / Client (button) → API / Backend (resume) | — | Click triggers `POST /runs/{id}/resume`; all resume logic (Command construction, thread targeting) is backend |
| Stub plan generation | API / Backend (graph node) | — | Pure Python stub-plan builder inside `stub_plan` node; zero LLM, zero client involvement |
| ADO work-item push + verification | API / Backend (`ado_client` service) | External Service (Azure DevOps) | All ADO calls are server-side using the shared PAT; browser never talks to ADO directly |
| Run metadata (status, timestamps) | Database / Storage (SQLite — same or separate file, Claude's discretion per CONTEXT.md) | — | Persisted so `GET /runs/{id}` survives backend restart independent of graph checkpoint internals |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Build the minimal straight-line spine only — `ingest_config → stub_plan → human_review → push_to_ado`. Do not scaffold the greenfield/brownfield branch node in Phase 1; it is added in Phase 2.
- **D-02:** ORCH-01 is only *partially* satisfied here — interrupt/resume half is proven now, branch half deferred to Phase 2. Do not attempt to fully deliver ORCH-01 in Phase 1.
- **D-03:** Single `StateGraph`, one `thread_id = run_id`. `interrupt()` lives in its own dedicated, side-effect-free `human_review` node — read state, pause, merge resume payload only. No plan mutation or ADO calls inside the interrupt node.
- **D-04:** Use a file-backed SQLite checkpointer (`AsyncSqliteSaver`, matching FastAPI's async handlers) from day one — required for ORCH-02 + success criterion #2. This overrides the `InMemorySaver` recommendation in CLAUDE.md's stack table. Never use `MemorySaver` even temporarily.
- **D-05:** Hardcoded stub is 1 epic + 2–3 tasks, all self-assigned to the lead's own ADO identity.
- **D-06:** The stub must be a real instance of the shared plan JSON/Pydantic schema (source-of-truth shape from `project-spec.md`), not an ad-hoc dict.
- **D-07:** Build a minimal React page with live status: Start button, polling status indicator showing transition into "awaiting_review" + rendering the stub plan, and an Approve button that resumes. Polling (not SSE) is sufficient.
- **D-08:** No styling/polish, no config or team forms — those are Phase 2. This page exists only to demo success criterion #1 through a real UI rather than curl.
- **D-09:** `push_to_ado` uses partial-success reporting: push what succeeds, collect per-item failures, return a structured report. One bad item does not hard-abort the whole run. Nothing is silently swallowed.
- **D-10:** After each work-item write, read the field back (`fields/System.AssignedTo`, parent link) and confirm it resolved — do not assume 200/201 means success. ADO writes use `Content-Type: application/json-patch+json` with a patch-op array; parent/child links use `System.LinkTypes.Hierarchy-Reverse` on the child; auth is Basic with empty username.
- **D-11:** The lead does not yet have a real ADO org/project/PAT/identity ready. The plan MUST call this out as a precondition to provision before `push_to_ado` and its verification can run. Needs: an ADO org + project, a PAT with work-item write scope, and the lead's own ADO account email for self-assign.
- **D-12:** Script A (create + self-assign one ADO work item via the PAT as a standalone script) must run and pass against the real ADO target before its logic is wired into `push_to_ado`. Script B (LLM → plan JSON) is NOT relevant to Phase 1.

### Claude's Discretion

- Exact FastAPI route shapes, run-metadata storage details, poll interval, and file/module layout — follow `.planning/research/ARCHITECTURE.md` "Recommended Project Structure".
- Whether run metadata lives in the same SQLite file as the checkpointer or a separate table.

### Deferred Ideas (OUT OF SCOPE)

- Greenfield/brownfield branch node — deferred to Phase 2 (D-01/D-02); Phase 1 spine is straight-line.
- Real config + team roster intake forms — Phase 2.
- SSE streaming for run status — Phase 1 uses polling; SSE is a post-MVP / larger-scale option.
- Mixed / multi-identity assignees in the plan — Phase 1 self-assigns only.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ORCH-01 | The greenfield/brownfield branch and human review/edit loop are orchestrated with LangGraph using interrupt-and-resume | Partially addressed (per D-02): "Pattern 2: `interrupt()` inside `human_review`" section below implements the interrupt-and-resume half fully; branch node explicitly out of scope this phase |
| ORCH-02 | Run state is checkpointed durably so an in-progress plan survives a backend restart | "AsyncSqliteSaver Wiring" section — file-backed checkpointer opened via FastAPI lifespan, `.setup()` called once, restart-survival verification procedure included |
| PUSH-01 | On approval, tool pushes tasks into ADO as real work items assigned to the correct people (one-way) | "ADO REST Call Reference" section — exact create-work-item calls with `System.AssignedTo` patch op |
| PUSH-02 | Pushed work items preserve epic → task hierarchy (parent/child links) | "ADO REST Call Reference" — `System.LinkTypes.Hierarchy-Reverse` on the child, with worked example and the exact direction gotcha called out |
| PUSH-03 | Tool verifies each pushed work item was created and assigned correctly | "Read-Back Verification Pattern" section — GET-after-write pattern with field-by-field checks and the partial-success report shape |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langgraph` | 1.2.8 | StateGraph, `interrupt()`, `Command(resume=...)` | Already locked project-wide; verified current on PyPI at research time [VERIFIED: PyPI registry] |
| `langgraph-checkpoint-sqlite` | 3.1.0 | Provides `AsyncSqliteSaver` (async) and `SqliteSaver` (sync) | This phase's D-04 override — mandatory file-backed checkpointer. Verified current on PyPI; `requires_dist` confirms `aiosqlite>=0.20` and `langgraph-checkpoint<5.0.0,>=4.1.0` [VERIFIED: PyPI registry] |
| `aiosqlite` | ≥0.20 (pulled transitively) | Async SQLite driver `AsyncSqliteSaver` wraps | Required dependency of `langgraph-checkpoint-sqlite`; do not pin separately, let the checkpointer package resolve it [VERIFIED: PyPI registry — declared dependency] |
| `fastapi` | 0.139.0 (`fastapi[standard]`) | HTTP API layer, async lifespan for checkpointer lifecycle | Already locked; async-native, required for correct `AsyncSqliteSaver` lifespan wiring [VERIFIED: PyPI registry] |
| `httpx` | 0.28.1 | ADO REST calls | Already locked; async-native, matches FastAPI/LangGraph async node style [VERIFIED: PyPI registry] |
| `pydantic` | 2.13.4 | Stub plan schema (D-06), FastAPI request/response models | Already locked; Pydantic v2 required by current FastAPI [VERIFIED: PyPI registry] |
| `python-dotenv` | 1.2.2 | Load `ADO_ORG`, `ADO_PROJECT`, `ADO_PAT` from `.env` | Already locked; simplest secrets handling for no-auth local MVP [VERIFIED: PyPI registry] |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `react` | 19.2.7 | Minimal Start/status/Approve page (D-07) | Frontend UI shell only; no plan editing in this phase |
| `react-dom` | 19.2.7 | React DOM renderer | Paired with `react` |
| `@tanstack/react-query` | 5.101.2 | Poll `GET /runs/{id}` on an interval | Handles the poll/refetch pattern with minimal hand-rolled `useEffect` code |
| `vite` | 8.1.4 | Dev server / build | Standard 2026 React scaffold, already locked project-wide |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `AsyncSqliteSaver` (async) | `SqliteSaver` (sync) | Sync `SqliteSaver` works but forces sync calls inside FastAPI's async handlers (blocking the event loop unless wrapped in a threadpool) — `AsyncSqliteSaver` is the correct choice given FastAPI's async-native routes per CONTEXT.md D-04 |
| Direct ADO REST via `httpx` | `azure-devops` SDK (`azure-devops-python-api` 7.1.0b4) | SDK is stale (no release since Nov 2023), still beta, targets an older api-version. Direct REST stays the default per CLAUDE.md/STACK.md — do not introduce the SDK in Phase 1 |
| Polling (`@tanstack/react-query` refetchInterval) | SSE (`GET /runs/{id}/stream`) | SSE deferred per D-07/D-08 and Deferred Ideas — do not build in Phase 1 |

**Installation:**
```bash
# Backend (Python 3.12+, venv)
pip install "fastapi[standard]==0.139.0" langgraph==1.2.8 langgraph-checkpoint-sqlite==3.1.0 \
  httpx==0.28.1 pydantic==2.13.4 python-dotenv==1.2.2

# Frontend
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install @tanstack/react-query@5.101.2
```

**Version verification:** All backend package versions above were re-confirmed live against the PyPI JSON API on 2026-07-09 (same day as this research), matching the versions already locked in CLAUDE.md's Technology Stack section — no drift detected since that research was written. `langgraph-checkpoint-sqlite`'s `requires_dist` was inspected directly and confirms the `aiosqlite>=0.20` dependency this phase relies on.

## Package Legitimacy Audit

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| `aiosqlite` | pypi | OK | Approved |
| `langgraph-checkpoint-sqlite` | pypi | OK | Approved |
| `httpx` | pypi | OK | Approved |
| `fastapi` | pypi | OK | Approved |
| `langgraph` | pypi | OK | Approved |
| `pydantic` | pypi | OK | Approved |
| `python-dotenv` | pypi | OK — flagged `HALLUCINATION_PATTERN` (info-level only: "name starts with `python-`, classic LLM naming pattern, but package is established") | Approved — info flag is a known false-positive pattern for this specific well-established package, not a suspicion signal |
| `react` | npm | OK | Approved |
| `react-dom` | npm | OK | Approved |
| `@tanstack/react-query` | npm | OK | Approved |
| `vite` | npm | OK | Approved |

**Packages removed due to slopcheck `[SLOP]` verdict:** none
**Packages flagged as suspicious `[SUS]`:** none

All packages listed above were already present in the project's committed STACK.md/CLAUDE.md research and are re-verified here specifically for Phase 1's scope (no net-new packages introduced beyond `aiosqlite`, which is a transitive dependency, not a direct install).

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  React (minimal page)                                            │
│  [Start] → POST /runs                                            │
│  (poll every N sec) → GET /runs/{id}  → render status + stub plan│
│  [Approve] → POST /runs/{id}/resume                              │
└──────────────────────────┬────────────────────────────────────────┘
                            │ HTTP/JSON
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI (single process, single event loop)                     │
│  app.state.graph = compiled StateGraph (built once at startup)   │
│  app.state.checkpointer = AsyncSqliteSaver (opened in lifespan)  │
│                                                                    │
│  POST /runs           → create run_id, thread_id=run_id,         │
│                          graph.ainvoke(initial_state, config)     │
│                          runs until interrupt() halts execution   │
│  GET /runs/{id}        → graph.aget_state(config) → status +     │
│                          stub plan (from state, not re-run)       │
│  POST /runs/{id}/resume → graph.ainvoke(Command(resume=...),      │
│                          config) → unblocks human_review,         │
│                          proceeds to push_to_ado                  │
└──────────────────────────┬────────────────────────────────────────┘
                            │ in-process node calls
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  LangGraph nodes (thin functions)                                 │
│  ingest_config → stub_plan → human_review(interrupt) → push_to_ado│
│       │              │              │                    │       │
│       │              │              │                    ▼       │
│       │              │              │            services/ado_client
│       │              │              │            (httpx, json-patch,│
│       │              │              │             read-back verify) │
│       ▼              ▼              ▼                    ▼        │
│  RunState (Pydantic/TypedDict, checkpointed to SQLite each step)  │
└──────────────────────────┬────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  SQLite file (checkpoints.db) — durable, survives process restart │
│  Azure DevOps (real org/project, via PAT) — external service      │
└─────────────────────────────────────────────────────────────────┘
```

A reader can trace the primary use case: Start (POST /runs) → graph runs `ingest_config`→`stub_plan`→pauses at `human_review`'s `interrupt()` → checkpoint written to SQLite → FastAPI returns "awaiting_review" status on the next poll → Approve (POST /runs/{id}/resume) → `human_review` node re-executes from its top (reads state, receives resume value, returns) → graph proceeds to `push_to_ado` → real ADO REST calls with read-back verification → structured partial-success report returned.

### Recommended Project Structure

Per CONTEXT.md's discretion note, follow `.planning/research/ARCHITECTURE.md`'s structure, scoped down to only what Phase 1 needs:

```
backend/
├── app/
│   ├── main.py                    # FastAPI app; lifespan opens AsyncSqliteSaver, compiles graph, stores in app.state
│   ├── routers/
│   │   └── runs.py                # POST /runs, GET /runs/{id}, POST /runs/{id}/resume
│   ├── graph/
│   │   ├── state.py                # RunState TypedDict: config, plan, approved, push_report
│   │   ├── build.py                # StateGraph construction (no compile — compile happens in lifespan with the checkpointer)
│   │   └── nodes/
│   │       ├── ingest_config.py    # reads hardcoded/stub config into state (Phase 1: trivial passthrough)
│   │       ├── stub_plan.py        # builds the hardcoded Plan Pydantic instance (D-05/D-06)
│   │       ├── human_review.py     # interrupt() ONLY — read state, pause, merge resume payload
│   │       └── push_to_ado.py      # gated by state["approved"]; calls services/ado_client; runs once
│   ├── services/
│   │   └── ado_client.py           # create_work_item, link_parent_child, verify_assignment (httpx)
│   ├── models/
│   │   └── plan.py                 # Pydantic: Epic, Task, Plan — the shared source-of-truth shape (D-06)
│   └── db/
│       └── run_metadata.py         # run_id -> status/timestamps table (SQLite; same or separate file — discretion)
frontend/
├── src/
│   ├── pages/
│   │   └── RunPage.tsx             # Start button, polling status, stub plan render, Approve button
│   └── lib/
│       └── runClient.ts            # fetch wrappers: startRun(), getRun(id), approveRun(id)
```

### Pattern 1: `AsyncSqliteSaver` opened once in FastAPI's lifespan, never per-request

**What:** The checkpointer's underlying `aiosqlite` connection must be opened exactly once for the life of the process and shared across every request — not opened/closed inside each route handler. This is the single most common wiring mistake reported for this integration.

**When to use:** Always, for this phase. This is the load-bearing pattern that makes ORCH-02 (survive backend restart) actually true: the SQLite *file* is what survives the restart; the open connection inside the running process is what must be correctly scoped to avoid "database is locked" or dangling-connection errors.

**Example:**
```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from app.graph.build import build_graph

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        await checkpointer.setup()  # creates schema tables if not present; idempotent, safe to call on every startup
        graph = build_graph().compile(checkpointer=checkpointer)
        app.state.graph = graph
        yield
    # connection closed automatically on app shutdown when the `async with` block exits

app = FastAPI(lifespan=lifespan)
```

**Source:** [reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver) — official LangChain reference docs, confirms `from_conn_string` factory usage as an async context manager and that `.setup()` initializes the schema. **MEDIUM confidence on the exact `.setup()` call signature** — the reference page does not show its full parameter list; verify against the installed `langgraph-checkpoint-sqlite==3.1.0` package at implementation time (`python -c "from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver; help(AsyncSqliteSaver.setup)"`).

**Trade-off called out by the docs:** `AsyncSqliteSaver` includes a `lock` property (built-in synchronization), but the official docs explicitly warn it is "not recommended for production workloads due to limitations in SQLite's write performance" — irrelevant risk for this single-lead local MVP, but do not carry this pattern forward if the project ever needs concurrent multi-run writes.

### Pattern 2: `interrupt()` inside `human_review`, resumed via `Command(resume=...)` — and the node RE-EXECUTES FROM THE TOP on resume

**What:** `human_review`'s entire body is: read whatever `stub_plan` already wrote into state, call `interrupt(payload)`, and on resume return a dict merging the resume value. LangGraph's documented behavior: "Whenever execution resumes, it starts at the beginning of the node" — not from the `interrupt()` line. Any code placed before the `interrupt()` call inside this node runs again every time this node resumes.

**When to use:** This is D-03's exact requirement. Do not deviate — do not add plan mutation, ADO calls, or any state-writing side effect before or after the `interrupt()` call inside this node.

**Example:**
```python
# app/graph/nodes/human_review.py
from langgraph.types import interrupt

def human_review(state: RunState) -> dict:
    # This entire function body re-runs from here on every resume.
    # No side effects. No re-computation of plan. Read-only + pause.
    decision = interrupt({
        "plan": state["plan"],   # already computed by stub_plan, just displayed
    })
    return {"approved": decision.get("approved", False)}
```

```python
# app/routers/runs.py — FastAPI side
from langgraph.types import Command

@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str, body: ResumeRequest, request: Request):
    config = {"configurable": {"thread_id": run_id}}
    graph = request.app.state.graph
    # This call re-executes human_review from its top, then proceeds to push_to_ado
    result = await graph.ainvoke(Command(resume={"approved": body.approved}), config)
    return result
```

**Source:** [docs.langchain.com/oss/python/langgraph/interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) (official LangChain docs, HIGH confidence) — confirms `interrupt()` requires a checkpointer + stable `thread_id`, and that resume restarts the node from its beginning. Cross-referenced against `.planning/research/PITFALLS.md` Pitfall 1 and `.planning/research/ARCHITECTURE.md` Pattern 2, both already HIGH confidence via the same official source.

### Pattern 3: `push_to_ado` gated so it runs exactly once, after resume

**What:** `push_to_ado` is a separate node from `human_review`, so it only executes as part of the graph's forward progress after `Command(resume=...)` unblocks `human_review`. It is not itself interrupted, so it does NOT re-execute on a second resume call — but the plan MUST still design for "what if the lead double-clicks Approve" as a defensive measure, since a second `POST /runs/{id}/resume` on an already-completed thread is a realistic operator error, not a LangGraph replay artifact.

**When to use:** Always for this node. The state should carry a `pushed: bool` (or equivalent) flag; `push_to_ado` should check it first and short-circuit (return the prior report) if already true, rather than re-push.

**Example:**
```python
# app/graph/nodes/push_to_ado.py
async def push_to_ado(state: RunState) -> dict:
    if state.get("pushed"):
        return {}  # idempotent no-op if somehow re-entered
    if not state.get("approved"):
        return {"push_report": {"status": "skipped", "reason": "not approved"}}

    report = await ado_client.push_plan(state["plan"])  # partial-success report, D-09
    return {"pushed": True, "push_report": report}
```

**Source:** Derived directly from CONTEXT.md D-03/D-09 and `.planning/research/PITFALLS.md` Pitfall 1's explicit recommendation ("check a state flag like `pushed: bool` before writing").

### Anti-Patterns to Avoid

- **Compiling the graph fresh with a new checkpointer per request:** Destroys durability — a new `AsyncSqliteSaver.from_conn_string(...)` call per request either fails to see prior checkpoints (if pointed at a fresh in-memory `:memory:` string by mistake) or thrashes the file lock. Compile once at startup, store on `app.state`.
- **Any code — including "just reading a value for logging" — placed before `interrupt()` that has an observable side effect (network call, file write, log line intended to fire once):** Will fire again on every resume of that node. Keep it to variable reads from `state`.
- **Trusting HTTP 200/201 from ADO as proof of correct assignment:** ADO resolves `System.AssignedTo` server-side and can silently leave it blank. Always read back (Pattern in "Read-Back Verification" below).
- **Using `SqliteSaver` (sync) inside an `async def` FastAPI route without wrapping it in a threadpool:** Blocks the event loop. Use `AsyncSqliteSaver` per D-04, which has native async methods (`aget_state`, `aget_tuple`, etc.) matching FastAPI's `async def` routes and `graph.ainvoke`/`graph.astream`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Run/review version history | A custom "plan versions" table | LangGraph checkpoint history (`graph.aget_state_history(config)`) | CLAUDE.md explicitly states: "`interrupt()` and the checkpointer are how plan review/editing and version history work — don't build a separate versioning table; read it from graph checkpoints." |
| Pause/resume signaling between FastAPI and the graph | A custom `status` polling flag stored outside the graph, hand-synced with graph progress | `graph.aget_state(config).next` (empty tuple = graph finished/at interrupt boundary; check `tasks` for pending interrupt) as the single source of truth for "is this run paused" | LangGraph's `StateSnapshot` already encodes this; a parallel hand-rolled status field risks drifting out of sync with actual graph state (this is exactly Pitfall 3's failure mode in `.planning/research/PITFALLS.md`) |
| JSON-Patch document construction for ADO | Raw dict literals scattered across call sites | A small typed `build_patch(op, path, value)` helper + `link_child_to_parent(child_id, parent_id)` helper, used everywhere | `.planning/research/PITFALLS.md` Pitfall 4 explicitly recommends this — reduces the "wrong path string" and "wrong hierarchy direction" error classes to one tested location |

**Key insight:** Both LangGraph and the ADO REST API already expose the exact durability/history/patch primitives this phase needs. The temptation in a 2-day MVP is to hand-roll a simpler-looking parallel mechanism (a status table, a bespoke patch builder per call site) — resist it; the built-in primitives are not meaningfully more code to wire up correctly, and the hand-rolled versions are precisely where the pitfalls documented for this project originate.

## Stub Plan Schema (D-06)

`project-spec.md` is referenced throughout CLAUDE.md as the canonical source of the plan JSON schema but **is not present in this repository** (confirmed via direct filesystem check — only `CLAUDE.md`, `.planning/`, `.git/` exist at the repo root). This is a gap CONTEXT.md already flagged under "Canonical References." Since the authoritative shape cannot be read, this research proposes a minimal, CLAUDE.md-consistent shape for the planner to use as the Phase 1 stub — the planner/lead should confirm or obtain `project-spec.md` before Phase 2, since later phases depend on this shape being final.

```python
# app/models/plan.py — the ONE shared shape, imported by both graph nodes and API responses (CLAUDE.md file/folder rule)
from pydantic import BaseModel
from typing import Literal

class Task(BaseModel):
    id: str                     # stable id, e.g. "task-1"
    title: str
    description: str
    suggested_assignee: str     # email/UPN string; ADO resolves it server-side
    estimate_hours: float
    skill_tag: str | None = None      # Phase 1: unused/None; Phase 2+ populates from taxonomy
    depends_on: list[str] = []        # display-only per CLAUDE.md scope discipline; no enforcement

class Epic(BaseModel):
    id: str                     # e.g. "epic-1"
    title: str
    description: str
    tasks: list[Task]

class Plan(BaseModel):
    epics: list[Epic]

class PushResultItem(BaseModel):
    item_id: str                        # local plan id (epic-1, task-1, ...)
    ado_work_item_id: int | None = None
    status: Literal["created", "assignment_unresolved", "create_failed", "link_failed"]
    detail: str | None = None

class PushReport(BaseModel):
    items: list[PushResultItem]
    all_succeeded: bool
```

**D-05 stub instance shape** (1 epic, 2–3 tasks, all self-assigned):
```python
def build_stub_plan(lead_email: str) -> Plan:
    return Plan(epics=[
        Epic(id="epic-1", title="Stub Epic: Scaffolding Slice", description="Hardcoded epic for Phase 1 pipeline proof.",
             tasks=[
                 Task(id="task-1", title="Stub Task 1", description="...", suggested_assignee=lead_email, estimate_hours=4),
                 Task(id="task-2", title="Stub Task 2", description="...", suggested_assignee=lead_email, estimate_hours=6),
                 Task(id="task-3", title="Stub Task 3", description="...", suggested_assignee=lead_email, estimate_hours=2),
             ])
    ])
```

This shape is a **proposal**, not a verified fact — see Assumptions Log.

## ADO REST Call Reference

All calls target `api-version=7.1` (confirmed current/supported per official Microsoft Learn docs; `azure-devops` SDK lags at an older effective version — this is why CLAUDE.md/STACK.md mandate direct REST). Auth header for every call: `Authorization: Basic {base64(":" + ADO_PAT)}` (empty username, per CLAUDE.md gotcha — confirmed pattern, standard Basic-auth-with-PAT-as-password convention for ADO).

### 1. Create the epic (parent)
```http
POST https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/$Epic?api-version=7.1
Content-Type: application/json-patch+json
Authorization: Basic {base64(":" + PAT)}

[
  {"op": "add", "path": "/fields/System.Title", "value": "Stub Epic: Scaffolding Slice"},
  {"op": "add", "path": "/fields/System.Description", "value": "Hardcoded epic for Phase 1 pipeline proof."}
]
```
Response `200 OK` includes `id` (the ADO work item id) — capture this for linking children.

### 2. Create each task (child), with title/estimate/assignee, THEN link to the epic
Two options: (a) create the task first, then a follow-up PATCH to add the relation + assignee; (b) include the relation add-op in the same create call if the parent id is already known (it is, since the epic is created first per Pitfall 4's guidance). Option (b) is fewer calls:

```http
POST https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/$Task?api-version=7.1
Content-Type: application/json-patch+json
Authorization: Basic {base64(":" + PAT)}

[
  {"op": "add", "path": "/fields/System.Title", "value": "Stub Task 1"},
  {"op": "add", "path": "/fields/System.Description", "value": "..."},
  {"op": "add", "path": "/fields/System.AssignedTo", "value": "lead@company.com"},
  {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate", "value": 4},
  {
    "op": "add",
    "path": "/relations/-",
    "value": {
      "rel": "System.LinkTypes.Hierarchy-Reverse",
      "url": "https://dev.azure.com/{organization}/{project}/_apis/wit/workItems/{epicId}",
      "attributes": {"comment": "linking to parent epic"}
    }
  }
]
```

**Direction gotcha (confirmed via multiple sources):** `System.LinkTypes.Hierarchy-Reverse` on the **child** (task) points **up** to the parent (epic) — "Reverse" refers to the direction relative to the natural parent→child hierarchy, not an intuitive label. `System.LinkTypes.Hierarchy-Forward` would go on the epic pointing down to children (not needed here since ADO auto-derives the forward view once the reverse relation exists on the child).

**Estimate field caveat:** `Microsoft.VSTS.Scheduling.OriginalEstimate` is the Agile-process-template field name. If the target ADO project uses Scrum or CMMI, the reference name differs — confirm the target project's process template before hardcoding this field name (per `.planning/research/PITFALLS.md` Pitfall 4/Technical Debt table).

### 3. Read back to verify (PUSH-03, D-10) — MUST happen after every write
```http
GET https://dev.azure.com/{organization}/{project}/_apis/wit/workitems/{id}?$expand=relations&api-version=7.1
Authorization: Basic {base64(":" + PAT)}
```

Check in the response:
- `fields["System.AssignedTo"]["uniqueName"]` (or `.uniqueName`/`.displayName`, depending on identity resolution) equals the expected email — if the field is absent/null, assignment did not resolve; record `assignment_unresolved` per D-09's partial-success shape.
- `relations` array contains an entry with `rel == "System.LinkTypes.Hierarchy-Reverse"` and `url` ending in `/workItems/{epicId}` — if missing, record `link_failed`.

**Response format gotcha (from PITFALLS.md, corroborated by the official docs' auth/security section):** always check `Content-Type` on the response before parsing as JSON — an expired/invalid PAT can return a 203 with an HTML login page body rather than a clean 401, which throws a confusing JSON-decode exception if parsed blindly.

**Sources for this section:**
- [learn.microsoft.com/.../wit/work-items/create](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create?view=azure-devops-rest-7.1) — HIGH confidence, official Microsoft Learn docs, fetched directly this session; confirmed endpoint URL, api-version, json-patch body shape, and sample response.
- [learn.microsoft.com/.../wit/work-items/get-work-item](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-item?view=azure-devops-rest-7.1) — HIGH confidence, official docs, fetched directly this session; confirmed GET endpoint, `$expand=relations` param, and that `fields.System.AssignedTo` is an identity object (not a bare string) in responses.
- [learn.microsoft.com/.../wit/work-items/update](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1) — HIGH confidence, official docs, fetched directly this session; confirmed PATCH endpoint shares the same json-patch array body shape as create, usable for follow-up field/relation updates if not done in the initial create call.
- WebSearch cross-referencing multiple sources (Merkle/Medium engineering blog, GitHub issue threads on `azure-devops-mcp`) for the exact `/relations/-` add-relation JSON-Patch shape — MEDIUM confidence (community-sourced but internally consistent across all sources found, and consistent with the official docs' `WorkItemRelation` schema definition of `{rel, url, attributes}`).
- `.planning/research/PITFALLS.md` Pitfall 4/5 and `.planning/research/ARCHITECTURE.md` — already HIGH-confidence project research reused directly.

## Common Pitfalls

(All pitfalls below are drawn from `.planning/research/PITFALLS.md`, filtered to what bears directly on Phase 1's scope, with Phase-1-specific detail added.)

### Pitfall 1: Node replay-on-resume double-fires side effects
**What goes wrong:** Any side effect placed in the same node as `interrupt()` re-executes on every resume — most dangerously, an ADO push placed before/alongside the interrupt call.
**Why it happens:** LangGraph resumes a node from its top, not from the `interrupt()` line — documented, expected behavior.
**How to avoid:** `human_review` (Pattern 2 above) contains ONLY the interrupt call and a read of already-computed state; `push_to_ado` is a separate node that only runs after resume unblocks the graph, gated with a `pushed` flag.
**Warning signs:** Duplicate ADO work items after a single Approve click; test this deliberately by calling `POST /runs/{id}/resume` twice on the same completed thread and confirming no new work items appear the second time.

### Pitfall 2: Wrong checkpointer choice loses in-progress runs on restart
**What goes wrong:** `MemorySaver`/`InMemorySaver` (the CLAUDE.md stack-table default, explicitly overridden by D-04) wipes all thread state on any process restart — including `uvicorn --reload` picking up a file save during active development.
**How to avoid:** `AsyncSqliteSaver` from the first commit (Pattern 1 above); never even temporarily use `MemorySaver`.
**Warning signs:** "My in-progress run disappeared after the dev server hot-reloaded." Verify by deliberately restarting the backend process mid-review (after Start, before Approve) and confirming `GET /runs/{id}` still returns "awaiting_review" with the stub plan intact.

### Pitfall 3: Interrupt/poll race — Approve fires before client confirms paused state
**What goes wrong:** If the frontend enables the Approve button as soon as it sees *any* non-"running" status, without confirming the thread is genuinely paused at the interrupt, a race is possible.
**How to avoid:** Poll `GET /runs/{id}` and only enable Approve when the response explicitly reports `status == "awaiting_review"` (derived from `graph.aget_state(config)` showing a pending interrupt task) — not merely "not running."
**Warning signs:** Approve click does nothing, or the UI shows the plan before the backend has actually reached the interrupt.

### Pitfall 4: JSON-Patch content-type/shape errors and hierarchy direction confusion
**What goes wrong:** Sending `application/json` instead of `application/json-patch+json`; sending a flat object instead of an array; using display names (`"Title"`) instead of reference names (`System.Title`); reversing the Hierarchy-Forward/Reverse direction.
**How to avoid:** Use the exact request shapes in "ADO REST Call Reference" above; build one small typed helper for patch-op construction and one for the relation-add op; write one test that creates an epic + task and confirms the read-back shows the correct parent/child relation.
**Warning signs:** HTTP 400 with a vague "value is not valid" message; work items created but not nested under the epic in ADO Boards.

### Pitfall 5: Assignment resolves silently to blank
**What goes wrong:** `System.AssignedTo` accepts an email string but ADO resolves identity server-side; if the email doesn't exactly match an org member, the work item still saves (200/201) with assignment blank.
**How to avoid:** The read-back verification pattern (D-10) is mandatory, not optional — this is precisely PUSH-03's requirement. Also: the lead's own ADO account email (used for self-assign per D-05) must actually exist in the target ADO org — this is a precondition, not something code can fix (see D-11).
**Warning signs:** Work item pushed successfully but shows "Unassigned" in ADO Boards.

### Pitfall 6 (Phase-1-specific, not in general PITFALLS.md): Precondition gap — no real ADO target exists yet
**What goes wrong:** D-11 states the lead does not yet have a real ADO org/project/PAT/identity. If planning proceeds as though these exist, the first attempt to run Script A or `push_to_ado` will fail on missing credentials, not on code defects — wasting debugging time on a non-code problem.
**How to avoid:** Treat "provision ADO org + project + PAT (Work Items Read & Write scope) + confirm lead's own account email resolves as an org member" as an explicit, first-class checkpoint task in the plan, sequenced before any `push_to_ado` implementation task. Script A (D-12) is the concrete verification gate: it must run and pass against the *real* target before its logic is wired into `push_to_ado`.
**Warning signs:** Planning or building `push_to_ado` before this precondition is confirmed provisioned.

## Code Examples

### Verifying `AsyncSqliteSaver` survives a restart (manual test procedure for ORCH-02 / success criterion #2)
```bash
# 1. Start the backend
uvicorn app.main:app

# 2. Start a run and let it reach the interrupt
curl -X POST http://localhost:8000/runs
# note the returned run_id

curl http://localhost:8000/runs/{run_id}
# confirm status == "awaiting_review"

# 3. Kill the backend process (simulate restart) — Ctrl+C or `kill`
# 4. Restart it
uvicorn app.main:app

# 5. Query the SAME run_id again — must still show "awaiting_review" with the stub plan,
#    proving the checkpoint survived the restart (not just held in RAM)
curl http://localhost:8000/runs/{run_id}

# 6. Approve — must proceed to push_to_ado correctly, proving resume works post-restart
curl -X POST http://localhost:8000/runs/{run_id}/resume -d '{"approved": true}'
```

### Verifying no double-fire on double-resume (Pitfall 1 test)
```bash
# After the above Approve call succeeds and work items are created in ADO,
# call resume AGAIN on the same run_id:
curl -X POST http://localhost:8000/runs/{run_id}/resume -d '{"approved": true}'
# Expected: no new work items created in ADO (check via ADO Boards or a follow-up GET);
# the `pushed` flag gate (Pattern 3) should short-circuit this second call.
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `SqliteSaver` (sync) as the "durable" checkpointer default in older LangGraph tutorials | `AsyncSqliteSaver` for async frameworks (FastAPI) | Ongoing LangGraph ecosystem convention as of `langgraph-checkpoint-sqlite` 3.x | Sync `SqliteSaver` inside an `async def` FastAPI route blocks the event loop unless explicitly offloaded; `AsyncSqliteSaver`'s native async methods avoid this entirely |
| ADO REST api-version 7.0/6.x in older sample code | api-version 7.1 (current stable, 7.2 also available) | Ongoing Azure DevOps REST API versioning | This phase pins to 7.1 per CLAUDE.md/STACK.md — verified still fully supported at research time |

**Deprecated/outdated:**
- `MemorySaver`/`InMemorySaver` as a "good enough" checkpointer for any workflow with a human-review pause of non-trivial duration — explicitly rejected by D-04 for this phase.
- `azure-devops` Python SDK (`azure-devops-python-api`) as the primary ADO integration path — stale since Nov 2023, superseded project-wide by direct `httpx` REST calls (already locked in STACK.md, reaffirmed here).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The proposed `Plan`/`Epic`/`Task` Pydantic shape (Stub Plan Schema section) matches what `project-spec.md` actually specifies | Stub Plan Schema | `project-spec.md` is referenced everywhere in CLAUDE.md as the canonical source but is **not present in the repo** (confirmed via filesystem check). If the real spec differs materially (e.g., different field names, nested risk/assignment sub-objects expected even in v1), Phase 2+ nodes built against this Phase 1 stub shape will need rework. Obtain or write `project-spec.md` before or during Phase 1 planning, and treat this schema as provisional until then. |
| A2 | `.setup()` on `AsyncSqliteSaver` takes no required arguments and is safe to call on every app startup (idempotent) | Pattern 1 (AsyncSqliteSaver lifespan wiring) | The official reference page does not show the full method signature/behavior in detail. If `.setup()` is not idempotent or requires different handling, startup could fail or duplicate schema objects on repeated restarts — verify directly against the installed `langgraph-checkpoint-sqlite==3.1.0` package (`help(AsyncSqliteSaver.setup)`) before relying on this in a task. |
| A3 | The `/relations/-` add-relation JSON-Patch shape (`{"op": "add", "path": "/relations/-", "value": {"rel": ..., "url": ..., "attributes": {...}}}`) is exactly correct as shown | ADO REST Call Reference, step 2 | Sourced from WebSearch cross-referencing a practitioner blog and a GitHub issue thread, not the official Microsoft Learn `WorkItemRelation` schema page directly (which defines the fields but doesn't show a full worked JSON-Patch example for adding one). The shape is consistent with the official `WorkItemRelation{rel, url, attributes}` object definition, so risk is LOW, but confirm with Script A / a real test call before trusting it in `push_to_ado`. |
| A4 | The frontend should use React (not Next.js) for this phase | Standard Stack, Recommended Project Structure | CLAUDE.md's top-level "Stack" section says "Frontend: Next.js," but CLAUDE.md's later "Technology Stack" (research) section and CONTEXT.md D-07 both say "React"/"React page." This research follows CONTEXT.md D-07 (the more recent, phase-specific locked decision) and the research-derived stack table, since CONTEXT.md explicitly says "minimal React page." Flag this contradiction for the lead to resolve in CLAUDE.md itself — it will resurface in every later frontend phase if left unresolved. |
| A5 | CLAUDE.md's top "Stack" section also says "LLM: Anthropic API," while the later Technology Stack section says GLM via NVIDIA NIM | (context only — not used in Phase 1, no LLM calls this phase) | Does not affect Phase 1 (no LLM call in this phase per CONTEXT.md), but will need resolving before Phase 2's `generate_plan` node. Noting here so it isn't lost. |

## Open Questions (RESOLVED — none blocking Phase 1)

> Both questions below are non-blocking for Phase 1 and are deferred to Phase 2, as annotated in each recommendation. Phase 1 proceeds using this research's proposed Plan schema (A1) and React per D-07.

1. **Where does `project-spec.md` live, and can it be obtained/written before Phase 1 execution starts?** — RESOLVED (not blocking Phase 1; use proposed schema A1 now, revisit in Phase 2).
   - What we know: CLAUDE.md references it extensively as the canonical plan-schema and LangGraph-pipeline source; CONTEXT.md's canonical_refs section already flags it as "not yet present in the repo."
   - What's unclear: Whether this is an oversight (file should exist and was never committed) or whether the project intends to derive it iteratively during Phase 1.
   - Recommendation: Planner should either (a) treat this research's proposed Plan schema (A1) as the working Phase 1 answer and flag schema stability as a risk for Phase 2, or (b) insert an early plan task to write/obtain `project-spec.md` before the `models/plan.py` implementation task, if time allows within the 2-day budget.

2. **CLAUDE.md's frontend/LLM stack contradiction (A4/A5) — does it need a standing correction?** — RESOLVED (not blocking Phase 1; React per D-07, no LLM this phase; lead to reconcile CLAUDE.md before Phase 2).
   - What we know: Two sections of CLAUDE.md disagree with each other and with CONTEXT.md's locked decisions.
   - What's unclear: Whether this is a stale first-draft section that should be edited, or intentional (e.g., "Stack" section describes an original intent, "Technology Stack" section describes the actual researched/adopted choice).
   - Recommendation: Not a Phase 1 blocker (Phase 1 uses React per D-07, no LLM at all), but the lead should resolve this in CLAUDE.md directly before Phase 2 begins, since Phase 2 is where `generate_plan` (LLM) and the fuller frontend actually get built.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | Backend runtime | Not verified in this session (no interpreter probe run against the target dev machine) | — | Confirm locally before starting; Python 3.10+ is the LangGraph/FastAPI floor per STACK.md, 3.12 is the recommended target |
| Real Azure DevOps org/project + PAT | `push_to_ado`, Script A, PUSH-01/02/03 | ✗ (explicitly confirmed absent per D-11) | — | None — this is a hard blocker for the ADO half of Phase 1 until provisioned. Must be provisioned before any ADO-touching task executes. |
| Lead's own ADO account email (org member) | Self-assignment (D-05), assignment verification (D-10) | ✗ (depends on the above being provisioned first) | — | None — required precondition, not a code fallback |
| Node.js + npm (for Vite/React frontend) | Frontend scaffold (D-07) | Not verified in this session | — | Confirm locally before starting |

**Missing dependencies with no fallback:**
- Real ADO org + project + PAT with Work Items Read & Write scope, and the lead's own account confirmed as an org member — this blocks PUSH-01/02/03 and Script A entirely until provisioned. This is D-11's precondition; surface it as an explicit early task/checkpoint in the plan, not something discovered mid-implementation.

**Missing dependencies with fallback:**
- None identified — the LangGraph/FastAPI/SQLite half of this phase has no external service dependency (SQLite is a local file, no separate service to provision).

## Sources

### Primary (HIGH confidence)
- [reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver](https://reference.langchain.com/python/langgraph.checkpoint.sqlite/aio/AsyncSqliteSaver) — official LangChain reference; `from_conn_string`, `.setup()`, context-manager lifecycle, production-workload warning, `lock` property
- [docs.langchain.com/oss/python/langgraph/interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) — official docs; `interrupt()` semantics, node-restarts-from-top-on-resume behavior, `Command(resume=...)`, checkpointer requirement
- [learn.microsoft.com/.../wit/work-items/create?view=azure-devops-rest-7.1](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create?view=azure-devops-rest-7.1) — official Microsoft Learn; create endpoint, api-version, json-patch+json body, sample response
- [learn.microsoft.com/.../wit/work-items/get-work-item?view=azure-devops-rest-7.1](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/get-work-item?view=azure-devops-rest-7.1) — official docs; GET endpoint, `$expand=relations`, `fields.System.AssignedTo` identity object shape
- [learn.microsoft.com/.../wit/work-items/update?view=azure-devops-rest-7.1](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1) — official docs; PATCH endpoint, same json-patch body shape as create
- PyPI JSON API — direct re-verification this session of `langgraph`, `langgraph-checkpoint-sqlite`, `fastapi`, `httpx`, `pydantic` current versions, all matching CLAUDE.md's existing STACK.md research
- `slopcheck scan` — direct this-session verification of all Phase 1 packages (`aiosqlite`, `langgraph-checkpoint-sqlite`, `httpx`, `fastapi`, `langgraph`, `pydantic`, `python-dotenv`, `azure-devops`, `PyGithub`, `GitPython`, `react`, `react-dom`, `@tanstack/react-query`, `vite`, `typescript`) — all `OK`, no `SLOP`/`SUS` flags except one info-level false-positive on `python-dotenv`'s name pattern

### Secondary (MEDIUM confidence)
- WebSearch cross-referencing Merkle/Medium engineering blog + GitHub `azure-devops-mcp` issue thread — `/relations/-` add-relation JSON-Patch worked example (consistent with but not verbatim from the official `WorkItemRelation` schema page)
- [github.com/MicrosoftDocs/azure-devops-docs — link-type-reference.md](https://github.com/MicrosoftDocs/azure-devops-docs/blob/main/docs/boards/queries/link-type-reference.md) — Hierarchy-Forward/Hierarchy-Reverse reference names confirmed, though the page itself doesn't show the JSON-Patch worked example
- `.planning/research/ARCHITECTURE.md` and `.planning/research/PITFALLS.md` — already-committed project research, HIGH-to-MEDIUM confidence per their own sourcing, reused directly here for patterns already established at the project level

### Tertiary (LOW confidence)
- None used as load-bearing claims in this document (all LOW-confidence findings were either cross-verified up to MEDIUM or explicitly logged in the Assumptions table above rather than stated as fact)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions re-verified against PyPI/npm registries this session, matching already-committed project research with zero drift
- Architecture (LangGraph interrupt/checkpoint patterns): HIGH — verified against official LangChain docs directly this session
- Architecture (ADO REST calls): HIGH for create/get/update endpoint shapes (official Microsoft Learn docs fetched directly); MEDIUM for the exact relation-add JSON-Patch example (community-sourced, schema-consistent but not from an official worked example)
- Pitfalls: HIGH — inherited from already-committed, well-sourced project-level PITFALLS.md research, Phase-1-scoped here
- Package legitimacy: HIGH — direct `slopcheck scan` run this session, all clean

**Research date:** 2026-07-09
**Valid until:** 30 days (stable ecosystem — LangGraph/FastAPI/ADO REST API move slowly; re-verify `langgraph-checkpoint-sqlite`'s `.setup()` signature directly against the installed package at implementation time regardless of this date, since that specific detail was not fully confirmed from docs alone)
