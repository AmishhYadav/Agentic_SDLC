---
phase: 02-config-team-greenfield-planning
plan: 02
subsystem: api
tags: [fastapi, sqlite, pydantic, react, team-roster, crud]

# Dependency graph
requires:
  - phase: 01-scaffolding-thin-end-to-end-slice
    provides: backend/app/db/run_metadata.py's sync sqlite3 access pattern (CHECKPOINT_DB_PATH), main.py lifespan wiring, frontend/src/lib/runClient.ts's typed fetch wrapper pattern
provides:
  - team_members SQLite table (CRUD via app/db/team_roster.py) in the shared checkpoints.sqlite file
  - TeamMember Pydantic model (backend/app/models/team.py) — shared shape for team member data
  - GET/POST/PUT/DELETE /team FastAPI routes (backend/app/routers/team.py)
  - Frontend Team tab (TeamPage.tsx) wired to /team routes via teamClient.ts
affects: [03-assignment-risk-scoring, 04-plan-editing]

# Tech tracking
tech-stack:
  added: [email-validator==2.3.0]
  patterns:
    - "team_roster.py mirrors run_metadata.py's sync sqlite3 connect/try/finally-close style — no ORM, same sqlite file, new table"
    - "TeamMember.experience_level typed as a Literal[\"junior\",\"mid\",\"senior\",\"lead\"] so frontend select matches backend exactly"
    - "Frontend tab switch (useState) instead of a routing library, matching App.tsx's existing minimalism"

key-files:
  created:
    - backend/app/db/team_roster.py
    - backend/app/models/team.py
    - backend/app/routers/team.py
    - backend/tests/test_team_roster.py
    - frontend/src/lib/teamClient.ts
    - frontend/src/pages/TeamPage.tsx
  modified:
    - backend/app/main.py
    - backend/requirements.txt
    - frontend/src/App.tsx

key-decisions:
  - "experience_level modeled as a fixed Literal (junior/mid/senior/lead) rather than free text, documented in the model so the frontend <select> matches exactly"
  - "email-validator==2.3.0 added (verified current via pip index versions) to support Pydantic's EmailStr, enforcing T-02-04's email-format mitigation at the request-model layer"
  - "Team roster kept fully independent of RunState/the LangGraph run — team_roster.py never imports app.graph.*, confirmed via grep"

patterns-established:
  - "New SQLite-backed resource modules mirror run_metadata.py's sync sqlite3 style (no ORM, shared CHECKPOINT_DB_PATH file, one table per resource)"
  - "New frontend API clients mirror runClient.ts's relative-path fetch + typed interface pattern"

requirements-completed: [TEAM-01, TEAM-02]

# Metrics
duration: 25min
completed: 2026-07-10
---

# Phase 2 Plan 2: Team Roster CRUD Summary

**Team roster as an independent vertical slice — SQLite-backed CRUD (name/email/designation/skills/experience_level) with a FastAPI /team surface and a React Team tab, fully decoupled from the LangGraph run.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-10T21:13:04Z
- **Tasks:** 2 completed
- **Files modified:** 9 (6 created, 3 modified)

## Accomplishments
- `team_members` SQLite table with full CRUD (`create_member`/`list_members`/`update_member`/`delete_member`) in `backend/app/db/team_roster.py`, mirroring `run_metadata.py`'s exact sync sqlite3 style and sharing the same `CHECKPOINT_DB_PATH` file
- `TeamMember` Pydantic model with `EmailStr` validation (rejects malformed email at the request layer, satisfying threat T-02-04) and a fixed `experience_level` taxonomy
- `GET/POST/PUT/DELETE /team` FastAPI routes, wired into `main.py`'s lifespan alongside the existing `run_metadata.init_db()` call
- Frontend Team tab: add/edit/remove form + list, wired to the backend via `teamClient.ts`, reachable via a minimal in-app tab switch (no router dependency added)
- TDD RED→GREEN cycle followed for Task 1: 9 failing tests written first (`268fdfc`), then implementation (`4364500`) made them all pass

## Task Commits

Each task was committed atomically:

1. **Task 1: team_members table, TeamMember model, and CRUD routes** — RED `268fdfc` (test), GREEN `4364500` (feat)
2. **Task 2: Frontend team roster page wired to /team routes** — `18c4f7d` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `backend/app/db/team_roster.py` - team_members table CRUD, mirrors run_metadata.py's style
- `backend/app/models/team.py` - shared TeamMember Pydantic model (EmailStr, Literal experience_level)
- `backend/app/routers/team.py` - GET/POST/PUT/DELETE /team routes
- `backend/app/main.py` - wired team_roster.init_team_table() + team_router into lifespan
- `backend/requirements.txt` - added email-validator==2.3.0
- `backend/tests/test_team_roster.py` - 9 tests covering CRUD, email validation, and full HTTP round-trip
- `frontend/src/lib/teamClient.ts` - typed fetch wrappers (listMembers/createMember/updateMember/deleteMember)
- `frontend/src/pages/TeamPage.tsx` - add/edit/remove UI, fetched once on mount
- `frontend/src/App.tsx` - minimal Run/Team tab switch

## Decisions Made
- `experience_level` modeled as `Literal["junior", "mid", "senior", "lead"]` (Claude's discretion per CONTEXT.md) rather than free text, with the four values documented in the model so the frontend `<select>` matches exactly
- `email-validator==2.3.0` added after verifying it's the current top version via `pip index versions email-validator` in the project venv
- No routing library added for the Run/Team tab switch — a `useState<"run" | "team">` toggle in `App.tsx` is sufficient for a 2-day MVP with two pages, per the plan's explicit instruction

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The team roster uses the same local SQLite file (`checkpoints.sqlite`) already configured via `CHECKPOINT_DB_PATH` in Phase 1; no new environment variables needed.

## Next Phase Readiness

- The `/team` CRUD surface is fully functional and independently verifiable (backend tests pass, frontend builds clean) without any run being started, satisfying the plan's isolation goal.
- `TeamMember.skills` remains free text as required by D-06 — Phase 3's skill-matching logic will reconcile it against the fixed skill taxonomy (D-10, introduced by a sibling plan in this phase).
- `team_roster.py` confirmed to never import `app.graph.*` — the roster stays decoupled from `RunState`, so Phase 3's assignment logic can read the roster directly via `team_roster.list_members()` without any graph-state plumbing.
- No blockers for downstream phases.

---
*Phase: 02-config-team-greenfield-planning*
*Completed: 2026-07-10*

## Self-Check: PASSED

All created files verified present on disk. All commit hashes (268fdfc, 4364500, 18c4f7d, e5a887c) verified present in git log.
