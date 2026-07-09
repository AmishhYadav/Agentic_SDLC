# AI Project Planning & Onboarding Dashboard

## What This Is

A local tool for an engineering lead kicking off a project on Azure DevOps and GitHub. The lead connects an ADO project and a GitHub repo, enters their team (name, designation, skills, experience), and the tool reads the repo — for greenfield it reads the docs, for brownfield it ingests the existing codebase (embedded for RAG) and produces an onboarding summary so the team understands what exists before planning. It then generates an editable implementation plan (epics → skill-tagged, estimated, auto-assigned tasks) with risk flags for skill-coverage gaps, and on approval pushes the tasks straight into Azure DevOps as work items assigned to the right people.

## Core Value

One clean end-to-end flow: connect ADO + GitHub → understand the repo → generate a skill-aware, load-balanced, editable plan → push approved tasks into ADO as assigned work items. If everything else fails, that single flow must work end to end.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. All are hypotheses until shipped and validated. -->

- [ ] Lead connects an Azure DevOps project and a GitHub repo via configuration (single shared ADO PAT, no auth/login)
- [ ] Lead enters team members with name, designation, skills, and experience level
- [ ] Tool reads a connected GitHub repo and branches on greenfield vs brownfield
- [ ] Greenfield path: read project docs to inform planning
- [ ] Brownfield path: ingest existing codebase, embed for RAG, and generate an onboarding summary before planning
- [ ] Generate an implementation plan: epics broken into tasks, each tagged with required skill, an hours/days estimate, and a suggested assignee
- [ ] Assignee suggestion accounts for team composition (skills/experience) and current load (who is already assigned work)
- [ ] Surface skill-coverage gaps as risks with a mostly-deterministic risk score plus an AI-written explanation
- [ ] Lead can edit the plan directly (tweak tasks/assignees/estimates)
- [ ] Lead can edit the plan via LLM chat ("split this task", "reassign to someone else") and preview the change as a diff before accepting
- [ ] On approval, push tasks into Azure DevOps as work items assigned to the correct people (one-way)
- [ ] Orchestrate the greenfield/brownfield branch and the human-review/edit loop with LangGraph using an interrupt-and-resume pattern

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Two-way ADO sync — MVP only pushes one way; reading state back and reconciling is a large surface area not needed to prove the flow
- RBAC / multi-user auth — single lead runs it locally; auth adds cost without validating the core value for a 2-day MVP
- Multi-repo support — one ADO project + one GitHub repo keeps the flow clean; multi-repo is a later concern
- Paid/hosted commercial LLMs — using free open-source models (GLM via NVIDIA's free API) to keep the MVP zero-cost

## Context

- **Ecosystem:** Azure DevOps (work items, assignment, boards) + GitHub (repo the plan is built from). Team members already have ADO boards; approved tasks should just appear there.
- **AI provider:** GLM served via NVIDIA's free OpenAI-compatible API (NIM) for planning, chat-based edits, and risk explanations; NVIDIA embedding models on the same platform for brownfield RAG. Zero-cost, one API key.
- **Risk scoring philosophy:** Risk score is mostly deterministic — driven by real skill-coverage gaps between task requirements and team composition — with the LLM only writing the human-readable explanation, not inventing the score.
- **Demo intent:** Nail one clean end-to-end flow rather than breadth. Both greenfield and brownfield are supported, with greenfield as the primary demo path.

## Constraints

- **Timeline**: 2-day MVP — scope aggressively toward one working end-to-end flow.
- **Tech stack**: Python FastAPI + LangGraph backend, React frontend — LangGraph handles the branching and interrupt/resume human-review loop cleanly.
- **AI models**: GLM via NVIDIA free API (OpenAI-compatible) for LLM tasks; NVIDIA embeddings for RAG — free/open-source only, no paid models.
- **Auth**: None — single lead uses it locally; one shared ADO PAT for all API calls.
- **Integration**: One Azure DevOps project + one GitHub repo per run; ADO push is one-way.
- **Estimates**: Tasks estimated in hours/days (maps to ADO Original Estimate).

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastAPI + LangGraph backend, React frontend | LangGraph handles greenfield/brownfield branching + human-review interrupt/resume; React gives the interactive plan/diff UI room to breathe | — Pending |
| GLM via NVIDIA free API + NVIDIA embeddings | Zero-cost open models, one OpenAI-compatible API key covers LLM + RAG embeddings | — Pending |
| No auth, single shared ADO PAT, local single-lead use | 2-day MVP; auth/RBAC adds cost without proving core value | — Pending |
| Deterministic risk score + AI explanation only | Trustworthy, reproducible risk signal from real skill-coverage gaps; LLM never invents the number | — Pending |
| One-way ADO push (no sync-back) | Reduces surface area; proving the push is enough for the MVP | — Pending |
| Estimates in hours/days | Maps to ADO Original Estimate; concrete for capacity/load balancing | — Pending |
| Both repo types, greenfield-first demo | Supports the full branching story while keeping the headline demo simple | — Pending |
| Edit-via-chat previewed as a diff before accept | Keeps the human in control of LLM-driven plan changes | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-09 after initialization*
