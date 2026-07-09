# Phase 1: Scaffolding + Thin End-to-End Slice - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-09
**Phase:** 1-Scaffolding + Thin End-to-End Slice
**Areas discussed:** UI scope, Stub plan shape, Graph skeleton scope, Push failure handling, ADO test environment

---

## UI scope

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal clickable page | Start button, paused/awaiting-review state showing the stub plan, Approve button. No polish. | |
| API-only (Swagger/curl) | No React in Phase 1; drive the loop via FastAPI endpoints. Real UI deferred to Phase 2. | |
| Minimal page + live status | Minimal page plus a polling status indicator so the pause/resume transition is visible without manual refresh. | ✓ |

**User's choice:** Minimal page + live status
**Notes:** Demonstrates success criterion #1 through a real UI; polling (not SSE) is sufficient.

---

## Stub plan shape

| Option | Description | Selected |
|--------|-------------|----------|
| 1 epic + 2-3 tasks, self-assigned | One epic parenting a few tasks, all assigned to the lead's own ADO identity. Exercises hierarchy + assignment verification with no dependency on other ADO users. | ✓ |
| 2 epics + several tasks, mixed assignees | Richer stub across two epics and multiple real identities. More coverage but needs those teammates to exist in ADO. | |
| 1 epic + 1 task, self-assigned | Thinnest slice with one parent/child link and one assignment. | |

**User's choice:** 1 epic + 2-3 tasks, self-assigned
**Notes:** Zero dependency on other real ADO users; stub must still match the real plan JSON schema.

---

## Graph skeleton scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full node skeleton w/ stubs | Scaffold every planned node incl. greenfield/brownfield branch as pass-throughs. | |
| Minimal straight-line spine | Only ingest → stub_plan → human_review → push_to_ado. No branch node yet; added in Phase 2. | ✓ |

**User's choice:** Minimal straight-line spine
**Notes:** ORCH-01 only partially satisfied in Phase 1 (interrupt/resume half); branch deferred to Phase 2. Flagged so the planner doesn't over-build.

---

## Push failure handling

| Option | Description | Selected |
|--------|-------------|----------|
| Partial-success report | Push what succeeds, collect per-item failures, return a structured report to the lead. No hard-abort on one bad item. | ✓ |
| All-or-nothing abort | Any failure fails the whole push; lead fixes and retries. | |

**User's choice:** Partial-success report
**Notes:** Satisfies success criterion #4 ("surfaced, not swallowed") without a single unresolved assignee blocking the demo.

---

## ADO test environment

| Option | Description | Selected |
|--------|-------------|----------|
| Ready now | Real ADO org/project + valid PAT + own email all available immediately. | |
| Need to set it up | ADO target not yet ready; flag as a setup precondition the plan must call out before push verification. | ✓ |
| Use a throwaway/test project | Create a scratch ADO project for Phase 1 testing. | |

**User's choice:** Need to set it up
**Notes:** Captured as a BLOCKER precondition (D-11) — ADO org/project, PAT with work-item write scope, and the lead's ADO email must exist before `push_to_ado` / Script A can be verified.

---

## Claude's Discretion

- Exact FastAPI route shapes, run-metadata storage, poll interval, module layout — follow `.planning/research/ARCHITECTURE.md`.
- Whether run metadata shares the SQLite checkpoint file or a separate table.

## Deferred Ideas

- Greenfield/brownfield branch node → Phase 2.
- Real config + team roster intake forms → Phase 2.
- SSE streaming for run status → post-MVP (polling used now).
- Mixed / multi-identity assignees → once the real roster exists (Phase 2/3).
