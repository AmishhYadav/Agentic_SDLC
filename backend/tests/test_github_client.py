"""Unit coverage for REPO-02's greenfield doc-fetch service (github_client).

Exercises the pure, network-free pieces (_match_doc_paths and the
concatenate-and-cap logic) directly against fixtures, per 02-03-PLAN.md's
Task 1 behavior spec. No real Github()/network calls are made — content
fetch is injected via a get_contents_fn callable so tests never hit the
network.
"""

from app.services import github_client


def test_match_doc_paths_selects_readme_and_docs_md_only():
    tree_paths = [
        "README.md",
        "docs/setup.md",
        "docs/nested/deep.md",
        "src/main.py",
        "package-lock.json",
    ]
    matched = github_client._match_doc_paths(tree_paths)
    assert set(matched) == {"README.md", "docs/setup.md", "docs/nested/deep.md"}


def test_match_doc_paths_excludes_non_root_readme_and_non_md_docs():
    tree_paths = [
        "docs/README",  # no .md extension -> excluded per D-11 scope
        "somedir/README.md",  # not repo root, not under docs/ -> excluded
        "docs/notes.txt",  # under docs/ but not .md -> excluded
        "Readme.MD",  # root, case-insensitive match -> included
    ]
    matched = github_client._match_doc_paths(tree_paths)
    assert matched == ["Readme.MD"]


def test_match_doc_paths_returns_empty_list_when_nothing_matches():
    tree_paths = ["src/main.py", "package-lock.json", "somedir/notes.md"]
    matched = github_client._match_doc_paths(tree_paths)
    assert matched == []


def test_fetch_greenfield_docs_concatenates_with_path_headers_and_caps(monkeypatch):
    tree_paths = ["README.md", "docs/setup.md"]
    contents = {
        "README.md": "readme text",
        "docs/setup.md": "setup text",
    }

    def fake_get_contents_fn(path: str) -> str:
        return contents[path]

    result = github_client.fetch_greenfield_docs(
        token="fake-token",
        owner_repo="acme/widgets",
        max_chars=60_000,
        tree_paths=tree_paths,
        get_contents_fn=fake_get_contents_fn,
    )

    assert result is not None
    assert "--- README.md ---" in result
    assert "readme text" in result
    assert "--- docs/setup.md ---" in result
    assert "setup text" in result


def test_fetch_greenfield_docs_returns_none_when_no_docs_match():
    tree_paths = ["src/main.py", "package-lock.json"]

    def fake_get_contents_fn(path: str) -> str:  # pragma: no cover - should never be called
        raise AssertionError("get_contents_fn should not be called when no paths match")

    result = github_client.fetch_greenfield_docs(
        token="fake-token",
        owner_repo="acme/widgets",
        tree_paths=tree_paths,
        get_contents_fn=fake_get_contents_fn,
    )
    assert result is None


def test_fetch_greenfield_docs_truncates_and_stops_early_at_small_max_chars():
    tree_paths = ["README.md", "docs/setup.md"]
    long_text_a = "A" * 100
    long_text_b = "B" * 100
    contents = {
        "README.md": long_text_a,
        "docs/setup.md": long_text_b,
    }
    calls: list[str] = []

    def fake_get_contents_fn(path: str) -> str:
        calls.append(path)
        return contents[path]

    result = github_client.fetch_greenfield_docs(
        token="fake-token",
        owner_repo="acme/widgets",
        max_chars=50,
        tree_paths=tree_paths,
        get_contents_fn=fake_get_contents_fn,
    )

    assert result is not None
    assert len(result) <= 50 + len("--- README.md ---\n")
    # Stops early: must not fetch every matched file regardless of the cap.
    assert calls == ["README.md"]
    assert "B" * 100 not in result
