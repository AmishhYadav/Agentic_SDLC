# Stack Research

**Domain:** AI-powered project planning & onboarding dashboard (FastAPI + LangGraph backend, React frontend, Azure DevOps + GitHub integration, RAG over codebases, GLM via NVIDIA NIM)
**Researched:** 2026-07-09
**Confidence:** HIGH for backend framework/orchestration/frontend versions (Context7 + PyPI/npm verified); MEDIUM-LOW for the exact NVIDIA NIM free GLM model ID (catalog churns model IDs roughly monthly — see flag below); HIGH for architecture pattern (interrupt-and-resume is a first-class, documented LangGraph feature).

This document validates the team's already-committed choices (FastAPI, LangGraph, React, GLM-via-NVIDIA-NIM) and fills the stated gaps: RAG vector store, ADO/GitHub client libraries, embedding model, diff rendering.

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

```bash
# Backend (Python 3.12+, use a venv)
pip install "fastapi[standard]"==0.139.0 \
  langgraph==1.2.8 \
  langchain-openai==1.3.4 \
  langchain-core==1.4.9 \
  httpx==0.28.1 \
  azure-devops==7.1.0b4 \
  PyGithub==2.9.1 \
  GitPython==3.1.50 \
  chromadb==1.5.9 \
  langchain-chroma==1.1.0 \
  langchain-text-splitters==1.1.2 \
  pydantic==2.13.4 \
  python-dotenv==1.2.2

# Frontend
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query@5.101.2 axios@1.18.1 diff@9.0.0 react-diff-view
```

## GLM via NVIDIA NIM — Exact Wiring

**Base URL:** `https://integrate.api.nvidia.com/v1`
**Auth:** `Authorization: Bearer $NVIDIA_API_KEY` (key from build.nvidia.com, prefix `nvapi-`, free tier, no credit card required)
**Chat model ID (current as of 2026-07-09):** `z-ai/glm-5.2`
**Embedding model ID (current as of 2026-07-09):** `nvidia/llama-3.2-nv-embedqa-1b-v2` (see embedding rationale below)

```python
import os
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["NVIDIA_API_KEY"],
    model="z-ai/glm-5.2",
    temperature=0.3,          # low temperature for plan generation / risk explanations
    max_tokens=8192,
)

# Used directly inside a LangGraph node, e.g.:
def generate_plan_node(state: PlanState) -> dict:
    response = llm.invoke(state["messages"])
    return {"messages": [response]}
```

**Embeddings** (via the raw `openai` SDK, since `langchain-openai`'s `OpenAIEmbeddings` assumes OpenAI's own embedding response shape — NVIDIA's embedding NIMs require an `input_type` field (`"query"` or `"passage"`) that isn't part of the standard OpenAI embeddings API, so the cleanest 2-day path is a small wrapper function rather than fighting a LangChain embeddings class):

```python
from openai import OpenAI

nim_client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ["NVIDIA_API_KEY"],
)

def embed_passages(texts: list[str]) -> list[list[float]]:
    resp = nim_client.embeddings.create(
        input=texts,
        model="nvidia/llama-3.2-nv-embedqa-1b-v2",
        encoding_format="float",
        extra_body={"input_type": "passage", "truncate": "END"},
    )
    return [d.embedding for d in resp.data]
```

Feed these vectors into Chroma directly (`collection.add(embeddings=..., documents=..., ids=...)`) rather than routing through `langchain-chroma`'s built-in embedding-function interface, since that interface also assumes a standard embeddings API — for a 2-day MVP, compute embeddings yourself and hand Chroma raw vectors.

### CRITICAL FLAG — NVIDIA NIM free catalog model IDs churn frequently

**Confidence: MEDIUM-LOW on the exact model ID staying valid for the life of this project.** Research surfaced an active pattern on NVIDIA's free NIM catalog: GLM-5 was deprecated 2026-04-20 and replaced by GLM-5.1; GLM-5.1 was itself deprecated and replaced by GLM-5.2 on 2026-07-02 — one week before this research was conducted. NVIDIA Developer Forum threads show this catches users off guard with no long runway (a forum thread titled "URGENT: GLM-5 Deprecation... Replacement Not Available" describes the replacement model missing from the API on the deprecation date itself).

**Mitigation for the roadmap:**
- Put the model ID behind an environment variable (`NVIDIA_CHAT_MODEL=z-ai/glm-5.2`), never hardcode it in graph node code.
- Before building, confirm `z-ai/glm-5.2` (or whatever is current) is live by hitting `https://integrate.api.nvidia.com/v1/models` with the API key, or checking `https://build.nvidia.com/z-ai/glm-5.2`.
- Because this is a 2-day local MVP with no production SLA concerns, this is a minor annoyance (re-point one env var if the model gets deprecated mid-build), not a blocker — but the roadmap should not assume the exact string `z-ai/glm-5.2` is stable for more than a few weeks.

**Free tier constraints to design around:** ~40 requests/minute rate limit, no SLA, response times can spike. For a single local lead doing one plan-generation flow at a time this is a non-issue, but avoid tight retry loops or parallel fan-out LLM calls inside the LangGraph graph that could burst past the rate limit.

## Vector Store for Brownfield RAG — Chroma

**Recommendation: `chromadb` (embedded/local mode), not FAISS, not LanceDB.**

