"""Text embeddings for brownfield RAG — real NVIDIA NIM path + offline fallback.

embeddings_available() gates whether the real NIM embeddings endpoint is
called; embed_texts() always returns usable vectors regardless — on any NIM
failure (missing key, network error, deprecated model id, rate limit) it
falls back to a deterministic local hashing embedding so the demo/tests never
crash and never depend on network access. This mirrors llm.py's
llm_available()/fallback pattern (generate_plan's offline planner) applied to
embeddings.
"""

import math
import os
import re

_LOCAL_EMBED_DIM = 256
_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
_BATCH_SIZE = 32

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embeddings_available() -> bool:
    """True iff NVIDIA_API_KEY and NVIDIA_EMBED_MODEL are both set/non-empty."""
    return bool(os.environ.get("NVIDIA_API_KEY", "").strip()) and bool(
        os.environ.get("NVIDIA_EMBED_MODEL", "").strip()
    )


def _local_embed(text: str) -> list[float]:
    """Deterministic, offline, dependency-free hashing bag-of-tokens embedding.

    Lowercases and tokenizes on runs of alphanumerics, hashes each token into
    one of _LOCAL_EMBED_DIM buckets (accumulating token counts), then
    L2-normalizes. Deterministic across runs/processes (Python's built-in
    hash() is randomized per-process via PYTHONHASHSEED, so this uses a
    stable hash instead) and requires nothing beyond stdlib + math.
    """
    vector = [0.0] * _LOCAL_EMBED_DIM
    tokens = _TOKEN_RE.findall(text.lower())

    for token in tokens:
        bucket = _stable_hash(token) % _LOCAL_EMBED_DIM
        vector[bucket] += 1.0

    norm = math.sqrt(sum(component * component for component in vector))
    if norm == 0.0:
        return vector
    return [component / norm for component in vector]


def _stable_hash(token: str) -> int:
    """Deterministic string hash stable across processes (unlike hash())."""
    digest = 0
    for char in token:
        digest = (digest * 131 + ord(char)) % (2**32)
    return digest


def _embed_via_nim(texts: list[str], input_type: str) -> list[list[float]]:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.environ["NVIDIA_API_KEY"],
        base_url=_NIM_BASE_URL,
        timeout=30,
        max_retries=1,
    )
    model = os.environ["NVIDIA_EMBED_MODEL"]

    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH_SIZE):
        batch = texts[start : start + _BATCH_SIZE]
        response = client.embeddings.create(
            model=model,
            input=batch,
            extra_body={"input_type": input_type, "truncate": "END"},
        )
        vectors.extend(item.embedding for item in response.data)
    return vectors


def embed_texts(texts: list[str], input_type: str = "passage") -> list[list[float]]:
    """Embed a batch of texts, real NIM if configured, local fallback otherwise.

    Never raises — on ANY exception from the NIM call (missing key at call
    time, network error, malformed response, deprecated model id) falls back
    to the deterministic local embedding for demo resilience.
    """
    if not texts:
        return []

    if embeddings_available():
        try:
            return _embed_via_nim(texts, input_type)
        except Exception:  # noqa: BLE001 — demo resilience, see module docstring
            pass

    return [_local_embed(text) for text in texts]


def embed_texts_local(texts: list[str]) -> list[list[float]]:
    """Force the deterministic local embedding, no network. Public wrapper."""
    return [_local_embed(text) for text in texts]


def embed_with(
    provider: str, texts: list[str], input_type: str = "passage"
) -> list[list[float]]:
    """Embed with a SPECIFIC provider — strict, so index and queries stay in the
    same vector space. "local" never touches the network; "nim" raises on any
    failure (no silent local fallback, which would mismatch a NIM-built index).
    """
    if not texts:
        return []
    if provider == "nim":
        return _embed_via_nim(texts, input_type)
    return embed_texts_local(texts)
