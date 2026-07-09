# Pitfalls Research

**Domain:** AI-powered project planning & onboarding dashboard — FastAPI + LangGraph + React, Azure DevOps + GitHub integration, GLM via NVIDIA free NIM API, code RAG, 2-day MVP
**Researched:** 2026-07-09
**Confidence:** MEDIUM-HIGH (LangGraph and ADO REST API findings verified against official docs/GitHub issues; NVIDIA NIM free-tier limits are best-effort from community/forum reports and change without notice — verify against your actual key before committing to a rate budget)

## Critical Pitfalls

### Pitfall 1: LangGraph re-executes the entire node on resume, double-firing side effects

**What goes wrong:**
When `interrupt()` is called partway through a node, LangGraph does not resume "mid-function." On resume it restores the last checkpoint and **re-runs the node from the top**. Any code before the `interrupt()` call — LLM calls, DB writes, ADO API calls — runs again. Local variables computed before the interrupt are not preserved in the checkpoint, so there's no way for the node to know "I already did this part." The canonical failure case: a node that generates the plan, calls `interrupt()` to show it to the user, then on resume regenerates the plan (extra LLM cost, possibly a *different* plan) or, worse, if a node mixes an auto-executing side effect with an approval gate, the side effect (e.g., an ADO work item creation) fires twice.

**Why it happens:**
LangGraph's durable-execution model treats a node as replay-from-start on resume; this is documented behavior, not a bug, but it's a non-obvious mental model shift from "the function pauses and continues" to "the function starts over and skips already-satisfied interrupts."

**How to avoid:**
- Never put non-idempotent side effects (ADO writes, plan-mutation, DB inserts) in the same node as an `interrupt()` call.
- Structure the graph so `interrupt()` sits in its own dedicated node whose only job is to pause and return the human's decision via `Command(resume=...)`.
- Do heavy/expensive work (plan generation, RAG retrieval) in a node *before* the interrupt node, persist the result into graph state, and have the interrupt node only read state — never recompute.
- Do the actual ADO push in a node *after* the resume, gated so it only runs once (check a state flag like `pushed: bool` before writing).
- If a node truly must do work and then pause, make that work idempotent (upsert semantics) rather than insert/append.

**Warning signs:**
- Duplicate ADO work items appearing after a single approval click.
- Plan content changing between "what the user approved" and "what got pushed."
- LLM cost/latency spikes that don't match the number of user-visible plan generations.

**Phase to address:**
Graph design phase (before any node writes code) — this is an architecture decision, not a bug fix applied later. Revisit explicitly when adding the ADO-push node and the chat-edit node.

---

### Pitfall 2: Wrong checkpointer choice loses all in-progress plans on backend restart

**What goes wrong:**
`MemorySaver` (the default/easiest checkpointer) keeps all thread state in process RAM. Any FastAPI restart (crash, hot-reload during dev, `uvicorn --reload` picking up a file change) wipes every in-flight interrupt — the user's plan-in-review vanishes and the graph cannot resume, because the thread_id no longer maps to any state.

**Why it happens:**
`MemorySaver` is what every LangGraph tutorial uses because it requires zero setup, and for a 2-day MVP it's tempting to leave it. But this project's core loop is "generate plan → human reviews/edits over potentially several minutes → approve → push" — exactly the workflow most vulnerable to a mid-review restart, and `uvicorn --reload` will restart on every backend file save during active development.

