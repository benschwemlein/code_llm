# Contract: Fusion Layer API

**Feature**: [../spec.md](../spec.md)
**Last Updated**: 2026-06-30

## Purpose

Defines the interface between the query engine and the graph-based fusion layer.
The query engine calls this API after ChromaDB retrieval. The fusion layer expands the
seed results via graph traversal and re-ranks all candidates using the KGCompass formula.

## expand_and_rerank

```
graph/fusion.py
```

### Signature

```
expand_and_rerank(
    seeds: list[SeedResult],
    query_text: str,
    graph_store: GraphStore,
    alpha: float = 0.3,
    beta: float = 0.6,
    max_hops: int = 3,
) -> list[FusionResult]
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| seeds | list[SeedResult] | required | ChromaDB results: file_path + cosine distance score |
| query_text | str | required | Raw query string (used for Levenshtein similarity) |
| graph_store | GraphStore | required | Loaded graph; used for Dijkstra shortest-path queries |
| alpha | float | 0.3 | Weight for embedding similarity vs. lexical similarity (0=pure lexical, 1=pure embedding) |
| beta | float | 0.6 | Path distance decay factor (0=ignore graph, 1=no decay) |
| max_hops | int | 3 | Maximum Dijkstra expansion depth from any seed node |

### Returns

`list[FusionResult]` sorted by `score` descending. May include files not in `seeds` if
they were discovered via graph traversal.

### Scoring Formula

For each candidate file `f`:

```
cos_norm(f) = 1 - chromadb_distance(f)        # normalize cosine distance to similarity
lev(f)      = Levenshtein.ratio(query_text, snippet(f))
l(f)        = min shortest-path distance from any seed node to f (0 for seed nodes)

score(f) = beta^l(f) * (alpha * cos_norm(f) + (1 - alpha) * lev(f))
```

### Contract

- MUST return results for all seed files, even if they have no graph edges.
- MUST NOT return candidates that have no `cos_norm` score (i.e., files discovered via
  graph traversal that are not in the ChromaDB index). These cannot be scored and are
  excluded from results.
- MUST return an empty list if `seeds` is empty (no expansion possible).
- MUST NOT raise exceptions if the graph_store has no edges for a seed file.
  Treat unreachable files as having `l(f) = ∞` and exclude them from results.
- When `beta=0`, all graph-discovered files score 0 and only seeds are returned.
- When `alpha=0`, `cos_norm` is ignored and scoring is purely lexical + path decay.
- When `alpha=1`, `lev` is ignored and scoring is purely embedding + path decay.
- Seed nodes always have `path_distance = 0`, so `beta^0 = 1.0` (no decay for seeds).

### Fallback Behavior

The query engine MUST catch `GraphLoadError` and any other exception from this function
and fall back to returning the original `seeds` as-is (vector-only mode). This ensures
graph errors never crash the query engine.

## SeedResult (Input Type)

Produced by the ChromaDB query layer; passed into `expand_and_rerank` as seeds.

| Field | Type | Description |
|---|---|---|
| file_path | str | Repo-relative path of the retrieved file |
| cos_distance | float | Raw ChromaDB cosine distance (lower = more similar) |
| content_snippet | str | First N characters of file content (used for Levenshtein) |

## Validation Criteria

The fusion implementation is correct if:

1. All seed files appear in the returned list with `path_distance = 0`
2. Graph-discovered files appear with `path_distance > 0`
3. Files with no ChromaDB embedding do not appear in results
4. Score for a seed (l=0) equals `alpha * cos_norm + (1 - alpha) * lev`
5. Score for a 1-hop neighbor equals `beta * (alpha * cos_norm + (1 - alpha) * lev)` when it has a cos_norm
6. Results are sorted descending by score
7. Empty seeds → empty results (no expansion)
8. Exception from graph_store → caller falls back to seeds (caller contract, not fusion's)
