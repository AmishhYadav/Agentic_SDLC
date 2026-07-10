"""Coverage for app.services.rag_store.RagStore — hermetic, no network."""

import pytest

from app.services.rag_store import RagStore


def test_query_returns_most_similar_chunk_first():
    store = RagStore()
    chunks = [
        {"text": "chunk about databases", "path": "db.py", "language": "py"},
        {"text": "chunk about frontend UI", "path": "ui.py", "language": "py"},
        {"text": "chunk about authentication", "path": "auth.py", "language": "py"},
    ]
    vectors = [
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    store.add(chunks, vectors)

    results = store.query([0.0, 1.0, 0.0], k=3)
    assert results[0]["path"] == "ui.py"


def test_query_respects_k():
    store = RagStore()
    chunks = [{"text": f"chunk {i}", "path": f"f{i}.py", "language": "py"} for i in range(5)]
    vectors = [[1.0, i * 0.1, 0.0] for i in range(5)]
    store.add(chunks, vectors)

    results = store.query([1.0, 0.0, 0.0], k=2)
    assert len(results) == 2


def test_query_on_empty_store_returns_empty_list():
    store = RagStore()
    assert store.query([1.0, 0.0], k=5) == []


def test_add_with_mismatched_lengths_raises():
    store = RagStore()
    with pytest.raises(ValueError):
        store.add([{"text": "a", "path": "a.py", "language": "py"}], [[1.0], [2.0]])


def test_len_reflects_added_chunks():
    store = RagStore()
    assert len(store) == 0
    store.add(
        [{"text": "a", "path": "a.py", "language": "py"}],
        [[1.0, 0.0]],
    )
    assert len(store) == 1


def test_add_accumulates_across_multiple_calls():
    store = RagStore()
    store.add([{"text": "a", "path": "a.py", "language": "py"}], [[1.0, 0.0]])
    store.add([{"text": "b", "path": "b.py", "language": "py"}], [[0.0, 1.0]])
    assert len(store) == 2

    results = store.query([0.0, 1.0], k=1)
    assert results[0]["path"] == "b.py"
