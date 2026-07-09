# CLAUDE.md

This file is the standing context for Claude Code on this repo. Read it before
making changes. The full design rationale lives in `project-spec.md` at the repo
root — refer to it for the "why," use this file for the "how to work here."

## What we're building

An AI project-planning tool for engineering leads. A lead connects an Azure
DevOps project + a GitHub repo, enters team members, and gets an AI-generated
implementation plan with a risk score. The lead edits the plan conversationally,
approves it, and the tool pushes tasks into Azure DevOps as assigned work items —
team members see their tasks on their own existing ADO boards. No new product
surface for team members; ADO is where they live.

Two-day MVP. Optimize for a working, demo-able end-to-end path over completeness.

## Non-negotiable constraints

- **No user auth.** Single shared session, opened only by the lead. Do not add
  login, sessions, or user-scoped access — it's explicitly out of scope for this
  MVP (see "Known limitations" in project-spec.md).
- **One Azure DevOps PAT**, read from `.env`, used for every ADO call. Never
  prompt for or store per-user ADO credentials.
- **Team members are typed in manually** (name, email, designation, skills text,
  level) via a plain form — not pulled from an org directory yet. Leave this
  swappable: the `graph/users` endpoint will replace free text with a dropdown
  once more real ADO users exist. Don't build the dropdown now.
- **Greenfield vs. brownfield is a manual toggle set by the lead** — never infer
  it from repo contents.
- **Risk score must be computed in plain Python, never by the LLM.** The LLM may
  only generate the narrative explanation that sits next to the number. If you
  find yourself asking the LLM to "return a risk score," stop — that's a bug.
- **The plan is a single JSON object matching the schema in project-spec.md.**
  Every node that touches the plan reads and returns this exact shape. Don't
  invent parallel representations (e.g., a separate task table) — the JSON is
  the source of truth; the UI renders it.
- **Work-item push only fires when `suggested_assignee` resolves to a real ADO
  org identity.** If it doesn't resolve, log what would have been sent and skip
  the API call — don't fail silently and don't fail loudly either.
- **Never build ADO notifications.** They're a side effect of ADO's own default
  subscription firing when `System.AssignedTo` changes. Building anything that
  looks like a notification system here is out of scope and wrong.

## Stack

