"""
Tests for the incremental indexer.

Most tests start from a copy of the session index (no re-embedding).
Only `test_incremental_first_run_indexes_all_files` starts from an empty index
to verify first-run behaviour — it is the only test here that calls Ollama.
"""

import os
import pytest
import chromadb
from chromadb.config import Settings


def _collection_count(index_dir: str) -> int:
    client = chromadb.PersistentClient(
        path=index_dir,
        settings=Settings(anonymized_telemetry=False),
    )
    cols = client.list_collections()
    return client.get_collection(cols[0].name).count() if cols else 0


def _run_incremental(sample_app_path, index_dir, **kwargs):
    from indexing.incremental_indexer import index_repo_incremental
    logs = []
    index_repo_incremental(
        repo_root=sample_app_path,
        index_dir=index_dir,
        log=logs.append,
        **kwargs,
    )
    return logs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_incremental_first_run_indexes_all_files(indexed_app, tmp_path):
    """Starting from an empty index should process every eligible file."""
    index_dir = str(tmp_path / "chroma_fresh")
    logs = _run_incremental(indexed_app["sample_app_path"], index_dir)
    joined = "\n".join(logs)
    assert "indexable files" in joined, f"Expected file count summary.\n{joined}"
    assert _collection_count(index_dir) >= 100


def test_incremental_no_changes_skips_processing(indexed_app, copied_index_dir):
    """Second run on unchanged repo reports no work to do — no Ollama calls."""
    logs = _run_incremental(indexed_app["sample_app_path"], copied_index_dir)
    joined = "\n".join(logs)
    assert "up to date" in joined.lower() or "Files to add:    0" in joined, (
        f"Expected second run to report no changes.\n{joined}"
    )


def test_incremental_detects_new_file(indexed_app, copied_index_dir):
    """Adding one new file triggers exactly one file indexed on next run."""
    count_before = _collection_count(copied_index_dir)
    new_file = os.path.join(indexed_app["sample_app_path"], "TestNewFile.java")
    try:
        with open(new_file, "w") as f:
            f.write(
                "public class TestNewFile {\n"
                "    // Marker: UNIQUE_TEST_STRING_XYZ\n"
                "    public void hello() { System.out.println(\"hello\"); }\n"
                "}\n"
            )
        logs = _run_incremental(indexed_app["sample_app_path"], copied_index_dir)
        joined = "\n".join(logs)
        assert "Files to add:    1" in joined, (
            f"Expected 1 new file detected.\n{joined}"
        )
        assert _collection_count(copied_index_dir) > count_before
    finally:
        if os.path.exists(new_file):
            os.remove(new_file)


def test_incremental_detects_modified_file(indexed_app, copied_index_dir):
    """Modifying one file triggers re-indexing of that file only."""
    target = None
    for root, _, files in os.walk(indexed_app["sample_app_path"]):
        for f in files:
            if f.endswith(".java"):
                target = os.path.join(root, f)
                break
        if target:
            break

    assert target, "No .java file found to modify"
    original = open(target).read()
    try:
        with open(target, "a") as f:
            f.write("\n// MODIFIED_BY_TEST\n")
        logs = _run_incremental(indexed_app["sample_app_path"], copied_index_dir)
        joined = "\n".join(logs)
        assert "Files to update: 1" in joined, (
            f"Expected 1 updated file detected.\n{joined}"
        )
    finally:
        with open(target, "w") as f:
            f.write(original)


def test_incremental_detects_deleted_file(indexed_app, tmp_path):
    """
    Index including a temp file, delete it, run incremental —
    deleted chunks removed with no Ollama calls for the rest.
    """
    index_dir = str(tmp_path / "chroma_with_extra")
    temp_file = os.path.join(indexed_app["sample_app_path"], "TempDeleteMe.java")
    try:
        with open(temp_file, "w") as f:
            f.write("public class TempDeleteMe { }\n")
        _run_incremental(indexed_app["sample_app_path"], index_dir)
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    logs = _run_incremental(indexed_app["sample_app_path"], index_dir)
    joined = "\n".join(logs)
    assert "Files to delete: 1" in joined, (
        f"Expected 1 deleted file detected.\n{joined}"
    )


def test_incremental_force_reindex_rebuilds_everything(indexed_app, copied_index_dir):
    """force_full_reindex=True logs that it performed a full reindex."""
    logs = _run_incremental(
        indexed_app["sample_app_path"], copied_index_dir, force_full_reindex=True
    )
    joined = "\n".join(logs)
    assert "FULL reindex" in joined, f"Expected full reindex log.\n{joined}"
    assert _collection_count(copied_index_dir) >= 100