| Option | Verdict for this project |
|--------|---------------------------|
| **Chroma** (chosen) | Runs fully embedded in-process (`chromadb.PersistentClient(path="./chroma_data")`), zero external service, persists to disk automatically between runs without any setup. Has first-class metadata filtering (needed to filter RAG results by file path/language when building the onboarding summary), and a mature LangChain integration (`langchain-chroma` 1.1.0). This is the standard default for "local RAG prototype" in 2026 for exactly this reason: least infrastructure for the capability delivered. |
| FAISS (`faiss-cpu` 1.14.3) | A pure similarity-search index, not a database — no built-in metadata storage/filtering or persistence layer; you'd hand-roll ID-to-metadata mapping and disk persistence. More setup work for no benefit at this scale (a single codebase's worth of chunks, not millions of vectors). |
| LanceDB (`lancedb` 0.34.0) | Excellent for larger-scale, production RAG (columnar on-disk format, versioning) but is more capability than a 2-day MVP needs, and its LangChain integration is less battle-tested than Chroma's. Reasonable "if this project grows" upgrade path, not a day-one pick. |

For the greenfield path (reading docs, not a full codebase), RAG/vector search likely isn't even needed — a handful of markdown/README files can be stuffed directly into the LLM context. Reserve Chroma + embeddings specifically for the brownfield ingestion path, as scoped in PROJECT.md.

## Azure DevOps Work Item API — Use REST Directly (via `httpx`), Not the SDK, as the Primary Path

**Confidence: HIGH on this recommendation, based on verified PyPI release history.**

The `azure-devops` PyPI package (`microsoft/azure-devops-python-api`) is **still in beta** — version `7.1.0b4`, last released **2023-11-20**. It has had no release in over two years and has never left beta status across its whole 7.1 line. The underlying Azure DevOps REST API has since introduced `api-version=7.2` (7.1 remains supported and is not deprecated, so this is not an immediate breakage risk, but it signals the SDK is not being kept current).

**For a 2-day MVP, call the REST API directly with `httpx`:**

```python
import httpx, base64, os

pat = os.environ["ADO_PAT"]
auth = base64.b64encode(f":{pat}".encode()).decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json-patch+json"}

async def create_work_item(org: str, project: str, work_item_type: str, fields: list[dict]):
    url = f"https://dev.azure.com/{org}/{project}/_apis/wit/workitems/${work_item_type}?api-version=7.1"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=fields)
        resp.raise_for_status()
        return resp.json()

# fields example (JSON Patch document):
# [{"op": "add", "path": "/fields/System.Title", "value": "Implement auth middleware"},
#  {"op": "add", "path": "/fields/System.AssignedTo", "value": "jane@company.com"},
#  {"op": "add", "path": "/fields/Microsoft.VSTS.Scheduling.OriginalEstimate", "value": 8}]
```

This is fewer total lines than it looks — work item creation is one `POST` with a JSON Patch body, and the REST surface needed (create work item, maybe set parent/epic link) is small and well-documented at `learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create`. Directly hitting REST avoids pinning a two-year-stale beta dependency for the one thing this project actually needs from ADO.

If the team prefers typed request/response models and is comfortable with the staleness risk, `azure-devops==7.1.0b4`'s `WorkItemTrackingClient.create_work_item()` is a reasonable fallback — it does still work against the current API — but it should not be the default recommendation for a fresh 2-day build.

## Diff Rendering — `react-diff-view` + `diff` (jsdiff)

The plan-edit-via-chat flow needs to show the lead a diff of the proposed change before they accept it (per PROJECT.md: "preview the change as a diff before accepting").

**Recommended approach:**
1. Represent the plan as a serializable text form (e.g., a formatted JSON or YAML string of epics/tasks/assignees/estimates) both before and after the LLM chat edit.
2. Use `diff` (jsdiff, npm `diff` package, v9.0.0) — specifically `diff.createPatch()` or `diff.diffLines()` — to compute a unified diff between old and new plan text.
3. Render that unified diff with `react-diff-view`, which parses unified diff format and renders a GitHub-style side-by-side or unified diff view with syntax highlighting hooks.

**Why not `react-diff-viewer` (the older, unmaintained original):** the original `praneshr/react-diff-viewer` package has had no meaningful release in years (last publish several years ago per npm). Its actively-maintained continuation, `react-diff-viewer-continued`, is a reasonable alternative if the team prefers its simpler string-in/diff-out API (`<ReactDiffViewer oldValue={...} newValue={...} />`, no manual unified-diff step) over `react-diff-view`'s more powerful but lower-level hunk-based API. For a 2-day MVP where the diff is plain structured text (not real source code), **`react-diff-viewer-continued` is actually the faster path to ship** — it does the diffing internally, so you can skip the separate `diff`/unified-diff step entirely. Recommend starting there and only reaching for `react-diff-view` + `diff` if finer control over hunk rendering is needed.

**Revised recommendation given the 2-day constraint:** use `react-diff-viewer-continued` (pass `oldValue`/`newValue` plan strings directly, get a rendered diff with zero manual diff computation) as the default; treat `react-diff-view` + `diff` as the fallback if more control is needed later.

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

**If the brownfield codebase is large (multi-thousand files):**
- Use `GitPython` to shallow-clone (`--depth 1`) rather than PyGithub's per-file REST calls, to avoid GitHub API rate limits and reduce latency.
- Use `Language`-aware splitting from `langchain-text-splitters` (e.g., `RecursiveCharacterTextSplitter.from_language(Language.PYTHON, ...)`) so chunks respect function/class boundaries instead of arbitrary character cuts.

**If the greenfield path only needs a few doc files:**
- Skip the vector store entirely — read the relevant markdown/README files directly via PyGithub and pass them straight into the GLM context window (GLM-5.2 supports a very large context, so a handful of docs fits easily without retrieval).

**If the review loop needs to survive a backend restart:**
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

---
*Stack research for: AI project planning & onboarding dashboard (Azure DevOps + GitHub, LangGraph, GLM via NVIDIA NIM)*
*Researched: 2026-07-09*