- Backend: FastAPI (Python), LangGraph for the planning pipeline, SQLite for
  storage (including LangGraph's checkpointer), Chroma (persistent local mode)
  for the brownfield RAG index.
- Frontend: Next.js.
- LLM: Anthropic API. Use structured output / tool calling for anything that
  must parse as JSON — never regex/parse free-form LLM text for the plan.
- External APIs: Azure DevOps REST API, GitHub API.

## LangGraph pipeline — the core of this app

State object, node sequence, and conditional edges are specified in full in
`project-spec.md` under "LangGraph pipeline." Key shape to remember while
coding:

```
ingest_repo → [conditional: greenfield | brownfield] → generate_plan
  → compute_risk (deterministic) → interrupt() → edit_plan (loops) → push_to_ado
```

`interrupt()` and the checkpointer are how plan review/editing and version
history work — don't build a separate versioning table; read it from graph
checkpoints.

## Before touching ADO push code

Two standalone scripts must run and succeed before their logic gets wired into
any LangGraph node — see "Setup checklist" in project-spec.md:
- Script A: create + self-assign one ADO work item via the PAT.
- Script B: send one repo file to the LLM, get back JSON matching the plan
  schema.

If asked to build `push_to_ado` or `generate_plan` and these scripts don't
exist yet or haven't been run, build and run them first.

## Azure DevOps API gotchas (don't relearn these)

- Work item creation/update requires header
  `Content-Type: application/json-patch+json` exactly — this is the most common
  point of failure.
- Assignment is just writing an email string to `System.AssignedTo`. That's the
  entire mechanism — nothing else is needed for a member to see their task.
- Auth is Basic with an empty username: `Basic {base64(":" + PAT)}`.

## Style / scope discipline

- This is a 2-day MVP. When a feature could be built simply or "properly," ask
  which the spec calls for before building the heavier version.
- Don't add: two-way sync with ADO, dependency-aware scheduling/enforcement
  (displaying `depends_on` is enough), multi-repo support, or RBAC — all
  explicitly deferred in project-spec.md.
- If an LLM-generated artifact (onboarding doc, risk narrative, estimates) could
  be mistaken for verified fact by a user, the UI copy around it should say
  otherwise (e.g., "AI-suggested," "verify before relying on this").

## File/folder expectations

- Keep the plan JSON schema in one shared location (e.g., a Pydantic model) that
  both the LangGraph nodes and the API response models import — don't duplicate
  the shape.
- `.env` holds `ADO_ORG`, `ADO_PROJECT`, `ADO_PAT`, `GITHUB_TOKEN`,
  `ANTHROPIC_API_KEY`, `DATABASE_URL`. Never commit this file; check `.gitignore`
  covers it before first commit.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**AI Project Planning & Onboarding Dashboard**

A local tool for an engineering lead kicking off a project on Azure DevOps and GitHub. The lead connects an ADO project and a GitHub repo, enters their team (name, designation, skills, experience), and the tool reads the repo — for greenfield it reads the docs, for brownfield it ingests the existing codebase (embedded for RAG) and produces an onboarding summary so the team understands what exists before planning. It then generates an editable implementation plan (epics → skill-tagged, estimated, auto-assigned tasks) with risk flags for skill-coverage gaps, and on approval pushes the tasks straight into Azure DevOps as work items assigned to the right people.

**Core Value:** One clean end-to-end flow: connect ADO + GitHub → understand the repo → generate a skill-aware, load-balanced, editable plan → push approved tasks into ADO as assigned work items. If everything else fails, that single flow must work end to end.

### Constraints

- **Timeline**: 2-day MVP — scope aggressively toward one working end-to-end flow.
- **Tech stack**: Python FastAPI + LangGraph backend, React frontend — LangGraph handles the branching and interrupt/resume human-review loop cleanly.
- **AI models**: GLM via NVIDIA free API (OpenAI-compatible) for LLM tasks; NVIDIA embeddings for RAG — free/open-source only, no paid models.
- **Auth**: None — single lead uses it locally; one shared ADO PAT for all API calls.
- **Integration**: One Azure DevOps project + one GitHub repo per run; ADO push is one-way.
- **Estimates**: Tasks estimated in hours/days (maps to ADO Original Estimate).
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12+ | Backend runtime | Required floor for FastAPI 0.139/LangGraph 1.2/langchain-core 1.4 (`requires_python >=3.10`, but 3.12 avoids edge-case dependency friction and is the practical 2026 default). |
| FastAPI | 0.139.0 | HTTP API layer serving the React frontend and hosting the LangGraph run/interrupt/resume endpoints | Already committed. Verified current on PyPI (released ~2026-07-01). Async-native, plays cleanly with LangGraph's async streaming, and `fastapi[standard]` bundles Uvicorn + the dev CLI so a 2-day MVP needs zero extra tooling decisions. |
| Uvicorn | 0.51.0 (via `fastapi[standard]`) | ASGI server | Standard FastAPI companion; ships with `fastapi[standard]`, no separate pin needed beyond what that extra resolves. |
| LangGraph | 1.2.8 | Orchestrates the greenfield/brownfield branch and the human-review interrupt-and-resume loop | Already committed. Interrupt/resume is a documented, first-class primitive (`interrupt()` + `Command(resume=...)`) purpose-built for exactly this "pause graph, wait for a human edit, resume" pattern — this is the single strongest reason to use LangGraph over a hand-rolled state machine. |
| langgraph-checkpoint (in-memory) | bundled with langgraph 1.2.8 (`langgraph.checkpoint.memory.InMemorySaver`) | Checkpointer that makes interrupt/resume durable across the pause | For a **2-day local MVP with no auth and a single lead**, `InMemorySaver` is correct: zero setup, checkpoints live in the FastAPI process memory, and the "durability" you actually need (surviving a single pause-for-human-review within one running process) is fully covered. Do not reach for a SQLite/Postgres checkpointer — it's unnecessary infrastructure for this scope. |
| langgraph-checkpoint-sqlite | 3.1.0 (optional, not needed for MVP) | Persistent checkpointer surviving process restarts | Only pull this in if the 2-day timebox slips and you need the review loop to survive a backend restart mid-review. Not recommended to add proactively — it's the first thing to cut for scope. |
| React | 19.2.7 | Frontend UI (plan view, diff preview, onboarding summary) | Already committed. Current stable major (React 19 line). |
| Vite | 8.1.4 | Frontend build tool / dev server | Fastest path from zero to a running React dev server; no CRA-era config tax. Standard 2026 default for new React projects. |
| TypeScript | 5.x (via Vite's React-TS template — do not jump to TS 7.0 for a 2-day MVP) | Type safety for plan/diff/work-item data models shared conceptually with the FastAPI Pydantic schemas | TypeScript 7.0 (the Go-ported compiler) is brand-new; pin to the 5.x line Vite's official template ships to avoid tooling churn eating into the 2-day budget. |
### Supporting Libraries — Backend
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langchain-openai` | 1.3.4 | OpenAI-compatible SDK wrapper (`ChatOpenAI`) used to call GLM via NVIDIA NIM's OpenAI-compatible endpoint, and inside LangGraph nodes | Use this, **not** `langchain-nvidia-ai-endpoints`. NVIDIA NIM's hosted catalog is explicitly OpenAI-compatible (`base_url="https://integrate.api.nvidia.com/v1"`), and the project's own stated integration path is "OpenAI-compatible SDK." `ChatOpenAI` with a custom `base_url` is fewer moving parts, one less dependency to version-match, and identical LangGraph node code to what you'd use with real OpenAI later if the team ever swaps providers. |
| `langchain-core` | 1.4.9 | Message/prompt primitives used inside LangGraph nodes | Pulled in transitively by `langchain-openai` and `langgraph`; pin explicitly to avoid resolver surprises. |
| `openai` | latest (pulled as a dependency of `langchain-openai`; do not pin separately) | Underlying OpenAI Python SDK that `ChatOpenAI` wraps | Not called directly in most cases — `langchain-openai` is the integration surface used inside LangGraph nodes. Only reach for the raw `openai` client if you need a quick one-off script (e.g., testing the NIM key) outside the graph. |
| `httpx` | 0.28.1 | Direct REST calls to Azure DevOps (see ADO section below) and general async HTTP | Already a FastAPI/Starlette-ecosystem standard; async-native, works naturally inside async LangGraph nodes and FastAPI route handlers. |
| `azure-devops` (`azure-devops-python-api`) | 7.1.0b4 (still beta — see flag below) | Typed Python client for Azure DevOps REST API (work item creation/update) | Use **only** for the narrow, well-trodden `wit_client.create_work_item()` / `update_work_item()` calls. See "What NOT to Use" — this package is stale (last released Nov 2023) and the ADO REST API has moved to `api-version=7.2` since. For a 2-day MVP, calling the ADO REST API directly via `httpx` with `api-version=7.1` (still fully supported) is the safer default; use the SDK only if the team wants typed models and accepts the staleness risk. |
| `PyGithub` | 2.9.1 | Read repo contents, file tree, and docs (greenfield) or full source (brownfield) from GitHub via the GitHub REST API | Actively maintained, typed, and covers everything needed to read a repo's file tree and file contents without hand-rolling REST calls. For brownfield RAG ingestion, either PyGithub's `Repository.get_contents()` (works with just a PAT, no local clone) or a shallow `git clone` via GitPython — see architecture note below. |
| `GitPython` | 3.1.50 | Shallow-clone a repo locally for brownfield codebase ingestion when the repo is large | Prefer this over PyGithub's file-by-file API when brownfield repos are non-trivial in size — `git clone --depth 1` once and walk the filesystem is dramatically fewer API calls (and avoids GitHub REST rate limits) than fetching every file over the API. |
| `chromadb` | 1.5.9 | Local embedded vector store for brownfield RAG | See "Vector Store" rationale below — this is the gap-fill the team asked for. |
| `langchain-chroma` | 1.1.0 | LangChain-idiomatic wrapper around Chroma for use inside LangGraph RAG nodes | Keeps the retrieval node's code in the same LangChain vocabulary (`Document`, `VectorStore.similarity_search`) as the rest of the graph; thin wrapper, not extra infrastructure. |
| `langchain-text-splitters` | 1.1.2 | Chunking source files before embedding | `RecursiveCharacterTextSplitter` (or `Language.PYTHON`/`Language.JS` splitters for code-aware chunking) is the standard, low-effort way to chunk a codebase for RAG without hand-rolling chunk boundaries. |
| `pydantic` | 2.13.4 | Request/response schemas for FastAPI, and typed LangGraph state | Already implied by FastAPI; pin explicitly since LangGraph state `TypedDict`s and Pydantic models will both be used — Pydantic v2 is required by current FastAPI/LangChain versions. |
| `python-dotenv` | 1.2.2 | Load `NVIDIA_API_KEY`, `ADO_PAT`, `GITHUB_TOKEN` from a local `.env` | Simplest possible secrets handling for a no-auth, single-local-lead MVP — do not build a secrets manager. |
### Supporting Libraries — Frontend
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `@tanstack/react-query` | 5.101.2 | Data fetching / caching for the plan, onboarding summary, and interrupt-state polling against the FastAPI backend | Standard 2026 default for React data fetching; handles the "poll/refetch plan state after resuming a LangGraph interrupt" pattern cleanly with minimal code — better fit than hand-rolled `useEffect` fetch chains for a 2-day build. |
| `axios` | 1.18.1 | HTTP client used by React Query's fetchers | Optional — `fetch` is also fine. Use `axios` only if the team wants interceptors (e.g., a single place to attach a base URL) for near-zero extra cost. |
| `react-diff-view` | latest (npm, actively maintained fork line — verify exact pin at install time) | Renders the diff preview when the lead edits the plan via LLM chat ("split this task", "reassign") before accepting | See "Diff Rendering" rationale below — this is the gap-fill the team asked for. |
| `diff` | 9.0.0 | Computes the actual diff (old plan JSON/text vs proposed new plan) that `react-diff-view`'s `parse-diff`-style renderer displays | `react-diff-view` renders unified-diff *hunks*; you need something to produce those hunks from two plan states. `diff` (jsdiff) is the standard, dependency-light way to diff two strings/JSON-serialized objects before rendering. |
## Installation
# Backend (Python 3.12+, use a venv)
# Frontend
## GLM via NVIDIA NIM — Exact Wiring
# Used directly inside a LangGraph node, e.g.:
### CRITICAL FLAG — NVIDIA NIM free catalog model IDs churn frequently
- Put the model ID behind an environment variable (`NVIDIA_CHAT_MODEL=z-ai/glm-5.2`), never hardcode it in graph node code.
- Before building, confirm `z-ai/glm-5.2` (or whatever is current) is live by hitting `https://integrate.api.nvidia.com/v1/models` with the API key, or checking `https://build.nvidia.com/z-ai/glm-5.2`.
- Because this is a 2-day local MVP with no production SLA concerns, this is a minor annoyance (re-point one env var if the model gets deprecated mid-build), not a blocker — but the roadmap should not assume the exact string `z-ai/glm-5.2` is stable for more than a few weeks.
## Vector Store for Brownfield RAG — Chroma
| Option | Verdict for this project |
|--------|---------------------------|
| **Chroma** (chosen) | Runs fully embedded in-process (`chromadb.PersistentClient(path="./chroma_data")`), zero external service, persists to disk automatically between runs without any setup. Has first-class metadata filtering (needed to filter RAG results by file path/language when building the onboarding summary), and a mature LangChain integration (`langchain-chroma` 1.1.0). This is the standard default for "local RAG prototype" in 2026 for exactly this reason: least infrastructure for the capability delivered. |
| FAISS (`faiss-cpu` 1.14.3) | A pure similarity-search index, not a database — no built-in metadata storage/filtering or persistence layer; you'd hand-roll ID-to-metadata mapping and disk persistence. More setup work for no benefit at this scale (a single codebase's worth of chunks, not millions of vectors). |
| LanceDB (`lancedb` 0.34.0) | Excellent for larger-scale, production RAG (columnar on-disk format, versioning) but is more capability than a 2-day MVP needs, and its LangChain integration is less battle-tested than Chroma's. Reasonable "if this project grows" upgrade path, not a day-one pick. |
## Azure DevOps Work Item API — Use REST Directly (via `httpx`), Not the SDK, as the Primary Path
# fields example (JSON Patch document):
# [{"op": "add", "path": "/fields/System.Title", "value": "Implement auth middleware"},
#  {"op": "add", "path": "/fields/System.AssignedTo", "value": "jane@company.com"},
#  {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate", "value": 8}]
## Diff Rendering — `react-diff-view` + `diff` (jsdiff)
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| `langchain-openai`'s `ChatOpenAI` with NIM `base_url` | `langchain-nvidia-ai-endpoints`'s `ChatNVIDIA` | If the team later self-hosts a NIM container locally (not the free hosted catalog) — `ChatNVIDIA` has NVIDIA-specific conveniences for local NIM deployments (default ports, health checks). Not needed for the hosted free API this project uses. |
| Direct ADO REST via `httpx` | `azure-devops` SDK (`azure-devops-python-api`) | If the team wants typed request/response models and is fine pinning a beta package last updated Nov 2023. Fine as a fallback, not the default. |
| Chroma (embedded/local) | LanceDB | If brownfield codebases turn out to be large (100K+ files) or the project grows past MVP into something needing versioned/columnar vector storage. |
| Chroma (embedded/local) | FAISS | If raw nearest-neighbor speed at very large scale matters more than convenience — not the case for a single-repo RAG use case. |
| `react-diff-viewer-continued` | `react-diff-view` + `diff` | If the plan diff needs custom hunk-level rendering (e.g., per-field diffing of task JSON rather than whole-text diffing) — worth revisiting post-MVP. |
| `InMemorySaver` checkpointer | `langgraph-checkpoint-sqlite` | If the interrupt/resume review loop must survive a backend process restart (e.g., lead closes laptop mid-review) — not needed for a 2-day demo but a natural next step. |
| GitPython shallow clone | PyGithub `get_contents()` per-file | For small greenfield repos where you're only reading a handful of doc files, PyGithub's per-file API call is simpler than managing a local clone directory — use PyGithub there, GitPython for brownfield full-codebase ingestion. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|--------------|
| `azure-devops` SDK as the *only* ADO integration path | Stale (no release since Nov 2023), still in beta after years, adds a dependency that could silently break against future ADO API changes with no maintainer response | Direct REST calls via `httpx` — see rationale above |
| Building auth/login, RBAC, or multi-user session handling | PROJECT.md explicitly scopes this out — single local lead, one shared PAT, no auth, 2-day timebox | A `.env` file with `ADO_PAT`, `GITHUB_TOKEN`, `NVIDIA_API_KEY`; nothing else |
| A hosted/external vector DB (Pinecone, Weaviate Cloud, Qdrant Cloud) | Adds network dependency, account setup, and cost for a single local run with no persistence-across-machines requirement | Chroma in embedded/local mode |
| `langchain-nvidia-ai-endpoints`'s `NVIDIAEmbeddings` LangChain wrapper for the embedding calls | Its embedding interface doesn't cleanly expose the NIM-specific `input_type` (`query` vs `passage`) parameter that these embedding NIMs require for good retrieval quality, in the same low-friction way the raw `openai` client's `extra_body` does | The raw `openai` SDK client pointed at the NIM `base_url`, called directly (see code above) |
| A SQL/Postgres-backed LangGraph checkpointer for this MVP | Unnecessary infrastructure for a single local process running one review loop at a time | `InMemorySaver` |
| Hardcoding `z-ai/glm-5.2` (or any NIM model ID) as a string literal deep in graph node code | The free NIM catalog has deprecated/replaced this exact model twice in the last 3 months (GLM-5 → 5.1 → 5.2) | An environment variable (`NVIDIA_CHAT_MODEL`) read once at startup and passed into `ChatOpenAI(model=...)` |
| TypeScript 7.0 (the new Go-ported compiler) as a fresh pin | Just-released major rewrite of the compiler; unnecessary risk/churn for a 2-day build where tooling stability matters more than compiler speed | TypeScript 5.x, whatever Vite's `react-ts` template scaffolds by default |
| `react-diff-viewer` (original, `praneshr/react-diff-viewer`) | Unmaintained for years | `react-diff-viewer-continued` (actively maintained fork) |
## Stack Patterns by Variant
- Use `GitPython` to shallow-clone (`--depth 1`) rather than PyGithub's per-file REST calls, to avoid GitHub API rate limits and reduce latency.
- Use `Language`-aware splitting from `langchain-text-splitters` (e.g., `RecursiveCharacterTextSplitter.from_language(Language.PYTHON, ...)`) so chunks respect function/class boundaries instead of arbitrary character cuts.
- Skip the vector store entirely — read the relevant markdown/README files directly via PyGithub and pass them straight into the GLM context window (GLM-5.2 supports a very large context, so a handful of docs fits easily without retrieval).
- Swap `InMemorySaver` for `langgraph-checkpoint-sqlite`'s `SqliteSaver` — same `interrupt()`/`Command(resume=...)` node code, only the checkpointer constructor changes.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| `langgraph==1.2.8` | `langchain-core>=1.4,<2.0` | Both require Python >=3.10; installing `langchain-openai==1.3.4` will pull a compatible `langchain-core` automatically — don't pin `langchain-core` lower than what `langchain-openai` 1.3.x resolves to. |
| `fastapi==0.139.0` | `pydantic>=2.x` | Current FastAPI requires Pydantic v2; do not attempt to use Pydantic v1 syntax anywhere in the codebase. |
| `chromadb==1.5.9` | `langchain-chroma==1.1.0` | Verify at install time that `langchain-chroma` 1.1.0's Chroma client pin overlaps 1.5.9 — if `pip install` reports a conflict, let `langchain-chroma` drive the Chroma version rather than forcing 1.5.9. |
| `react==19.2.7` | `@tanstack/react-query@5.101.2`, Vite 8.x React template | React 19 is fully supported by current React Query and Vite's official `react-ts` template as of this research. |
## Sources
- Context7 `/websites/langchain_oss_python_langgraph` — `interrupt()`, `Command(resume=...)`, `InMemorySaver`, `stream_events` human-in-the-loop pattern (HIGH confidence, official LangChain docs source)
- PyPI JSON API (`pypi.org/pypi/<pkg>/json`) — direct version/release-date lookups for `langgraph`, `langchain-openai`, `langchain-core`, `fastapi`, `uvicorn`, `azure-devops`, `PyGithub`, `chromadb`, `langchain-chroma`, `pydantic`, `python-dotenv`, `httpx`, `langgraph-checkpoint`, `langgraph-checkpoint-sqlite`, `faiss-cpu`, `lancedb`, `GitPython`, `langchain-text-splitters`, `langchain-nvidia-ai-endpoints` (HIGH confidence — authoritative package index, checked 2026-07-09)
- npm registry JSON API (`registry.npmjs.org/<pkg>/latest`) — `vite`, `@vitejs/plugin-react`, `react`, `react-dom`, `typescript`, `@tanstack/react-query`, `axios`, `react-diff-view`, `diff` (HIGH confidence, checked 2026-07-09)
- `docs.api.nvidia.com/nim/reference/z-ai-glm-5.2` — confirmed exact model ID string `z-ai/glm-5.2` (MEDIUM confidence — official NVIDIA docs page, but catalog is volatile, see flag)
- NVIDIA Developer Forums: "URGENT: GLM-5 Deprecation (April 20, 2026)" (forums.developer.nvidia.com/t/366610) and "GLM5.1 was deprecated!" (forums.developer.nvidia.com/t/375179) — established the churn pattern GLM-5 → 5.1 (2026-04-20) → 5.2 (2026-07-02) (MEDIUM confidence, community forum but corroborated across multiple threads)
- `docs.langchain.com/oss/python/integrations/providers/nvidia` — confirmed `langchain-nvidia-ai-endpoints` exists as an alternative integration path and its `base_url`/local-NIM pattern (HIGH confidence, official LangChain docs)
- WebSearch, verified against official docs where noted — general ecosystem context on NVIDIA NIM free tier (rate limits ~40 req/min, no SLA), Azure DevOps REST API structure, React diff library maintenance status (MEDIUM confidence, cross-referenced across multiple sources)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
