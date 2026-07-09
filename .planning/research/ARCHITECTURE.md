# Architecture Research

**Domain:** AI-powered project planning & onboarding dashboard (LangGraph orchestration, Azure DevOps + GitHub integration, RAG for brownfield)
**Researched:** 2026-07-09
**Confidence:** HIGH (LangGraph interrupt/checkpoint/streaming patterns verified via Context7 official docs; MEDIUM on RAG chunking specifics and ADO batch API, verified via multiple web sources; LOW on GLM-via-NIM specific model IDs, training-data dependent)

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                              React Frontend                               │
│  ┌────────────┐  ┌─────────────┐  ┌───────────────┐  ┌────────────────┐  │
│  │ Config Form │  │ Onboarding  │  │ Plan Editor   │  │ Risk Panel /   │  │
│  │ (ADO/GH/    │  │ Summary View│  │ (table + diff │  │ Approve Button │  │
│  │  team)      │  │             │  │  + chat edit) │  │                │  │
│  └──────┬─────┘  └──────┬──────┘  └───────┬───────┘  └───────┬────────┘  │
│         │               │                 │                  │           │
└─────────┼───────────────┼─────────────────┼──────────────────┼───────────┘
          │  POST /runs   │  GET /runs/{id}/state (poll or SSE)│  POST /runs/{id}/resume
          ▼               ▼                 ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application Layer                        │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Run Controller: create thread, invoke graph, stream/poll state,  │    │
│  │  detect interrupt, accept edits, build Command(resume=...)        │    │
│  └───────────────────────────────┬──────────────────────────────────┘    │
├───────────────────────────────────┼───────────────────────────────────────┤
│                          LangGraph Orchestration Layer                    │
│  ┌────────┐  ┌──────────┐  ┌────────────┐  ┌────────┐  ┌─────────────┐   │
│  │ ingest │→ │ branch:  │→ │  plan_gen  │→ │  risk  │→ │ human_review│   │
│  │ config │  │ greenfield│  │  (LLM)     │  │ (deter-│  │ (interrupt) │   │
│  │        │  │ /brownfield│  │            │  │ ministic│  │  ↺ resume  │   │
│  └────────┘  └──────────┘  └────────────┘  │ +LLM   │  └──────┬──────┘   │
│                                             │ expl.) │         │          │
│                                             └────────┘         ▼          │
│                                                          ┌─────────────┐  │
│                                                          │  ado_push   │  │
│                                                          └─────────────┘  │
│  Checkpointer: SqliteSaver, keyed by thread_id = run_id                   │
├──────────────────────────────────────────────────────────────────────────┤
│                    Supporting Services (called from nodes)                │
│  ┌──────────────┐  ┌──────────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ GitHub adapter│  │ RAG pipeline      │  │ Risk engine │  │ ADO adapter│ │
│  │ (clone/read)  │  │ (chunk/embed/     │  │ (pure Python│  │ (REST /    │ │
│  │               │  │  store/retrieve)  │  │  no LLM)    │  │  SDK)      │ │
│  └──────────────┘  └────────┬──────────┘  └─────────────┘  └────────────┘ │
├────────────────────────────────┼──────────────────────────────────────────┤
│                        Data / External Layer                              │
│  ┌──────────┐  ┌───────────────┐  ┌──────────────┐  ┌───────────────────┐ │
│  │ SQLite   │  │ Chroma/FAISS  │  │ GLM via      │  │ Azure DevOps REST  │ │
│  │ (check-  │  │ (local vector │  │ NVIDIA NIM   │  │ / GitHub REST      │ │
│  │ points + │  │  store, on    │  │ (chat +      │  │ (work items, repo) │ │
│  │ run meta)│  │  disk per run)│  │  embeddings) │  │                    │ │
│  └──────────┘  └───────────────┘  └──────────────┘  └───────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|-------------------------|
| React Frontend | Config intake, poll/stream run state, render plan as editable table, render chat-diff, approve/resume | React + fetch/EventSource, a table/grid component, a diff viewer (e.g. rendering added/removed/changed rows) |
| FastAPI Run Controller | Own the HTTP boundary: create runs, expose state, accept direct edits and chat-edit requests, translate approval into `Command(resume=...)` | A `routers/runs.py` with `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/stream`, `PATCH /runs/{id}/plan`, `POST /runs/{id}/chat-edit`, `POST /runs/{id}/resume` |
| LangGraph Graph | Own the workflow: sequencing, branching, state shape, interrupt/resume boundary, retries | One `StateGraph` compiled with a checkpointer; nodes are plain Python functions with a shared `RunState` TypedDict |
| GitHub Adapter | Read repo (docs for greenfield, full clone for brownfield) via GitHub API/git clone | `PyGithub` or raw REST for docs listing; `git clone --depth 1` (via `GitPython` or subprocess) for brownfield |
| RAG Pipeline | Chunk brownfield code, embed via NVIDIA NIM, store in local vector store, retrieve for onboarding summary + plan grounding | LangChain `RecursiveCharacterTextSplitter` (language-aware) or tree-sitter chunker → `NVIDIAEmbeddings` → `Chroma`/`FAISS` local persisted store |
| Deterministic Risk Engine | Compute skill-coverage risk score from task skill tags vs team skills/experience/load — pure function, no LLM | Plain Python module: input = plan + team, output = per-task/per-epic risk score (0-100) + structured gap data; unit-testable in isolation |
| ADO Adapter | Push approved plan as work items (Epics/Tasks), set assignee, estimate, parent links | Azure DevOps REST `wit/$batch` API (or `azure-devops` Python SDK) with negative-ID batch pattern for parent-child links |
| SQLite (checkpoints) | Durable graph state across the interrupt/resume boundary, survives server restarts within the 2-day build/demo | `langgraph-checkpoint-sqlite` `SqliteSaver`, one thread_id per run |
| Local Vector Store | Per-run embedded codebase chunks for retrieval during onboarding-summary generation and plan grounding | `Chroma` (persisted dir) or `FAISS` (in-memory + pickle); scoped per run_id/repo so runs don't bleed into each other |

