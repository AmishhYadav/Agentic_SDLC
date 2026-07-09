# Project Research Summary

**Project:** AI Project Planning & Onboarding Dashboard
**Domain:** AI-assisted project planning / developer onboarding (ADO + GitHub integration, LangGraph orchestration, RAG over codebases)
**Researched:** 2026-07-09
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is a 2-day local MVP that connects an Azure DevOps project and a GitHub repo, reads the repo (docs for greenfield, RAG-embedded codebase for brownfield), generates a skill-aware and load-aware implementation plan via an LLM, lets a lead review/edit that plan (directly or via chat with diff preview), and pushes the approved plan into ADO as real work items. Experts building this category of tool (AI sprint planning, codebase-RAG onboarding, human-in-the-loop AI review) converge on a consistent pattern: FastAPI + LangGraph for orchestration with a first-class `interrupt()`/`Command(resume=...)` human-review boundary, React for the interactive plan/diff UI, Chroma for embedded local RAG, and a hard separation between deterministic scoring logic and LLM-generated prose. No single competitor (Jira AI, Linear, ClickUp, TachyonGPT, Copilot4DevOps, Bloop/Greptile-style codebase tools) combines repo-aware planning + skill/load-aware assignment + deterministic risk scoring + chat-diff editing + one-way ADO push in one flow — the combination, not any single piece, is this project's differentiator.

The recommended approach is a **single `StateGraph`** with a router-node fork for greenfield/brownfield that reconverges before plan generation, an `AsyncSqliteSaver` checkpointer (not `MemorySaver`) from day one, and a strict architectural rule that the interrupt-calling node never contains side effects (LangGraph re-executes the entire node from the top on resume — the single most consequential pitfall discovered). Deterministic risk scoring must be a pure Python function fed only by structured (not free-text) LLM outputs, with the LLM strictly confined to writing explanation prose over an already-computed score — this is both a differentiator (addresses a real explainability gap in competitor AI risk tools) and the pitfall most likely to be silently violated (Pitfall 11: score determinism breaks if the *inputs* to the formula are non-reproducible LLM extractions, even if the arithmetic itself is pure).

Key risks: (1) LangGraph's replay-on-resume semantics can silently double-fire ADO writes or regenerate plans unless side effects are strictly isolated to post-resume, gated nodes; (2) Azure DevOps' JSON-Patch API and hierarchy-link direction (`Hierarchy-Reverse` on the child) are easy to get backwards and fail non-obviously; (3) NVIDIA NIM's free-tier model catalog churns (GLM-5 → 5.1 → 5.2 in under 3 months) and has a tight ~40 req/min shared rate limit across chat+embeddings, both requiring env-var-based model IDs and proactive client-side throttling rather than reactive retry; (4) unfiltered brownfield repo ingestion can burn most of a 2-day budget on `node_modules`/binaries before real planning starts. All four are addressable with known, well-documented mitigations and should be designed in from the first phase, not patched in later.

## Key Findings

### Recommended Stack

The team's already-committed choices (FastAPI, LangGraph, React, GLM via NVIDIA NIM) are validated as sound and current. Research filled the stated gaps: Chroma for local embedded RAG vector storage, direct `httpx` REST calls (not the stale, still-beta `azure-devops` SDK) for Azure DevOps, PyGithub/GitPython for repo reading, and `react-diff-viewer-continued` for the fastest-to-ship diff preview UI.

**Core technologies:**
- FastAPI 0.139.0 + Uvicorn — async HTTP layer hosting the LangGraph run/interrupt/resume endpoints; `fastapi[standard]` needs zero extra tooling decisions
- LangGraph 1.2.8 with `AsyncSqliteSaver` (not `MemorySaver`) — orchestrates greenfield/brownfield branching and the human-review interrupt/resume loop; the checkpointer choice must survive dev-server hot-reloads
- React 19.2.7 + Vite 8.1.4 + TypeScript 5.x — plan editor, diff preview, onboarding summary UI
- `langchain-openai`'s `ChatOpenAI` pointed at NIM's OpenAI-compatible `base_url` (not `langchain-nvidia-ai-endpoints`) — fewer moving parts, model ID `z-ai/glm-5.2` behind an env var since NIM's free catalog deprecates model IDs roughly every 2-3 months
- `chromadb` (embedded/local mode) + `langchain-chroma` — zero-infrastructure local vector store for brownfield RAG, with first-class metadata filtering
- Direct `httpx` REST calls to Azure DevOps `wit/$batch` API (not the 2+ year stale `azure-devops` beta SDK) — one well-documented POST per work item with JSON-Patch body
- `react-diff-viewer-continued` — string-in/diff-out, no manual unified-diff computation needed, fastest path to a working diff preview in a 2-day window