**How to avoid:**
Use `SqliteSaver` (sync) or `AsyncSqliteSaver` (async, matches FastAPI's async handlers) pointed at a local file from day one — it's nearly as easy to wire up as `MemorySaver` and survives process restarts. Skip Postgres; this is local/single-user and SQLite's file-locking limitation only matters under concurrent writes, which won't happen with one lead running one session. Do not use `MemorySaver` even "temporarily" — swapping checkpointers mid-project risks losing test state and is a 10-minute fix to do right the first time.

**Warning signs:**
- "My plan disappeared after I edited a file and the server reloaded."
- Resume calls returning "no checkpoint found for thread_id" after any backend restart.

**Phase to address:**
Initial LangGraph scaffolding / graph setup phase — pick `AsyncSqliteSaver` before writing the first node.

---

### Pitfall 3: Interrupt payload and React streaming get out of sync — client renders stale or wrong review state

**What goes wrong:**
The interrupt pattern requires the backend to (a) run the graph until `interrupt()`, (b) return the interrupt payload to the client (often via SSE or a polling `GET /thread/{id}/state`), (c) receive the human's decision via a separate `POST /resume`, and (d) continue streaming. It's easy to build this so the client's "resume" button fires before the client has actually received/rendered the full interrupt payload, or so a second interrupt in the same run gets matched to the wrong pending UI state (LangGraph matches resume values to interrupts by order within the node when there are multiple `interrupt()` calls — the ordering is a subtle contract, not enforced by types).

**Why it happens:**
SSE and polling both introduce a race between "graph state changed on the backend" and "client is displaying up-to-date state." Multi-interrupt nodes (e.g., approve plan interrupt AND, later, approve individual diff-edit interrupts within the same thread) make positional resume-matching fragile.

**How to avoid:**
- Use exactly one `interrupt()` per node (Pitfall 1's fix already forces this) so there is never ordering ambiguity to reason about.
- After `interrupt()` returns to the client, immediately fetch full graph state (`GET` the checkpoint) rather than trusting only the streamed event — treat the stream as a notification, not the source of truth.
- Disable the "approve/resume" button in the UI until the client has confirmed (via a state fetch) that the thread is actually paused at the expected interrupt — don't just enable it as soon as an SSE event arrives.
- Use the `thread_id` as the single correlation key for every request; never let the frontend guess or reconstruct it.

**Warning signs:**
- "Approve" click does nothing or resumes the wrong step.
- UI shows the plan but the backend is still mid-generation (race between streaming tokens and interrupt payload).

**Phase to address:**
Frontend-backend contract phase, when building the review/diff UI — define the state-fetch-after-interrupt pattern before wiring buttons.

---

### Pitfall 4: JSON-Patch document errors on ADO work item creation — wrong content-type, wrong field references, malformed relations

**What goes wrong:**
The ADO work item create/update API requires `Content-Type: application/json-patch+json` (not plain `application/json`) and a body that's an **array** of patch operations (`{op, path, value}`), not a flat object. Common failures: using display names instead of reference names (`"Title"` instead of `/fields/System.Title`), forgetting the leading slash in `path`, sending a JSON object instead of an array, and — for parent/child links — getting the relation direction backwards (`System.LinkTypes.Hierarchy-Reverse` on the **child** work item points to its parent; `Hierarchy-Forward` on the parent points to children). Getting this backwards silently creates the link in the wrong direction or a duplicate/orphaned relation.

**Why it happens:**
JSON-Patch is an unusual format most engineers haven't used outside ADO/similar APIs, and the hierarchy link naming is genuinely confusing (Reverse = "points up to parent" is not intuitive).

**How to avoid:**
- Build a small typed helper (`build_patch(op, path, value)`) and a `link_child_to_parent(child_id, parent_id)` helper that always emits `Hierarchy-Reverse` on the child — write one unit test that creates an epic + task and asserts the parent/child query returns correctly, before wiring this into the main flow.
- Always set `Content-Type: application/json-patch+json` explicitly; don't rely on library defaults.
- Use `System.Title`, `System.Description`, `System.AssignedTo`, `Microsoft.VSTS.Scheduling.OriginalEstimate`, `System.AreaPath`, `System.IterationPath` — verify each reference name against the target ADO process template (Agile/Scrum/CMMI use different field sets for estimate fields specifically — `Microsoft.VSTS.Scheduling.OriginalEstimate` vs others).
- Create the parent (epic) first, capture its returned `id`, then create children referencing that `id` in the same or a follow-up PATCH — don't try to create both in one batch unless using the batch API correctly.

**Warning signs:**
- HTTP 400 "value is not valid" errors with no clear message about which field.
- Work items created but not appearing nested under the epic in ADO Boards.
- 203 response with an HTML login page body instead of JSON — this means the PAT is invalid/expired, not a JSON-Patch problem; always check response `Content-Type` before parsing as JSON.

**Phase to address:**
ADO integration phase — build and test the JSON-Patch helper + hierarchy link helper against a real (test) ADO project before wiring into the plan-approval flow.

---

### Pitfall 5: Assigning work items by email fails silently or assigns the wrong person

**What goes wrong:**
`System.AssignedTo` accepts an email/UPN string in the JSON-Patch value, and ADO resolves it server-side to an identity. This resolution can fail silently (work item saves but assignment is blank) if the email doesn't exactly match an ADO organization member, if the person hasn't been added to the ADO project/org yet, or if there's a display-name collision. There is no client-side validation — you only find out by reading the work item back after creation.

**Why it happens:**
The convenience of "just send an email string" hides the fact that ADO requires exact identity resolution against org membership, and team members entered into this tool (name/designation/skills) are **not** guaranteed to already exist as ADO identities.

**How to avoid:**
- Before the MVP demo, confirm every team member email entered into the tool actually exists as a member of the target ADO organization/project (this is a manual precondition worth stating explicitly in your setup docs, not something the tool can silently fix).
- After creating/assigning a work item, read the field back in the response body (`fields/System.AssignedTo`) and confirm it resolved to the expected identity — don't assume 200 OK means assignment succeeded as intended.
- Surface unresolved assignments as a visible error in the UI rather than a silent partial success.

**Warning signs:**
- Work items pushed successfully (200/201) but appear "Unassigned" in ADO Boards.
- Assignment appears to go to a different person with a similar name.

**Phase to address:**
ADO push phase — add a post-write verification read as part of the push flow, and document the "team members must exist in ADO" precondition during team-setup phase.

---

### Pitfall 6: Single shared PAT scope too narrow (or too broad) and PAT expiry breaks the demo mid-flow

**What goes wrong:**
A single shared PAT is used for all ADO calls, so its scopes must cover work item read/write, and (if pulling process/area/iteration metadata to populate valid paths) project/team read too. Two common failures: (a) PAT created with only `vso.work` (read) instead of `vso.work_write`, so pushes fail with 401/403 after everything else works in testing; (b) PAT created with a short default expiry (ADO defaults often to 30 or 90 days, but org policy can force much shorter) that silently expires between build and demo day, returning a 203 HTML-login-page response that looks like a network error rather than an auth error.

**Why it happens:**
Scope selection during PAT creation is easy to get wrong (the ADO PAT creation UI groups many scopes and it's easy to pick "read" when "read & write" was needed), and expiry dates are easy to forget on a token created early in a 2-day sprint.

**How to avoid:**
- Create the PAT with explicit scopes: Work Items (Read & Write), plus Project and Team (Read) if you'll be resolving area/iteration paths dynamically. Avoid "Full access" (unnecessary blast radius) but don't under-scope either.
- Set PAT expiry to cover the full MVP window plus buffer for the demo — don't use a 7-day default that was already ticking before day 1.
- On startup, do a cheap authenticated smoke-test call (e.g., `GET _apis/projects/{project}`) and fail fast with a clear "PAT invalid/expired/wrong scope" message rather than letting the first real user-facing failure be a cryptic push error during the demo.
- Always check response `Content-Type: application/json` before parsing — a 203 with HTML body is ADO's way of saying "your PAT didn't authenticate," and naively parsing it as JSON throws a confusing exception.

**Warning signs:**
- Everything works in local dev, then fails right before/during demo with no code changes.
- JSON parse errors on what should be a work item response.

**Phase to address:**
Setup/configuration phase — bake the smoke-test call into the app's startup or "connect ADO project" step, not an afterthought.

---

### Pitfall 7: Bulk-pushing tasks hits ADO rate limiting because requests fire in parallel

**What goes wrong:**
A plan can easily contain 20-50+ tasks across several epics. Pushing them all with `asyncio.gather()` or unthrottled parallel requests can exhaust the ADO throughput budget (global limit ~200 TSTUs per sliding 5-minute window) and trigger HTTP 429 throttling, especially since epic creation, task creation, and hierarchy-link updates are each separate calls (potentially 2-3x the task count in total requests).

**Why it happens:**
Async Python makes "just fire them all at once" the path of least resistance, and this looks fine at low task counts in testing but degrades unpredictably as demo plans get larger or as parent/child link calls stack on top of create calls.

**How to avoid:**
- Push sequentially or with a small concurrency cap (5-10 concurrent requests max) using a semaphore, not unbounded `gather()`.
- Implement exponential backoff on 429 responses (respect any `Retry-After` header if present) rather than failing the whole push on first throttle.
- Consider the ADO work item **batch API** (`_apis/wit/$batch`) if pushing many items — this reduces total request count and gives you a single failure surface to handle, though it adds complexity that may not be worth it for a 2-day MVP's expected task counts (in which case, just throttle).

**Warning signs:**
- Push works for small test plans (2-3 tasks) but partially fails for realistic plans (20+ tasks).
- Intermittent 429s that "go away" if you retry the whole push.

**Phase to address:**
ADO push phase — implement the concurrency cap and backoff as part of the initial push implementation, not as a fix after a failed demo.

---

### Pitfall 8: RAG over a large/unfiltered repo blows the time and token budget

**What goes wrong:**
Cloning a repo and naively walking every file to chunk and embed will include `node_modules`, `.git`, build artifacts, binaries, lockfiles, and generated code — inflating embedding calls by 10-100x with zero retrieval value, and burning through NVIDIA NIM's free-tier rate limit before real content is even embedded. On a 2-day budget, this can consume most of day 1 just waiting on embedding calls or debugging why ingestion "hangs."

**Why it happens:**
It's tempting to just `git clone` and glob `**/*` because filtering feels like scope creep, but unfiltered ingestion is the single most likely way to silently blow both the time budget and the free-tier rate limit on day 1.

**How to avoid:**
- Shallow clone (`git clone --depth 1`) — full history is never needed for RAG-over-current-state.
- Filter aggressively before chunking: respect `.gitignore`, hard-exclude `node_modules/`, `dist/`, `build/`, `vendor/`, lockfiles (`package-lock.json`, `yarn.lock`), binary/media extensions, and anything over a reasonable size threshold (e.g., skip files >500KB — likely generated/data files, not hand-written code worth embedding).
- Cap total files/tokens ingested for the MVP (e.g., first N files by relevance heuristic — source directories over config/test directories) rather than promising "ingest the whole repo" as a hard requirement; document this as a known MVP limitation.
- Chunk by logical unit, not fixed character windows: use tree-sitter/AST-aware chunking if time allows (functions/classes as atomic units, target roughly 1000-1500 tokens per chunk), or at minimum chunk by file with a fallback split for very large files — never chunk mid-function on a fixed character count, as it destroys retrieval quality for "what does this function do" style queries.
- Batch embedding calls rather than one-request-per-chunk to reduce request count against the rate limit.

**Warning signs:**
- Ingestion step running for many minutes on a modest repo.
- Embedding call count wildly exceeding the number of source files you'd expect.
- Onboarding summary citing `node_modules` dependency code instead of the project's own code.

**Phase to address:**
Brownfield ingestion phase — build the file filter and shallow-clone step first, before wiring up chunking/embedding; treat "what NOT to embed" as equally important as chunking strategy.

---

### Pitfall 9: NVIDIA NIM free-tier rate limits stall plan generation and RAG mid-flow

**What goes wrong:**
The free NIM API tier is commonly reported around a ~40 requests/minute global cap shared across all model calls on the key (chat completions AND embeddings share the same budget). A brownfield run that embeds dozens of code chunks, then immediately calls the chat model repeatedly for onboarding summary + plan generation + risk explanations, can hit 429s mid-run — especially with retries (naive retry-without-backoff makes the throttling worse, not better). Because this is a live demo flow, hitting a rate limit mid-generation is highly visible failure, not a background job that quietly retries later.

**Why it happens:**
Free tiers are rate-limited by design, and this project stacks two rate-limited call types (embeddings for RAG + chat completions for planning/chat-edit/risk-explanation) on the same key with no budget separation, in a workflow that's naturally bursty (ingest → many embedding calls in a short window → several chat calls right after).

**How to avoid:**
- Rate-limit your own client-side calls proactively (a simple token-bucket/semaphore) rather than relying on the API to tell you when you've gone too fast — hitting the actual 429 in the middle of a demo is worse than self-throttling to stay under budget.
- Batch embedding requests where the API supports it, and cache embeddings per file hash so re-running ingestion during development doesn't re-burn the budget on unchanged files.
- Implement exponential backoff with jitter on 429s for both embedding and chat calls, with a visible "retrying, this may take a moment" state in the UI rather than a hard failure.
- During development, budget your testing runs — don't repeatedly re-run full brownfield ingestion against a large repo just to test an unrelated UI change; cache/mock after the first successful ingestion.
- Confirm actual current limits for your key at build.nvidia.com before the demo — free-tier limits and the specific GLM model available change over time; treat any number found in research as directionally useful, not exact.

**Warning signs:**
- 429 responses appearing only when running the full end-to-end flow, not in isolated unit tests.
- Demo runs succeeding in the morning (fresh rate-limit window) and failing on repeated attempts.

**Phase to address:**
AI provider integration phase — build the throttle/backoff wrapper around the NVIDIA client before building features that call it, so every downstream feature (RAG, planning, chat-edit, risk explanation) inherits the protection.

---

### Pitfall 10: LLM-returned JSON for plan generation doesn't reliably match the expected schema

**What goes wrong:**
NIM's OpenAI-compatible endpoint supports `response_format` for JSON mode/structured outputs on tool-calling-capable models (GLM is reported to support function calling), but enforcement is not guaranteed to be as strict as OpenAI's native structured outputs — deviations from the schema (missing fields, wrong types, extra prose before/after the JSON, truncated output at token limits) can still occur, especially under NIM's OpenAI-compatibility layer which isn't a perfect 1:1 match to OpenAI's actual API. For a plan-generation feature where the output must map cleanly into epics → tasks → skill tags → estimates → assignees, a malformed response breaks the entire downstream pipeline (ADO push, risk scoring, diff rendering).

**Why it happens:**
Teams assume "OpenAI-compatible" means "identical guarantees," but compatibility is at the request/response shape level, not at the enforcement/reliability level — and free/open models under load are more prone to schema drift than flagship hosted models.

**How to avoid:**
- Always validate LLM JSON output against a strict schema (Pydantic model) immediately after parsing — never pass raw LLM output directly into ADO push or risk scoring logic.
- Use defensive parsing: strip markdown code fences if present, attempt `json.loads`, and on failure, retry once with an explicit "return ONLY valid JSON matching this schema" repair prompt before giving up.
- Keep the schema for a single plan-generation call as small/flat as reasonably possible — deeply nested schemas with many optional fields increase drift risk; consider generating the epic list and each epic's tasks as separate, smaller calls rather than one giant nested JSON blob, trading a few extra API calls (mind Pitfall 9's rate limit) for much higher reliability per call.
- Set a generous `max_tokens` for plan generation — truncated JSON (cut off mid-object because the response hit the token cap) is a common and easy-to-miss cause of parse failures, distinct from the model actually producing malformed JSON.
- Log raw LLM output on any parse failure so failures are debuggable rather than silent.

**Warning signs:**
- Intermittent parse failures that don't reproduce on retry with the same prompt.
- Plans with missing tasks or fields that silently default to empty/zero rather than erroring.

**Phase to address:**
Plan generation phase — build the Pydantic-schema-validate-and-repair loop as the very first thing wrapping the plan-generation LLM call, before building any UI on top of it.

---

### Pitfall 11: Risk score drifts into "LLM-influenced" territory despite the deterministic-score design goal

**What goes wrong:**
The stated design is "risk score is deterministic (skill-coverage gap math), LLM only explains it." The natural implementation trap: computing the score from LLM-extracted inputs (e.g., asking the LLM to identify "which skill this task requires" or "how experienced is enough") means the score is only as deterministic as those upstream LLM extractions — two runs of plan generation for the same repo/team can produce different required-skill tags, and therefore different risk scores, even though the scoring *formula* itself never changed. This quietly breaks the "trustworthy, reproducible risk signal" goal stated in the project's Key Decisions.

**Why it happens:**
It's easy to conflate "the arithmetic is deterministic" with "the overall score is deterministic" — the arithmetic can be a pure function while its inputs are LLM-generated and non-reproducible, which defeats the actual goal (a lead re-running the same plan generation should see stable risk signals, not different ones each time).

**How to avoid:**
- Draw the deterministic/LLM boundary explicitly in the architecture: skill tags on tasks should either come from a fixed taxonomy the LLM selects from (constrained choice, e.g., an enum in the JSON schema) rather than free-text extraction, or be reviewable/editable by the lead before scoring runs — not silently re-derived on every plan regeneration.
- The score formula itself (gap between required skill/experience and team's actual skill/experience, weighted by task count/hours) should be pure Python with no LLM call in its path at all — write it as a testable function independent of the graph.
- Only the explanation-generation call should touch the LLM, and it should receive the already-computed score + gap details as input (not be asked to infer or restate the score in its own words in a way that could imply a different number).
- Add a test that runs the scoring function twice on the same fixed task/team input and asserts identical output — this is cheap insurance against accidental non-determinism creeping in.

**Warning signs:**
- Regenerating a plan from the same inputs produces a different risk score without any team/task data changing.
- The LLM's explanation text mentions a risk level or number that doesn't match the computed score.

**Phase to address:**
Risk scoring phase — define the skill-tag taxonomy and the score formula as a standalone, LLM-free module before wiring the explanation-generation call around it.

---

### Pitfall 12: Chat-driven diff/edit loop applies changes without a真正 reversible preview, or drifts plan state out of sync with what's shown

**What goes wrong:**
"Edit via chat, preview as diff, accept" sounds simple but has a subtle state-management trap: if the diff is computed against a stale copy of the plan (e.g., the frontend's local state instead of the backend's canonical graph state), the user can approve a diff that doesn't actually match what gets applied — especially if the LLM chat-edit node also suffers from Pitfall 1's double-execution issue (regenerating a different edit on resume than what was shown in the diff preview). A second common failure: the "accept" action applies the LLM's proposed change directly without validating it still respects the plan schema (e.g., an LLM-driven "reassign to someone else" edit that assigns to a person not in the team roster).

**Why it happens:**
The diff/accept loop is essentially a second interrupt-and-resume cycle nested inside the first (plan review) one, so it inherits all of Pitfalls 1 and 3, and it's easy to under-scope how much validation the "accept" step needs versus treating it as a trusted pass-through.

**How to avoid:**
- Generate the diff from backend canonical state, send both the diff and a content hash/version marker to the frontend, and on "accept" have the backend re-verify the hash still matches current state before applying — reject stale accepts with a clear "plan changed, please retry" rather than silently applying an edit to the wrong base.
- Run the same Pydantic schema validation on chat-edit output as on initial plan generation (Pitfall 10) — a chat edit is just another LLM JSON-producing call with the same reliability risks.
- Validate semantic constraints post-schema: assignee must be in the team roster, skill tags must be from the fixed taxonomy, estimates must be positive numbers — reject and surface an error rather than pushing an invalid edit into state.
- Keep the diff/accept node structured the same way as Pitfall 1's fix: generate-edit node (produces proposed diff, no side effects) → interrupt node (pure pause) → apply-edit node (only runs after resume, only runs once).

**Warning signs:**
- User accepts a diff and the resulting plan doesn't match what was shown.
- Chat edits occasionally assign tasks to people not on the team or with impossible estimates.

**Phase to address:**
Chat-edit/diff phase — design this as "plan review interrupt, done twice" reusing the same node-separation pattern, not as a bespoke new mechanism.

---

### Pitfall 13: Scope creep blows the 2-day budget via "just one more polish pass" on non-core features

**What goes wrong:**
Given the project explicitly scopes out two-way sync, auth/RBAC, and multi-repo support, the highest-probability scope-creep vectors are *inside* the stated MVP flow rather than outside it: over-building the diff UI (rich inline editing, undo/redo, multi-step diff history) instead of a minimally-functional accept/reject; over-engineering the risk-scoring formula (multi-factor weighted models) instead of a simple, defensible gap calculation; polishing the onboarding summary's prose quality instead of just proving the RAG pipeline surfaces relevant content; and building generic/reusable abstractions (e.g., a pluggable multi-provider LLM client) for a project explicitly locked to one provider.

**Why it happens:**
Each individual "just a bit more" feels small in isolation, but a 2-day budget has zero slack for polish passes on secondary surfaces — every hour spent on the diff UI's visual polish is an hour not spent proving the core connect→understand→plan→push flow works end to end, which the project document explicitly calls out as the one thing that must work if everything else fails.

**How to avoid:**
- Before starting each phase, write down the single acceptance check for "this phase is done" and stop building once it's met — resist adding a feature because "it would be easy" if it doesn't move the acceptance check.
- Timebox the two riskiest/most novel integration points (LangGraph interrupt/resume + streaming, ADO JSON-Patch push) with explicit checkpoints early on day 1 — if either isn't working end-to-end (even with a fake/hardcoded plan) by a fixed checkpoint, cut scope elsewhere rather than letting both integration risk and feature scope grow simultaneously.
- Treat greenfield as the only path that must be demo-polished; brownfield/RAG should be "functional and honest," not perfected — the project document itself says greenfield is the primary demo path.
- Explicitly defer: multi-turn chat conversation history/context beyond the current diff exchange, undo across multiple accepted edits, sophisticated risk-score weighting beyond a simple gap formula, and any UI state that isn't required to show the connect→understand→plan→push story.

**Warning signs:**
- End of day 1 and the core push-to-ADO path hasn't been exercised even once with real (non-mocked) data.
- Time spent on frontend visual polish exceeding time spent on the LangGraph graph and ADO integration combined.

**Phase to address:**
Every phase — but concretely, structure the roadmap so phase 1 proves the full flow end-to-end with the simplest possible version of every step (hardcoded/stubbed where needed), and later phases only replace stubs with real implementations one at a time. This "thin vertical slice first" ordering is the single most effective scope-creep defense for a 2-day budget.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|--------------------|-----------------|------------------|
| `MemorySaver` checkpointer instead of `AsyncSqliteSaver` | Zero setup | Loses all in-progress reviews on any restart | Never — the swap cost is minutes, do it right from the start |
| Skipping the Pydantic schema-validation wrapper around LLM JSON output | Faster to first working demo | Silent downstream failures (bad ADO pushes, broken risk scores) that are hard to trace back to a malformed LLM response | Never for plan-generation/chat-edit; acceptable only for pure-text (non-structured) explanation calls |
| Unfiltered repo ingestion (no `.gitignore`/binary filtering) | Simpler ingestion code | Burns rate-limit budget and time on irrelevant content; may not finish before demo | Never — filtering is a ~30 minute investment with large payoff |
| Fixed-size/character-window code chunking instead of AST-aware | Simpler, faster to build | Chunks split mid-function, degrading RAG relevance for the onboarding summary | Acceptable for MVP if time-constrained — chunk by file with a size-based fallback split rather than truly naive fixed windows; skip full tree-sitter integration only if day 1 is already behind schedule |
| No concurrency cap on ADO push requests | Simpler push code | 429 throttling on realistic-sized plans, especially with hierarchy links | Never — a semaphore is a 5-line change |
| Hardcoding a single ADO process template's field names (Agile) | Faster to build against your test project | Breaks if the demo/target project uses Scrum/CMMI (different estimate field names) | Acceptable for MVP if you control and confirm the target project's process template in advance |
| No post-write verification read after ADO push | Fewer API calls, simpler code | Silent partial failures (unassigned work items) go unnoticed until manually checked in ADO | Acceptable to skip full verification, but at minimum log the response body for spot-checking before a live demo |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|--------------|------------------|---------------------|
| Azure DevOps REST API | Sending `application/json` instead of `application/json-patch+json`, using display names instead of reference names (`System.Title`) | Explicit `application/json-patch+json` content-type; a typed patch-builder helper with reference names verified against the target process template |
| Azure DevOps REST API | Confusing `Hierarchy-Forward`/`Hierarchy-Reverse` direction when linking epic→task | `Hierarchy-Reverse` goes on the **child**, pointing up to the parent; write one integration test proving the link direction before relying on it |
| Azure DevOps REST API | Assuming `System.AssignedTo` email resolution always succeeds | Read back the created/updated work item and confirm the field resolved to the expected identity; surface failures visibly |
| Azure DevOps REST API | Unbounded parallel push requests | Concurrency cap (5-10) + exponential backoff on 429, or use the `$batch` API |
| Azure DevOps PAT | Under-scoped (read-only) or short-expiry PAT discovered mid-demo | Explicit Work Items Read&Write scope, expiry covering the full MVP window, startup smoke-test call |
| LangGraph checkpointing | `MemorySaver` in a dev server with hot-reload | `AsyncSqliteSaver` from the first commit |
| LangGraph interrupts | Side effects and `interrupt()` in the same node | Dedicated interrupt-only nodes; side effects strictly before (idempotent) or after (gated, once) the interrupt |
| LangGraph + React streaming | Trusting SSE stream events as source of truth for "is the graph actually paused here" | Fetch canonical thread state after receiving an interrupt event before enabling user actions |
| NVIDIA NIM (OpenAI-compatible) | Assuming full OpenAI API parity (structured outputs enforcement, timeout behavior) | Defensive JSON parsing + schema validation on every structured call; don't assume `response_format` guarantees schema conformance |
| NVIDIA NIM free tier | Unthrottled bursts of embedding + chat calls during ingestion+planning | Client-side rate limiting (token bucket) tuned below the free-tier cap, with backoff+jitter on 429 |
| GitHub repo cloning | Full clone with history, no filtering | `git clone --depth 1`, filter via `.gitignore` + hard-excluded directories/extensions before chunking |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Naive full-repo embedding | Ingestion step takes many minutes; rate-limit exhaustion before planning even starts | Shallow clone + aggressive pre-chunking filtering + file size cap | Any repo beyond a small/medium size (hundreds of files or more), i.e., almost any real brownfield target |
| Unbounded parallel ADO pushes | 429s appear only on realistic (20-50 task) plans, not small test plans | Concurrency cap + backoff from the start | Any plan large enough to be a believable real-world epic breakdown |
| Fixed-size code chunking | RAG answers reference incomplete/truncated function bodies | AST-aware or at-minimum file-level chunking with logical fallback splits | Any file with functions larger than the fixed chunk window |
| One-LLM-call-per-chunk embedding pattern | Rate limit hit early in ingestion | Batch embedding requests where the API supports batch input | Repos beyond ~50-100 chunks on a 40 RPM-class free tier |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging the ADO PAT or NVIDIA API key in request/error logs | Credential leak if logs are shared/committed | Redact secrets from all logging; never log full request headers |
| Storing the shared PAT in a committed config file | Credential leak via version control | `.env` file excluded via `.gitignore`, loaded via environment variables only |
| Passing raw LLM-suggested assignee/skill values straight into ADO writes without validation | LLM hallucination could assign work to an unintended identity string, or inject unexpected field values via prompt-influenced output | Validate assignee against the known team roster and skill tags against the fixed taxonomy before any ADO write (same fix as Pitfall 12) |
| No timeout on outbound calls to ADO/NVIDIA | A hung external call blocks the whole graph node indefinitely, freezing the UI with no feedback | Explicit request timeouts on all external HTTP calls, surfaced as a UI error rather than an infinite spinner |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-------------------|
| Silent long-running ingestion/plan-generation with no progress indication | Lead thinks the tool is frozen during a multi-minute brownfield ingestion or plan generation, especially with NIM's free-tier latency variance | Use `get_stream_writer()` / SSE to stream progress ("cloning repo", "embedding 12/40 files", "generating epic 2 of 5") rather than a single opaque loading state |
| "Approve" button enabled before the plan has actually finished streaming/rendering | User approves an incomplete plan | Only enable approve once the client has confirmed full state via the post-interrupt state fetch (Pitfall 3) |
| Diff preview that doesn't clearly show what changed vs. what stayed the same | Lead can't quickly verify a chat-edit did what they asked, undermining trust in the "human stays in control" design goal | Structured, field-level diff (task X: estimate 3d → 5d) rather than a full plan re-render; highlight only the delta |
| Pushing to ADO with no confirmation of what's about to be created | Accidental push of an unreviewed or partially-edited plan | Explicit final confirmation step showing exactly which work items (with parent/child structure) will be created before the push fires |

## "Looks Done But Isn't" Checklist

- [ ] **LangGraph interrupt/resume flow:** Often "works" in the happy path but re-fires side effects on resume — verify by deliberately triggering a resume twice on the same thread and checking for duplicate ADO writes.
- [ ] **ADO push:** Often creates work items but not the parent/child hierarchy link — verify by opening the ADO Board/Backlog view (not just checking API 200 responses) and confirming tasks nest under their epic.
- [ ] **Work item assignment:** Often returns 200 OK but the assignment didn't resolve — verify by reading the created work item back and checking `System.AssignedTo` is a resolved identity, not blank or an unresolved string.
- [ ] **RAG onboarding summary:** Often "runs" but is grounded in irrelevant chunks (config files, lockfiles, `node_modules`) — verify by spot-checking that cited/retrieved chunks are actually from meaningful source files.
- [ ] **Risk score reproducibility:** Often looks deterministic in a single run — verify by regenerating the plan twice from identical inputs and confirming identical risk scores.
- [ ] **Checkpointer persistence:** Often works during a continuous dev session — verify by restarting the backend process mid-review and confirming the thread resumes correctly.
- [ ] **PAT scope/expiry:** Often works during development against a token created weeks ago — verify expiry date and exact scopes right before the demo, not just at initial setup.
- [ ] **Structured LLM output:** Often parses fine in testing with short/simple plans — verify with a larger, more complex plan (more epics/tasks) that's more likely to hit token limits or schema drift.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|-------------------|
| Duplicate ADO work items from double-execution | LOW-MEDIUM | Manually delete duplicates in ADO; fix by moving side effect to a post-interrupt, gated node; add a `pushed` state flag check |
| Lost in-progress plan due to `MemorySaver` restart | LOW (if caught early) | Swap to `AsyncSqliteSaver`; user must restart the affected session, but no code redesign needed |
| Malformed LLM JSON breaking the plan pipeline | LOW | Add/strengthen the Pydantic validation + repair-prompt retry loop; log raw output for the failing case to refine the prompt |
| ADO push 429 mid-demo | LOW | Add concurrency cap + backoff; for the moment, manually retry the remaining un-pushed items after a short wait |
| NVIDIA NIM rate limit hit during a live demo | MEDIUM | Pre-warm/cache demo data (pre-run ingestion and embedding ahead of the live demo so only the fast plan-generation call happens live); add client-side throttling |
| Wrong-direction parent/child link created | LOW | Update the relation via a follow-up PATCH removing the incorrect relation and adding the correct one; fix the helper function so it can't recur |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|-------------------|-----------------|
| Double-execution of side effects on resume | LangGraph graph design phase | Trigger a resume twice on the same thread in a test; confirm no duplicate writes |
| Lost state from wrong checkpointer | LangGraph scaffolding phase | Restart backend mid-review in a test session; confirm resume works |
| Interrupt/streaming race condition | Frontend-backend contract phase | Confirm UI action (approve) is gated on a confirmed state fetch, not just an SSE event |
| JSON-Patch format/hierarchy link errors | ADO integration phase | Integration test: create epic + child task, confirm hierarchy visible via ADO Boards query |
| Assignment resolution failures | ADO push phase + team setup phase | Post-write read-back check; documented precondition that team emails must exist in ADO org |
| PAT scope/expiry issues | Setup/configuration phase | Startup smoke-test API call with clear error messaging |
| Unbounded parallel push causing 429s | ADO push phase | Load test with a realistic-size plan (20-50 tasks) before the demo |
| Unfiltered repo ingestion blowing budget | Brownfield ingestion phase | Time and log embedding call count on a real test repo; confirm filtering excludes `node_modules`/binaries/lockfiles |
| Naive chunking hurting RAG quality | Brownfield ingestion phase | Spot-check retrieved chunks for a sample query; confirm no mid-function truncation |
| NIM rate limits stalling the flow | AI provider integration phase | Build throttle/backoff wrapper first; run full end-to-end flow once to confirm no unhandled 429s |
| Unreliable structured LLM output | Plan generation phase | Schema-validate every LLM JSON response; test with a larger/complex plan, not just a trivial one |
| Risk score non-determinism | Risk scoring phase | Unit test: same input twice, assert identical score |
| Diff/accept loop correctness | Chat-edit phase | Test stale-accept rejection (change state after diff generated, before accept); test invalid-assignee rejection |
| Scope creep past the 2-day budget | Every phase, enforced via roadmap ordering | Thin vertical slice complete (even if stubbed) by a fixed early checkpoint; core flow exercised end-to-end before any polish work |

## Sources

- [Interrupts — Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph's HITL Has a Double Execution Problem — blog.raed.dev](https://blog.raed.dev/posts/langgraph-hitl/)
- [Do not re-execute a node that interrupted unless all of its interrupts have been resumed — GitHub Issue #6208](https://github.com/langchain-ai/langgraph/issues/6208)
- [Graph not getting continued from the interrupt — GitHub Issue #1569](https://github.com/langchain-ai/langgraph/issues/1569)
- [Persistence — Docs by LangChain](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph State Management: Checkpoints, Thread State, and Failure Recovery — Easton Blog](https://eastondev.com/blog/en/posts/ai/20260424-langgraph-agent-architecture/)
- [Work Items - Create - REST API — Microsoft Learn](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create?view=azure-devops-rest-7.1)
- [Work Items - Update - REST API — Microsoft Learn](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/update?view=azure-devops-rest-7.1)
- [azure-devops-docs link-type-reference.md — GitHub](https://github.com/MicrosoftDocs/azure-devops-docs/blob/main/docs/boards/queries/link-type-reference.md)
- [Use personal access tokens — Azure DevOps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops)
- [Rate and usage limits — Azure DevOps — Microsoft Learn](https://learn.microsoft.com/en-us/azure/devops/integrate/concepts/rate-limits?view=azure-devops)
- [All Azure DevOps REST APIs now support PAT scopes — Azure DevOps Blog](https://devblogs.microsoft.com/devops/all-azure-devops-rest-apis-now-support-pat-scopes/)
- [NVIDIA NIM Free API: Rate Limits, Pricing & Keys 2026 — decodethefuture.org](https://decodethefuture.org/en/nvidia-nim-api-explained/)
- [NVIDIA NIM API Pricing 2026: Free Tier, 40 RPM & Real Cost — decodethefuture.org](https://decodethefuture.org/en/nvidia-nim-api-pricing-limits-guide/)
- [Clarity on NIM API Free Tier Rate Limit Increases — NVIDIA Developer Forums](https://forums.developer.nvidia.com/t/clarity-on-nim-api-free-tier-rate-limit-increases/369624)
- [NVIDIA NIM vs OpenAI API: A Developer's Guide to LLM Inference — n1n.ai](https://explore.n1n.ai/blog/nvidia-nim-vs-openai-api-developer-guide-llm-inference-2026-05-02)
- [NVIDIA NIM — OpenAI Compatible Providers — ai-sdk.dev](https://ai-sdk.dev/providers/openai-compatible-providers/nim)
- [RAG for a Codebase with 10k Repos — Qodo](https://www.qodo.ai/blog/rag-for-large-scale-code-repos/)
- [cAST: Enhancing Code Retrieval-Augmented Generation with Structural Chunking via Abstract Syntax Tree — arXiv](https://arxiv.org/html/2506.15655v1)
- [code-chunk: AST-Aware Code Chunking, Explained — Supermemory](https://supermemory.ai/blog/building-code-chunk-ast-aware-code-chunking/)
- [Get up to speed with partial clone and shallow clone — The GitHub Blog](https://github.blog/open-source/git/get-up-to-speed-with-partial-clone-and-shallow-clone/)
- [Introducing Structured Outputs in the API — OpenAI](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- [Structured Output for Open Source and Local LLMs — Instructor](https://python.useinstructor.com/blog/2024/03/07/open-source-local-structured-output-pydantic-json-openai/)
- [Handling Interrupts in LangGraph with FastAPI — Generative AI on Medium](https://generativeai.pub/when-llms-need-humans-managing-langgraph-interrupts-through-fastapi-97d0912fb6af)
- [langgraph-hitl-fastapi-demo — GitHub](https://github.com/esurovtsev/langgraph-hitl-fastapi-demo)

---
*Pitfalls research for: AI-powered project planning & onboarding dashboard (Azure DevOps + GitHub, FastAPI + LangGraph + React, GLM/NVIDIA NIM, code RAG)*
*Researched: 2026-07-09*