## Recommended Project Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI app, CORS, router mounting
│   ├── routers/
│   │   ├── runs.py              # POST /runs, GET /runs/{id}, resume, edits
│   │   └── config.py            # ADO/GitHub connection + team roster CRUD
│   ├── graph/
│   │   ├── state.py             # RunState TypedDict (config, docs, plan, risk, edits, approval)
│   │   ├── build.py             # StateGraph construction, compile(checkpointer=...)
│   │   ├── nodes/
│   │   │   ├── ingest_config.py
│   │   │   ├── branch_repo_type.py     # routing function, not a node
│   │   │   ├── read_docs_greenfield.py
│   │   │   ├── ingest_brownfield.py    # clone + chunk + embed + store + summarize
│   │   │   ├── generate_plan.py        # LLM: epics -> skill-tagged tasks
│   │   │   ├── score_risk.py           # deterministic engine + LLM explanation
│   │   │   ├── human_review.py         # interrupt() node
│   │   │   ├── apply_chat_edit.py      # LLM edit -> diff, no interrupt itself
│   │   │   └── push_to_ado.py
│   │   └── checkpointer.py      # SqliteSaver factory
│   ├── services/
│   │   ├── github_client.py     # clone, list docs, read files
│   │   ├── rag/
│   │   │   ├── chunker.py       # language-aware code + doc chunking
│   │   │   ├── embedder.py      # NVIDIAEmbeddings wrapper
│   │   │   ├── store.py         # Chroma/FAISS wrapper, per-run collection
│   │   │   └── retriever.py     # top-k retrieval for summary + plan grounding
│   │   ├── risk_engine.py       # pure deterministic scoring, unit-tested standalone
│   │   ├── ado_client.py        # work item batch create, assignment, estimate
│   │   └── llm.py               # ChatNVIDIA (GLM) wrapper, shared across nodes
│   ├── models/
│   │   ├── config.py            # Pydantic: ADOConfig, GitHubConfig, TeamMember
│   │   ├── plan.py               # Pydantic: Epic, Task, PlanDiff
│   │   └── risk.py               # Pydantic: RiskScore, SkillGap
│   └── db/
│       └── sqlite.py             # run metadata table (separate from checkpoint db, or same file/different tables)
frontend/
├── src/
│   ├── pages/
│   │   ├── ConfigPage.tsx        # connect ADO/GH, enter team
│   │   ├── OnboardingPage.tsx    # brownfield summary display
│   │   ├── PlanPage.tsx          # editable plan table + risk panel
│   │   └── ReviewPage.tsx        # chat edit box + diff preview + approve
│   ├── components/
│   │   ├── PlanTable.tsx
│   │   ├── DiffView.tsx
│   │   ├── RiskBadge.tsx
│   │   └── ChatEditPanel.tsx
│   └── lib/
│       └── runClient.ts          # poll/SSE state, POST resume/edit calls
```

### Structure Rationale

- **`graph/nodes/` as thin functions, `services/` as the real logic:** Nodes should mostly call into services and shape state — this keeps the graph readable as an orchestration diagram and makes services (risk engine, RAG pipeline, ADO client) independently unit-testable without spinning up LangGraph.
- **`risk_engine.py` isolated in `services/`, never imported by an LLM-calling module:** Enforces the deterministic/LLM separation architecturally, not just by convention — the risk *number* has zero LLM dependency in its call path.
- **`rag/` as its own service package:** Brownfield ingestion is a multi-stage pipeline (clone → chunk → embed → store → retrieve) reused twice (onboarding summary generation, plan grounding) — packaging it separately avoids duplicating retrieval logic between the two call sites.
- **One `RunState` TypedDict shared across all nodes:** LangGraph state is the contract between nodes; keeping it in one file makes the full data shape (config → plan → risk → edits → approval) auditable in one place, which matters a lot for a 2-day build where every teammate needs to understand the shape fast.

## Architectural Patterns

### Pattern 1: Single StateGraph with a router-node fork (greenfield/brownfield) and a linear spine

**What:** One `StateGraph` for the whole run. `ingest_config` runs first, then a conditional edge (router function, not an LLM) inspects the detected repo type and routes to `read_docs_greenfield` or `ingest_brownfield`. Both converge back onto the same `generate_plan` node. This keeps a single thread_id / single checkpoint history per run — critical because the interrupt/resume loop later needs one coherent state object, not two graphs to reconcile.

**When to use:** When the two branches produce a compatible output shape into the same downstream state field (here: both branches populate `state["context_summary"]` and `state["retrieval_context"]`, just via different mechanisms — doc reading vs RAG retrieval). This is the case here.

**Trade-offs:** A single graph is simpler to checkpoint and reason about, but the `RunState` schema must accommodate both branches' fields (some will be `None` depending on path). Subgraphs (compiled sub-`StateGraph`s used as nodes) are the alternative if brownfield ingestion grows complex enough to need its own retry/checkpoint semantics — not needed for a 2-day MVP.

**Example:**
```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

