# Roadmap: AI Project Planning & Onboarding Dashboard

## Overview

A 2-day MVP delivered as five vertical slices. Phase 1 proves the riskiest plumbing first — LangGraph interrupt/resume with durable checkpointing, and a real Azure DevOps work-item push with correct epic→task hierarchy — using a stubbed plan, so every later phase builds on validated infrastructure instead of discovering integration failures late. Phase 2 replaces the stub with the real config/team intake and greenfield-first plan generation (the primary demo path). Phase 3 adds the two headline differentiators — skill/load-aware assignment and deterministic risk scoring — on top of the same plan/team data shape. Phase 4 makes the plan editable, both directly and via LLM chat with diff-preview, reusing Phase 1's interrupt pattern a second time. Phase 5 adds brownfield codebase RAG last, since it is the highest-complexity, most cuttable piece — sequencing it last protects a working greenfield demo regardless of how it goes.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scaffolding + Thin End-to-End Slice** - Prove LangGraph interrupt/resume with durable checkpointing and a real ADO push, end to end, with a stubbed plan
- [ ] **Phase 2: Config, Team & Greenfield Planning** - Connect ADO+GitHub, build the team roster, detect greenfield/brownfield, and generate a real epic→task plan from project docs
- [ ] **Phase 3: Skill/Load-Aware Assignment & Risk Scoring** - Auto-assign tasks against real team skill/load data and surface deterministic, explained risk scores
- [ ] **Phase 4: Plan Editing — Direct & Chat with Diff Preview** - Let the lead edit the plan directly or via LLM chat, reviewing chat-driven changes as a diff before accepting
- [ ] **Phase 5: Brownfield Codebase RAG & Onboarding Summary** - Ingest an existing codebase, embed it for RAG, and generate an onboarding summary that grounds planning

## Phase Details

### Phase 1: Scaffolding + Thin End-to-End Slice

**Goal**: The full connect→plan→review→push pipeline runs end to end — with a hardcoded/stubbed plan — proving the two riskiest integration points (LangGraph interrupt/resume with durable checkpointing, and a real ADO work-item push with correct hierarchy) work before any real feature logic is built.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: ORCH-01, ORCH-02, PUSH-01, PUSH-02, PUSH-03
**Success Criteria** (what must be TRUE):

  1. Lead can start a run, watch it pause at a human-review interrupt, and resume it by approving — the graph does not silently re-run or double-fire side effects
  2. Restarting the backend mid-run does not lose the in-progress run; it resumes from its last checkpoint
  3. Approving the stubbed plan creates real Azure DevOps work items with correct epic→task parent/child hierarchy links
  4. Each pushed work item's creation and assignment is verified (not assumed) and any failure is surfaced, not silently swallowed

**Plans**: 3 plans

Plans:
**Wave 1**

- [ ] 01-01-PLAN.md — Backend LangGraph spine (ingest_config -> stub_plan -> human_review -> push_to_ado stub) wired to FastAPI + AsyncSqliteSaver, proving interrupt/resume and restart survival (ORCH-01 partial, ORCH-02)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02-PLAN.md — Script A ADO smoke test + real ado_client wired into push_to_ado, replacing the stub (PUSH-01, PUSH-02, PUSH-03); gated behind ADO org/project/PAT provisioning (D-11)
- [ ] 01-03-PLAN.md — Minimal React + Vite page (Start/poll/Approve) wired to the Plan 01-01 backend routes (D-07/D-08)

**Cross-cutting constraints:**

- Lead can start a run, watch it pause at a human-review interrupt, and resume it by approving — the graph does not silently re-run or double-fire side effects

### Phase 2: Config, Team & Greenfield Planning

**Goal**: A lead can connect their real ADO project and GitHub repo, build a team roster, and get a real LLM-generated epic→task plan (skill-tagged, estimated) grounded in the repo's docs for the greenfield path — the primary demo flow.
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: CONN-01, CONN-02, CONN-03, TEAM-01, TEAM-02, REPO-01, REPO-02, PLAN-01, PLAN-02, PLAN-03, PLAN-04
**Success Criteria** (what must be TRUE):

  1. Lead can configure an ADO project + shared PAT and a GitHub repo, and immediately see a clear pass/fail smoke-test result for the PAT (scope, expiry, project access)
  2. Lead can add, edit, and remove team members (name, designation, skills, experience level) before planning starts
  3. Tool correctly detects whether the configured repo is greenfield or brownfield and takes the greenfield doc-reading path when appropriate
  4. Tool generates a real epic→task plan from the repo's docs, where every task has a skill tag (from a fixed taxonomy) and an hours/days estimate
  5. Malformed LLM plan output is caught by schema validation and repaired/retried automatically rather than surfacing broken data

**Plans**: TBD

### Phase 3: Skill/Load-Aware Assignment & Risk Scoring

**Goal**: Every task in the plan has a defensible suggested assignee that accounts for real skill match, experience, and each person's running load within the generated plan, and every skill-coverage gap is surfaced as a risk with a reproducible score and a human-readable explanation.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: ASSIGN-01, ASSIGN-02, RISK-01, RISK-02
**Success Criteria** (what must be TRUE):

  1. Each task shows a suggested assignee chosen by matching required skill and experience against the team roster
  2. Assignment suggestions visibly shift as tasks accumulate, balancing each member's running total load within the generated plan (hours assigned so far)
  3. Each skill-coverage gap produces the same numeric risk score on repeated runs given the same inputs (deterministic, pure-logic scoring, no LLM in the number)
  4. Each surfaced risk includes an AI-written explanation describing the gap, generated over the already-computed score rather than inventing it

**Plans**: TBD

### Phase 4: Plan Editing — Direct & Chat with Diff Preview

**Goal**: The lead has full control over the generated plan before it ships — editing tasks/assignees/estimates directly, or describing a change in chat and reviewing it as an explicit diff before it takes effect.
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: EDIT-01, EDIT-02, EDIT-03
**Success Criteria** (what must be TRUE):

  1. Lead can directly edit a task's fields (assignee, estimate, description) and see the plan update immediately
  2. Lead can type a natural-language instruction (e.g. "split this task", "reassign to someone else") and get back a proposed change
  3. Every chat-driven change is shown as a diff against the current plan before it is applied, and the lead can accept or reject it
  4. Rejected chat-driven changes leave the plan completely unchanged

**Plans**: TBD

### Phase 5: Brownfield Codebase RAG & Onboarding Summary

**Goal**: For an existing codebase, the tool ingests the repo, embeds it for retrieval, and produces an onboarding summary that grounds plan generation — so the team understands what already exists before a brownfield plan is generated.
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: REPO-03, REPO-04
**Success Criteria** (what must be TRUE):

  1. When a brownfield repo is configured, the tool shallow-clones and filters it (excluding binaries/lockfiles/vendored code) before ingestion
  2. The filtered codebase is chunked and embedded into a local vector store usable for retrieval
  3. Lead sees a generated onboarding summary of the existing codebase before the brownfield plan is generated
  4. The brownfield plan generation step reuses the same plan-generation path from Phase 2, now grounded in retrieved codebase context instead of docs alone

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffolding + Thin End-to-End Slice | 0/TBD | Not started | - |
| 2. Config, Team & Greenfield Planning | 0/TBD | Not started | - |
| 3. Skill/Load-Aware Assignment & Risk Scoring | 0/TBD | Not started | - |
| 4. Plan Editing — Direct & Chat with Diff Preview | 0/TBD | Not started | - |
| 5. Brownfield Codebase RAG & Onboarding Summary | 0/TBD | Not started | - |
