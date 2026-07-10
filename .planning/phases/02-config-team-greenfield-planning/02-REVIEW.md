---
phase: 02-config-team-greenfield-planning
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 30
files_reviewed_list:
  - backend/.env.example
  - backend/app/db/team_roster.py
  - backend/app/graph/build.py
  - backend/app/graph/nodes/generate_plan.py
  - backend/app/graph/nodes/ingest_brownfield_stub.py
  - backend/app/graph/nodes/ingest_config.py
  - backend/app/graph/nodes/read_docs_greenfield.py
  - backend/app/graph/state.py
  - backend/app/main.py
  - backend/app/models/skills.py
  - backend/app/models/team.py
  - backend/app/routers/runs.py
  - backend/app/routers/team.py
  - backend/app/services/ado_client.py
  - backend/app/services/github_client.py
  - backend/app/services/llm.py
  - backend/pytest.ini
  - backend/requirements.txt
  - backend/tests/__init__.py
  - backend/tests/conftest.py
  - backend/tests/test_ado_smoketest.py
  - backend/tests/test_build_graph.py
  - backend/tests/test_generate_plan.py
  - backend/tests/test_github_client.py
  - backend/tests/test_ingest_config.py
  - backend/tests/test_team_roster.py
  - frontend/src/App.tsx
  - frontend/src/lib/teamClient.ts
  - frontend/src/pages/RunPage.tsx
  - frontend/src/pages/TeamPage.tsx
findings:
  critical: 3
  warning: 7
  info: 5
  total: 15
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 30
**Status:** issues_found

## Summary

Reviewed the config-intake, team-roster CRUD, greenfield doc-fetch, and GLM
plan-generation slice added in this phase, plus the frontend Run/Team pages
that consume it. The backend node/service layering is generally clean and
well-documented, and the ADO smoke-test / doc-fetch logic has solid unit test
coverage. However, there is a real cross-file contract break between the
backend (`routers/runs.py`) and the frontend (`lib/runClient.ts`,
`pages/RunPage.tsx`): the new `blocked_smoke_test_failed` status and the
`smoke_test`/`smoke_test_passed` fields this phase's `_derive_status` now
returns are completely invisible to the UI, so a blocked run silently looks
like it's stuck "running" forever with no explanation to the lead. There is
also a real bug in `generate_plan.py`'s short-circuit path (missing
`docs_text`/`blocked_reason`/`repo_mode` propagation causes `human_review` to
KeyError on the brownfield/no-docs path), and `ado_client.push_plan` is dead
code that is never invoked from the actually-wired `push_to_ado` node,
meaning all of the read-back verification logic this phase built has no
caller yet.

## Critical Issues

### CR-01: `generate_plan`'s blocked short-circuit drops required state, causing `human_review`/`push_to_ado` to KeyError downstream

**File:** `backend/app/graph/nodes/generate_plan.py:17-23`
**Issue:** When `state["blocked_reason"]` is set (brownfield-stub or no-docs
case), the node returns only `{"plan": Plan(epics=[])}`. Because LangGraph
merges returned dict keys into state (rather than replacing state), the
`blocked_reason` set by the upstream node does persist. However `human_review`
(`backend/app/graph/nodes/human_review.py:17`) does `state["plan"]` — that key
is present here so it will not crash — but the graph still proceeds to
`interrupt()` and, after resume, to `push_to_ado`, generating a fake
`awaiting_review` UI state and prompting the lead to "approve" an empty plan
for a run that is actually blocked (no docs found / brownfield unsupported).
There is no code path that treats `blocked_reason` as a terminal state after
`generate_plan` — `build.py`'s graph unconditionally wires
`generate_plan -> human_review -> push_to_ado` with no conditional edge
checking `blocked_reason`, unlike the smoke-test blocking gate which does have
a conditional edge. The result: a no-docs greenfield run or a brownfield run
sails through to "awaiting_review" with an empty plan and no indication to the
lead that planning never actually happened.
**Fix:** Add a conditional edge after `generate_plan` (mirroring
`route_after_config`'s pattern) that routes straight to `END` when
`blocked_reason` is set, bypassing `human_review`/`push_to_ado` entirely, and
surface `blocked_reason` in `_derive_status`'s response (similar to how
`smoke_test_passed` is surfaced) so the frontend can show why the run
stopped:
```python
def route_after_generate_plan(state: RunState) -> str:
    if state.get("blocked_reason") is not None:
        return "blocked"
    return "human_review"

builder.add_conditional_edges(
    "generate_plan",
    route_after_generate_plan,
    {"blocked": END, "human_review": "human_review"},
)
```

