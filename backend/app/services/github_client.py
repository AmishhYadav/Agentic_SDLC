"""GitHub doc-fetch service for greenfield planning (REPO-02).

Enumerates the target repo's tree once via PyGithub's get_git_tree(...,
recursive=True), matches README + docs/**/*.md paths with explicit string
checks (NOT fnmatch's "**", which does not support recursive-glob semantics
per 02-RESEARCH.md Pitfall 5), then fetches only the matched files' content
and concatenates them, capped at max_chars (D-12/T-02-07 DoS mitigation).

The path-matching (_match_doc_paths) and concatenation logic are pure/
network-free and independently unit-testable; fetch_greenfield_docs accepts
optional tree_paths/get_contents_fn injection points so tests never need a
real Github() client or network access. When not supplied, it builds them
from a real PyGithub client against the given token/owner_repo.
"""

import base64
from typing import Callable

from github import Github


def _match_doc_paths(tree_paths: list[str]) -> list[str]:
    """Select README (repo root only) + docs/**/*.md paths from a flat path list.

    - Root README: no "/" in the path AND the basename starts with "readme"
      (case-insensitive), per D-11's plain "README" wording. `docs/README.md`
      is NOT matched by this rule (it has no root position) but IS matched by
      the docs/ rule below since it ends in .md; `docs/README` (no .md) is
      correctly excluded by both rules.
    - docs/: path.lower().startswith("docs/") and path.lower().endswith(".md")
      — explicit checks, not fnmatch("docs/**/*.md"), per Pitfall 5.
    """
    matched: list[str] = []
    for path in tree_paths:
        lower = path.lower()
        is_root_readme = "/" not in path and lower.startswith("readme")
        is_docs_md = lower.startswith("docs/") and lower.endswith(".md")
        if is_root_readme or is_docs_md:
            matched.append(path)
    return matched


def fetch_greenfield_docs(
    token: str,
    owner_repo: str,
    max_chars: int = 60_000,
    tree_paths: list[str] | None = None,
    get_contents_fn: Callable[[str], str] | None = None,
) -> str | None:
    """Fetch and concatenate README + docs/**/*.md content, capped at max_chars.

    tree_paths/get_contents_fn are injection points for tests (see
    tests/test_github_client.py); when omitted, a real PyGithub client is used
    to enumerate the tree (get_git_tree(default_branch, recursive=True)) and
    fetch each matched file's content (get_contents(path).decoded_content).

    Returns None when no README/docs paths match (D-12: caller blocks with a
    clear "No project docs found" message rather than planning from nothing).
    Never fetches more files than needed to reach max_chars — stops as soon
    as the cap is hit, truncating the final chunk rather than exceeding it.
    """
    if tree_paths is None or get_contents_fn is None:
        gh = Github(token)
        repo = gh.get_repo(owner_repo)
        tree = repo.get_git_tree(repo.default_branch, recursive=True)
        tree_paths = [entry.path for entry in tree.tree if entry.type == "blob"]

        def _real_get_contents_fn(path: str) -> str:
            content_file = repo.get_contents(path)
            raw = content_file.content
            return base64.b64decode(raw).decode("utf-8", errors="replace")

        get_contents_fn = _real_get_contents_fn

    matched_paths = _match_doc_paths(tree_paths)
    if not matched_paths:
        return None

    chunks: list[str] = []
    total = 0
    for path in matched_paths:
        text = get_contents_fn(path)
        header = f"--- {path} ---\n"
        remaining = max_chars - total
        if remaining <= 0:
            break
        if len(header) + len(text) > remaining:
            text = text[: max(remaining - len(header), 0)]
        chunks.append(f"{header}{text}")
        total += len(header) + len(text)
        if total >= max_chars:
            break

    return "\n\n".join(chunks)