### Expected Features

The feature category (AI work breakdown, skill/capacity-aware assignment, AI risk flags, codebase-RAG onboarding, chat-diff editing) is well-established individually across Jira AI, Linear, ClickUp, TachyonGPT, and code-editor tools (Copilot Edits, Cursor) — but no single tool combines all five into one flow, which is this project's core differentiator claim (reasoned synthesis, not a direct competitor match).

**Must have (table stakes):**
- Connect ADO + GitHub via config (single shared PAT, no OAuth)
- Team roster with skills/experience
- Epic → task breakdown with skill tag + hours/days estimate
- Suggested assignee per task
- Editable plan before commit (direct edit)
- Push to tracker as real work items (one-way)
- Basic "why" explanation for AI risk suggestions

**Should have (differentiators):**
- Skill-match **combined with current load** in one auto-assignment pass (competitors do one or the other, rarely both)
- Deterministic risk score with AI-only-explains-it-never-invents-it design (addresses a known trust gap in AI risk tooling)
- Codebase-RAG onboarding summary for brownfield (genuine differentiator inside a *planning* tool, though table stakes in standalone codebase-onboarding tools like Bloop/Greptile)
- LLM chat-driven plan editing with diff preview before accept (imports the code-editor diff-review pattern into a PM context — novel application)

**Defer (v2+):**
- Two-way ADO sync, RBAC/auth, multi-repo support — all explicitly out of scope per PROJECT.md
- Optimizer/solver-based assignment (LP/simulated annealing) — greedy skill+load scoring is sufficient at this scale
- Historical-velocity-based estimation — no historical data exists yet to train on
- Real ADO-workload reading for load-awareness (vs. within-plan running total) — reasonable v1.x upgrade, not a blocker
- Field-level diff granularity — whole-plan-object diff is sufficient for MVP

### Architecture Approach

A single `StateGraph` with one shared `RunState` TypedDict carries the run from config ingestion through a router-node fork (greenfield reads docs directly; brownfield clones→chunks→embeds→retrieves) that reconverges before plan generation, then flows through deterministic risk scoring, a dedicated `human_review` interrupt node, and a terminal one-shot ADO push node. FastAPI owns the HTTP boundary (create runs, poll/stream state, accept edits via `graph.update_state()`, and unblock the interrupt via `Command(resume=...)` only on explicit Approve) while LangGraph and FastAPI live in the same process — no separate LangGraph server needed for this scope.

**Major components:**
1. **FastAPI Run Controller** — owns HTTP boundary: create runs, expose state (poll/SSE), accept direct/chat edits without resuming, translate Approve into `Command(resume=...)`
2. **LangGraph Orchestration Layer** — one compiled `StateGraph` with `AsyncSqliteSaver`; nodes are thin, calling into `services/` for real logic
3. **RAG Pipeline** (`services/rag/`) — chunk (language-aware) → embed (NVIDIA NIM) → store (Chroma, per-run collection) → retrieve; reused for both onboarding summary and plan-grounding
4. **Deterministic Risk Engine** (`services/risk_engine.py`) — pure Python, zero LLM/network imports, unit-testable in isolation; this is the architectural enforcement of the trust boundary
5. **ADO Adapter** (`services/ado_client.py`) — direct `httpx` REST calls with JSON-Patch bodies, batch/throttled work-item creation, hierarchy-link helper

### Critical Pitfalls

