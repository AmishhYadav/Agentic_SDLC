"""Coverage for app.services.embeddings — offline-only, hermetic.

Forces embeddings_available() False by clearing NVIDIA_API_KEY/NVIDIA_EMBED_MODEL
so every test here exercises only the deterministic local fallback path —
no network access, ever.
"""

import math

import pytest

from app.services.embeddings import _local_embed, embed_texts, embeddings_available


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)


def test_embeddings_available_false_when_key_and_model_missing(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)
    assert embeddings_available() is False


def test_embeddings_available_true_when_both_set(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-key")
    monkeypatch.setenv("NVIDIA_EMBED_MODEL", "nvidia/nv-embedqa-e5-v5")
    assert embeddings_available() is True


def test_embeddings_available_false_when_only_key_set(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "fake-key")
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)
    assert embeddings_available() is False


def test_local_embed_has_fixed_dimension():
    vector = _local_embed("hello world")
    assert len(vector) == 256


def test_local_embed_is_l2_normalized():
    vector = _local_embed("some sample text with several tokens")
    norm = math.sqrt(sum(component * component for component in vector))
    assert norm == pytest.approx(1.0, abs=1e-9)


def test_local_embed_empty_string_is_zero_vector():
    vector = _local_embed("")
    assert vector == [0.0] * 256


def test_local_embed_deterministic_identical_text():
    text = "def main(): print('hello')"
    assert _local_embed(text) == _local_embed(text)


def test_local_embed_differs_for_different_text():
    vec_a = _local_embed("apples and oranges and bananas")
    vec_b = _local_embed("quantum computing distributed systems")
    assert vec_a != vec_b


def test_embed_texts_offline_returns_local_vectors_for_each_input():
    texts = ["alpha beta", "gamma delta", "epsilon"]
    vectors = embed_texts(texts, input_type="passage")
    assert len(vectors) == len(texts)
    for vector in vectors:
        assert len(vector) == 256


def test_embed_texts_empty_list_returns_empty_list():
    assert embed_texts([], input_type="passage") == []


def test_embed_texts_query_and_passage_use_same_local_fallback():
    text = "same content either way"
    passage_vecs = embed_texts([text], input_type="passage")
    query_vecs = embed_texts([text], input_type="query")
    assert passage_vecs == query_vecs
