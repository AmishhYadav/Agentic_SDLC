---
phase: 02-config-team-greenfield-planning
plan: 04
subsystem: api
tags: [langgraph, langchain-openai, glm-nim, structured-output, plan-generation, skill-taxonomy]

# Dependency graph
requires:
  - phase: 02-config-team-greenfield-planning
    plan: 03
    provides: "route_after_config conditional edge, read_docs_greenfield/ingest_brownfield_stub nodes converging into stub_plan, RunState.docs_text/blocked_reason"
provides:
  - "SKILL_TAXONOMY — 15-item fixed skill list (backend/app/models/skills.py), canonical import location for Phase 3 skill-matching"
  - "validate_skill_tags(plan, skill_taxonomy=None) — post-parse taxonomy enforcement, raises ValueError on violation"
  - "build_chat_llm() / generate_plan_with_repair() (backend/app/services/llm.py) — ChatOpenAI factory + bounded validate-then-repair structured-output loop"
  - "generate_plan graph node — replaces stub_plan, short-circuits on blocked_reason, otherwise produces a real 2-5 epic / 2-6 task Plan via GLM"
affects: []

# Tech tracking
tech-stack:
  added: [langchain-openai==1.3.4]
  patterns:
    - "Hand-rolled validate-then-repair retry loop over with_structured_output(Plan, method=\"function_calling\", include_raw=True) — OutputFixingParser is removed from current langchain-core, per RESEARCH.md"
    - "Taxonomy enforcement kept as a post-parse ValueError check (approach (b) from Pitfall 4) rather than a Literal type on the shared Task model, to avoid invasiveness to push_to_ado.py/frontend consumers"
    - "generate_plan checks blocked_reason first and never calls the LLM in the short-circuit branch — mirrors read_docs_greenfield/ingest_brownfield_stub's own env-read-fresh, no-side-effects-before-checkpoint-safe pattern"

key-files:
  created:
    - backend/app/models/skills.py
    - backend/app/services/llm.py
    - backend/app/graph/nodes/generate_plan.py
    - backend/tests/test_generate_plan.py
  modified:
    - backend/app/graph/build.py
    - backend/app/graph/nodes/ingest_config.py
    - backend/tests/test_build_graph.py
    - backend/requirements.txt
    - backend/.env.example
    - frontend/src/pages/RunPage.tsx
  deleted:
    - backend/app/graph/nodes/stub_plan.py

key-decisions:
  - "Task.skill_tag stays str | None on the shared Plan schema (Pitfall 4 approach (b), not a Literal type) — taxonomy compliance is enforced by a standalone validate_skill_tags() call inside the repair loop, treated exactly like a schema validation failure; avoids invasiveness to push_to_ado.py and the frontend Task interface"
  - "validate_skill_tags() takes an optional skill_taxonomy parameter (defaults to the module constant) so services/llm.py always validates against the exact same list it used to build the prompt"
  - "generate_plan_with_repair uses same-method (function_calling) + repair-prompt retry across all attempts, per 02-RESEARCH.md's resolved Open Question 2 — no method-switching to json_mode on retry for this MVP"
  - "test_build_graph.py's greenfield integration test now mocks generate_plan.build_chat_llm/generate_plan_with_repair so the compiled-graph test stays fast and network-free; the brownfield integration test needed no change since it already exercises generate_plan's blocked_reason short-circuit without touching the LLM"

requirements-completed: [PLAN-01, PLAN-02, PLAN-03, PLAN-04]

# Metrics
duration: 35min
completed: 2026-07-10
---

# Phase 2 Plan 4: Real GLM-Backed Plan Generation Summary

**Replaced the hardcoded `stub_plan` node with a real GLM-via-NVIDIA-NIM plan generator: every task now carries a skill tag from a fixed 15-item taxonomy and an hours estimate, plan size is steered to 2-5 epics / 2-6 tasks via prompt, malformed/taxonomy-violating output triggers a bounded validate-then-repair retry loop that fails loudly (RuntimeError) rather than emitting broken data, and `suggested_assignee` is force-blanked to `""` on every task regardless of what the LLM returns.**

