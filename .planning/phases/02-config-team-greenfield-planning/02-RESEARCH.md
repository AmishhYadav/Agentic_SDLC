# Phase 2: Config, Team & Greenfield Planning - Research

**Researched:** 2026-07-10
**Domain:** ADO PAT smoke-testing, team roster CRUD (SQLite), GitHub doc fetching for greenfield grounding, LangGraph conditional branching, GLM-via-NVIDIA-NIM structured output with validate/repair
**Confidence:** MEDIUM-HIGH overall — HIGH on LangGraph conditional-edge mechanics and PyGithub API surface (official docs/reference verified); MEDIUM on ADO PAT introspection (genuine API ambiguity, documented below); MEDIUM-LOW on GLM/NIM structured-output reliability (an active, dated bug report exists for exactly this model+endpoint combination) — this LOW-confidence area is the single biggest execution risk in the phase and is flagged accordingly.

## Summary

Phase 2 replaces three things in the existing 4-node spine: (1) `ingest_config` grows from a passthrough into a real `.env`-driven config load + ADO PAT smoke-test that blocks the run, (2) a new conditional edge routes on `REPO_MODE` to either a real greenfield doc-reading path or a placeholder brownfield leg, and (3) `stub_plan` is replaced by a real GLM-backed plan generator with schema validation and retry/repair. A new team-roster CRUD surface (FastAPI + SQLite) is added alongside, independent of the graph.

The two areas needing the most planning care are: **ADO PAT introspection has no clean, single-call answer** — Azure DevOps does not expose a PAT-scope-introspection endpoint reachable using the PAT itself in the way a typical OAuth `/introspect` endpoint would; the practical answer is a small sequence of low-cost, purpose-built probe calls (already partially proven out by `script_a_ado_smoke_test.py`) rather than one clean "check my scope" call. **GLM via NVIDIA NIM's tool-calling / structured-output path has an open, dated bug report for malformed tool-call JSON** — this means PLAN-04's validate+repair loop is not a nice-to-have defensive measure, it is load-bearing, and the design must assume the first structured-output call can fail even under normal operation, not only under adversarial input.

