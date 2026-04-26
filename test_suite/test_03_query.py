"""
Tests for run_query against the pre-indexed sample app.

All tests in this file depend on the session-scoped `indexed_app` fixture
(defined in conftest.py), which indexes the sample app once for the session.
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _query(indexed_app, question, **kwargs):
    from querying.query_engine import run_query
    logs = []
    result = run_query(
        bug_text=question,
        index_dir=indexed_app["index_dir"],
        log=logs.append,
        **kwargs,
    )
    result["_logs"] = logs
    return result


# ---------------------------------------------------------------------------
# Basic sanity tests
# ---------------------------------------------------------------------------

def test_query_returns_answer(indexed_app):
    """run_query must return a non-empty answer string."""
    result = _query(indexed_app, "What does this application do?")
    answer = result.get("answer", "")
    assert isinstance(answer, str) and answer.strip(), (
        f"Expected a non-empty answer string. Got: {repr(answer)}"
    )


def test_query_returns_docs(indexed_app):
    """run_query must return a non-empty list of retrieved documents."""
    result = _query(indexed_app, "What does this application do?")
    docs = result.get("docs", [])
    assert isinstance(docs, list) and len(docs) > 0, (
        "Expected at least one retrieved document chunk."
    )


def test_query_returns_metas(indexed_app):
    """run_query must return metadata for each retrieved document."""
    result = _query(indexed_app, "What does this application do?")
    metas = result.get("metas", [])
    docs = result.get("docs", [])
    assert len(metas) == len(docs), (
        f"Metadata count ({len(metas)}) must match doc count ({len(docs)})"
    )


def test_query_sources_have_source_key(indexed_app):
    """Every returned metadata entry must include a 'source' key."""
    result = _query(indexed_app, "What does this application do?")
    for i, meta in enumerate(result.get("metas", [])):
        assert "source" in meta, f"Missing 'source' key in metadata[{i}]: {meta}"


def test_query_sources_are_from_sample_app(indexed_app):
    """Retrieved sources should be paths from within the sample app."""
    result = _query(indexed_app, "How is MongoDB connected and configured?")
    sources = [m.get("source", "") for m in result.get("metas", [])]
    assert sources, "No sources returned"
    # Sources are relative paths — they should not contain absolute path prefixes
    for s in sources:
        assert not s.startswith("/"), (
            f"Source looks like an absolute path (expected relative): {s}"
        )


def test_query_scores_are_in_range(indexed_app):
    """Similarity scores must be in [0, 100]."""
    result = _query(indexed_app, "How is the application structured?")
    scores = result.get("scores", [])
    assert scores, "No scores returned"
    for score in scores:
        assert 0.0 <= score <= 100.0, f"Score out of range: {score}"


# ---------------------------------------------------------------------------
# Domain-specific queries (Java / Spring Boot)
# ---------------------------------------------------------------------------

def test_query_mongodb_configuration(indexed_app):
    """Query about MongoDB config should retrieve Java config files."""
    result = _query(indexed_app, "How is MongoDB configured and what client is used?")
    sources = [m.get("source", "") for m in result.get("metas", [])]
    java_sources = [s for s in sources if s.endswith(".java")]
    assert java_sources, (
        f"Expected Java files in results for MongoDB query. Sources: {sources}"
    )
    assert result["answer"].strip(), "Answer must not be empty"


def test_query_kafka_usage(indexed_app):
    """Query about Kafka should find relevant Java code."""
    result = _query(indexed_app, "How is Kafka used for messaging in this application?")
    answer = result["answer"]
    sources = [m.get("source", "") for m in result.get("metas", [])]
    # Should retrieve some Java files and produce an answer
    assert any(s.endswith(".java") for s in sources), (
        f"Expected Java sources for Kafka query. Got: {sources}"
    )
    assert answer.strip()


def test_query_rest_controllers(indexed_app):
    """Query about REST endpoints should surface controller classes."""
    result = _query(indexed_app, "What REST API endpoints are exposed by the controllers?")
    sources = [m.get("source", "") for m in result.get("metas", [])]
    controller_sources = [s for s in sources if "controller" in s.lower() or "Controller" in s]
    assert controller_sources, (
        f"Expected controller files in results. Sources: {sources}"
    )


def test_query_user_authentication(indexed_app):
    """Query about authentication should find user/auth related code."""
    result = _query(indexed_app, "How does user authentication and login work?")
    answer = result["answer"]
    assert answer.strip(), "Expected a non-empty answer about authentication"
    sources = [m.get("source", "") for m in result.get("metas", [])]
    assert sources


# ---------------------------------------------------------------------------
# Domain-specific queries (Angular / TypeScript)
# ---------------------------------------------------------------------------

def test_query_angular_components(indexed_app):
    """Query about Angular components should retrieve TypeScript files."""
    result = _query(indexed_app, "What Angular components are defined in the frontend?")
    sources = [m.get("source", "") for m in result.get("metas", [])]
    ts_sources = [s for s in sources if s.endswith(".ts")]
    assert ts_sources, (
        f"Expected TypeScript files in Angular query results. Sources: {sources}"
    )


def test_query_statistics_component(indexed_app):
    """Query about statistics display should find the statistics component."""
    result = _query(indexed_app, "How does the statistics component display trading data?")
    sources = [m.get("source", "") for m in result.get("metas", [])]
    stat_sources = [s for s in sources if "statistic" in s.lower()]
    assert stat_sources, (
        f"Expected statistics-related files in results. Sources: {sources}"
    )


def test_query_routing_configuration(indexed_app):
    """Query about Angular routing should find routing config files."""
    result = _query(indexed_app, "How is Angular routing configured in the application?")
    sources = [m.get("source", "") for m in result.get("metas", [])]
    route_sources = [s for s in sources if "rout" in s.lower()]
    assert route_sources, (
        f"Expected routing files in results. Sources: {sources}"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_query_empty_string_raises(indexed_app):
    """Passing an empty query should raise ValueError."""
    from querying.query_engine import run_query
    with pytest.raises(ValueError, match="required"):
        run_query(bug_text="", index_dir=indexed_app["index_dir"])


def test_query_whitespace_only_raises(indexed_app):
    """Passing only whitespace should raise ValueError."""
    from querying.query_engine import run_query
    with pytest.raises(ValueError, match="required"):
        run_query(bug_text="   \n  ", index_dir=indexed_app["index_dir"])


def test_query_top_k_limits_results(indexed_app):
    """Requesting top_k=3 should return at most 3 documents."""
    result = _query(indexed_app, "What services exist in this application?", top_k=3)
    docs = result.get("docs", [])
    assert len(docs) <= 3, f"Expected at most 3 docs with top_k=3, got {len(docs)}"
