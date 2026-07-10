"""Coverage for app.services.onboarding — offline path only, hermetic (no network)."""

import pytest

from app.services.embeddings import _local_embed
from app.services.onboarding import build_onboarding
from app.services.rag_store import RagStore


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)


def _sample_store_and_stats():
    store = RagStore()
    chunks = [
        {
            "text": "def main():\n    print('starting app')\n",
            "path": "app/main.py",
            "language": "py",
        },
        {
            "text": "# Project Overview\nThis project is a task planning tool.\n",
            "path": "README.md",
            "language": "md",
        },
    ]
    vectors = [_local_embed(chunk["text"]) for chunk in chunks]
    store.add(chunks, vectors)
    stats = {
        "file_count": 2,
        "chunk_count": 2,
        "languages": {"py": 1, "md": 1},
        "sample_paths": ["app/main.py", "README.md"],
    }
    return store, stats


def test_build_onboarding_returns_nonempty_summary_and_grounding():
    store, stats = _sample_store_and_stats()
    summary, grounding = build_onboarding(store, stats)

    assert summary.strip() != ""
    assert grounding.strip() != ""


def test_build_onboarding_summary_mentions_languages_from_stats():
    store, stats = _sample_store_and_stats()
    summary, _ = build_onboarding(store, stats)

    assert "py" in summary or "md" in summary


def test_build_onboarding_grounding_mentions_sample_paths():
    store, stats = _sample_store_and_stats()
    _, grounding = build_onboarding(store, stats)

    assert "app/main.py" in grounding or "README.md" in grounding


def test_build_onboarding_grounding_bounded_length():
    store, stats = _sample_store_and_stats()
    _, grounding = build_onboarding(store, stats)
    assert len(grounding) <= 6000


def test_build_onboarding_handles_empty_store():
    store = RagStore()
    stats = {"file_count": 0, "chunk_count": 0, "languages": {}, "sample_paths": []}

    summary, grounding = build_onboarding(store, stats)
    assert summary.strip() != ""
    assert grounding.strip() != ""