def route_repo_type(state: RunState) -> str:
    return "ingest_brownfield" if state["repo_type"] == "brownfield" else "read_docs_greenfield"

builder = StateGraph(RunState)
builder.add_node("ingest_config", ingest_config)
builder.add_node("read_docs_greenfield", read_docs_greenfield)
builder.add_node("ingest_brownfield", ingest_brownfield)
builder.add_node("generate_plan", generate_plan)
builder.add_node("score_risk", score_risk)
builder.add_node("human_review", human_review)   # contains interrupt()
builder.add_node("push_to_ado", push_to_ado)

builder.add_edge(START, "ingest_config")
builder.add_conditional_edges("ingest_config", route_repo_type,
    {"read_docs_greenfield": "read_docs_greenfield", "ingest_brownfield": "ingest_brownfield"})
builder.add_edge("read_docs_greenfield", "generate_plan")
builder.add_edge("ingest_brownfield", "generate_plan")
builder.add_edge("generate_plan", "score_risk")
builder.add_edge("score_risk", "human_review")
builder.add_edge("human_review", "push_to_ado")
builder.add_edge("push_to_ado", END)

graph = builder.compile(checkpointer=SqliteSaver.from_conn_string("checkpoints.db"))
```

### Pattern 2: `interrupt()` inside `human_review`, resumed via `Command(resume=...)` on a stable `thread_id`

**What:** The `human_review` node calls `interrupt(payload)` where `payload` is the current plan + risk data (or simply a signal — the frontend already has the plan via `GET /runs/{id}`). LangGraph persists the full state at that point via the checkpointer and halts. The node **restarts from the top** on resume (not from mid-function) — so `human_review` should be side-effect-light: its job is to pause, receive the resume value, and merge it into state, not to do heavy compute. Direct table edits and chat-edit-accepted diffs both get applied as writes to `state["plan"]` *before* resuming — i.e., the FastAPI layer calls `graph.update_state(config, {"plan": edited_plan})` for direct/chat edits, then a separate `POST /resume` sends `Command(resume=True)` to actually unblock the interrupt once the lead clicks Approve. This separates "editing state" from "unblocking execution," which maps cleanly to the UI (edit freely, then one Approve button).

**When to use:** Any point where a human must review/modify LLM output before an irreversible downstream action (here: the ADO push). This is the textbook LangGraph human-in-the-loop use case.

**Trade-offs:** Requires a checkpointer (in-memory is fine for a single-process 2-day demo; SQLite is safer if the FastAPI process might restart mid-review, which is likely during dev). The resumed node re-runs its earlier code path (idempotency matters if `human_review` does anything besides read the interrupt value) — keep it to "read + merge," push all mutation logic to the update_state calls made outside the interrupt.

**Example:**
```python
from langgraph.types import interrupt, Command

