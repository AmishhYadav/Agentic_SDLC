# Phase 2: Config, Team & Greenfield Planning - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 2-Config, Team & Greenfield Planning
**Areas discussed:** Config intake surface, Greenfield/brownfield determination, Greenfield doc-reading scope, Skill taxonomy & assignee handling

---

## Config intake surface

### Where ADO org/project + GitHub repo config lives (PAT is .env-only regardless)
| Option | Description | Selected |
|--------|-------------|----------|
| Full UI form | Org/project/repo in a UI form persisted to SQLite; PAT from .env | |
| .env for everything | Org/project/repo/PAT all in .env; UI only shows a test result | ✓ |
| Hybrid: secrets in .env | PAT+org in .env; project+repo in UI form | |

**User's choice:** .env for everything

### When the PAT smoke-test runs / how surfaced (CONN-03, SC-1)
| Option | Description | Selected |
|--------|-------------|----------|
| On-demand button | "Test connection" button; lead controls timing | |
| Auto at run start | Fires at run start; failure blocks the run | ✓ |
| Both | Manual button + auto re-check at run start | |

**User's choice:** Auto at run start
**Notes:** Claude added the constraint that the run-start result must *display*
scope/expiry/project-access detail (not an opaque block) to satisfy SC-1's "see a
clear pass/fail".

### Config + team roster scope
| Option | Description | Selected |
|--------|-------------|----------|
| Global single set | One persisted config + roster reused across runs | ✓ |
| Per-run snapshot | Each run captures its own config + roster snapshot | |

**User's choice:** Global single set

---

## Greenfield/brownfield determination

### Resolving the CLAUDE.md (manual toggle) ↔ roadmap (detect) conflict
| Option | Description | Selected |
|--------|-------------|----------|
| Manual toggle (honor CLAUDE.md) | Lead sets mode; SC-3 "detect" = route on toggle | ✓ |
| Auto-detect from repo | Infer from repo contents (violates CLAUDE.md) | |
| Auto-detect + override | Inferred default, lead can override (still infers) | |

**User's choice:** Manual toggle (honor CLAUDE.md)

### Where the toggle lives
| Option | Description | Selected |
|--------|-------------|----------|
| .env variable | REPO_MODE=greenfield in .env | ✓ |
| UI toggle on run screen | Greenfield/brownfield switch on the run page | |

**User's choice:** .env variable

### What happens if brownfield is selected in Phase 2
| Option | Description | Selected |
|--------|-------------|----------|
| Stub node: "coming in Phase 5" | Branch exists; brownfield routes to a placeholder node | |
| Hidden until Phase 5 | Only greenfield exposed; brownfield added in Phase 5 | ✓ |
| Fall back to greenfield | Brownfield quietly runs greenfield path | |

**User's choice:** Hidden until Phase 5
**Notes:** Reconciled with REPO-01 + ORCH-01's deferred branch-half: Phase 2 still
builds the thin conditional edge on REPO_MODE (greenfield real, brownfield a
guarded "not until Phase 5" leg) — no brownfield feature work, not surfaced as a
real option. Captured as D-09.

---

## Greenfield doc-reading scope

### Which docs ground plan generation (REPO-02, SC-4)
| Option | Description | Selected |
|--------|-------------|----------|
| README + docs/ markdown | README plus docs/**/*.md, capped | ✓ |
| README only | Just top-level README | |
| All markdown in repo | Every .md anywhere (risks noise) | |

**User's choice:** README + docs/ markdown

### Thin/no docs handling
| Option | Description | Selected |
|--------|-------------|----------|
| Plan from metadata + warn | Best-effort from name/desc/tree, low-confidence flag | |
| Block with clear message | Stop: "No project docs found — add a README" | ✓ |
| Lead supplies a brief | Prompt lead to paste a project brief | |

**User's choice:** Block with clear message

### Plan size/shape steering (PLAN-01)
| Option | Description | Selected |
|--------|-------------|----------|
| Guide to a bounded range | ~2-5 epics, ~2-6 tasks each | ✓ |
| Let the LLM decide freely | No size guidance | |

**User's choice:** Guide to a bounded range

---

## Skill taxonomy & assignee handling

### What defines the fixed skill taxonomy (PLAN-02)
| Option | Description | Selected |
|--------|-------------|----------|
| Hardcoded canonical list | Fixed ~12-20 skill list; same list for tasks + team | ✓ |
| Derived from team roster | Taxonomy = union of team skills (changes per roster) | |

**User's choice:** Hardcoded canonical list

### How the lead enters team-member skills (TEAM-01)
| Option | Description | Selected |
|--------|-------------|----------|
| Multi-select from taxonomy | Skills picked from the fixed taxonomy | |
| Free text (per CLAUDE.md) | Free-text skills field; Phase 3 maps text→taxonomy | ✓ |
| Both: text + taxonomy tags | Free-text notes plus structured tags | |

**User's choice:** Free text (per CLAUDE.md)
**Notes:** Phase 3 owns reconciling free-text team skills against the fixed task
taxonomy.

### suggested_assignee in Phase 2 (assignment is Phase 3)
| Option | Description | Selected |
|--------|-------------|----------|
| Leave unassigned | Empty string; Phase 3 fills it | ✓ |
| Naive LLM guess | LLM guesses now, overwritten in Phase 3 | |
| Default to lead | Self-assign to lead like Phase 1 stub | |

**User's choice:** Leave unassigned

---

## Claude's Discretion

- Fetch mechanism for greenfield docs (PyGithub per-file vs shallow clone) — per STACK.md.
- Exact contents of the hardcoded skill taxonomy (~12-20 items).
- Team roster / config table location (shared vs separate SQLite table).
- FastAPI route shapes for config smoke-test + team CRUD, and run-input plumbing for REPO_MODE.
- PLAN-04 retry count and repair strategy.

## Deferred Ideas

- Brownfield codebase RAG + onboarding summary — Phase 5.
- Skill/load-aware assignment + deterministic risk scoring — Phase 3.
- Plan editing (direct + chat/diff) — Phase 4.
- UI config form / "Test connection" button — rejected (config is .env-only).
- Team skills as taxonomy multi-select — rejected for free text; possible post-MVP upgrade.
- `graph/users` ADO dropdown for team identities — later (per CLAUDE.md).
