# Phase 1: Scaffolding + Thin End-to-End Slice - Context

**Gathered:** 2026-07-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the two riskiest integration points end-to-end, using a **hardcoded stub
plan** and no real feature logic:

1. **LangGraph interrupt/resume with durable checkpointing** — a run pauses at a
   human-review interrupt, survives a backend restart, and resumes on approval
   without re-running or double-firing side effects.
2. **A real Azure DevOps work-item push** — approving the stub creates real work
   items with correct epic→task hierarchy and verified assignment.

Requirements in scope: ORCH-01, ORCH-02, PUSH-01, PUSH-02, PUSH-03.

**Not in this phase:** real config/team intake, greenfield/brownfield ingestion,
LLM plan generation, risk scoring, plan editing. All plan data is stubbed.
</domain>

<decisions>
## Implementation Decisions

### Graph skeleton scope
- **D-01:** Build the **minimal straight-line spine only** — `ingest_config →
  stub_plan → human_review → push_to_ado`. Do **not** scaffold the
  greenfield/brownfield branch node in Phase 1; it is added in Phase 2 when it
  does real work.
- **D-02:** ORCH-01 ("orchestrate the greenfield/brownfield branch") is only
  *partially* satisfied here — the interrupt/resume half is proven now, the
  branch half is deferred to Phase 2. Planner must NOT try to fully deliver
  ORCH-01 in Phase 1.
- **D-03 (locked by research/roadmap, not re-litigated):** Single `StateGraph`,
  one `thread_id = run_id`. `interrupt()` lives in its own dedicated,
  side-effect-free `human_review` node — read state, pause, merge the resume
  payload only. No plan mutation or ADO calls inside the interrupt node (research
  Pitfall 1).

### Checkpointer
- **D-04 (locked):** Use a **file-backed SQLite checkpointer**
  (`AsyncSqliteSaver`, matching FastAPI's async handlers) from day one — required
  to satisfy ORCH-02 + success criterion #2 (survive backend restart mid-run).
  This **overrides** the `InMemorySaver` recommendation in CLAUDE.md's stack
  table, which cannot survive a restart. Do not use `MemorySaver` even
  temporarily (research Pitfall 2).

### Stub plan shape
- **D-05:** The hardcoded stub is **1 epic + 2–3 tasks, all self-assigned to the
  lead's own ADO identity.** Enough to exercise epic→task hierarchy (PUSH-02) and
  assignment verification (PUSH-03) with zero dependency on other real ADO users.
- **D-06:** The stub must be a real instance of the shared plan JSON/Pydantic
  schema (the source-of-truth shape from project-spec.md), not an ad-hoc dict —
  so later phases swap the stub generator for the real one without reshaping
  downstream nodes.

### UI scope for this slice
- **D-07:** Build a **minimal React page with live status**: a Start button, a
  polling status indicator that shows the run transition into
  "awaiting_review" and renders the stub plan, and an Approve button that
  resumes the run. Polling (not SSE) is sufficient for this slice.
- **D-08:** No styling/polish, no config or team forms — those are Phase 2. This
  page exists only to demo success criterion #1 (start → watch it pause →
  approve) through a real UI rather than curl.