def human_review(state: RunState) -> dict:
    decision = interrupt({
        "plan": state["plan"],
        "risk": state["risk"],
    })
    # decision is whatever the frontend/resume call sent — e.g. {"approved": True}
    return {"approved": decision.get("approved", False)}

# FastAPI: apply an edit without resuming (keeps the graph paused)
graph.update_state(config, {"plan": edited_plan})

# FastAPI: approve — this is what actually resumes execution
graph.invoke(Command(resume={"approved": True}), config)
```

### Pattern 3: Deterministic risk score computed in a plain Python function; LLM only writes the explanation string

**What:** `score_risk` node calls `risk_engine.compute(plan, team)` — a pure function with no network calls, fully unit-testable, returning `{task_id: {"score": int, "gaps": [...]}}`. Only *after* that deterministic result exists does the node call the LLM once (batched, not per-task ideally) with the structured gap data to produce a human-readable explanation string per risk. The LLM prompt explicitly includes the computed score as a given fact ("Explain why this task has a risk score of 72, given these gaps: ...") so the model is grounded and cannot invent a different number.

**When to use:** Any "trustworthy score + narrative" feature — this is the standard pattern for hybrid deterministic/LLM systems (e.g., credit scoring explanations, code review severity + LLM commentary).

**Trade-offs:** Keeps the score reproducible and testable, but means two passes over the risk data (compute, then explain) rather than one LLM call doing both — slightly more latency, fully worth it for trust. Batch the explanation call (one LLM call for all tasks' gaps, not N calls) to keep it fast for a 2-day demo.

**Example:**
```python
# services/risk_engine.py — zero LLM imports, zero network calls
def compute_skill_coverage_risk(tasks: list[Task], team: list[TeamMember]) -> dict[str, RiskScore]:
    results = {}
    for task in tasks:
        covering = [m for m in team if task.required_skill in m.skills]
        load = sum(t.estimate_hours for t in tasks if t.assignee_id == task.assignee_id)
        gap_score = 0 if covering else 60
        overload_score = min(40, max(0, (load - 40) * 2))  # arbitrary deterministic formula
        results[task.id] = RiskScore(score=gap_score + overload_score, covering_members=covering, load_hours=load)
    return results

# graph/nodes/score_risk.py — the only place that touches both
def score_risk(state: RunState) -> dict:
    scores = compute_skill_coverage_risk(state["plan"].tasks, state["team"])
    explanations = llm_explain_risks(scores)  # LLM sees scores as given facts, writes prose only
    return {"risk": scores, "risk_explanations": explanations}
```

## Data Flow

### Request Flow (end-to-end run)

```
[Lead submits config: ADO project, GH repo, team roster]
    ↓ POST /runs
[FastAPI: create thread_id, graph.invoke(initial_state, config) — runs until interrupt]
    ↓
[ingest_config] → [branch: greenfield|brownfield]
    ↓                          ↓
[read_docs_greenfield]   [ingest_brownfield: clone→chunk→embed→store→retrieve→summarize]
    ↓                          ↓
              [generate_plan] (LLM, grounded on docs or RAG context)
                    ↓
              [score_risk] (deterministic engine + LLM explanation)
                    ↓
              [human_review] → interrupt() → STATE CHECKPOINTED, graph paused
    ↓