For GitHub doc fetching, the phase's D-11 scope ("README + docs/**/*.md, capped size, no full clone") is well-served by PyGithub's `get_git_tree(recursive=True)` (one API call to enumerate the whole repo's paths) followed by a handful of targeted `get_contents()` calls only for matched doc files — this is a refinement of STACK.md's "PyGithub for a handful of doc files" recommendation and is clearly the right mechanism for this specific use case (distinct from Phase 5's brownfield full-codebase GitPython shallow-clone, which remains correct for that different problem).

**Primary recommendation:** Build the ADO smoke-test as a sequence of cheap, purpose-specific REST probes (project access -> PAT list/self-introspection best-effort -> work-item write capability), not a single call; build plan generation as `ChatOpenAI(...).with_structured_output(Plan, method="function_calling", include_raw=True)` wrapped in a hand-rolled validate-then-repair-prompt retry loop (LangChain's `OutputFixingParser` is **removed** from current `langchain-core`, do not reach for it); use `get_git_tree` + targeted `get_contents()` for greenfield doc fetching, never a shallow clone for this phase.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `.env` config load (ADO_ORG/PROJECT/PAT, GITHUB_REPO, REPO_MODE) | API/Backend (graph node) | — | D-01: no config form; read once at run start inside `ingest_config`, same pattern as existing `LEAD_EMAIL` read |
| ADO PAT smoke-test (auth, write scope, expiry, project access) | API/Backend (`services/ado_client.py` extension) | — | Must block the run before any graph work proceeds (D-02); reuses the existing `ado_client` auth/response-parsing helpers |
| Team roster CRUD | API/Backend (new FastAPI router) + Database/Storage (SQLite) | — | D-04/D-07: global, persisted, editable before planning; independent of the LangGraph run — never part of `RunState` |
| Greenfield/brownfield routing | API/Backend (LangGraph conditional edge) | — | D-08/D-09: pure routing function reading `state["repo_mode"]`, no LLM involved in the routing decision itself |
| GitHub doc fetch (README + docs/**/*.md) | API/Backend (`services/github_client.py`, new) | — | D-11: server-side only; the React frontend never talks to GitHub directly |
| Skill taxonomy (fixed list) | API/Backend (shared constant/module) | Frontend (rendered read-only, if team roster UI shows it) | D-10: single source of truth importable by both the plan-generation node and any future API response models |
| Plan generation (LLM call + schema validate/repair) | API/Backend (`services/llm.py` + `graph/nodes/generate_plan.py`, new) | — | D-15: structured output against `backend/app/models/plan.py`; LLM never touches ADO or DB directly |
| Plan/team data shape | Database/Storage (SQLite) + API/Backend (Pydantic) | — | Plan stays in graph state/checkpoint (per Phase 1 pattern); team roster is a separate persisted table, not graph state |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `PyGithub` | 2.9.1 (verified via `pip index versions`, matches STACK.md) | Enumerate repo tree + fetch README/docs content for greenfield grounding | Already the project's committed choice (STACK.md); confirmed current on PyPI and installed clean via slopcheck in this research session |
| `langchain-openai` | 1.3.4 (verified) | `ChatOpenAI` wrapper pointed at NVIDIA NIM `base_url` for real plan generation | Already committed (STACK.md); the project's stated "OpenAI-compatible SDK" integration path |
| `pydantic` | 2.13.4 (already installed) | Validate LLM plan output against `backend/app/models/plan.py` | Already in use throughout the codebase; `Plan`/`Epic`/`Task` are the schema PLAN-04 validates against |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `GitPython` | 3.1.50 (verified) | NOT used in Phase 2 | Reserved for Phase 5 brownfield full-codebase ingestion only — do not pull it into the greenfield doc-reading path; see "Don't Hand-Roll" / doc-fetch mechanism section below for why `get_git_tree` beats a clone for this narrower use case |
| `httpx` | 0.28.1 (already installed, used by `ado_client.py`) | Additional ADO REST probe calls for the smoke-test (e.g. `_apis/tokens/pats`, `_apis/projects/{project}`) | Reuse the existing `_auth_header()`/`_check_json_response()` helpers in `ado_client.py` rather than duplicating auth/parsing logic in a new module |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PyGithub `get_git_tree` + targeted `get_contents()` | PyGithub per-directory `get_contents("")` walk | Per-directory walk costs one API call per directory traversed (STACK.md's original framing), which is fine for a shallow doc tree but strictly worse than one `get_git_tree(recursive=True)` call — no reason to prefer it for this phase's narrow "README + docs/**/*.md" scope |
| PyGithub `get_git_tree` + targeted `get_contents()` | `GitPython` shallow clone | Reasonable if greenfield repos turn out to have deeply nested or very large doc trees, but D-11's scope (README + docs/**/*.md, capped size) does not justify a full clone's filesystem/subprocess overhead for a 2-day MVP; reserve clone-based ingestion for Phase 5 |
| Hand-rolled validate+repair retry loop | LangChain `OutputFixingParser` | **Not viable** — `OutputFixingParser` has been removed from current `langchain-core`/`langchain` as of a still-open GitHub issue (langchain-ai/langchain#34098, opened 2025-11-25); do not plan around it existing |
| `with_structured_output(..., method="function_calling")` | `method="json_schema"` | `json_schema` invokes OpenAI's native Structured Outputs API, which is an OpenAI-specific enforcement mechanism not guaranteed to be replicated by NVIDIA NIM's OpenAI-compatibility layer; `function_calling` (tool-calling) is the documented GLM capability and the safer default for a non-OpenAI endpoint |
| Multi-probe ADO smoke-test | Single "introspect my PAT" call | Azure DevOps has no such call reachable via PAT Basic auth for scope introspection at the org-membership level — see Common Pitfalls below |

**Installation:**
```bash
pip install PyGithub==2.9.1 langchain-openai==1.3.4
```
(`langchain-core` is already satisfied transitively at 1.4.9; no version bump needed.)

**Version verification:** Confirmed via `pip index versions PyGithub` (2.9.1 top) and `pip index versions langchain-openai` (1.3.4 top) run directly against PyPI in this research session (2026-07-10), consistent with STACK.md's 2026-07-09 findings — no drift in the one-day gap.

## Package Legitimacy Audit

Ran `slopcheck install PyGithub GitPython langchain-openai` in the backend venv (`slopcheck` 0.6.1, installed fresh this session). All three packages installed and passed cleanly.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| `PyGithub` | PyPI | Long-established (10+ yrs, v2.x actively maintained) | High (widely used GitHub API client) | github.com/PyGithub/PyGithub | [OK] | Approved |
| `langchain-openai` | PyPI | Established LangChain partner package | High | github.com/langchain-ai/langchain | [OK] — flagged only a generic naming-pattern note ("Name starts with 'langchain-'... package is established") | Approved |
| `GitPython` | PyPI | Long-established | High | github.com/gitpython-developers/GitPython | [OK] | Approved (reserved for Phase 5, not installed for Phase 2 work) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

All three packages are tagged `[VERIFIED: npm/PyPI registry]`-equivalent for this ecosystem — confirmed via official PyPI + slopcheck in this session, and each was already present in the project's own STACK.md (itself sourced from PyPI JSON API + Context7). No postinstall-script concern applies (Python packages have no npm-style postinstall hook vector).

## Architecture Patterns

### System Architecture Diagram

```
                     .env (ADO_ORG, ADO_PROJECT, ADO_PAT, GITHUB_REPO, REPO_MODE)
                                    |
                                    v
                     +----------------------------+
                     |  ingest_config (grown)     |
                     |  - load env config          |
                     |  - run ADO smoke-test       |----(FAIL)--> blocked run, detailed
                     |    (blocking)                |               per-check reasons surfaced
                     +--------------+---------------+
                                    | (PASS)
                                    v
                     +----------------------------+
                     |  route_repo_mode (router)   |
                     |  reads state["repo_mode"]   |
                     +------+---------------+------+
                            |                 |
                 REPO_MODE= |                 | REPO_MODE=
                 greenfield |                 | brownfield
                            v                 v
              +----------------------+  +---------------------------+
              | read_docs_greenfield |  | ingest_brownfield_stub     |
              | - get_git_tree(rec)  |  | (guarded placeholder,      |
              | - filter README +    |  |  returns "Phase 5" message,|
              |   docs/**/*.md       |  |  never crashes/falls back) |
              | - get_contents() per |  +-------------+---------------+
              |   matched file, cap  |                |
              |   total size         |                |
              | - no docs -> BLOCK   |                |
              |   (D-12)             |                |
              +----------+-----------+                |
                         +-------------+----------------+
                                       v
                        +-----------------------------+
                        |  generate_plan (LLM, real)   |
                        |  - ChatOpenAI @ NIM base_url  |
                        |  - with_structured_output(    |
                        |      Plan, function_calling,  |
                        |      include_raw=True)        |
                        |  - validate vs Plan schema     |
                        |  - on failure: repair-prompt   |
                        |    retry (bounded N)           |
                        |  - skill_tag constrained to     |
                        |    fixed taxonomy (D-10)        |
                        |  - suggested_assignee = "" (D-14)|
                        +---------------+-----------------+
                                        v
                              human_review (unchanged)
                                        v
                                  push_to_ado (unchanged)

  Team roster CRUD (independent of the graph, runs before/between runs):
  React "Team" UI --> FastAPI team router --> SQLite `team_members` table
```

### Recommended Project Structure

```
backend/app/
├── graph/
│   ├── nodes/
│   │   ├── ingest_config.py          # grows: adds smoke-test call + repo_mode read
│   │   ├── read_docs_greenfield.py   # NEW
│   │   ├── ingest_brownfield_stub.py # NEW — guarded placeholder only
│   │   └── generate_plan.py          # NEW — replaces stub_plan.py
│   └── build.py                      # add conditional edge after ingest_config
├── services/
│   ├── ado_client.py                 # grows: add smoke-test probe functions
│   ├── github_client.py              # NEW — get_git_tree + targeted get_contents
│   └── llm.py                        # NEW — ChatOpenAI factory + validate/repair loop
├── models/
│   ├── plan.py                       # unchanged (already the shared schema)
│   └── skills.py                     # NEW — hardcoded skill taxonomy constant (D-10)
├── db/
│   ├── run_metadata.py               # unchanged
│   └── team_roster.py                # NEW — team_members table CRUD, same sqlite file
└── routers/
    ├── runs.py                       # unchanged
    ├── team.py                       # NEW — team CRUD endpoints
    └── config_status.py              # NEW (or folded into runs.py) — expose smoke-test result
```

### Pattern 1: Conditional edge after `ingest_config`, reading `state["repo_mode"]`

**What:** A router function (not a node) inspects `state["repo_mode"]` and returns one of two node names; `add_conditional_edges` maps those names to `read_docs_greenfield` or `ingest_brownfield_stub`. Both converge on `generate_plan`.

**When to use:** Exactly ARCHITECTURE.md's already-documented Pattern 1 — this phase is simply implementing what that document already specified for Phase 1/2's deferred branch half.

**Example:**
```python
# Source: LangGraph official docs (Graph API overview, docs.langchain.com/oss/python/langgraph/graph-api)
# and reference.langchain.com/python/langgraph/graph/state/StateGraph/add_conditional_edges
def route_repo_mode(state: RunState) -> str:
    return "ingest_brownfield_stub" if state.get("repo_mode") == "brownfield" else "read_docs_greenfield"

builder.add_node("read_docs_greenfield", read_docs_greenfield)
builder.add_node("ingest_brownfield_stub", ingest_brownfield_stub)
builder.add_node("generate_plan", generate_plan)

builder.add_conditional_edges(
    "ingest_config",
    route_repo_mode,
    {"read_docs_greenfield": "read_docs_greenfield", "ingest_brownfield_stub": "ingest_brownfield_stub"},
)
builder.add_edge("read_docs_greenfield", "generate_plan")
builder.add_edge("ingest_brownfield_stub", "generate_plan")
```
Note: per D-09, `ingest_brownfield_stub` must still converge into `generate_plan` in the graph wiring even though it does no real work — but its returned state should set a flag (e.g. `state["blocked_reason"] = "brownfield planning arrives in Phase 5"`) that `generate_plan` checks first and short-circuits on, rather than actually attempting to plan from nothing. This keeps the "no silent greenfield fallback" requirement (D-09) enforceable in one place.

### Pattern 2: GitHub doc fetch — tree enumeration + targeted content fetch, no clone

**What:** One `get_git_tree(sha, recursive=True)` call enumerates every path in the repo. Filter that list in Python for `README*` (any case/extension) and `docs/**/*.md`. Fetch only the matched files' content via `get_contents(path)` (one call per matched file — typically a handful for a real greenfield repo). Concatenate into a single text blob, capped at a size threshold (e.g. ~40-60K characters, well inside GLM-5.2's stated 1M-token context per WebSearch findings, but keeping the prompt small and fast for a demo) before handing to the LLM.

**When to use:** Any greenfield "read just the docs" scenario — this is the correct mechanism for D-11's exact scope and is a **refinement** of STACK.md's "PyGithub for a handful of doc files" guidance (STACK.md did not specify tree-vs-per-directory; this research closes that gap). Do not use this pattern for Phase 5's brownfield full-codebase ingestion — that remains GitPython shallow-clone per STACK.md, because tree enumeration for a full codebase still requires fetching every matched file's content individually, which is where a clone wins at scale.

**Example:**
```python
# Source: PyGithub official reference (pygithub.readthedocs.io/en/latest/github_objects/Repository.html)
from github import Github
import base64, fnmatch

def fetch_greenfield_docs(token: str, owner_repo: str, max_chars: int = 60_000) -> str | None:
    gh = Github(token)
    repo = gh.get_repo(owner_repo)
    default_branch = repo.default_branch
    tree = repo.get_git_tree(default_branch, recursive=True)

    matched_paths = [
        entry.path for entry in tree.tree
        if entry.type == "blob" and (
            fnmatch.fnmatch(entry.path.lower(), "readme*")
            or fnmatch.fnmatch(entry.path.lower(), "docs/**/*.md")
        )
    ]
    if not matched_paths:
        return None  # D-12: no usable docs -> caller blocks with a clear message

    chunks: list[str] = []
    total = 0
    for path in matched_paths:
        content_file = repo.get_contents(path)
        text = base64.b64decode(content_file.content).decode("utf-8", errors="replace")
        if total + len(text) > max_chars:
            text = text[: max_chars - total]
        chunks.append(f"--- {path} ---\n{text}")
        total += len(text)
        if total >= max_chars:
            break

    return "\n\n".join(chunks)
```
Note: `fnmatch.fnmatch(path, "docs/**/*.md")` does not actually support `**` glob semantics the way shell globbing does — in practice, match with `path.lower().startswith("docs/") and path.lower().endswith(".md")` instead of relying on `fnmatch`'s `**`, which the standard library does not special-case. Flagged here so the planner does not copy the glob pattern verbatim into working code.

### Pattern 3: Structured LLM output with bounded validate-then-repair retry

**What:** Call `.with_structured_output(Plan, method="function_calling", include_raw=True)` so parsing failures are returned (not raised) as `{"raw": ..., "parsed": None, "parsing_error": ...}`. On `parsed is None` or a downstream Pydantic `ValidationError` (e.g. an `skill_tag` value outside the fixed taxonomy — `with_structured_output`'s tool-schema binding does not itself enforce the D-10 taxonomy constraint unless the Pydantic field is typed as a `Literal`/`Enum` over the taxonomy, which it should be), construct a repair prompt that includes the original request, the raw failed output, and the specific validation error, and retry with a fresh LLM call. Bound retries (2-3 attempts is a defensible MVP number per Pitfall 10's "log raw output on failure" and the free-tier rate-limit constraint in STACK.md/PITFALLS.md). After exhausting retries, fail loudly (raise a clear exception surfaced to the run's status) — per D-15, never emit partially-broken plan data.

**When to use:** Every real LLM-structured-output call in this phase (plan generation is the only one in Phase 2's scope — risk explanation is Phase 3).

**Example:**
```python
# Source: reference.langchain.com/python/langchain-openai/chat_models/base/BaseChatOpenAI/with_structured_output
# (method param + include_raw semantics), combined with the standard hand-rolled
# repair-retry pattern (OutputFixingParser is REMOVED from current langchain-core —
# see langchain-ai/langchain#34098, open as of 2026-07-10 — do not use it)
from pydantic import ValidationError

def generate_plan_with_repair(llm, docs_text: str, skill_taxonomy: list[str], max_attempts: int = 3) -> Plan:
    structured_llm = llm.with_structured_output(Plan, method="function_calling", include_raw=True)
    prompt = build_plan_prompt(docs_text, skill_taxonomy)  # includes taxonomy as an explicit constraint

    last_error: str | None = None
    for attempt in range(max_attempts):
        msg = prompt if attempt == 0 else build_repair_prompt(prompt, last_error)
        result = structured_llm.invoke(msg)

        if result["parsing_error"] is not None:
            last_error = str(result["parsing_error"])
            continue

        try:
            # result["parsed"] is already a Plan instance if tool-call args matched
            # the schema; re-validate explicitly for defense-in-depth (Pitfall 10).
            plan = Plan.model_validate(result["parsed"])
            _validate_skill_tags(plan, skill_taxonomy)  # extra guard if not using Literal/Enum
            return plan
        except ValidationError as exc:
            last_error = str(exc)
            continue

    raise RuntimeError(
        f"Plan generation failed schema validation after {max_attempts} attempts: {last_error}"
    )
```

### Anti-Patterns to Avoid

- **Assuming `.with_structured_output()` on a non-OpenAI `base_url` has OpenAI's enforcement guarantees:** ChatOpenAI targets official OpenAI API specs; NVIDIA NIM's OpenAI-compatibility is at the request/response shape level, not the enforcement level — always validate output explicitly, never trust the tool-call binding alone (confirmed by both WebSearch findings and PITFALLS.md Pitfall 10).
- **Reaching for `OutputFixingParser`:** removed from current `langchain-core`; a hand-rolled retry loop (Pattern 3 above) is the only current option.
- **One "introspect the PAT" API call for CONN-03:** no such call exists reachable via PAT Basic auth for org-membership-level scope introspection — see Common Pitfalls below.
- **Full clone for greenfield doc reading:** unnecessary process/filesystem overhead for "README + a handful of markdown files"; reserve `GitPython` clone for Phase 5.
- **Silent brownfield-to-greenfield fallback:** D-09 explicitly forbids this — the brownfield leg must set a distinct, checkable state field that `generate_plan` short-circuits on with a clear message, never attempt real planning from empty context.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| LLM JSON schema binding | Custom prompt-only "return JSON matching this shape" parsing | `ChatOpenAI(...).with_structured_output(Plan, method="function_calling")` | Tool-calling binding is still far more reliable than pure prompt-based JSON extraction, even on a compatibility layer — it's the right first line of defense; the gap it doesn't close is validation/repair, which Pattern 3 adds on top |
| GitHub tree traversal | Recursive per-directory `get_contents("")` walk | `repo.get_git_tree(sha, recursive=True)` | One call vs. one call per directory; already how PyGithub exposes the GitHub Git Trees API, no need to hand-roll pagination or recursion bookkeeping |
| ADO Basic-auth header construction | New auth helper in the new smoke-test code | Existing `ado_client._auth_header()` / `_check_json_response()` | Already built and tested in Phase 1; the smoke-test should call into `ado_client`, not duplicate its auth/response-parsing logic |
| Team roster table access | Raw SQL scattered across routers | A `db/team_roster.py` module mirroring `db/run_metadata.py`'s existing sync-sqlite3 pattern | Established pattern in this codebase (`run_metadata.py`); reuse it rather than introducing a second data-access style |

**Key insight:** The two "don't hand-roll" traps most likely to bite this phase are (1) hand-rolling JSON extraction instead of using tool-calling as the first line of defense, and (2) hand-rolling a "check my own PAT scope" call that does not exist — both traps come from assuming a clean single mechanism exists where the real answer is "combine an existing primitive with defensive validation."

## Common Pitfalls

### Pitfall 1: There is no single ADO API call that reliably answers "what scope does this PAT have"

**What goes wrong:** Teams assume an OAuth-style `/introspect` endpoint exists for PATs and design the smoke-test around one clean call. It doesn't exist in that form. Azure DevOps Basic-auth PATs have no documented introspection endpoint that returns scope for the *currently authenticating* PAT without already knowing its `authorizationId`.

**Why it happens:** The `Pats - List` REST endpoint (`GET https://vssps.dev.azure.com/{org}/_apis/tokens/pats`) documents `Security: accessToken — Personal access token. Use any value for the user name and the token as the password. Type: basic` — meaning its own reference docs say it accepts PAT Basic auth directly. However, separate community-sourced findings state the broader "PAT Lifecycle Management" surface (which includes this same family of endpoints) is intended for Microsoft Entra bearer-token-authenticated org-admin flows, creating a circular dependency for a PAT to introspect itself. **This is a genuine, unresolved contradiction between two credible sources** — flagged `[ASSUMED — needs validation]`, not asserted as fact in either direction.

**How to avoid:** Do not depend on `_apis/tokens/pats` as the primary mechanism. Use the **capability-probe approach** instead (Pitfall 2 has the concrete design) — this is unambiguous, already partially implemented in this codebase (`script_a_ado_smoke_test.py`, `ado_client.verify_work_item`), and matches PITFALLS.md's own documented approach ("Try calling an endpoint requiring a specific scope and catch 203/401/403 errors"). Optionally *attempt* `_apis/tokens/pats?api-version=7.1-preview.1` as a best-effort enrichment (it may work; if it 401s/403s, silently fall back to the probe-based checks rather than treating that failure as the smoke-test's own failure).

**Warning signs:** Smoke-test code that expects a single "scope" field in a response and has no fallback path when that call itself 401s.

### Pitfall 2: Distinguishing "expired," "wrong scope," and "no project access" requires multiple targeted probes, not one

**What goes wrong:** A single failing call (e.g., work item create) can fail for several different underlying reasons (expired token, read-only scope, project doesn't exist, wrong org name) but the HTTP response alone often doesn't disambiguate cleanly — and per the existing codebase's own documented finding, an expired/invalid PAT returns **HTTP 203 with an HTML body**, not a clean 401.

**How to avoid:** Structure CONN-03's smoke-test as an ordered sequence of independent, purpose-built calls, each answering exactly one question, reusing the existing `_check_json_response()` non-JSON/203 detection:
1. **Project access probe:** `GET https://dev.azure.com/{org}/{project}/_apis/wit/workitemtypes?api-version=7.1` (cheap, read-only, project-scoped — fails distinctly if org/project name is wrong or PAT can't see the project at all).
2. **Auth validity check:** inspect the response from step 1 via `_check_json_response()` — a non-JSON (203/HTML) response means "PAT invalid or expired," independent of scope.
3. **Write-scope probe:** create-then-delete (or create-and-leave, since ADO work items aren't hard-deleted easily) a throwaway work item exactly as `script_a_ado_smoke_test.py` already does — this is the only reliable way to confirm **write** scope, since there is no read-only "can I write" check.
4. **Best-effort expiry enrichment:** attempt `_apis/tokens/pats` (Pitfall 1) and if it succeeds, surface `validTo` directly to the lead; if it fails, the lead only learns "the PAT works today" not "and expires on X" — document this as a known MVP limitation, not a bug to chase down given the 2-day budget.

Each probe's pass/fail maps directly to one of D-03's required detail categories (scope, expiry, project access), satisfying "surfaced, not swallowed."

**Warning signs:** A smoke-test that reports only "PAT check failed" with no distinction between the four D-03 categories.

**Phase to address:** This phase (CONN-03), in `ingest_config`/`ado_client` — build the ordered-probe sequence before wiring it as a run-start blocking gate.

### Pitfall 3: GLM via NVIDIA NIM has a documented, dated bug producing malformed tool-call JSON

**What goes wrong:** An NVIDIA Developer Forums thread ("[NIM] [GLM-5] Malformed tool-call JSON (missing '}') via OpenAI-compatible endpoint") documents exactly the failure mode PLAN-04 must defend against — truncated/malformed JSON from a tool call on this exact model family via this exact OpenAI-compatible endpoint. This is not a hypothetical edge case; it is an observed, reported failure pattern.

**Why it happens:** NIM's OpenAI-compatibility layer sits on top of GLM's own tool-calling implementation, which per WebSearch findings does support structured JSON output and function calling, but with less rigorous enforcement than OpenAI's native structured-outputs feature — and free/open models under the NIM hosting layer are more prone to schema/format drift than flagship hosted models (consistent with PITFALLS.md Pitfall 10, now corroborated by a specific bug report for this exact model).

**How to avoid:** Treat the validate-then-repair retry loop (Pattern 3) as load-bearing, not optional polish. Set a generous `max_tokens` (plan JSON for 2-5 epics x 2-6 tasks each is not huge, but truncation at the token cap is a distinct failure mode from malformed-but-complete JSON — budget generously, e.g. 4096-8192 tokens). Log raw output on every failure for debugging. Do not ship a version of `generate_plan` that only tries once.

**Warning signs:** Plan generation "usually works" in a few manual tests but fails unpredictably — this is consistent with a known-flaky upstream behavior, not necessarily a prompt-engineering problem to keep tuning away.

**Phase to address:** Plan generation phase (this phase) — build the repair loop as the first thing wrapping the LLM call, per PITFALLS.md's own guidance, now with added urgency given the specific bug report.

### Pitfall 4: The fixed skill taxonomy must be enforced at the schema level, not just prompted

**What goes wrong:** D-10 requires the LLM tag every task with a value from a fixed list. If this constraint is only stated in the prompt text ("pick from: Frontend, Backend, ...") and `Task.skill_tag` remains typed as `str | None`, a schema-valid-but-taxonomy-invalid value (e.g. "Machine Learning" when the list doesn't include it) will pass Pydantic validation silently, defeating the "reproducibility" goal D-10 states.

**How to avoid:** Either (a) type the skill-tag field as a `Literal[...]` or `Enum` over the taxonomy in a way `.with_structured_output()`'s tool-schema binding can enforce structurally, or (b) if changing `plan.py`'s shared `Task.skill_tag: str | None` type is judged too invasive for this phase (it's the one shared schema per CLAUDE.md — changing it affects `stub_plan.py`/`push_to_ado.py`/frontend consumers too), add an explicit post-parse validation step (`_validate_skill_tags` in Pattern 3's example) that checks every task's `skill_tag` against the taxonomy list and triggers the repair-retry loop on violation, exactly like a schema validation failure. Either is acceptable; silently trusting the prompt alone is not.

**Warning signs:** Tasks with skill tags that don't match anything in the taxonomy constant, discovered only when Phase 3's skill-matching logic can't find a corresponding team skill.

**Phase to address:** This phase — decide (a) vs (b) during planning, not as an afterthought once `generate_plan` is "working."

### Pitfall 5: `fnmatch`'s `**` does not mean what shell/glob users expect

**What goes wrong:** Python's standard-library `fnmatch` module treats `*` as "match anything including `/`" — it has no special double-star recursive-directory semantics the way `pathlib.Path.glob("**/*.md")` or shell globstar does. A pattern written as `fnmatch.fnmatch(path, "docs/**/*.md")` may behave unexpectedly (in practice `*` already matches across what look like path separators in a flat string, so it can appear to work by accident, then behave differently once path structures are less trivial).

**How to avoid:** For matching "any `.md` file under `docs/`" against a list of path strings (already flat, already known from `get_git_tree`), just check `path.lower().startswith("docs/") and path.lower().endswith(".md")` directly — simpler and unambiguous. Reserve `fnmatch`/`pathlib.glob` for actual filesystem glob use cases, not flat path-string lists already enumerated via the Git Trees API.

**Warning signs:** Doc files not being picked up (or unrelated files being picked up) when the repo's `docs/` folder has more than one level of nesting.

**Phase to address:** This phase — `github_client.py`'s doc-matching logic.

## Code Examples

### ADO PAT smoke-test — reusing existing `ado_client` helpers
```python
# Source: adapted from backend/app/services/ado_client.py's existing
# _auth_header() / _check_json_response() (already in this codebase) combined
# with the general "probe by capability" approach corroborated via WebSearch
# (Microsoft Q&A: "the recommended approach is to call an endpoint requiring a
# specific scope and catch 203/401/403 errors")
import httpx
from app.services.ado_client import _auth_header, _check_json_response, _org_project, _API_VERSION

async def check_project_access() -> dict:
    org, project = _org_project()
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitemtypes?api-version={_API_VERSION}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(url, headers=_auth_header())

    is_json, body = _check_json_response(response)
    if not is_json:
        return {"check": "project_access", "passed": False,
                "reason": "PAT invalid or expired (non-JSON/203 response)"}
    if response.status_code == 401:
        return {"check": "project_access", "passed": False, "reason": "PAT auth rejected (401)"}
    if response.status_code == 403:
        return {"check": "project_access", "passed": False,
                "reason": "PAT lacks access to this project (403)"}
    if response.status_code != 200:
        return {"check": "project_access", "passed": False,
                "reason": f"unexpected status {response.status_code}"}
    return {"check": "project_access", "passed": True, "reason": None}
```

### Structured output call shape (parsing_error is returned, not raised)
```python
# Source: reference.langchain.com/python/langchain-openai/chat_models/base/BaseChatOpenAI/with_structured_output
# "include_raw=True: parsing errors are caught and returned within a dictionary
# containing 'raw', 'parsed' (None if parsing failed), and 'parsing_error'"
structured_llm = llm.with_structured_output(Plan, method="function_calling", include_raw=True)
result = structured_llm.invoke(prompt_messages)
# result = {"raw": AIMessage(...), "parsed": Plan(...) | None, "parsing_error": Exception | None}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `OutputFixingParser` for repairing malformed structured output | Hand-rolled validate-then-repair-prompt retry loop | Removed from `langchain-core`/`langchain`, open feature request langchain-ai/langchain#34098 as of 2025-11-25, still unresolved as of this research (2026-07-10) | Any plan written assuming `OutputFixingParser` exists will fail at import; the planner must design the repair loop from scratch (Pattern 3 above), not reference this removed API |
| GLM-5 / GLM-5.1 via NVIDIA NIM | GLM-5.2 (as of 2026-07-02) | Third model-ID rotation in 3 months (GLM-5 -> 5.1 -> 5.2) | Confirms STACK.md's existing flag: keep `NVIDIA_CHAT_MODEL` as an env var, verify live before each session — this phase's `services/llm.py` must read the model ID from env, never hardcode `"z-ai/glm-5.2"` |

**Deprecated/outdated:**
- `OutputFixingParser`: removed, no direct replacement — use a hand-rolled retry loop (Pattern 3).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `_apis/tokens/pats` (Pats-List) can be called with PAT Basic auth to self-introspect scope/expiry, OR it requires Entra bearer auth and will 401/403 for a plain PAT — genuinely unresolved from sources found this session | Pitfall 1, Standard Stack | If assumed to work and it doesn't: smoke-test code has a dead code path that always falls through to probe-based checks (low risk, since probe-based checks are the primary recommendation anyway and this is explicitly a best-effort enrichment, not the primary mechanism) |
| A2 | GLM-5.2 via NIM supports `method="function_calling"` tool-calling reliably enough to be the primary structured-output mechanism (vs. falling back to prompt-only JSON mode) | Architecture Patterns, Pattern 3 | If GLM's tool-calling is more broken than assumed, the repair-retry loop may need a `method="json_mode"` fallback path added; the retry loop design already tolerates this (it retries on any parse/validation failure) but does not currently attempt a different `method` on retry — the planner should decide whether attempt 2+ should also try `json_mode` as an alternate extraction method, not just re-prompt the same `function_calling` binding |
| A3 | `docs/**/*.md` capped-size doc concatenation (no vector store) will fit comfortably and meaningfully within GLM-5.2's context window without truncation issues for a typical greenfield MVP repo's doc set | Pattern 2 | If a greenfield repo has unusually large docs (unlikely for MVP demo repos but possible), the `max_chars` cap (60K chars ~ 15-20K tokens) could cut off relevant content mid-document; D-11 already specifies "capped at a sensible total size" so this is within spec, but the exact cap value is this research's own choice, not user-specified |

**If this table is empty:** N/A — see entries above.

## Open Questions (RESOLVED)

1. **(RESOLVED)** Does `_apis/tokens/pats?api-version=7.1-preview.1` actually succeed when called with the project's own ADO_PAT via Basic auth, in this specific org?
   - What we know: Microsoft's own reference docs for `Pats - List` state `Security: accessToken` type `basic`, implying PAT auth is accepted; separately, general community sourcing describes the wider "PAT Lifecycle Management" API family as intended for Entra-authenticated org-admin flows.
   - What's unclear: Whether this specific `tokens/pats` (not `tokenadmin/personalaccesstokens`) endpoint, called by a PAT for its own authorizations, actually returns 200 in practice, or 401/403.
   - Resolution: Treated as best-effort only (per Pitfall 1) — Plan 02-01 tries it, and if it fails, does not block the smoke-test on it; the probe-based approach (Pitfall 2) already independently satisfies CONN-03's four required checks (auth validity via 203/401 detection, write scope via create-throwaway-item, project access via workitemtypes call) except for exact expiry date, which becomes "unknown, but the PAT works today" if this call fails. See `02-01-PLAN.md`.

2. **(RESOLVED)** Should the repair-retry loop vary its extraction `method` across attempts (e.g., attempt 1 = `function_calling`, attempt 2 = `json_mode`), or always retry the same method with a repair prompt appended?
   - What we know: Both methods exist in `langchain-openai`; `function_calling` is the safer default for a non-OpenAI endpoint (Alternatives Considered table); a same-method retry with an explicit error-repair prompt is the standard documented pattern (RetryWithErrorOutputParser-equivalent, hand-rolled).
   - What's unclear: Whether varying the method on retry meaningfully improves success odds against GLM/NIM specifically, versus just adding complexity — no source found tests this combination.
   - Resolution: Plan 02-04 uses same-method + repair-prompt retry (simpler, matches Pattern 3's example) for the MVP; method-switching is deferred as a possible refinement only if empirical testing during implementation shows the same-method retry doesn't recover from the documented malformed-JSON bug (Pitfall 3). See `02-04-PLAN.md`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyGithub | REPO-02 greenfield doc fetch | Not yet installed (installed successfully during this research session's verification) | 2.9.1 | — (install step required in plan) |
| langchain-openai | PLAN-04 structured plan generation | Not yet installed (installed successfully during this research session's verification) | 1.3.4 | — (install step required in plan) |
| GitPython | Not needed this phase | Not yet installed | 3.1.50 | Deferred to Phase 5 — do not install this phase |
| NVIDIA NIM API key (`NVIDIA_API_KEY`) | PLAN-04 LLM calls | Unknown — not present in `.env.example`; only `ANTHROPIC_API_KEY` slot exists there, and STACK.md/CLAUDE.md both specify NVIDIA NIM as the actual LLM provider | — | Blocking if absent — the plan must add a `NVIDIA_API_KEY` (and `NVIDIA_CHAT_MODEL`) slot to `.env.example`/`.env`; this is a config gap, not a code gap |
| GitHub PAT/token (`GITHUB_TOKEN`) | REPO-02 doc fetch via PyGithub | Present in `.env.example` slot, actual value unknown/unverified this session | — | Blocking if absent for a private target repo; PyGithub can read public repos unauthenticated at lower rate limits, but D-11's fetch mechanism should use the token when present |
| ADO PAT (`ADO_PAT`) | CONN-03 smoke-test | Per STATE.md: **currently expired**, blocking Phase 1 Task 2 | — | Blocking — STATE.md documents this as an open blocker requiring a fresh PAT before Script A (and by extension this phase's smoke-test) can be verified against real ADO |

**Missing dependencies with no fallback:**
- `NVIDIA_API_KEY` / `NVIDIA_CHAT_MODEL` env slots — must be added to `.env`/`.env.example` before `generate_plan` can be implemented or tested against the real API.
- A valid (non-expired) `ADO_PAT` — per STATE.md, this is already a known, carried-forward blocker from Phase 1 and directly blocks verifying this phase's CONN-03 smoke-test against real ADO.

**Missing dependencies with fallback:**
- `GITHUB_TOKEN` — PyGithub can operate unauthenticated for public repos at a lower rate limit; not a hard blocker for a single small doc-fetch call, but should still be wired through `.env` per CLAUDE.md's stated env-var list.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | None detected in `backend/` (no `pytest.ini`, `conftest.py`, or `tests/` directory found) |
| Config file | none — see Wave 0 |
| Quick run command | `cd backend && pytest -x` (once added) |
| Full suite command | `cd backend && pytest` (once added) |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONN-03 | Smoke-test correctly reports pass/fail per check (auth, scope, expiry, project access) against mocked ADO responses (203/401/403/200) | unit | `pytest tests/test_ado_smoketest.py -x` | ❌ Wave 0 |
| PLAN-04 | Malformed/invalid LLM structured output triggers repair retry, and exhausting retries raises a clear error (not broken plan data) | unit | `pytest tests/test_generate_plan.py -x` (mock the LLM call) | ❌ Wave 0 |
| PLAN-02 | Every generated task's `skill_tag` is a member of the fixed taxonomy | unit | `pytest tests/test_generate_plan.py::test_skill_tags_in_taxonomy -x` | ❌ Wave 0 |
| REPO-02 | Doc-matching correctly selects README + `docs/**/*.md` paths from a `get_git_tree`-shaped fixture and excludes non-doc paths | unit | `pytest tests/test_github_client.py -x` | ❌ Wave 0 |
| REPO-01 | Conditional edge routes to `read_docs_greenfield` when `repo_mode="greenfield"` and to `ingest_brownfield_stub` when `repo_mode="brownfield"`, defaulting to greenfield when unset | unit | `pytest tests/test_build_graph.py -x` | ❌ Wave 0 |
| TEAM-01/TEAM-02 | Team CRUD (add/edit/remove) persists correctly and roster is readable before planning | integration | `pytest tests/test_team_roster.py -x` (sqlite temp file) | ❌ Wave 0 |
| D-12 | No-docs greenfield repo blocks with a clear message rather than best-effort planning | unit | `pytest tests/test_github_client.py::test_no_docs_blocks -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -x` (fast subset touching the changed module)
- **Per wave merge:** `pytest` (full suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/conftest.py` — shared fixtures (temp sqlite path, mocked `httpx` responses for ADO probes, a fake `get_git_tree` fixture)
- [ ] `backend/tests/test_ado_smoketest.py` — covers CONN-03
- [ ] `backend/tests/test_generate_plan.py` — covers PLAN-02, PLAN-04 (mock `ChatOpenAI`/`with_structured_output` to return controlled malformed/valid outputs)
- [ ] `backend/tests/test_github_client.py` — covers REPO-02, D-12
- [ ] `backend/tests/test_build_graph.py` — covers REPO-01 conditional routing
- [ ] `backend/tests/test_team_roster.py` — covers TEAM-01/TEAM-02
- [ ] Framework install: `pip install pytest pytest-asyncio` — no test framework present in the repo at all yet; this is a from-scratch Wave 0 for the whole backend, not just this phase

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | Partial — the ADO PAT and NVIDIA/GitHub tokens are the only credentials in play; no user auth exists or should be built (CLAUDE.md non-negotiable) | `.env`-only secrets, never logged (already the pattern in `ado_client.py`) |
| V3 Session Management | No | N/A — no user sessions in this MVP |
| V4 Access Control | No | N/A — single shared lead, no RBAC (explicitly out of scope) |
| V5 Input Validation | Yes | Pydantic (`Plan`/`Epic`/`Task` schema validation, D-15); team roster fields (email format) should be validated at the FastAPI request-model layer |
| V6 Cryptography | No | N/A — no custom crypto; Basic auth over HTTPS is ADO's own documented mechanism, not something this project implements |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| PAT/API key leakage via logs or error messages | Information Disclosure | Never log the raw PAT/API key value; `ado_client.py` already follows this (auth header built fresh from `os.environ`, never echoed) — extend the same discipline to the new smoke-test probes and `services/llm.py`'s NVIDIA key handling |
| LLM prompt injection via repo doc content (a malicious README could attempt to influence the plan-generation prompt) | Tampering | Low severity for a local single-lead MVP tool with no multi-tenant exposure, but worth a one-line mitigation: treat fetched doc content as data within the prompt, never as instructions — standard prompt-templating (data in a clearly delimited section) already achieves this; no special library needed |
| Team roster email field accepting non-email garbage that later silently fails ADO assignment resolution (Phase 3 concern, but the field is captured in this phase) | Tampering / Data Integrity | Basic email-format validation at the FastAPI Pydantic model layer for `TeamMember.email` (e.g. Pydantic's `EmailStr` type, if the `email-validator` extra is added) — cheap insurance against garbage data entering the roster that Phase 3 would otherwise have to defend against alone |

## Sources

### Primary (HIGH confidence)
- [with_structured_output — LangChain Reference](https://reference.langchain.com/python/langchain-openai/chat_models/base/BaseChatOpenAI/with_structured_output) — method parameter semantics, `include_raw` error-handling behavior
- [PyGithub Repository — official docs](https://pygithub.readthedocs.io/en/latest/github_objects/Repository.html) — `get_git_tree`, `get_contents`, `get_readme` signatures
- [Pats - List — Azure DevOps REST API, Microsoft Learn](https://learn.microsoft.com/en-us/rest/api/azure/devops/tokens/pats/list?view=azure-devops-rest-7.1) — endpoint URL, response shape (`scope`, `validTo`), documented Basic PAT auth
- [Pats - Create — Azure DevOps REST API, Microsoft Learn](https://learn.microsoft.com/en-us/rest/api/azure/devops/tokens/pats/create?view=azure-devops-rest-7.1) — same auth model confirmation
- `pip index versions PyGithub / GitPython / langchain-openai` — direct PyPI verification, run in this research session (2026-07-10), confirms no drift from STACK.md's 2026-07-09 findings
- `slopcheck install PyGithub GitPython langchain-openai` — run in this research session against the project's own venv; all three `[OK]`
- Direct reads of `backend/app/models/plan.py`, `backend/app/graph/*`, `backend/app/services/ado_client.py`, `backend/app/db/run_metadata.py`, `backend/scripts/script_a_ado_smoke_test.py` — authoritative for existing code shape/patterns to extend

### Secondary (MEDIUM confidence)
- [langchain-ai/langchain#34098 — GitHub issue](https://github.com/langchain-ai/langchain/issues/34098) — `OutputFixingParser` removal, open as of 2025-11-25, unresolved as of 2026-07-10 (WebFetch-summarized from the issue thread)
- [NVIDIA Developer Forums — "[NIM] [GLM-5] Malformed tool-call JSON" thread](https://forums.developer.nvidia.com/t/nim-glm-5-malformed-tool-call-json-missing-via-openai-compatible-endpoint-opencode/360809) — corroborates PLAN-04's repair-loop necessity with a specific, dated bug report
- [docs.api.nvidia.com/nim/reference/z-ai-glm-5.2](https://docs.api.nvidia.com/nim/reference/z-ai-glm-5.2) — GLM-5.2 confirmed current as of 2026-07-02, consistent with STACK.md
- Microsoft Q&A / community threads on ADO PAT scope introspection and 203/HTML expired-PAT behavior — cross-referenced across multiple sources, consistent with this codebase's own already-implemented `_check_json_response()` handling

### Tertiary (LOW confidence)
- General WebSearch synthesis on "PAT Lifecycle Management API requires Entra bearer token" — single-search-synthesis claim, not independently verified against an official Microsoft doc page stating this restriction explicitly for the exact `tokens/pats` (vs. `tokenadmin/personalaccesstokens`) endpoint; treated as Open Question 1, not fact

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all three new packages verified via PyPI + slopcheck in this session, versions match already-approved STACK.md
- Architecture (conditional edge, doc-fetch mechanism): HIGH — LangGraph pattern already documented in ARCHITECTURE.md and confirmed via official docs; PyGithub tree-vs-per-file mechanism confirmed via official reference docs
- Pitfalls (ADO PAT introspection ambiguity, GLM/NIM structured-output reliability): MEDIUM — both are corroborated by multiple sources but retain genuine unresolved ambiguity (documented as Open Questions / Assumptions rather than asserted as settled fact)

**Research date:** 2026-07-10
**Valid until:** 2026-07-24 (14 days — shorter than the default 30 given the actively-churning NVIDIA NIM model catalog and the open, unresolved `OutputFixingParser` GitHub issue that could change status at any time)

---
*Phase 2 research: Config, Team & Greenfield Planning*
*Researched: 2026-07-10*