### CR-02: Frontend never surfaces `blocked_smoke_test_failed` status or smoke-test detail — blocked runs appear to hang indefinitely

**File:** `frontend/src/lib/runClient.ts:50`, `frontend/src/pages/RunPage.tsx:11,94`
**Issue:** `backend/app/routers/runs.py`'s `_derive_status` (this phase) added
a new status value `"blocked_smoke_test_failed"` plus `smoke_test` and
`smoke_test_passed` fields to every response. `RunResponse["status"]` in
`runClient.ts:50` only types `"running" | "awaiting_review" | "completed" |
"not_found"` — `blocked_smoke_test_failed` is not a member of this union, and
`smoke_test`/`smoke_test_passed` are not declared on the interface at all.
`RunPage.tsx`'s `isRunInProgress` (`line 94`) computes
`status !== "idle" && status !== "completed"`, so when the backend returns
`blocked_smoke_test_failed`, the UI treats it as "in progress," keeps the
Start button disabled, keeps polling forever (the `useEffect` on line 49 only
stops on `"completed"` or `"idle"`), and never shows the lead *why* the run is
stuck (e.g., "PAT auth rejected (401)"). This directly defeats D-03's
"not an opaque run blocked" requirement — the backend does the work to
produce a detailed reason, but the frontend throws it away.
**Fix:** Extend the shared type and add explicit UI handling:
```typescript
export interface RunResponse {
  run_id: string;
  status: "running" | "awaiting_review" | "completed" | "not_found" | "blocked_smoke_test_failed";
  plan: Plan | null;
  push_report: PushReport | null;
  smoke_test: { passed: boolean; checks: unknown[] } | null;
  smoke_test_passed: boolean | null;
}
```
And in `RunPage.tsx`, stop polling and render `smoke_test.checks` reasons when
`status === "blocked_smoke_test_failed"`.

### CR-03: `ado_client.push_plan`/`verify_work_item`/`_identity_matches` are entirely dead code — no caller exists, so the read-back verification this phase built is never exercised in production

**File:** `backend/app/services/ado_client.py:362-486`
**Issue:** `push_plan` (and the `verify_work_item` it depends on for
assignment/link verification) is never imported or called anywhere in the
reviewed codebase. `backend/app/graph/nodes/push_to_ado.py` (the actual graph
node wired into `build.py`) contains its own hand-rolled loop that
unconditionally marks every item `"not_implemented"` and never calls
`ado_client.push_plan`. This means the entire "verify every write, partial
success reporting" mechanism described in this file's docstring — which is
core to D-09/D-10/PUSH-03 — currently has zero effect on any real run. This
isn't just unused code; the smoke-test's `check_write_scope`
(`ado_client.py:277`) *does* get called via `run_smoke_test`, so it creates a
real throwaway ADO work item, but the actual plan-push path this phase's
`push_plan` was built for is orphaned. A reviewer reading `build.py`/
`push_to_ado.py` would reasonably conclude the ADO push is not implemented
yet, while `ado_client.py`'s extensive docstrings claim otherwise ("Every
write is followed by a read-back verification").
**Fix:** Either wire `push_to_ado.py` to call `ado_client.push_plan(plan)`
now (if that's this phase's intended scope), or, if `push_to_ado.py`'s real
implementation is explicitly deferred to a later phase/plan (as its docstring
states: "Plan 01-02 REPLACES this function's body"), add a `# TODO` /
tracking note in `ado_client.py` clarifying `push_plan` is not yet wired, so
this isn't mistaken for a shipped, tested code path. At minimum this needs a
test exercising `push_plan` end-to-end (currently absent) since it's
production-shaped, non-trivial logic with no coverage at all.

## Warnings

### WR-01: `ingest_config` reads `LEAD_EMAIL` and passes it unvalidated into `run_smoke_test`/`System.AssignedTo`

