# Quickstart: Hybrid Graph + Vector Retrieval

**Feature**: [spec.md](./spec.md)
**Last Updated**: 2026-06-30

## Prerequisites

- LocalScope repo cloned and Python 3.14 environment active
- library-catalog-app indexed (vector index exists at default index dir)
- Ollama running with `mxbai-embed-large` available
- Dependencies installed: `pip install networkx tree-sitter tree-sitter-java tree-sitter-typescript tree-sitter-html python-Levenshtein`

## 1. Enable Graph Retrieval

```bash
export LCQ_GRAPH_ENABLED=true
```

## 2. Build the Graph Index

Trigger a re-index of library-catalog-app with graph enabled:

```bash
python cli/index.py --repo /path/to/library-catalog-app
```

Expected output:
```
[vector] Skipping N unchanged files...
[graph] Building graph for 397 Java files, 143 TypeScript files...
[graph] Extracted 5,241 edges in 12.3s
[graph] Saved to /path/to/index/graph.json
```

Full build should complete in under 60 seconds (SC-007).

## 3. Run a Query

```bash
python cli/query.py "how does the system calculate overdue fines for different member types"
```

Expected: `StandardFineStrategy.java`, `PremiumFineStrategy.java`, `StudentFineStrategy.java`,
and `OverdueFineContext.java` all appear in the top-10 results.

With graph disabled (baseline):
```bash
LCQ_GRAPH_ENABLED=false python cli/query.py "how does the system calculate overdue fines for different member types"
```

Expected: strategy files mostly missing from top-10 (vector-only baseline R@10 ≈ 0.20).

## 4. Run the Benchmark (test_10)

```bash
LCQ_GRAPH_ENABLED=true pytest test_suite/test_10_graph_retrieval.py -v
```

Assertions that MUST pass:
- `fine_calculation_strategy` R@10 ≥ 0.80
- `loan_eligibility_chain` R@10 ≥ 0.80
- Mean R@10 ≥ 0.70
- Mean P@5 ≥ 0.50
- Mean MRR ≥ 0.88

Regression guard (all 9 currently-passing test_04 queries must still pass).

## 5. Test Incremental Update

Edit one Java file in library-catalog-app (add a comment), then re-index:

```bash
echo "// test" >> /path/to/library-catalog-app/src/main/java/com/example/library/service/BookService.java
python cli/index.py --repo /path/to/library-catalog-app
```

Expected: only `BookService.java` shows `[graph] Processing 1 changed file` in output.
Incremental update should complete in under 5 seconds (SC-008).

## 6. Tune α and β (Optional)

Run the parametrized tuning test to find optimal weights for Java/Angular corpus:

```bash
LCQ_GRAPH_ENABLED=true pytest test_suite/test_10_graph_retrieval.py::test_alpha_beta_sweep -v
```

The sweep covers α ∈ {0.1, 0.3, 0.5, 0.7} and β ∈ {0.4, 0.6, 0.8}.
Output shows mean R@10 per combination. Update `LCQ_GRAPH_ALPHA` and `LCQ_GRAPH_BETA`
in your environment or `config.py` defaults with the winning values.

## 7. Test Fallback Behavior

Corrupt the graph file and confirm graceful fallback to vector-only:

```bash
echo "corrupt" > $(python -c "from config import INDEX_DIR; print(INDEX_DIR)")/graph.json
LCQ_GRAPH_ENABLED=true python cli/query.py "test query"
```

Expected: warning logged, results identical to vector-only baseline, no crash.

## Verifying Plugin Registration

Confirm all three plugins registered correctly:

```bash
python -c "
from graph.plugins import java_plugin, typescript_plugin, html_plugin
from graph.plugin_registry import default_registry
for ext in ['.java', '.ts', '.tsx', '.html', '.css']:
    plugin = default_registry.get(ext)
    print(f'{ext}: {plugin.__class__.__name__ if plugin else None}')
"
```

Expected output:
```
.java: JavaPlugin
.ts: TypeScriptPlugin
.tsx: TypeScriptPlugin
.html: HtmlPlugin
.css: None
```
