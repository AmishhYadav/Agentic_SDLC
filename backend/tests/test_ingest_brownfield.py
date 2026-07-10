"""Coverage for app.graph.nodes.ingest_brownfield — offline, hermetic (no network)."""

import pytest

from app.graph.nodes.ingest_brownfield import ingest_brownfield


@pytest.fixture(autouse=True)
def _force_offline(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "")
    monkeypatch.delenv("NVIDIA_EMBED_MODEL", raising=False)
    monkeypatch.setenv("GITHUB_REPO", "")


@pytest.mark.asyncio
async def test_ingest_brownfield_with_sample_source_returns_docs_and_summary(tmp_path, monkeypatch):
    (tmp_path / "main.py").write_text(
        "def main():\n    print('hello from the sample app')\n"
    )
    (tmp_path / "README.md").write_text("# Sample Project\nA small demo project.\n")
    monkeypatch.setenv("BROWNFIELD_PATH", str(tmp_path))

    result = await ingest_brownfield({})

    assert result["blocked_reason"] is None
    assert result["docs_text"]
    assert result["onboarding_summary"]


@pytest.mark.asyncio
async def test_ingest_brownfield_with_empty_dir_sets_blocked_reason(tmp_path, monkeypatch):
    monkeypatch.setenv("BROWNFIELD_PATH", str(tmp_path))

    result = await ingest_brownfield({})

    assert result["docs_text"] is None
    assert result["onboarding_summary"] is None
    assert result["blocked_reason"] == "Brownfield ingestion found no source files to analyze."


@pytest.mark.asyncio
async def test_ingest_brownfield_never_raises_on_bad_path(monkeypatch):
    monkeypatch.setenv("BROWNFIELD_PATH", "/definitely/does/not/exist/anywhere")

    result = await ingest_brownfield({})

    # Either a clean "no files" block, or a caught-exception block — never a raised exception.
    assert result["blocked_reason"] is not None
    assert result["docs_text"] is None
