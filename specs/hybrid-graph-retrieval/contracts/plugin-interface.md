# Contract: Language Plugin Interface

**Feature**: [../spec.md](../spec.md)
**Last Updated**: 2026-06-30

## Purpose

Defines the interface every language plugin must implement to participate in graph edge
extraction. Plugins are the extension point for adding new language support without
modifying the graph builder, graph store, or fusion layer.

## LanguagePlugin (Abstract Base Class)

```
graph/plugin_registry.py
```

### Class Attributes

| Attribute | Type | Required | Description |
|---|---|---|---|
| extensions | list[str] | Yes | File extensions this plugin handles (e.g., `[".java"]`) |

### Methods

#### extract_edges

```
extract_edges(file_path: str, source: str) -> list[Edge]
```

**Parameters**:
- `file_path` — absolute path to the file on disk (used for reading content)
- `source` — repo-relative path of the file (used as the `source` field in returned edges)

**Returns**: List of `Edge` objects extracted from the file. May be empty.

**Contract**:
- MUST NOT raise exceptions. On any parse error (syntax error, encoding error, etc.),
  log a warning and return `[]`.
- MUST use repo-relative paths for both `source` and `target` fields of returned edges.
- MUST only return edges where `target` is resolvable to a file within the repository.
  Edges to external library classes (e.g., `org.springframework.*`) are stored with the
  unresolved class name as target — the fusion layer skips nodes with no vector embedding.
- MAY set `edge.weight` to a value < 1.0 for lower-confidence inferences (e.g., HTML
  template selector matching).
- MUST register itself with `default_registry` at module import time.

### Registration

Each plugin module must call `default_registry.register(PluginClass())` at module level
so that importing the module auto-registers it:

```python
# At module bottom:
default_registry.register(JavaPlugin())
```

The graph builder imports all plugin modules during initialization, which triggers
registration without any explicit configuration.

## PluginRegistry

```
graph/plugin_registry.py
```

### Methods

#### register

```
register(plugin: LanguagePlugin) -> None
```

Register a plugin for all extensions in `plugin.extensions`. If an extension is already
registered, the new plugin replaces the previous one (last-write-wins).

#### get

```
get(ext: str) -> LanguagePlugin | None
```

Return the plugin registered for the given extension (e.g., `".java"`), or `None` if
no plugin is registered. Extension lookup is case-insensitive.

## Example Implementation

```python
class JavaPlugin(LanguagePlugin):
    extensions = [".java"]

    def extract_edges(self, file_path: str, source: str) -> list[Edge]:
        try:
            content = Path(file_path).read_text(encoding="utf-8")
            tree = JAVA_PARSER.parse(bytes(content, "utf-8"))
            edges = []
            # ... extract IMPORTS, INHERITS, INVOKES, CONTAINS edges ...
            return edges
        except Exception as e:
            logger.warning(f"Java plugin: failed to parse {file_path}: {e}")
            return []

default_registry.register(JavaPlugin())
```

## Validation Criteria

A plugin implementation is correct if:

1. It can be imported without error and auto-registers via `default_registry`
2. `registry.get(".java")` returns the plugin after import
3. Calling `extract_edges` on a valid file returns a non-empty list of typed Edge objects
4. Calling `extract_edges` on a syntactically broken file returns `[]` (no exception)
5. All returned Edge `source` fields match the `source` parameter passed in
6. All returned Edge `target` fields are repo-relative paths (not absolute, not class FQNs)
