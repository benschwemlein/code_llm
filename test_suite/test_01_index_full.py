"""
Tests for the full indexer against the sample app.
All read-only tests share the session-scoped `indexed_app` fixture — no re-embedding.
`test_second_full_index_replaces_first` copies the session index to avoid re-embedding.
"""

import pytest
import chromadb
from chromadb.config import Settings


def _open_first_collection(index_dir: str):
    client = chromadb.PersistentClient(
        path=index_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    collections = client.list_collections()
    assert collections, "No collections found in index"
    return client.get_collection(collections[0].name)


def test_index_completes_without_error(indexed_app):
    logs = indexed_app["logs"]
    assert any("chunks" in line.lower() for line in logs), (
        "Expected chunk count in logs. Got:\n" + "\n".join(logs)
    )


def test_index_creates_collection(indexed_app):
    collection = _open_first_collection(indexed_app["index_dir"])
    assert collection is not None


def test_index_produces_chunks(indexed_app):
    collection = _open_first_collection(indexed_app["index_dir"])
    count = collection.count()
    assert count >= 100, f"Expected at least 100 chunks, got {count}"


def test_index_java_files_present(indexed_app):
    collection = _open_first_collection(indexed_app["index_dir"])
    result = collection.get(include=["metadatas"])
    sources = {m.get("source", "") for m in result["metadatas"] if m}
    java_sources = [s for s in sources if s.endswith(".java")]
    assert java_sources, f"No .java files in index. Sample sources: {list(sources)[:10]}"


def test_index_typescript_files_present(indexed_app):
    collection = _open_first_collection(indexed_app["index_dir"])
    result = collection.get(include=["metadatas"])
    sources = {m.get("source", "") for m in result["metadatas"] if m}
    ts_sources = [s for s in sources if s.endswith(".ts")]
    assert ts_sources, f"No .ts files in index. Sample sources: {list(sources)[:10]}"


def test_index_chunks_have_required_metadata_keys(indexed_app):
    collection = _open_first_collection(indexed_app["index_dir"])
    result = collection.get(include=["metadatas"], limit=50)
    for meta in result["metadatas"]:
        assert meta is not None, "Got a None metadata entry"
        assert "source" in meta, f"Missing 'source': {meta}"
        assert "chunk_index" in meta, f"Missing 'chunk_index': {meta}"
        assert "file_hash" in meta, (
            f"Missing 'file_hash': {meta}\n"
            "Full indexer must write file_hash so incremental indexing works."
        )


def test_index_no_empty_documents(indexed_app):
    collection = _open_first_collection(indexed_app["index_dir"])
    result = collection.get(include=["documents"], limit=200)
    empty = [i for i, doc in enumerate(result["documents"]) if not doc or not doc.strip()]
    assert not empty, f"Found {len(empty)} empty chunks at indices: {empty[:5]}"


def test_second_full_index_replaces_first(indexed_app, copied_index_dir, sample_app_path):
    """Running full index on an existing collection should replace, not accumulate."""
    from indexing.indexer import index_repo
    count_before = _open_first_collection(copied_index_dir).count()

    index_repo(repo_root=sample_app_path, index_dir=copied_index_dir, log=lambda _: None)
    count_after = _open_first_collection(copied_index_dir).count()

    assert count_after < count_before * 1.1, (
        f"After second index: {count_after} chunks vs {count_before} before. "
        "Chunks appear to be accumulating instead of replacing."
    )