**File:** `backend/app/graph/nodes/ingest_config.py:23`
**Issue:** `lead_email = os.environ.get("LEAD_EMAIL", "")` — if unset, this is
an empty string, which then flows into `ado_client.check_write_scope`'s
`System.AssignedTo` field (`ado_client.py:290`) and into `verify_work_item`'s
`expected_assignee` comparison. An empty-string assignee will likely create an
unassigned ADO work item and then report `assignment_unresolved` opaquely
rather than a clear "LEAD_EMAIL not configured" error, making the failure
mode confusing to a lead who forgot to set `.env`.
**Fix:** Fail fast with a clear message when `LEAD_EMAIL` is missing/empty,
either in `ingest_config` (return a distinct `blocked_reason`) or on app
startup in `main.py`'s lifespan, before any smoke test runs.

### WR-02: `TeamMember.id` is trusted from the request body and silently ignored on create/update, which is confusing but not enforced

**File:** `backend/app/routers/team.py:22-32`, `backend/app/models/team.py:24`
**Issue:** `create_team_member`/`update_team_member` accept a full
`TeamMember` (including client-supplied `id`) but `team_roster.create_member`
always generates a fresh server-side `uuid`, and `update_member` uses the
path-param `member_id`, not `member.id`. If a client sends a mismatched `id`
in the body of a PUT, it is silently discarded with no validation error —
which is intentional-looking but undocumented, and could mask a client bug
where the wrong ID was serialized.
**Fix:** Either strip `id` from the request model for create/update (use a
separate `TeamMemberInput` model without `id`) or explicitly validate that
`member.id in (None, member_id)` on update and reject mismatches with a 400.

### WR-03: `generate_plan_with_repair` calls a blocking synchronous `structured_llm.invoke` from inside an `async def generate_plan` node without `await`/executor offload