1. **LangGraph re-executes the entire node from the top on resume** — never put non-idempotent side effects (ADO writes, plan mutation) in the same node as `interrupt()`; keep the interrupt node to "pause, read resume payload, merge" only. This is an architecture decision to get right in graph design, not a later bug fix.
2. **`MemorySaver` loses all in-progress plans on any backend restart** (including `uvicorn --reload` hot-reload during dev) — use `AsyncSqliteSaver` from the first commit; the swap cost is minutes, the cost of not doing it is losing test/demo state repeatedly.
3. **ADO JSON-Patch format and hierarchy-link direction errors** — must use `Content-Type: application/json-patch+json`, reference names (`System.Title` not `"Title"`), and `Hierarchy-Reverse` on the *child* pointing to the parent (non-intuitive). Build and unit-test a typed patch-builder helper before wiring into the main flow.
4. **NVIDIA NIM free-tier rate limits (~40 req/min shared across chat+embeddings) and model-ID churn** — self-throttle proactively (token bucket) rather than reacting to 429s, put the model ID behind an env var, and confirm the current model ID is live before building against it.
5. **Risk score determinism breaks if upstream LLM-extracted inputs (e.g., skill tags) are non-reproducible**, even though the scoring arithmetic itself is pure — constrain skill tags to a fixed taxonomy (enum in the LLM's JSON schema) rather than free-text extraction, and add a test asserting identical scores on identical inputs.

## Implications for Roadmap

Based on combined research, the strongest defense against the 2-day budget (Pitfall 13: scope creep) is a **thin vertical slice first** ordering — get the full connect→understand→plan→push flow working end-to-end with stubbed/hardcoded pieces before polishing any single stage. Suggested phase structure:

### Phase 1: Scaffolding + Thin End-to-End Slice
**Rationale:** The riskiest integration points (LangGraph interrupt/resume, ADO JSON-Patch push) must be proven working end-to-end — even with a fake/hardcoded plan — before investing in any real feature logic. This directly defends against Pitfall 13 (scope creep) and surfaces Pitfall 1/2 (double-execution, checkpointer choice) immediately when they're cheapest to fix.
**Delivers:** FastAPI + LangGraph skeleton with `AsyncSqliteSaver`, a single `StateGraph` (ingest → stub plan → interrupt → stub push), React shell that can create a run, see a hardcoded plan, click Approve, and see a "pushed" status. One real ADO work item created via the JSON-Patch helper, proving the hierarchy-link direction is correct.
**Addresses:** Orchestrate greenfield/brownfield branch + human-review loop with LangGraph (foundational requirement); one-way ADO push (proven early, not last)
**Avoids:** Pitfall 1 (double-execution), Pitfall 2 (wrong checkpointer), Pitfall 4/5 (JSON-Patch/hierarchy errors), Pitfall 13 (scope creep — this phase IS the scope-creep defense)

### Phase 2: Config Intake + Greenfield Planning Path
**Rationale:** Greenfield is explicitly the primary demo path per PROJECT.md and is lower complexity than brownfield RAG — de-risk the core "generate a real plan" flow before adding RAG complexity.
**Delivers:** ADO/GitHub config connection with startup PAT smoke-test, team roster CRUD, greenfield doc-read node, real LLM-generated epic→task breakdown with skill tags + estimates, Pydantic schema validation + repair-prompt retry loop around the LLM JSON output.
**Addresses:** Connect ADO+GitHub, team roster entry, greenfield doc-read path, epic→task breakdown (all P1 table-stakes features from FEATURES.md)
**Uses:** `ChatOpenAI` wrapper around NIM, `httpx` direct ADO REST calls, Pydantic validation
**Avoids:** Pitfall 6 (PAT scope/expiry — smoke-test at connect time), Pitfall 10 (malformed LLM JSON — validation from day one)

### Phase 3: Skill/Load-Aware Assignment + Deterministic Risk Scoring
**Rationale:** Both features consume the same task+team data structure produced in Phase 2 and are independently the two "headline differentiator" features (per FEATURES.md) — building them together avoids re-touching the plan data model twice.
**Delivers:** Greedy skill-match + within-plan-load-aware assignee suggestion; pure-Python deterministic risk engine (skill-coverage gap formula) with a single batched LLM call for explanation prose, fed only structured score data.
**Implements:** `risk_engine.py` as a zero-LLM-import module (architectural trust boundary from ARCHITECTURE.md)
**Avoids:** Pitfall 11 (risk score non-determinism from LLM-extracted inputs) — constrain skill tags to a fixed taxonomy in this phase, add the same-input-same-output unit test here

### Phase 4: Plan Editing — Direct Edit + Chat Edit with Diff Preview
**Rationale:** Direct edit is the simpler table-stakes fallback; chat edit with diff preview is the second differentiator and structurally "the plan review interrupt, done twice" (per PITFALLS.md) — build direct edit first so there's a working fallback if chat-edit time runs short.
**Delivers:** In-UI direct plan editing funneling into the same `update_state` mutation path as chat edits; LLM chat-edit node producing a structured diff, rendered via `react-diff-viewer-continued`, with backend-canonical-state hash verification on accept to prevent stale-accept bugs.
**Addresses:** Editable plan (direct), LLM chat edit with diff preview (both P1 in FEATURES.md)
**Avoids:** Pitfall 12 (diff/accept loop state drift, invalid-assignee edits) — validate chat-edit output with the same schema+taxonomy checks as Phase 2/3

### Phase 5: Brownfield RAG (Codebase Ingestion + Onboarding Summary)
**Rationale:** Highest-complexity item in the whole feature set (per FEATURES.md) and explicitly the first thing to cut/simplify if time runs short — sequencing it last means a working greenfield demo exists regardless of how this phase goes, directly implementing the "greenfield-first" hedge from PROJECT.md.
**Delivers:** Shallow clone + aggressive `.gitignore`/binary/lockfile filtering, language-aware chunking, NVIDIA embedding calls with `input_type` wrapper, Chroma storage, retrieval-grounded onboarding summary feeding the same `generate_plan` node used in Phase 2.
**Addresses:** Brownfield codebase ingestion + onboarding summary (P2 in FEATURES.md — explicitly a "should have if time allows")
**Avoids:** Pitfall 8 (unfiltered repo ingestion blowing the budget), Pitfall 9 (NIM rate limits mid-ingestion), Anti-Pattern 3 (fixed-size chunking degrading retrieval quality)

### Phase Ordering Rationale

- **Vertical slice before feature depth:** Phase 1 exists specifically because two of the four critical/architecture-defining pitfalls (double-execution on resume, checkpointer choice) are catastrophic if discovered late and cheap to get right early — proving interrupt/resume and one real ADO push first means every subsequent phase builds on validated plumbing.
- **Greenfield before brownfield:** Directly follows PROJECT.md's own stated demo strategy and FEATURES.md's complexity assessment (RAG is HIGH complexity, greenfield doc-reading is LOW-MEDIUM) — sequencing brownfield last protects the demo if RAG runs over budget.
- **Risk scoring immediately after assignment (not deferred):** Both depend on the same plan+team data shape from Phase 2, and risk scoring's determinism constraint (fixed skill taxonomy) needs to be decided before chat-editing (Phase 4) can validate edits against that taxonomy — sequencing risk scoring before chat-edit avoids retrofitting the taxonomy constraint.
- **Chat-edit as "the interrupt pattern, done twice":** Per PITFALLS.md, this reuses Phase 1's node-separation pattern directly — sequencing it after Phase 1's plumbing is proven, rather than inventing a parallel mechanism, is both faster and avoids Pitfall 12.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (LangGraph interrupt/resume + FastAPI wiring):** ARCHITECTURE.md and PITFALLS.md both flag this as a genuinely subtle execution model (replay-from-start on resume, multi-interrupt ordering fragility) — worth a `--research-phase` pass on the exact FastAPI-side state-fetch-before-enabling-approve pattern if the team hasn't built this pattern before.
- **Phase 5 (Brownfield RAG):** STACK.md and ARCHITECTURE.md flag chunking strategy (AST-aware vs. language-aware fallback) and NVIDIA embedding wiring (`input_type` field not exposed cleanly by `langchain-nvidia-ai-endpoints`) as areas with real implementation subtlety — confirm the exact embedding wrapper approach before building.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Config + greenfield planning):** ADO REST work-item creation and FastAPI/Pydantic patterns are HIGH confidence, officially documented, and well-trodden — no additional research needed.
- **Phase 3 (Risk scoring):** The deterministic/LLM separation pattern is a standard hybrid-AI-system pattern (credit scoring explanations, code review severity) with clear precedent in ARCHITECTURE.md's Pattern 3 — implementation is straightforward once the architecture is understood.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH for framework/library versions (Context7 + PyPI/npm verified); MEDIUM-LOW for the exact NVIDIA NIM GLM model ID staying stable (catalog has churned 3x in 3 months) |
| Features | MEDIUM — individual features are well-verified across multiple competitor products (Jira AI, Linear, ClickUp, TachyonGPT), but the specific 5-feature combination this project builds has no direct competitor match, so "differentiator" claims are reasoned synthesis, not directly sourced |
| Architecture | HIGH — LangGraph interrupt/checkpoint/streaming patterns verified via official Context7 docs; MEDIUM on RAG chunking specifics and ADO batch API (multiple corroborating but non-official sources) |
| Pitfalls | MEDIUM-HIGH — LangGraph and ADO REST API pitfalls verified against official docs and GitHub issues; NVIDIA NIM free-tier rate limits are best-effort from community/forum reports and can change without notice |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Exact NVIDIA NIM model ID stability:** `z-ai/glm-5.2` was current as of 2026-07-09 but has been deprecated/replaced twice in the prior 3 months. Mitigation already built into the stack recommendation (env var, not hardcoded) — verify the model ID is live via `GET /v1/models` immediately before each work session, not just once at project start.
- **Whether "current load" means real ADO workload or within-plan running total:** PROJECT.md's phrasing ("who is already assigned work") implies reading real ADO assignments, which FEATURES.md flags as the higher-complexity interpretation. Recommend defaulting to within-plan running total for the 2-day MVP (both branches) and treating real ADO-workload reading as an explicit v1.x stretch — this should be confirmed with the requirements/roadmap step, not assumed.
- **ADO process template field names:** `Microsoft.VSTS.Scheduling.OriginalEstimate` and other field reference names vary by process template (Agile/Scrum/CMMI). Confirm the target demo ADO project's process template before Phase 1's ADO push proof, since this affects the JSON-Patch field names used throughout.
- **No single competitor validates the full 5-feature combination** this project builds — the differentiator narrative is sound reasoning from adjacent-category evidence but should be treated as a hypothesis to validate via the demo itself, not a pre-verified market fact.

