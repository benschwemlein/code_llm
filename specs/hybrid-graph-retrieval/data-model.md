# Data Model: Hybrid Graph + Vector Retrieval

**Feature**: [spec.md](./spec.md)
**Last Updated**: 2026-06-30

## Entities

### Edge

Represents a directed structural relationship between two files in the repository.

| Field | Type | Description |
|---|---|---|
| source | string | Absolute or repo-relative path of the originating file |
| target | string | Absolute or repo-relative path of the referenced file |
| edge_type | EdgeType | The kind of structural relationship |
| weight | float | Confidence weight, default 1.0; plugins may set < 1.0 for lower-confidence edges |

**Notes**:
- Edges are directional: `A IMPORTS B` does not imply `B IMPORTS A`
- Both source and target must be file paths, not class names or symbols
- weight < 1.0 is used by the HTML plugin for Angular selector-inferred references

---

### EdgeType

Enum of standard structural relationship types shared across all language plugins.

| Value | Meaning | Example |
|---|---|---|
| IMPORTS | File A statically imports/includes File B | `BookService.java` imports `BookRepository.java` |
| INVOKES | File A calls a function or method defined in File B | `OverdueFineContext.java` invokes `StandardFineStrategy.java` |
| INHERITS | File A extends or implements a type defined in File B | `StandardFineStrategy.java` implements `FineCalculationStrategy.java` |
| REFERENCES | File A references a type or symbol from File B (template/markup) | Angular template references its component class |
| CONTAINS | File A contains a logical sub-unit defined in File B | Class file contains inner class (file-level scope, v1 limited use) |

---

### GraphStore

The in-memory graph that holds all edges for the indexed repository.

**Responsibilities**:
- Store the directed graph of file-to-file edges
- Answer shortest-path queries (Dijkstra) from a seed file to any reachable file
- Persist to and load from disk as a JSON file
- Support incremental update: remove all edges for a given file, add new edges

**Key operations**:
- `add_edges(edges)` — bulk insert edges from one file's extraction pass
- `remove_file(path)` — remove all edges where source == path (for modified/deleted files)
- `shortest_path_length(source, target)` — Dijkstra distance; returns ∞ if unreachable
- `save(path)` — serialize to `graph.json`
- `load(path)` — deserialize; raises `GraphLoadError` on corrupt/incompatible file

**Storage format**: networkx node-link JSON. Nodes are file paths; edges carry `edge_type`
and `weight` attributes.

---

### LanguagePlugin

Abstract base class that each language-specific plugin implements.

**Contract** (see [contracts/plugin-interface.md](./contracts/plugin-interface.md)):
- Declares `extensions: list[str]` — the file extensions this plugin handles
- Implements `extract_edges(file_path: str, source: str) -> list[Edge]`
- Registers itself with the `default_registry` at module import time
- Returns `[]` on parse error (never raises); logs a warning

**Implementations**:
- `JavaPlugin` — handles `.java`
- `TypeScriptPlugin` — handles `.ts`, `.tsx`
- `HtmlPlugin` — handles `.html`

---

### PluginRegistry

Maps file extensions to the plugin instance responsible for that extension.

| Operation | Description |
|---|---|
| `register(plugin)` | Register a LanguagePlugin for all its declared extensions |
| `get(ext)` | Return the plugin for this extension, or `None` if unregistered |

**Module-level instance**: `default_registry` — auto-populated when plugin modules are imported.

---

### FusionResult

A single re-ranked retrieval candidate produced by the fusion layer.

| Field | Type | Description |
|---|---|---|
| file_path | string | Path of the candidate file |
| score | float | KGCompass composite score: `β^l · (α·cos_norm + (1−α)·lev)` |
| cos_norm | float | Normalized cosine similarity from ChromaDB (0–1) |
| lev | float | Levenshtein ratio between query text and file content snippet (0–1) |
| path_distance | float | Dijkstra shortest-path distance from nearest vector seed; 0 for seeds |
| source | string | `"vector"` if seed from ChromaDB, `"graph"` if discovered via traversal |

**Ordering**: FusionResults are returned sorted by `score` descending.

---

## Relationships

```
PluginRegistry
    ├── JavaPlugin        (ext: .java)
    ├── TypeScriptPlugin  (ext: .ts, .tsx)
    └── HtmlPlugin        (ext: .html)

Each plugin → extract_edges() → list[Edge]
                                    │
                                    ▼
                              GraphStore (networkx DiGraph)
                                    │
                         shortest_path_length()
                                    │
                                    ▼
                           fusion.expand_and_rerank()
                                    │
                                    ▼
                            list[FusionResult]
```

## Graph Persistence

The graph is co-located with the ChromaDB index directory:

```
{index_dir}/
    chroma/          ← ChromaDB vector index
    graph.json       ← networkx node-link serialization of GraphStore
    graph_hashes.json  ← file path → content hash (for incremental build)
```

`GraphLoadError` is raised when `graph.json` exists but cannot be parsed or has an
incompatible schema version. The query engine catches this and falls back to vector-only.
