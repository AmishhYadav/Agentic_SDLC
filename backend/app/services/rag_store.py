"""Minimal in-memory numpy vector store for brownfield RAG.

No external vector DB — a single run's codebase chunk set is small enough
that an in-memory cosine-similarity scan is fast and requires zero
infrastructure (matches the 2-day-MVP "least infrastructure" stance used
elsewhere in this codebase, e.g. InMemorySaver for the graph checkpointer).
"""

import json
import os

import numpy as np

_VECTORS_FILE = "vectors.npy"
_CHUNKS_FILE = "chunks.json"


class RagStore:
    """Holds L2-normalized chunk vectors + their metadata for cosine-similarity search."""

    def __init__(self) -> None:
        self._vectors: np.ndarray | None = None
        self._chunks: list[dict] = []

    def add(self, chunks: list[dict], vectors: list[list[float]]) -> None:
        """Append chunks + their (not-necessarily-normalized) vectors to the store."""
        if not chunks:
            return
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")

        matrix = np.array(vectors, dtype=np.float64)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized = matrix / norms

        if self._vectors is None:
            self._vectors = normalized
        else:
            self._vectors = np.vstack([self._vectors, normalized])
        self._chunks.extend(chunks)

    def query(self, query_vec: list[float], k: int = 6) -> list[dict]:
        """Return the top-k chunks by cosine similarity to query_vec."""
        if self._vectors is None or not self._chunks:
            return []

        query = np.array(query_vec, dtype=np.float64)
        query_norm = np.linalg.norm(query)
        if query_norm == 0:
            return []
        query = query / query_norm

        scores = self._vectors @ query
        top_k = min(k, len(self._chunks))
        top_indices = np.argsort(-scores)[:top_k]

        return [self._chunks[i] for i in top_indices]

    def __len__(self) -> int:
        return len(self._chunks)

    def save(self, dir_path: str) -> None:
        """Persist the (already L2-normalized) vectors + chunk metadata to disk.

        Two files under dir_path: vectors.npy (float matrix) + chunks.json.
        Lets the codebase index be pre-computed once and reloaded at startup
        instead of re-embedding the whole repo on every run/query.
        """
        os.makedirs(dir_path, exist_ok=True)
        matrix = self._vectors if self._vectors is not None else np.zeros((0, 0))
        np.save(os.path.join(dir_path, _VECTORS_FILE), matrix)
        with open(os.path.join(dir_path, _CHUNKS_FILE), "w", encoding="utf-8") as fh:
            json.dump(self._chunks, fh)

    @classmethod
    def load(cls, dir_path: str) -> "RagStore":
        """Reconstruct a store previously written by save(). Vectors are already
        normalized on disk, so query() (which normalizes only the query) works
        unchanged."""
        store = cls()
        vectors = np.load(os.path.join(dir_path, _VECTORS_FILE))
        with open(os.path.join(dir_path, _CHUNKS_FILE), encoding="utf-8") as fh:
            chunks = json.load(fh)
        if vectors.size and chunks:
            store._vectors = vectors
            store._chunks = chunks
        return store


def build_store_from_dir(root: str) -> tuple[RagStore, dict]:
    """Collect, chunk, embed (passage), and index every file under root.

    Never raises on an empty/unreadable dir — returns an empty store plus
    zeroed stats instead, so ingest_brownfield can distinguish "nothing to
    ingest" from a hard failure.
    """
    from app.services.code_ingest import chunk_files, collect_files
    from app.services.embeddings import embed_texts

    store = RagStore()

    try:
        files = collect_files(root)
    except OSError:
        files = []

    if not files:
        return store, {
            "file_count": 0,
            "chunk_count": 0,
            "languages": {},
            "sample_paths": [],
        }

    chunks = chunk_files(files)
    if not chunks:
        return store, {
            "file_count": len(files),
            "chunk_count": 0,
            "languages": {},
            "sample_paths": [path for path, _ in files[:10]],
        }

    texts = [chunk["text"] for chunk in chunks]
    vectors = embed_texts(texts, input_type="passage")
    store.add(chunks, vectors)

    languages: dict[str, int] = {}
    for chunk in chunks:
        languages[chunk["language"]] = languages.get(chunk["language"], 0) + 1

    sample_paths = []
    seen_paths = set()
    for chunk in chunks:
        if chunk["path"] not in seen_paths:
            sample_paths.append(chunk["path"])
            seen_paths.add(chunk["path"])
        if len(sample_paths) >= 10:
            break

    stats = {
        "file_count": len(files),
        "chunk_count": len(chunks),
        "languages": languages,
        "sample_paths": sample_paths,
    }

    return store, stats
