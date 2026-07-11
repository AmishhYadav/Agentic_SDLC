"""Pre-computed, persisted codebase RAG index for the "Ask the codebase" chat.

Unlike the brownfield ingest node (which builds an in-memory store per run and
throws it away), this index is built ONCE — via scripts/build_codebase_index.py
or the POST /codebase/reindex endpoint — and persisted to disk so the chatbot
loads it at startup and answers instantly, decoupled from any planning run.

Reuses the existing walk/chunk/embed/store machinery; the only new concern is
persistence + an embedder stamp (meta["embedder"]) so queries embed in the same
vector space the index was built with (see embeddings.embed_with).
"""

import json
import os
import shutil
from datetime import datetime, timezone

from app.services.code_ingest import (
    chunk_files,
    clone_repo,
    collect_files,
    resolve_source_dir,
)
from app.services.embeddings import embed_with, embeddings_available
from app.services.rag_store import RagStore

INDEX_DIR = os.environ.get("CODEBASE_INDEX_DIR", "./codebase_index")
_META_FILE = "meta.json"

# Fields surfaced to the UI via /codebase/status.
_STATUS_FIELDS = ("embedder", "file_count", "chunk_count", "languages", "built_at", "root")


def project_root() -> str:
    """This repo's root — the default target to index (parent of the backend dir)."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.dirname(backend_dir)


def index_exists(index_dir: str = INDEX_DIR) -> bool:
    return os.path.exists(os.path.join(index_dir, _META_FILE))


def _display_root() -> str:
    """A human-meaningful source label for the index (survives temp clones)."""
    return (
        os.environ.get("GITHUB_REPO", "").strip()
        or os.environ.get("BROWNFIELD_PATH", "").strip()
        or project_root()
    )


def build_index(
    root: str | None = None,
    provider: str | None = None,
    github_repo: str | None = None,
    index_dir: str = INDEX_DIR,
) -> tuple[RagStore, dict]:
    """Resolve the source repo → walk → chunk → embed → persist. Returns (store, meta).

    Source precedence: explicit `github_repo` ("owner/repo", shallow-cloned) >
    explicit `root` dir > `resolve_source_dir()` (env GITHUB_REPO / BROWNFIELD_PATH
    / this repo). So the UI can pass a repo name to index *that* repo on demand.

    provider: None (default) auto-selects "nim" when a live embedding model is
    configured (fast + strong retrieval), else "local". A NIM embedding failure
    falls back to "local" so the build never hard-fails. The chosen embedder is
    stamped in meta so queries embed in the same space.
    """
    if provider is None:
        provider = "nim" if embeddings_available() else "local"

    github_repo = (github_repo or "").strip()
    display_root: str
    if github_repo:
        source_dir, is_temp = clone_repo(github_repo), True
        display_root = github_repo
    elif root is not None:
        source_dir, is_temp = os.path.abspath(root), False
        display_root = source_dir
    else:
        source_dir, is_temp = resolve_source_dir()
        display_root = _display_root()

    try:
        files = collect_files(source_dir)
        chunks = chunk_files(files) if files else []

        store = RagStore()
        languages: dict[str, int] = {}
        if chunks:
            texts = [c["text"] for c in chunks]
            try:
                vectors = embed_with(provider, texts, input_type="passage")
            except Exception:  # noqa: BLE001 — NIM embed failed; fall back to local
                provider = "local"
                vectors = embed_with("local", texts, input_type="passage")
            store.add(chunks, vectors)
            for chunk in chunks:
                languages[chunk["language"]] = languages.get(chunk["language"], 0) + 1
    finally:
        if is_temp:
            shutil.rmtree(source_dir, ignore_errors=True)

    meta = {
        "embedder": provider,
        "root": display_root,
        "file_count": len(files),
        "chunk_count": len(chunks),
        "languages": languages,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    store.save(index_dir)
    with open(os.path.join(index_dir, _META_FILE), "w", encoding="utf-8") as fh:
        json.dump(meta, fh)

    return store, meta


def load_index(index_dir: str = INDEX_DIR) -> tuple[RagStore, dict] | None:
    """Load a previously built index, or None if it hasn't been built yet."""
    if not index_exists(index_dir):
        return None
    with open(os.path.join(index_dir, _META_FILE), encoding="utf-8") as fh:
        meta = json.load(fh)
    store = RagStore.load(index_dir)
    return store, meta


def status_payload(meta: dict) -> dict:
    return {"indexed": True, **{k: meta.get(k) for k in _STATUS_FIELDS}}
