"""Brownfield source resolution, file collection, and chunking for RAG ingestion.

resolve_source_dir() reads GITHUB_REPO/BROWNFIELD_PATH/GITHUB_TOKEN fresh from
os.environ (config, not run data — mirrors read_docs_greenfield's own
"read fresh from env" pattern). collect_files()/chunk_files() are pure
functions over a filesystem path so they're trivially testable against a
tmp_path fixture.
"""

import os
import tempfile

_INCLUDE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".go",
    ".rs",
    ".java",
    ".rb",
    ".c",
    ".h",
    ".cpp",
    ".css",
    ".html",
    ".sh",
}

_EXCLUDE_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "chroma_data",
    ".planning",
    ".pytest_cache",
}

_EXCLUDE_FILENAMES = {
    "package-lock.json",
    "poetry.lock",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
}

_MAX_FILE_BYTES = 200_000
_MAX_FILES = 400
_MAX_CHUNKS = 1200


def resolve_source_dir() -> tuple[str, bool]:
    """Decide what codebase to ingest for brownfield RAG.

    Precedence: GITHUB_REPO (shallow-clone via GitPython) > BROWNFIELD_PATH
    (a local path already on disk) > default to the repo root (parent of the
    backend dir) so the demo ingests this real codebase with zero config.

    Returns (path, is_temp_clone) — is_temp_clone is True only for the
    GITHUB_REPO clone path, so the caller knows to clean up the tempdir.
    """
    github_repo = os.environ.get("GITHUB_REPO", "").strip()
    if github_repo:
        return _clone_repo(github_repo), True

    brownfield_path = os.environ.get("BROWNFIELD_PATH", "").strip()
    if brownfield_path:
        return brownfield_path, False

    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    project_root = os.path.dirname(backend_dir)
    return project_root, False


def _clone_repo(github_repo: str) -> str:
    import git

    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    if github_token:
        url = f"https://{github_token}@github.com/{github_repo}.git"
    else:
        url = f"https://github.com/{github_repo}.git"

    tmpdir = tempfile.mkdtemp(prefix="brownfield_clone_")
    git.Repo.clone_from(url, tmpdir, depth=1)
    return tmpdir


def collect_files(root: str) -> list[tuple[str, str]]:
    """Walk root, returning (relative_path, text) for included, readable files.

    Excludes noisy/vendored directories, lockfiles, oversized files (>200KB),
    and binary files (detected via decode failure or embedded NUL byte). Caps
    the total number of files collected at _MAX_FILES for bounded runtime.
    """
    collected: list[tuple[str, str]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDE_DIRS]

        for filename in sorted(filenames):
            if len(collected) >= _MAX_FILES:
                return collected

            if filename in _EXCLUDE_FILENAMES:
                continue

            _, ext = os.path.splitext(filename)
            if ext.lower() not in _INCLUDE_EXTENSIONS:
                continue

            full_path = os.path.join(dirpath, filename)

            try:
                if os.path.getsize(full_path) > _MAX_FILE_BYTES:
                    continue
            except OSError:
                continue

            try:
                with open(full_path, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue

            if b"\x00" in raw:
                continue

            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue

            relative_path = os.path.relpath(full_path, root)
            collected.append((relative_path, text))

    return collected


def _split_lines_with_overlap(lines: list[str], chunk_size: int, overlap: int) -> list[str]:
    """Group lines into overlapping character-bounded chunks."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # account for the newline join
        if current and current_len + line_len > chunk_size:
            chunks.append("\n".join(current))
            # Build overlap tail from the end of the current chunk.
            overlap_lines: list[str] = []
            overlap_len = 0
            for prev_line in reversed(current):
                overlap_len += len(prev_line) + 1
                overlap_lines.insert(0, prev_line)
                if overlap_len >= overlap:
                    break
            current = overlap_lines
            current_len = sum(len(l) + 1 for l in current)

        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


def chunk_files(
    files: list[tuple[str, str]], chunk_size: int = 900, overlap: int = 150
) -> list[dict]:
    """Split each file's text into overlapping, line-respecting chunks.

    Each chunk dict carries {"text", "path", "language"} metadata. Caps total
    chunks across all files at _MAX_CHUNKS for bounded embedding cost.
    """
    all_chunks: list[dict] = []

    for path, text in files:
        if not text.strip():
            continue

        _, ext = os.path.splitext(path)
        language = ext[1:].lower() if ext else "text"

        lines = text.splitlines()
        if not lines:
            continue

        for chunk_text in _split_lines_with_overlap(lines, chunk_size, overlap):
            if not chunk_text.strip():
                continue
            all_chunks.append({"text": chunk_text, "path": path, "language": language})
            if len(all_chunks) >= _MAX_CHUNKS:
                return all_chunks

    return all_chunks
