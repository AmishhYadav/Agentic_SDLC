"""Pre-compute and persist the codebase RAG index.

Run this once (e.g. before starting the server) so the "Ask the codebase" chat
loads a ready index at startup instead of embedding the repo live.

    python scripts/build_codebase_index.py                     # default source
    python scripts/build_codebase_index.py --repo owner/name   # clone + index a repo
    python scripts/build_codebase_index.py --nim               # force NIM embeddings
    python scripts/build_codebase_index.py --local             # force local embeddings

Source precedence when --repo is omitted: env GITHUB_REPO > BROWNFIELD_PATH >
this repo. Embedder auto-selects NIM when a live model is configured, else local;
--nim / --local force it. The index is stamped so queries embed the same way.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from app.services import codebase_index  # noqa: E402


def _arg_value(args: list[str], flag: str) -> str | None:
    if flag in args:
        i = args.index(flag)
        if i + 1 < len(args):
            return args[i + 1]
    return None


def main() -> None:
    args = sys.argv[1:]
    if "--nim" in args:
        provider = "nim"
    elif "--local" in args:
        provider = "local"
    else:
        provider = None  # auto

    # --repo owner/name overrides the env/default source.
    github_repo = _arg_value(args, "--repo")

    source = github_repo or os.environ.get("GITHUB_REPO", "").strip() or "default source"
    print(f"Building codebase index (source={source}, embedder={provider or 'auto'}) …")
    _, meta = codebase_index.build_index(provider=provider, github_repo=github_repo)
    print(
        f"Done: {meta['file_count']} files, {meta['chunk_count']} chunks "
        f"({', '.join(f'{k}:{v}' for k, v in meta['languages'].items())}) "
        f"from {meta['root']}"
    )
    print(f"Saved to {os.path.abspath(codebase_index.INDEX_DIR)}")


if __name__ == "__main__":
    main()
