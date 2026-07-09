# Phase 2: Config, Team & Greenfield Planning - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace Phase 1's stub with **real config/team intake and greenfield-first plan
generation** — the primary demo path:

1. **Config** — the lead points the tool at a real ADO org/project + GitHub repo
   and a PAT; the tool smoke-tests the PAT (scope, expiry, project access) and
   surfaces a clear pass/fail.
2. **Team roster** — the lead adds/edits/removes team members (name, email,
   designation, skills, experience level) before planning.
3. **Greenfield planning** — the tool routes on a manual greenfield/brownfield
   toggle, reads the repo's docs on the greenfield path, and generates a real
   LLM-produced epic→task plan where every task carries a skill tag (from a fixed
   taxonomy) and an hours/days estimate, with schema-validated / repaired LLM
   output.

Requirements in scope: CONN-01, CONN-02, CONN-03, TEAM-01, TEAM-02, REPO-01,
REPO-02, PLAN-01, PLAN-02, PLAN-03, PLAN-04.

**Not in this phase:** skill/load-aware *assignment* and risk scoring (Phase 3),
plan editing (Phase 4), brownfield codebase RAG + onboarding summary (Phase 5).
The greenfield/brownfield branch is built, but the brownfield leg does no real
work here.
</domain>

<decisions>
## Implementation Decisions

### Config intake surface
- **D-01:** **All config lives in `.env`** — `ADO_ORG`, `ADO_PROJECT`, `ADO_PAT`,
  and `GITHUB_REPO` (owner/repo). There is **no config form**. "Configure" per
  CONN-01/CONN-02 is satisfied by editing `.env`. This is the deliberate,
  leanest MVP reading and is consistent with CLAUDE.md's `.env`-first,
  PAT-never-prompted stance. Do **not** build a UI form for ADO/GitHub config.
- **D-02:** The PAT **smoke-test runs automatically at run start** and **blocks
  the run on failure** — no separate "Test connection" button. The check must
  cover PAT auth, work-item **write** scope, PAT **expiry**, and **project
  access** (CONN-03).
- **D-03 (satisfies SC-1 "immediately see a clear pass/fail"):** The run-start
  smoke-test result must be **displayed to the lead with detail** — scope,
  expiry, project access — not an opaque "run blocked". A failed smoke-test
  surfaces *why* (e.g., "PAT lacks work-item write scope", "PAT expired",
  "project not accessible"), mirroring Phase 1's "surfaced, not swallowed"
  discipline (D-09/D-10).
- **D-04:** **Config + team roster are global**, persisted in SQLite as a single
  current set reused across runs (the lead edits between runs). No per-run config
  snapshot. Fits the single-lead local MVP and TEAM-02's "before planning starts"
  framing.

### Team roster intake
- **D-05:** The team form captures **name, email, designation, skills (free
  text), experience level** (TEAM-01). **Email is required** even though Phase 2
  does not assign tasks — CLAUDE.md's `System.AssignedTo` mechanism (Phase 3
  assignment + ADO push) depends on it. Do not drop the email field just because
  TEAM-01's wording omits it.
- **D-06:** **Skills are entered as free text**, per CLAUDE.md's "skills text"
  constraint. Reconciling free-text skills against the fixed task-skill taxonomy
  (D-10) is **Phase 3's** job (skill-matching), not Phase 2's. Phase 2 only
  stores the text.
