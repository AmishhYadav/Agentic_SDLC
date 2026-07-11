"""GET /codebase/status, POST /codebase/ask, POST /codebase/reindex.

The index lives on app.state.codebase_index as (RagStore, meta) — loaded once at
startup (main.py lifespan). Blocking work (embedding + LLM, or a full reindex)
is offloaded via asyncio.to_thread so it never pins the event loop.
"""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.services import codebase_index, codebase_qa

router = APIRouter()


class AskRequest(BaseModel):
    question: str


class ReindexRequest(BaseModel):
    github_repo: str | None = None


def _current_index(request: Request):
    return getattr(request.app.state, "codebase_index", None)


@router.get("/codebase/status")
def codebase_status(request: Request):
    index = _current_index(request)
    if index is None:
        return {"indexed": False}
    _, meta = index
    return codebase_index.status_payload(meta)


@router.post("/codebase/ask")
async def codebase_ask(body: AskRequest, request: Request):
    index = _current_index(request)
    if index is None:
        return {
            "answer": "The codebase index hasn't been built yet — click 'Build index' first.",
            "sources": [],
        }
    store, meta = index
    question = body.question.strip()
    if not question:
        return {"answer": "Ask a question about the codebase.", "sources": []}
    return await asyncio.to_thread(codebase_qa.answer_question, store, meta, question)


@router.post("/codebase/reindex")
async def codebase_reindex(body: ReindexRequest, request: Request):
    """(Re)build the index. If github_repo ("owner/repo") is given, clone and
    index that repo; otherwise fall back to the env/default source. Auto-selects
    the NIM embedder when available. Clone/index failures return a 400 with the
    reason rather than a 500."""
    repo = (body.github_repo or "").strip()
    try:
        store, meta = await asyncio.to_thread(
            codebase_index.build_index, None, None, repo or None
        )
    except Exception as exc:  # noqa: BLE001 — surface clone/index failures to the UI
        detail = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return JSONResponse(
            status_code=400,
            content={
                "indexed": False,
                "error": f"Could not index '{repo or 'default source'}': {detail}",
            },
        )
    request.app.state.codebase_index = (store, meta)
    return codebase_index.status_payload(meta)