**File:** `backend/app/services/llm.py:112`, `backend/app/graph/nodes/generate_plan.py:17-23`
**Issue:** `generate_plan` is `async def` and is invoked inside FastAPI's
async event loop (via `graph.ainvoke`), but `generate_plan_with_repair` calls
`structured_llm.invoke(prompt)` synchronously — a blocking network call
(potentially up to 3 attempts). This blocks the entire asyncio event loop for
the duration of each LLM round-trip, stalling all other concurrent requests
(e.g., `/team` CRUD, other runs' polling) on this single-process FastAPI app.
**Fix:** Use `await structured_llm.ainvoke(prompt)` (LangChain's async
invoke) inside `generate_plan_with_repair`, or run the sync call in a thread
via `asyncio.to_thread(...)`.

### WR-04: `_match_doc_paths` docstring/comment claims are subtly wrong for mixed-case `docs/` prefixes combined with case folding creating false negatives elsewhere

**File:** `backend/app/services/github_client.py:22-40`
**Issue:** Minor but worth flagging: `is_root_readme` checks
`lower.startswith("readme")`, which will also match unrelated root files like
`readme-old.txt` or `READMETEMPLATE.docx` (i.e., anything whose name starts
with "readme", not just README/README.md). Given `fetch_greenfield_docs` then
tries to fetch and decode these as UTF-8 text, a binary `readme.pdf` at repo
root would match and either decode as garbage (silently, since
`errors="replace"` is used) or waste context budget on binary noise.
**Fix:** Tighten the match to `lower in ("readme", "readme.md", "readme.txt", "readme.rst")` or at least require a recognized extension/no-extension, not just a prefix.

### WR-05: `verify_work_item`'s `link_resolved=False` case still leaves `status="link_failed"` reported even though the item and assignment succeeded — but `push_plan`'s overall `all_succeeded` conflates all failure types

**File:** `backend/app/services/ado_client.py:484`
**Issue:** `all_succeeded = all(item.status == "created" for item in items)` —
this correctly requires every item including the epic to be `"created"`. Not
a bug per se, but combined with CR-03 (dead code, no test coverage), this
logic path has never been exercised against a real or mocked multi-item plan,
so its correctness is unverified. Flagging as a warning since it's
untested production logic, not merely unused.
**Fix:** Add unit tests for `push_plan` covering: full success, epic
create-failure cascading to all child tasks, task create-failure,
assignment-unresolved, and link-failed cases — before this code is relied
upon.

### WR-06: `check_expiry_best_effort` swallows all non-200/non-JSON responses including transient network errors as "passed": true silently

**File:** `backend/app/services/ado_client.py:299-339`
**Issue:** This is documented as intentional ("never fails the overall
smoke-test"), but the implementation also swallows genuine bugs (e.g., a
malformed URL, a DNS failure unrelated to the PAT) into the same "unknown"
bucket as "this ADO org doesn't support PAT introspection." A lead debugging
a broken network setup gets no signal distinguishing "your PAT probably
doesn't support this optional check" from "your network/DNS is broken,"
since both produce identical `{"passed": True, "reason": "unknown (best-effort check unavailable)"}`.
**Fix:** Low priority given this is explicitly best-effort — but consider
logging the underlying exception server-side (not surfaced to the API
response) so operators can distinguish these cases if the demo breaks in an
unexpected way.

### WR-07: `RunPage.tsx` approve button silently does nothing (early return) if the client's local `status` state is stale, without informing the user why

**File:** `frontend/src/pages/RunPage.tsx:77-92`
**Issue:** `handleApprove`'s guard `if (!runId || status !== "awaiting_review") return;` is a defensive no-op with no user feedback. Since the button is only rendered when `status === "awaiting_review"` (line 128), this guard should be unreachable in practice — but if it *does* trigger (e.g., a stale render between poll ticks), the click is silently swallowed with zero error message, which will look like a broken button to the lead.
**Fix:** If this branch is truly believed unreachable, consider removing the guard's silent return and instead let `approveRun` fail server-side with a clear error surfaced via the existing `setError` path — that's more debuggable than a silent no-op.

## Info

### IN-01: `_db_path()` is duplicated verbatim between `team_roster.py` and `run_metadata.py`

**File:** `backend/app/db/team_roster.py:20-21`
**Issue:** Both modules define an identical `_db_path()` helper reading
`CHECKPOINT_DB_PATH`. Minor duplication given both modules explicitly avoid
importing each other (team_roster.py's docstring says it must never import
from `app.graph.*`, but nothing prevents a shared `app.db` helper module).
**Fix:** Extract to `app/db/_shared.py` or `app/db/__init__.py` and import
from both.

### IN-02: `TeamMember` `skills` field has no length/emptiness constraint

**File:** `backend/app/models/team.py:28`
**Issue:** `skills: str` accepts an empty string with no validation, silently
producing team members with no skill information that later reconciliation
logic (Phase 3, per the docstring) will need to handle as a degenerate case.
**Fix:** Not urgent for MVP; consider `Field(min_length=1)` if empty skills
should be disallowed, or explicitly document that empty is valid.

### IN-03: `requirements.txt` omits explicit `langchain-core` pin despite `STACK.md`/`CLAUDE.md` calling out pinning it explicitly to avoid resolver drift

**File:** `backend/requirements.txt:1-11`
**Issue:** The stack notes state: "Pulled in transitively by langchain-openai
and langgraph; pin explicitly to avoid resolver surprises," but no
`langchain-core` line appears in `requirements.txt`. Also `chromadb`/
`langchain-chroma`/`langchain-text-splitters`/`GitPython` are absent (fine,
since brownfield RAG is out of scope for this phase per `ingest_brownfield_stub.py`),
but `langchain-core`'s absence contradicts the explicit stack guidance for a
dependency this phase does exercise (`generate_plan.py` uses `langchain-openai`).
**Fix:** Add an explicit `langchain-core==1.4.x` pin matching whatever
`langchain-openai==1.3.4` resolves to, to avoid silent version drift on a
future `pip install`.

### IN-04: `tests/__init__.py` is an empty file with no content

**File:** `backend/tests/__init__.py:1`
**Issue:** Present but empty — not a defect, just confirming there's no
shared test-package setup logic here; flagged only because it was in the
required-reading list and is otherwise unremarkable.
**Fix:** None needed.

### IN-05: `PushResultItem.status` includes `"not_implemented"` as a permanent literal member, coupling the shared schema to a temporary stub state

**File:** `backend/app/models/plan.py:37-43`
**Issue:** The shared `Plan`/`PushReport` schema (explicitly called out as
the single source of truth across LangGraph nodes and API responses) has a
`"not_implemented"` status literal baked in to accommodate `push_to_ado.py`'s
current stub behavior. Once `push_to_ado.py` is replaced with a real
implementation (per its own docstring, this is expected), this literal
becomes permanent dead vocabulary in the shared schema unless explicitly
cleaned up.
**Fix:** Track removal of `"not_implemented"` from the `Literal` once
`push_to_ado.py` is wired to `ado_client.push_plan` (see CR-03).

---

_Reviewed: 2026-07-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