## Performance

- **Duration:** ~35 min
- **Completed:** 2026-07-10
- **Tasks:** 3 completed (Task 0, Task 1 TDD, Task 2)
- **Files modified:** 11 (4 created, 6 modified, 1 deleted — excluding SUMMARY/STATE/ROADMAP)

## Accomplishments

- Created `backend/app/models/skills.py` with `SKILL_TAXONOMY` (15 items, within the D-10 12-20 range) and `validate_skill_tags()` — the single canonical taxonomy source, importable by both plan generation and future Phase 3 skill-matching
- Built `backend/app/services/llm.py`: `build_chat_llm()` (ChatOpenAI factory at NVIDIA NIM's `base_url`, model/key read fresh from env, `max_tokens=8192` per Pitfall 3's truncation-avoidance guidance) and `generate_plan_with_repair()` (validate-then-repair loop over `with_structured_output(Plan, method="function_calling", include_raw=True)`)
- Wrote 5 TDD tests (`test_generate_plan.py`) covering first-try success, parse-error retry, taxonomy-violation retry, exhausted-retries `RuntimeError`, and the `suggested_assignee=""` defensive force-blank — RED confirmed (ModuleNotFoundError) before GREEN implementation
- Created `backend/app/graph/nodes/generate_plan.py`, replacing `stub_plan` in `build.py`'s edge wiring (same positions: `read_docs_greenfield`/`ingest_brownfield_stub` -> `generate_plan` -> `human_review`); deleted `stub_plan.py` as dead code
- Updated `frontend/src/pages/RunPage.tsx` to render `task.skill_tag` next to the existing estimate text
- Fixed the pre-existing `test_build_graph.py` greenfield integration test to mock `generate_plan`'s LLM call (it now traverses the real node and would otherwise require live NVIDIA credentials)

## Task Commits

1. **Task 0: Skill taxonomy constant + taxonomy enforcement helper** - `68bf581`
2. **Task 1: LLM service — ChatOpenAI factory + validate-then-repair loop (TDD)** - `bdfffed` (test, RED) then `87ce35a` (feat, GREEN)
3. **Task 2: Wire generate_plan into the graph, remove stub_plan, surface skill_tag** - `a7e72fe`

**Plan metadata:** _pending — this SUMMARY's own commit_

_Note: Task 1 was tdd="true" and followed RED/GREEN — no REFACTOR commit was needed._

## Files Created/Modified

- `backend/app/models/skills.py` - `SKILL_TAXONOMY` constant (15 items) + `validate_skill_tags(plan, skill_taxonomy=None)`
- `backend/app/services/llm.py` - `build_chat_llm()`, `build_plan_prompt()`, `build_repair_prompt()`, `generate_plan_with_repair()`
- `backend/app/graph/nodes/generate_plan.py` - real plan-generation node, checks `blocked_reason` first
- `backend/tests/test_generate_plan.py` - 5 unit tests, mocked `structured_llm.invoke`, no network calls
- `backend/app/graph/build.py` - `generate_plan` registered/wired in place of `stub_plan`
- `backend/app/graph/nodes/ingest_config.py` - docstring reference updated (`stub_plan` -> `generate_plan`)
- `backend/tests/test_build_graph.py` - greenfield integration test now mocks `generate_plan`'s LLM call
- `backend/requirements.txt` - added `langchain-openai==1.3.4` (verified current via `pip index versions`)
- `backend/.env.example` - added `NVIDIA_API_KEY=` and `NVIDIA_CHAT_MODEL=z-ai/glm-5.2` placeholders
- `frontend/src/pages/RunPage.tsx` - task list now renders `— skill: {task.skill_tag ?? "none"}`
- `backend/app/graph/nodes/stub_plan.py` - deleted (unwired, dead code)

