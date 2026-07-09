# Requirements: AI Project Planning & Onboarding Dashboard

**Defined:** 2026-07-09
**Core Value:** One clean end-to-end flow — connect ADO + GitHub → understand the repo → generate a skill-aware, load-balanced, editable plan → push approved tasks into ADO as assigned work items.

## v1 Requirements

Requirements for the 2-day MVP. Each maps to a roadmap phase.

### Connection & Config

- [ ] **CONN-01**: Lead can configure an Azure DevOps project connection using a single shared PAT (no OAuth/login)
- [ ] **CONN-02**: Lead can configure a GitHub repo to plan from
- [ ] **CONN-03**: On connect, the tool smoke-tests the ADO PAT and surfaces a clear pass/fail (scope, expiry, project access)

### Team Roster

- [ ] **TEAM-01**: Lead can add team members with name, designation, skills, and experience level
- [ ] **TEAM-02**: Lead can edit or remove team members before planning

### Repo Understanding

- [ ] **REPO-01**: Tool detects whether the repo is greenfield or brownfield and branches accordingly
- [ ] **REPO-02**: Greenfield path reads the repo's project docs to ground plan generation
- [ ] **REPO-03**: Brownfield path ingests the existing codebase (shallow clone, filtered) and embeds it for RAG
- [ ] **REPO-04**: Brownfield path generates an onboarding summary of what exists before planning, so the team understands the codebase first

### Plan Generation

- [ ] **PLAN-01**: Tool generates an implementation plan of epics broken into tasks
- [ ] **PLAN-02**: Each task is tagged with the required skill (constrained to a fixed skill taxonomy for reproducibility)
- [ ] **PLAN-03**: Each task carries an effort estimate in hours/days
- [ ] **PLAN-04**: Plan generation validates the LLM's structured output against a schema and repairs/retries on malformed output

### Assignment

- [ ] **ASSIGN-01**: Each task gets a suggested assignee based on skill match and experience against the team roster
- [ ] **ASSIGN-02**: Assignment factors in each member's current load using a within-plan running total (hours assigned so far across the generated plan)

### Risk

- [ ] **RISK-01**: Tool computes a mostly-deterministic risk score from real skill-coverage gaps between task requirements and team composition (pure logic, no LLM in the number)
- [ ] **RISK-02**: Tool surfaces each skill-coverage gap as a risk with an AI-written explanation over the already-computed score (LLM explains, never invents the score)

### Plan Editing

- [ ] **EDIT-01**: Lead can edit the plan directly (tasks, assignees, estimates) before approval
- [ ] **EDIT-02**: Lead can edit the plan via LLM chat (e.g. "split this task", "reassign to someone else")
- [ ] **EDIT-03**: Chat-driven changes are shown as a diff the lead reviews and accepts or rejects before they apply

### ADO Push

- [ ] **PUSH-01**: On approval, tool pushes tasks into Azure DevOps as real work items assigned to the correct people (one-way)
- [ ] **PUSH-02**: Pushed work items preserve epic → task hierarchy (parent/child links)
- [ ] **PUSH-03**: Tool verifies each pushed work item was created and assigned correctly (guards against silent assignment failures)

### Orchestration

- [x] **ORCH-01**: The greenfield/brownfield branch and the human review/edit loop are orchestrated with LangGraph using an interrupt-and-resume pattern
- [x] **ORCH-02**: Run state is checkpointed durably so an in-progress plan survives a backend restart

## v2 Requirements

Deferred to future release. Tracked but not in the current roadmap.

### Sync

- **SYNC-01**: Two-way sync between the tool and Azure DevOps work item state

### Access

- **ACCS-01**: Multi-user auth and role-based access control (RBAC)

### Scale

- **SCAL-01**: Multi-repo support (plan across more than one GitHub repo)

### Assignment (advanced)

- **ASGX-01**: Optimizer/solver-based assignment (LP / simulated annealing) instead of greedy skill+load scoring
- **ASGX-02**: Historical-velocity-based estimation once historical delivery data exists
- **ASGX-03**: Load-awareness reads each member's real existing open Azure DevOps work items instead of a within-plan running total

## Out of Scope

Explicitly excluded for this MVP. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Two-way ADO sync | Push-only is enough to prove the flow; reconciling state back is a large surface area (deferred to v2 SYNC-01) |
| RBAC / multi-user auth | Single lead runs it locally; auth adds cost without validating core value (deferred to v2 ACCS-01) |
| Multi-repo support | One ADO project + one repo keeps the flow clean (deferred to v2 SCAL-01) |
| Paid/hosted commercial LLMs | Free open models (GLM via NVIDIA NIM) keep the MVP zero-cost |
| Optimizer/solver assignment | Greedy skill+load scoring is sufficient at this scale (deferred to v2 ASGX-01) |
| Field-level diff granularity | Whole-plan-object diff review is sufficient for the MVP |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONN-01 | Phase 2 | Pending |
| CONN-02 | Phase 2 | Pending |
| CONN-03 | Phase 2 | Pending |
| TEAM-01 | Phase 2 | Pending |
| TEAM-02 | Phase 2 | Pending |
| REPO-01 | Phase 2 | Pending |
| REPO-02 | Phase 2 | Pending |
| REPO-03 | Phase 5 | Pending |
| REPO-04 | Phase 5 | Pending |
| PLAN-01 | Phase 2 | Pending |
| PLAN-02 | Phase 2 | Pending |
| PLAN-03 | Phase 2 | Pending |
| PLAN-04 | Phase 2 | Pending |
| ASSIGN-01 | Phase 3 | Pending |
| ASSIGN-02 | Phase 3 | Pending |
| RISK-01 | Phase 3 | Pending |
| RISK-02 | Phase 3 | Pending |
| EDIT-01 | Phase 4 | Pending |
| EDIT-02 | Phase 4 | Pending |
| EDIT-03 | Phase 4 | Pending |
| PUSH-01 | Phase 1 | Pending |
| PUSH-02 | Phase 1 | Pending |
| PUSH-03 | Phase 1 | Pending |
| ORCH-01 | Phase 1 | Complete |
| ORCH-02 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25 (Phase 1: 5, Phase 2: 11, Phase 3: 4, Phase 4: 3, Phase 5: 2)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-09*
*Last updated: 2026-07-09 after scoping load-awareness to within-plan running total (real-ADO-workload deferred to v2 ASGX-03)*