[FastAPI returns run state to React: plan + risk, status="awaiting_review"]
    ↓
[Lead edits directly OR via chat] → PATCH/POST edit endpoints
    ↓ each edit: graph.update_state(config, {"plan": updated_plan})  (graph stays paused)
[Lead reviews diff, clicks Approve] → POST /runs/{id}/resume
    ↓ graph.invoke(Command(resume={"approved": True}), config)
[human_review resumes] → [push_to_ado] (batch create work items, assign, estimate)
    ↓
[FastAPI returns final state: status="pushed", ADO work item URLs]
```

### State Management (frontend)

```
[runClient polls GET /runs/{id} every N seconds, or subscribes to SSE /runs/{id}/stream]
    ↓ (state includes: status, plan, risk, onboarding_summary, interrupt_payload)
[React state store (e.g. useState/useReducer or lightweight store)]
    ↓
[PlanPage renders table from plan; RiskPanel renders risk; ReviewPage enables edit/chat/approve]
    ↓ (edit) PATCH /runs/{id}/plan  or  POST /runs/{id}/chat-edit → returns diff, awaits confirm
    ↓ (approve) POST /runs/{id}/resume
[Poll picks up new status on next tick, or SSE pushes "pushed" event]
```

### Key Data Flows

1. **Config → context grounding:** ADO project + GitHub repo + team roster flow into `RunState` at ingestion; greenfield reads docs directly into a text blob, brownfield produces both an onboarding summary (LLM-generated from retrieved chunks) and a persisted vector store handle used again during plan generation for grounding task descriptions in real code.
2. **Plan → Risk → Explanation:** The plan (epics/tasks with skill tags, estimates, assignees) is the sole input to the deterministic risk engine; the engine's structured output (never raw plan data) is the sole input to the LLM explanation call — this one-directional dependency is what keeps the score trustworthy.
3. **Edit-before-resume:** Both direct table edits and accepted chat-edit diffs write into the *same* graph state field (`state["plan"]`) via `update_state`, without touching the interrupt. Only the explicit Approve action sends `Command(resume=...)`. This means the UI can allow arbitrarily many edit round-trips before one final resume call — important for the "chat edit as diff preview" requirement, since the diff can be generated, shown, and only committed to state if the lead accepts it.
4. **ADO push is a one-way, one-shot terminal node:** `push_to_ado` reads final approved `state["plan"]` and calls the ADO batch API once; it does not loop back into the graph. No read-back/reconciliation node exists (matches "one-way" scope decision).

## Scaling Considerations

Given this is a local, single-lead, 2-day MVP tool (not a scaled multi-tenant service), "scaling" here means "robustness for a live demo and near-term reuse," not user growth.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Single demo run (MVP, today) | In-memory or SQLite checkpointer is sufficient; FAISS/Chroma local persisted store per run; synchronous FastAPI endpoints, polling from React is simplest to build in 2 days |
| Repeated local use by one lead (post-MVP) | Move to SQLite checkpointer if not already (survives process restarts mid-review); namespace vector store collections by run_id to avoid cross-run bleed; add a lightweight run history list |
| Multiple leads / concurrent runs (future, out of current scope) | Postgres checkpointer (`PostgresSaver`) for concurrent thread safety; move vector store to a shared service (e.g. Chroma server mode or a managed vector DB) instead of local files; SSE streaming becomes more valuable than polling at this scale |

### Scaling Priorities

1. **First bottleneck (even at MVP scale): brownfield clone+embed latency.** Cloning a large repo and embedding many chunks via a remote NIM API can take minutes — this is the one place worth showing a progress indicator (via SSE or a polled `progress` field in state) rather than a blank wait, since it directly affects demo quality.
2. **Second bottleneck: LLM call latency/rate limits on NVIDIA's free tier.** Free-tier NIM endpoints often have stricter rate limits than paid tiers — batch LLM calls where possible (one explanation call for all risks, not N), and add basic retry/backoff in the `llm.py` wrapper so a transient 429 doesn't kill a demo run.

## Anti-Patterns

### Anti-Pattern 1: Letting the LLM compute or adjust the risk score directly

**What people do:** Prompt the LLM with "here's the plan and team, give each task a risk score 0-100 and explain it" in one call.
**Why it's wrong:** Non-reproducible (same input can yield different scores across runs), impossible to unit test, and undermines the explicit product requirement that risk be "mostly deterministic." It also makes debugging risk complaints ("why is this 85?") much harder since there's no formula to point to.
**Do this instead:** Compute the score with a pure Python function first (skill-coverage gap + load-balance formula), then pass the *already-computed* score and its structured inputs to the LLM only to generate prose explaining it — as in Pattern 3 above.

### Anti-Pattern 2: Doing heavy work or side effects inside the `interrupt()`-calling node

**What people do:** Put plan-mutation logic, DB writes, or API calls inside the same node that calls `interrupt()`, assuming it runs once.
**Why it's wrong:** Per LangGraph's execution model, when a graph resumes after an interrupt, the **node containing the interrupt re-executes from its start** (not from the `interrupt()` line). Any code before the `interrupt()` call — including side effects — runs again on every resume. If that code calls an external API or mutates state destructively, resuming becomes unsafe or produces duplicate effects.
**Instead:** Keep the interrupt-calling node minimal (read state, call `interrupt()`, merge the resume payload into a return dict). Do plan edits via `graph.update_state()` calls from FastAPI endpoints *outside* the node, before the resume call — never inside the node itself.

### Anti-Pattern 3: Fixed-size text chunking for brownfield code ingestion

**What people do:** Reuse a generic `RecursiveCharacterTextSplitter` with a fixed character/token window across all file types, including source code.
**Why it's wrong:** Fixed-width splitting frequently cuts functions mid-body, separating a signature from its implementation and losing enclosing class/import context — this directly degrades both the onboarding summary quality and the plan-grounding retrieval quality, since a fragment without the function signature is nearly useless as retrieved context.
**Instead:** Use language-aware or AST-based chunking (tree-sitter, or at minimum a splitter configured with code-aware separators per language) so chunks respect function/class boundaries; target roughly 1000-1500 token chunks matching typical function sizes. For a 2-day MVP, LangChain's language-specific splitters (e.g. `Language.PYTHON`, `Language.JS` variants of `RecursiveCharacterTextSplitter`) are a pragmatic middle ground between "fixed-size" and "full AST parser."

### Anti-Pattern 4: Polling the graph state faster than the LLM/RAG stages actually progress, without a progress signal

**What people do:** Poll `GET /runs/{id}` every second showing only a static "processing..." spinner with no stage indicator.
**Why it's wrong:** Brownfield ingestion (clone + chunk + embed) and plan generation can take real wall-clock time; a spinner with no stage feedback reads as "broken" in a live demo, and it hides where slowness actually comes from during development.
**Instead:** Have each node write a `state["progress"]` field (e.g. `"cloning_repo"`, `"embedding_chunks: 40/120"`, `"generating_plan"`) via LangGraph's `get_stream_writer()` or simple state updates, and surface that in the polled/streamed response so the UI can show real stage progress.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| GitHub | REST API (docs listing, greenfield) + `git clone` via subprocess/GitPython (brownfield full read) | Use a shallow clone (`--depth 1`) for brownfield to keep 2-day-MVP clone times low; single PAT/token, read-only scope |
| Azure DevOps | REST API `wit/$batch` (PATCH) for work item creation with parent-child links via negative temp IDs and fully-qualified relation URLs | One shared PAT per constraints; batch endpoint keeps epic+task creation to one or few HTTP calls; failed items in a batch don't block others — surface partial-failure results to the UI rather than silently swallowing them |
| NVIDIA NIM (GLM chat) | OpenAI-compatible endpoint via `langchain_nvidia_ai_endpoints.ChatNVIDIA`, or any OpenAI-compatible client pointed at NVIDIA's base URL | Single API key covers chat + embeddings; watch free-tier rate limits, add retry/backoff |
| NVIDIA NIM (embeddings) | `langchain_nvidia_ai_endpoints.NVIDIAEmbeddings` | Same API key/base URL family as chat; used only in the brownfield RAG pipeline |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| React ↔ FastAPI | HTTP/JSON, polling `GET /runs/{id}` (simplest for 2-day MVP) or SSE `GET /runs/{id}/stream` (better UX for long brownfield ingestion) | Start with polling for MVP simplicity; upgrade the same endpoint's underlying node to also emit stream-writer progress if time allows — don't block the interrupt/resume mechanics on choosing streaming vs polling, they're independent decisions |
| FastAPI ↔ LangGraph | Direct in-process Python calls (`graph.invoke`, `graph.update_state`, `graph.get_state`) — not a separate service | No need for LangGraph Platform/server in a 2-day local MVP; the compiled graph lives in the same process as FastAPI |
| LangGraph nodes ↔ Services | Plain function calls from node bodies into `services/` modules | Keeps nodes thin; services are independently testable and reusable (e.g. `risk_engine.py` has zero LangGraph or LLM imports) |
| Risk Engine ↔ LLM | One-directional: risk engine output feeds the LLM explanation prompt; LLM output never feeds back into the score | This is the core trust boundary in the product — enforce it by literally not importing any LLM client inside `risk_engine.py` |
| Human Review ↔ Graph State | `interrupt()` pause + `Command(resume=...)` unblock, with edits applied via `update_state` while paused | thread_id must be stable across the whole run (store it as the run_id) so resume always targets the correct paused checkpoint |

## Sources

- [Interrupts — LangChain Docs](https://docs.langchain.com/oss/python/langgraph/interrupts) — HIGH confidence, official docs, verified via Context7
- [Persistence / Checkpointers — LangChain Docs](https://docs.langchain.com/oss/python/langgraph/persistence) — HIGH confidence, official docs
- [Checkpointers reference — LangChain Docs](https://docs.langchain.com/oss/python/langgraph/checkpointers) — HIGH confidence, official docs (SqliteSaver, PostgresSaver, InMemorySaver comparison)
- [Graph API overview — LangChain Docs](https://docs.langchain.com/oss/python/langgraph/graph-api) — HIGH confidence, official docs (conditional edges, subgraph composition)
- [Functional API — LangChain Docs](https://docs.langchain.com/oss/python/langgraph/functional-api) — HIGH confidence, official docs (Command(resume=...) pattern)
- [Event streaming — LangChain Docs](https://docs.langchain.com/oss/python/langgraph/event-streaming) — HIGH confidence, official docs
- [LangGraph Human-in-the-Loop (HITL) Deployment with FastAPI — Medium](https://shaveen12.medium.com/langgraph-human-in-the-loop-hitl-deployment-with-fastapi-be4a9efcd8c0) — MEDIUM confidence, community pattern consistent with official docs
- [KirtiJha/langgraph-interrupt-workflow-template — GitHub](https://github.com/KirtiJha/langgraph-interrupt-workflow-template) — MEDIUM confidence, reference implementation of FastAPI + LangGraph interrupt pattern
- [cAST: Enhancing Code RAG with Structural Chunking via AST — arXiv](https://arxiv.org/pdf/2506.15655) — MEDIUM-HIGH confidence, research paper on code chunking quality
- [Building code-chunk: AST Aware Code Chunking](https://www.nexxel.dev/blog/code-chunk) — MEDIUM confidence, practitioner writeup, corroborates AST-based chunking benefits
- [ChatNVIDIA integration — LangChain Docs](https://docs.langchain.com/oss/python/integrations/chat/nvidia_ai_endpoints) — HIGH confidence, official docs
- [NVIDIAEmbeddings — LangChain API Reference](https://python.langchain.com/api_reference/nvidia_ai_endpoints/embeddings/langchain_nvidia_ai_endpoints.embeddings.NVIDIAEmbeddings.html) — HIGH confidence, official docs
- [Azure DevOps REST API — Batch Requests, Brian Kohrs](https://www.briankohrs.com/posts/azdo-rest-api-batch-requests/) — MEDIUM confidence, practitioner writeup on negative-ID batch pattern for parent-child work items
- [Work Items - Create — Azure DevOps REST API, Microsoft Learn](https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items/create?view=azure-devops-rest-7.1) — HIGH confidence, official Microsoft docs

---
*Architecture research for: AI-powered project planning & onboarding dashboard (LangGraph + FastAPI + React, ADO/GitHub integration)*
*Researched: 2026-07-09*