### Push failure handling
- **D-09:** `push_to_ado` uses **partial-success reporting**: push what
  succeeds, collect per-item failures (create failed / assignment didn't resolve
  to a real identity), and return a structured report surfaced to the lead. One
  bad item does NOT hard-abort the whole run. Nothing is silently swallowed
  (success criterion #4).
- **D-10 (locked by research/CLAUDE.md):** After each work-item write, **read the
  field back** (`fields/System.AssignedTo`, parent link) and confirm it resolved
  — do not assume 200/201 means success (research Pitfall 5). ADO writes use
  `Content-Type: application/json-patch+json` with a patch-op **array**;
  parent/child links use `System.LinkTypes.Hierarchy-Reverse` on the **child**;
  auth is Basic with empty username (research Pitfall 4, CLAUDE.md gotchas).

### Setup precondition (BLOCKER — must be surfaced in the plan)
- **D-11:** The lead does **not yet have a real ADO org/project/PAT/identity
  ready.** The plan MUST call this out as a precondition that has to be
  provisioned before `push_to_ado` and its verification can run. Needs: an ADO
  org + project, a PAT with work-item **write** scope, and the lead's own ADO
  account email for self-assign.
- **D-12 (locked by CLAUDE.md setup checklist):** **Script A** (create +
  self-assign one ADO work item via the PAT as a standalone script) must run and
  pass against the real ADO target before its logic is wired into
  `push_to_ado`. Script B (LLM → plan JSON) is NOT relevant to Phase 1 — Phase 1
  uses a stub, no LLM call.

### Claude's Discretion
- Exact FastAPI route shapes, run-metadata storage details, poll interval, and
  file/module layout are Claude's call — follow the structure in
  `.planning/research/ARCHITECTURE.md` ("Recommended Project Structure").
- Whether run metadata lives in the same SQLite file as the checkpointer or a
  separate table — Claude's discretion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase orchestration / spec
- `CLAUDE.md` — standing repo instructions; LangGraph pipeline shape, ADO API
  gotchas (json-patch content-type, Basic auth empty username, AssignedTo
  mechanism), setup checklist (Script A/B), non-negotiable constraints.
- `project-spec.md` (repo root) — full design rationale, the LangGraph state
  object + node sequence + conditional edges, and the **plan JSON schema** that
  is the single source of truth. **Note:** referenced throughout CLAUDE.md but
  **not yet present in the repo** — confirm/obtain before planning; the stub plan
  (D-06) must match its schema.
- `.planning/ROADMAP.md` §"Phase 1" — goal, requirements, and the four success
  criteria this phase is verified against.
- `.planning/REQUIREMENTS.md` — ORCH-01, ORCH-02, PUSH-01, PUSH-02, PUSH-03
  wording.

### Architecture & pitfalls (research)
- `.planning/research/ARCHITECTURE.md` — Patterns 1 & 2 (single StateGraph,
  interrupt/resume via `Command(resume=...)`, edit-before-resume via
  `update_state`), recommended project structure, ADO batch/hierarchy notes.
- `.planning/research/PITFALLS.md` §Pitfalls 1–5 — node replay-on-resume
  double-fire, checkpointer choice, interrupt/stream sync, JSON-Patch errors,
  silent assignment failures. All five bear directly on Phase 1.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield. Repo currently contains only `CLAUDE.md`, `.planning/`, and
  `.git/`. No `backend/` or `frontend/` scaffolding exists yet; this phase
  creates the initial structure.

### Established Patterns
- No code patterns yet. Follow `.planning/research/ARCHITECTURE.md`
  "Recommended Project Structure" as the layout starting point (thin
  `graph/nodes/` calling into `services/`).

### Integration Points
- This phase establishes the integration *skeleton* everything later plugs into:
  the `RunState` TypedDict, the compiled graph + checkpointer, the FastAPI run
  controller (`POST /runs`, `GET /runs/{id}`, `POST /runs/{id}/resume`), and the
  `ado_client` push helper.

</code_context>

<specifics>
## Specific Ideas

- Stub plan is self-assigned to the lead so Phase 1 needs zero other real ADO
  users to prove the assignment path.
- "Surfaced, not swallowed" for push failures = a structured per-item report the
  lead can read, not a thrown-away log line and not a hard crash.

</specifics>

<deferred>
## Deferred Ideas

- **Greenfield/brownfield branch node** — deferred to Phase 2 (D-01/D-02); Phase
  1 spine is straight-line.
- **Real config + team roster intake forms** — Phase 2.
- **SSE streaming for run status** — Phase 1 uses polling; SSE is a post-MVP /
  larger-scale option noted in ARCHITECTURE.md scaling table.
- **Mixed / multi-identity assignees in the plan** — Phase 1 self-assigns only;
  richer assignment is exercised once the real team roster exists (Phase 2/3).

</deferred>

---

*Phase: 1-Scaffolding + Thin End-to-End Slice*
*Context gathered: 2026-07-09*