## Decisions Made

- Chose Pitfall 4's approach (b) over a `Literal[tuple(SKILL_TAXONOMY)]` type change to the shared `Task.skill_tag` field — kept `str | None` on the shared schema to avoid invasiveness to `push_to_ado.py` and the frontend `Task` interface (which already declares `skill_tag: string | null`); taxonomy compliance is enforced as an explicit post-parse `ValueError` check in the repair loop, functionally equivalent to a schema validation failure for retry purposes.
- `validate_skill_tags()` accepts an optional `skill_taxonomy` parameter (defaulting to the module constant) so `services/llm.py`'s repair loop always validates against the exact same list threaded into the prompt, rather than silently relying on the global default staying in sync.
- Confirmed `langchain-openai==1.3.4` was already the installed and current top PyPI version (`pip index versions` — no drift from 02-RESEARCH.md's one-day-prior finding).
- No method-switching between `function_calling` and `json_mode` across repair attempts — followed 02-RESEARCH.md's resolved Open Question 2, using same-method + repair-prompt retry for MVP simplicity.
- Fixed `test_build_graph.py`'s pre-existing greenfield integration test (Rule 1 — this plan's own change to `build.py` made that test traverse the new real `generate_plan` node, which would otherwise attempt a live NVIDIA API call and fail with `KeyError: 'NVIDIA_CHAT_MODEL'` in CI/test environments without credentials). Mocked `generate_plan.build_chat_llm`/`generate_plan.generate_plan_with_repair` to keep the test fast and network-free. The brownfield integration test needed no change — it already exercises `generate_plan`'s `blocked_reason` short-circuit for free, confirming that code path never touches the LLM.
- Added `NVIDIA_API_KEY`/`NVIDIA_CHAT_MODEL` to the local (gitignored) `.env` in addition to `.env.example`, since the app cannot start `generate_plan` for a real run without them — left both blank/placeholder as no live key was available in this environment.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing greenfield integration test broken by this plan's own graph wiring change**
- **Found during:** Task 2 verification (`pytest -x`)
- **Issue:** `test_build_graph.py::test_compiled_graph_reaches_read_docs_greenfield_for_greenfield_state` compiles and invokes the real graph end-to-end; before this plan it terminated at `stub_plan` (no LLM call). After wiring `generate_plan` in stub_plan's place, the same test now reaches `generate_plan`'s real-LLM branch and fails with `KeyError: 'NVIDIA_CHAT_MODEL'` since no NVIDIA credentials are configured in the test environment.
- **Fix:** Patched `app.graph.nodes.generate_plan.build_chat_llm` and `app.graph.nodes.generate_plan.generate_plan_with_repair` in that one test to return a stub `Plan(epics=[])` without touching the network, consistent with how the test already mocks `ado_client.run_smoke_test` and `github_client.fetch_greenfield_docs`.
- **Files modified:** `backend/tests/test_build_graph.py`
- **Commit:** `a7e72fe`

## Issues Encountered

None blocking. All behaviors specified in the plan's `<behavior>`/`<action>` sections were implemented and verified as described.

## Verification Evidence

- `cd backend && pytest tests/test_generate_plan.py -x -v` -> 5 passed (first-try success, parse-error retry, taxonomy-violation retry, exhausted-retries RuntimeError, suggested_assignee force-blank)
- `cd backend && pytest -x` (full suite) -> 40 passed, no regressions
- `grep -c "SKILL_TAXONOMY" backend/app/models/skills.py` -> 4 (>= 1); `len(SKILL_TAXONOMY)` -> 15 (within 12-20)
- `cd backend && .venv/bin/python -c "from app.models.skills import SKILL_TAXONOMY; from app.models.plan import Task; print(len(SKILL_TAXONOMY))"` -> 15, no ImportError
- Manually constructed a `Plan` with a task `skill_tag="NotARealSkill"` and confirmed `validate_skill_tags()` raises `ValueError` listing the offending task
- `grep -c "stub_plan" backend/app/graph/build.py` -> 0
- `grep -c "generate_plan" backend/app/graph/build.py` -> 6 (>= 2)
- `test -f backend/app/graph/nodes/stub_plan.py` -> file removed
- `grep -n "skill_tag" frontend/src/pages/RunPage.tsx` -> match on line 119
- `cd backend && .venv/bin/python -c "from app.graph.build import build_graph; build_graph()"` -> "graph builds OK", no import errors
- `cd frontend && node_modules/.bin/tsc --noEmit -p .` -> no output, no type errors

