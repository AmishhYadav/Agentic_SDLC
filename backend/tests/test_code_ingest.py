"""Coverage for app.services.code_ingest — collect_files/chunk_files, hermetic (no network)."""

from app.services.code_ingest import chunk_files, collect_files


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_collect_files_includes_source_and_doc_files(tmp_path):
    _write(tmp_path / "main.py", "print('hello')\n")
    _write(tmp_path / "README.md", "# Title\nSome docs.\n")

    files = collect_files(str(tmp_path))
    paths = {path for path, _ in files}

    assert "main.py" in paths
    assert "README.md" in paths


def test_collect_files_excludes_node_modules_dir(tmp_path):
    _write(tmp_path / "main.py", "print('hi')\n")
    _write(tmp_path / "node_modules" / "pkg" / "index.js", "module.exports = {};\n")

    files = collect_files(str(tmp_path))
    paths = {path for path, _ in files}

    assert "main.py" in paths
    assert not any("node_modules" in path for path in paths)


def test_collect_files_excludes_lockfiles(tmp_path):
    _write(tmp_path / "main.py", "print('hi')\n")
    _write(tmp_path / "package-lock.json", '{"lockfileVersion": 3}\n')

    files = collect_files(str(tmp_path))
    paths = {path for path, _ in files}

    assert "main.py" in paths
    assert "package-lock.json" not in paths


def test_collect_files_excludes_oversized_files(tmp_path):
    _write(tmp_path / "small.py", "x = 1\n")
    big_content = "a" * 200_001
    _write(tmp_path / "big.py", big_content)

    files = collect_files(str(tmp_path))
    paths = {path for path, _ in files}

    assert "small.py" in paths
    assert "big.py" not in paths


def test_collect_files_excludes_binary_files(tmp_path):
    _write(tmp_path / "text.py", "print('ok')\n")
    binary_path = tmp_path / "image.py"  # extension included but content is binary
    binary_path.write_bytes(b"\x00\x01\x02\xff\xfe")

    files = collect_files(str(tmp_path))
    paths = {path for path, _ in files}

    assert "text.py" in paths
    assert "image.py" not in paths


def test_collect_files_excludes_unrecognized_extensions(tmp_path):
    _write(tmp_path / "main.py", "print('ok')\n")
    _write(tmp_path / "binary.exe", "not really binary but wrong ext\n")

    files = collect_files(str(tmp_path))
    paths = {path for path, _ in files}

    assert "main.py" in paths
    assert "binary.exe" not in paths


def test_chunk_files_produces_chunks_with_path_and_language_metadata(tmp_path):
    files = [("app/main.py", "\n".join(f"line {i}" for i in range(50)))]
    chunks = chunk_files(files, chunk_size=200, overlap=50)

    assert len(chunks) > 0
    for chunk in chunks:
        assert chunk["path"] == "app/main.py"
        assert chunk["language"] == "py"
        assert isinstance(chunk["text"], str)
        assert chunk["text"].strip() != ""


def test_chunk_files_skips_empty_files():
    files = [("empty.py", "   \n\n   ")]
    chunks = chunk_files(files)
    assert chunks == []


def test_chunk_files_respects_overlap_by_producing_multiple_chunks_for_long_file():
    long_text = "\n".join(f"line number {i} of content" for i in range(200))
    files = [("long.py", long_text)]
    chunks = chunk_files(files, chunk_size=300, overlap=50)
    assert len(chunks) > 1