- **D-07:** Add / edit / remove of team members must all work **before planning
  starts** (TEAM-02). Roster lives in SQLite (may share the Phase 1 DB or its own
  table — Claude's discretion).

### Greenfield / brownfield determination
- **D-08 (resolves the CLAUDE.md ↔ roadmap conflict):** Mode is a **manual
  toggle set by the lead via `REPO_MODE` in `.env`** (`greenfield` | `brownfield`),
  **never inferred from repo contents** — CLAUDE.md non-negotiable wins over
  SC-3/REPO-01's word "detects". "Detects/branches accordingly" is reinterpreted
  as **"correctly routes on the lead's toggle."** Do not scan repo files to guess
  the mode.
- **D-09 (satisfies REPO-01 + ORCH-01 branch-half deferred from Phase 1 per
  Phase 1 D-02):** Build the **thin conditional branch** on `REPO_MODE` now. The
  **greenfield leg is real**; the **brownfield leg is a guarded placeholder** that
  returns a clear "brownfield planning arrives in Phase 5" result — **no
  brownfield feature work, and brownfield is not surfaced as a real option in
  Phase 2**. Keep the brownfield leg minimal; do not let it crash or silently
  fall back to greenfield. Default `REPO_MODE=greenfield`.

### Greenfield doc-reading + plan generation
- **D-10 (fixed skill taxonomy — PLAN-02):** Task skill tags come from a
  **hardcoded canonical skill list** (~12–20 items, e.g. Frontend, Backend,
  Database, DevOps, Testing, API-Design, Auth, Infra, …) defined once in
  code/config. This is the "fixed taxonomy for reproducibility." The same list is
  the intended matching target for team skills in Phase 3. The LLM must tag every
  task with a value **from this list** (constrained/validated, not free-form).
- **D-11 (doc scope — REPO-02):** Greenfield planning reads **`README` +
  `docs/**/*.md`**, capped at a sensible total size before passing to the GLM
  context window (no vector store on the greenfield path — read markdown
  directly, per CLAUDE.md stack notes). Fetch mechanism (PyGithub per-file vs
  shallow clone) is Claude/research's call per STACK.md.
- **D-12 (no-docs handling):** If a greenfield repo has **no usable docs**,
  **block with a clear message** ("No project docs found — add a README to
  plan") rather than best-effort planning from metadata. Honest dead-end over a
  low-confidence guess.
- **D-13 (plan size — PLAN-01):** Steer the LLM toward a **bounded, demo-able
  plan: ~2–5 epics, ~2–6 tasks each**, every task **skill-tagged (D-10) and
  estimated in hours/days (PLAN-03)**. Avoid both a 1-task stub and a 40-task
  wall.
- **D-14 (assignee — Phase 2/3 boundary):** In Phase 2, **`suggested_assignee`
  is left empty** (`""`). Phase 3's skill/load-aware logic populates it. Do
  **not** have the LLM guess assignees and do not default them to the lead — keep
  the boundary clean so Phase 3 owns assignment.
- **D-15 (PLAN-04 — schema validation/repair):** Plan generation uses
  **structured output / tool-calling** and validates against the shared
  `Plan/Epic/Task` Pydantic schema. Malformed output is **caught and
  repaired/retried automatically** rather than surfacing broken data. Behavior
  after exhausting retries (surface a clear error) is Claude's discretion — but
  it must fail loudly, not emit broken plan data.

### Claude's Discretion
- Fetch mechanism for greenfield docs (PyGithub `get_contents` per-file vs shallow
  clone) — follow `.planning/research/STACK.md`.
- The exact contents of the hardcoded skill taxonomy list (D-10) — pick a
  reasonable ~12–20 item software-engineering skill set; keep it in one shared
  location importable by both nodes and API models.
- Where the team roster + run config table lives (same SQLite file as the
  checkpointer/run-metadata DB or a separate table).
- FastAPI route shapes for config smoke-test + team CRUD, and the run-input plumbing
  that carries `REPO_MODE` / config into the graph.
- Retry count and exact repair strategy for PLAN-04.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase orchestration / spec
- `CLAUDE.md` — standing repo instructions. Directly load-bearing for Phase 2:
  `.env` keys (`ADO_ORG`, `ADO_PROJECT`, `ADO_PAT`, `GITHUB_TOKEN`,
  `ANTHROPIC_API_KEY`/NVIDIA key, `DATABASE_URL`); "team members typed manually,
  skills text, leave swappable"; "greenfield/brownfield is a **manual toggle**,
  never inferred"; "risk score never by the LLM" (Phase 3 guardrail); "plan is a
  single JSON object — one shared Pydantic model"; ADO API gotchas
  (json-patch content-type, Basic auth empty username, `System.AssignedTo`
  mechanism); Script A/B setup checklist (Script B = LLM→plan JSON becomes
  relevant this phase).
- ⚠️ `project-spec.md` (repo root) — cited by CLAUDE.md and Phase 1 as the "plan
  JSON schema source of truth" but **DOES NOT EXIST in the repo**. The real
  source of truth for the plan shape is `backend/app/models/plan.py`. Do not
  block planning waiting for `project-spec.md`; treat `plan.py` as authoritative.
- `.planning/ROADMAP.md` §"Phase 2" — goal, requirements list, and the five
  success criteria this phase is verified against.
- `.planning/REQUIREMENTS.md` — CONN-01/02/03, TEAM-01/02, REPO-01/02,
  PLAN-01/02/03/04 wording.

### Architecture & pitfalls (research)
- `.planning/research/ARCHITECTURE.md` — recommended project structure
  (`graph/nodes/` calling into `services/`), branch/conditional-edge patterns,
  ADO notes.
- `.planning/research/STACK.md` — GLM-via-NVIDIA wiring (`ChatOpenAI` +
  `base_url`, `NVIDIA_CHAT_MODEL` env var), PyGithub vs shallow-clone guidance for
  greenfield docs, structured-output approach for PLAN-04.
- `.planning/research/PITFALLS.md` — LLM/JSON parsing and ADO pitfalls; relevant
  to PLAN-04 (schema validation) and the smoke-test.
- `.planning/research/FEATURES.md`, `.planning/research/SUMMARY.md` — feature
  breakdown and research synthesis.

### Prior phase context (carry-forward)
- `.planning/phases/01-scaffolding-thin-end-to-end-slice/01-CONTEXT.md` — D-01
  (straight-line spine, branch deferred to Phase 2), D-06 (stub is a real Plan
  instance so this phase swaps the generator without reshaping downstream), D-09/
  D-10 (partial-success push + read-back verification), D-11/D-12 (ADO
  provisioning + Script A precondition, still open — PAT was expired).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/models/plan.py` — the shared `Plan/Epic/Task/PushReport` Pydantic
  schema. `Task` already has `skill_tag: str | None` and `estimate_hours: float`
  fields waiting for this phase. **This is the plan source of truth** (not the
  missing `project-spec.md`). Real plan generation must emit this exact shape.
- `backend/app/graph/nodes/stub_plan.py` — the stub this phase **replaces** with
  real greenfield plan generation. Its output shape (a real `Plan`) is the
  contract to preserve.
- `backend/app/graph/nodes/ingest_config.py` — currently a passthrough reading
  `LEAD_EMAIL` from env; this phase grows it into real config intake / smoke-test
  / mode routing (or splits into new nodes feeding the branch).
- `backend/app/graph/build.py` — the 4-node straight-line spine; this phase adds
  the greenfield/brownfield **conditional edge** (D-09) after `ingest_config`.
- `backend/app/graph/state.py` — `RunState` TypedDict; extend with config, team
  roster, and `repo_mode` fields as needed.
- `backend/app/db/run_metadata.py` — existing SQLite access pattern to mirror for
  the team roster / config table.
- `backend/scripts/script_a_ado_smoke_test.py` — existing ADO smoke-test script;
  its PAT-check logic informs the CONN-03 run-start smoke-test (D-02/D-03).
- `backend/app/services/ado_client.py` — ADO REST client (Basic auth empty user,
  json-patch); reuse for the smoke-test's scope/project checks.

### Established Patterns
- Status is always derived from `graph.aget_state()` — never a hand-rolled status
  field (`routers/runs.py`). New run-status states (e.g., smoke-test failed,
  awaiting docs) should follow the same derive-from-graph pattern.
- Checkpointer opened once in `main.py` lifespan; graph compiled once. New nodes
  must stay checkpoint-safe (no side effects that can't survive a replay-on-resume).
- Nodes are thin and call into `services/`; keep GitHub/LLM/ADO calls in service
  modules, not inline in nodes.

### Integration Points
- New config + team CRUD FastAPI routes alongside `routers/runs.py`.
- New greenfield service(s): GitHub doc reader (PyGithub) + GLM plan generator
  (`ChatOpenAI` at NVIDIA `base_url`, model from `NVIDIA_CHAT_MODEL`).
- The conditional edge in `build.py` reading `REPO_MODE`/state.

</code_context>

<specifics>
## Specific Ideas

- The `.env` is the entire config surface for ADO/GitHub — the UI shows results
  (smoke-test pass/fail, generated plan), it does not collect ADO/GitHub config.
- Smoke-test failure must read like Phase 1's push report: concrete, per-check
  reasons (scope / expiry / project access), surfaced to the lead, not swallowed.
- The greenfield path deliberately uses **no vector store** — read markdown docs
  straight into the GLM context (Chroma/RAG is Phase 5's brownfield concern only).
- Keep the brownfield leg a visible, honest placeholder ("arrives in Phase 5"),
  not a silent greenfield fallback.

</specifics>

<deferred>
## Deferred Ideas

- **Brownfield codebase RAG + onboarding summary** — Phase 5 (D-09 keeps the
  brownfield leg a guarded placeholder here).
- **Skill/load-aware assignment + deterministic risk scoring** — Phase 3; Phase 2
  leaves `suggested_assignee` empty (D-14) and stores team skills as free text
  (D-06) for Phase 3 to reconcile against the taxonomy (D-10).
- **Plan editing (direct + chat/diff)** — Phase 4.
- **UI config form / "Test connection" button** — rejected for Phase 2 (config is
  `.env`-only, D-01); could return if config moves out of `.env` post-MVP.
- **Team skills as taxonomy multi-select** — considered and rejected in favor of
  free text per CLAUDE.md (D-06); a structured skill picker is a possible post-MVP
  upgrade once free-text→taxonomy matching proves lossy.
- **`graph/users` ADO dropdown for team identities** — CLAUDE.md notes this
  replaces free-text member entry later; not built now.

None lost — discussion otherwise stayed within phase scope.

</deferred>

---

*Phase: 2-Config, Team & Greenfield Planning*
*Context gathered: 2026-07-10*