## TDD Gate Compliance

Task 1 (tdd="true"): RED commit `bdfffed` (`test(02-04): add failing tests for generate_plan_with_repair loop` — collection error, `ModuleNotFoundError: No module named 'app.services.llm'`) precedes GREEN commit `87ce35a` (`feat(02-04): implement generate_plan_with_repair LLM service (GREEN)` — all 5 tests passing). Gate sequence satisfied. No REFACTOR commit needed.

## Known Stubs

None. `stub_plan.py` (Phase 1's hardcoded plan generator) is fully removed and replaced by real plan generation. `ingest_brownfield_stub.py` remains an intentional, documented Phase 5 placeholder (unchanged by this plan, already flagged in 02-03-SUMMARY.md's Known Stubs).

**Manual live-LLM verification not performed in this session:** no `NVIDIA_API_KEY` was available in this environment, so `generate_plan_with_repair` was verified exclusively via mocked unit tests (5/5 passing) and the compiled-graph integration test (mocked LLM boundary). The plan's own `<verification>` section flags this as requiring "a valid NVIDIA_API_KEY/NVIDIA_CHAT_MODEL and a real greenfield GITHUB_REPO with docs" — this is a documented follow-up for whoever runs the Phase 2 demo with real credentials, not a defect in this plan's implementation. All code paths (prompt construction, structured-output invocation, retry/repair, taxonomy validation, force-blank) are covered by mocked tests; only the actual GLM/NIM network round-trip and its real-world malformed-JSON failure mode (Pitfall 3) remain unverified against the live API.

## Threat Flags

None beyond what the plan's own `<threat_model>` already anticipated and mitigated:
- T-02-09 (prompt injection via malicious repo docs) — mitigated by `build_plan_prompt`'s explicit `--- PROJECT DOCS ---`/`--- END PROJECT DOCS ---` delimiters and system-message instruction to treat docs as reference material.
- T-02-10 (malformed/adversarial LLM tool-call output) — mitigated by the validate-then-repair retry loop with bounded attempts and a hard `RuntimeError` failure.
- T-02-11 (NVIDIA_API_KEY disclosure) — mitigated by reading fresh from `os.environ` inside `build_chat_llm`, never logged or echoed to the frontend.

## Next Steps

- A live NVIDIA API key + `NVIDIA_CHAT_MODEL` value must be confirmed against `GET https://integrate.api.nvidia.com/v1/models` (per STACK.md's CRITICAL FLAG) before the Phase 2 demo, and a real greenfield `GITHUB_REPO` with docs run end-to-end to confirm the manual verification criteria in this plan's `<verification>` section (2-5 epics, taxonomy-valid skill tags, positive estimates, empty `suggested_assignee`).
- Phase 3 owns populating `suggested_assignee` (skill/load-aware assignment) and reconciling team members' free-text skills (D-06) against `SKILL_TAXONOMY` — both are explicitly deferred, not started here.

## Self-Check: PASSED

All 4 created files (`backend/app/models/skills.py`, `backend/app/services/llm.py`, `backend/app/graph/nodes/generate_plan.py`, `backend/tests/test_generate_plan.py`) confirmed present on disk; `backend/app/graph/nodes/stub_plan.py` confirmed removed; all 4 task commit hashes (`68bf581`, `bdfffed`, `87ce35a`, `a7e72fe`) confirmed in `git log --oneline`.