## Sources

### Primary (HIGH confidence)
- Context7 `/websites/langchain_oss_python_langgraph` — `interrupt()`, `Command(resume=...)`, `InMemorySaver`/`AsyncSqliteSaver`, human-in-the-loop pattern
- PyPI JSON API — direct version/release lookups for langgraph, langchain-openai, fastapi, chromadb, and all pinned backend dependencies
- npm registry JSON API — vite, react, typescript, @tanstack/react-query, diff, react-diff-view version verification
- `docs.langchain.com/oss/python/langgraph/interrupts`, `/persistence`, `/checkpointers`, `/graph-api`, `/functional-api`, `/event-streaming` — official LangGraph docs
- `learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create` and `/update` — official Azure DevOps REST API docs
- GitHub Issues `langchain-ai/langgraph#6208`, `#1569` — confirmed interrupt re-execution/resume behavior directly from maintainers

### Secondary (MEDIUM confidence)
- WebSearch across Zenhub, Augment Code, Martin Fowler, Security Boulevard — competitor feature landscape (Jira AI, Linear, ClickUp, TachyonGPT, Copilot4DevOps, codebase-onboarding tools)
- NVIDIA Developer Forums (multiple threads) — corroborated GLM-5 → 5.1 → 5.2 deprecation churn pattern and free-tier ~40 RPM rate limit
- `blog.raed.dev/posts/langgraph-hitl` and community FastAPI+LangGraph reference implementations — HITL wiring patterns consistent with official docs
- `arxiv.org/pdf/2506.15655` (cAST paper) and practitioner writeups — AST-aware code chunking quality rationale

### Tertiary (LOW confidence)
- `docs.api.nvidia.com/nim/reference/z-ai-glm-5.2` — exact model ID confirmed but catalog volatility means this needs re-verification before each work session, not treated as fixed
- Single-source blogs on rate limits and probabilistic drift — used only to corroborate themes already established by multiple independent sources, not as sole basis for any recommendation

---
*Research completed: 2026-07-09*
*Ready for roadmap: yes*
