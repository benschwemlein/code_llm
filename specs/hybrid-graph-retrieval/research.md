# Research: Hybrid Graph + Vector Retrieval

**Feature**: [spec.md](./spec.md)
**Last Updated**: 2026-06-30

## Academic Foundations

### KGCompass (arXiv 2503.21710)

The primary academic basis for the scoring formula. KGCompass builds a knowledge graph of
a repository and fuses graph traversal with vector search using:

```
S(f) = β^l(f) · (α · cos_norm(e_query, e_f) + (1−α) · lev(query, f))
```

Where `l(f)` is the shortest path distance from the query's seed nodes to file `f`,
`α` balances embedding vs. lexical similarity, and `β` decays score with path distance.

**Published defaults**: α=0.3, β=0.6 (tuned on Python/SWE-bench corpus).
**Key finding**: Graph traversal recovers files that are structurally reachable from
semantically-found seeds but not themselves semantically similar to the query.
**Takeaway for LocalScope**: These defaults need tuning for the Java/Angular corpus.
test_10 provides the tuning loop (α sweep × β sweep → best mean R@10).

### RepoGraph (arXiv 2410.14684)

Builds file-level and function-level graphs from repositories using static analysis.
Demonstrated significant retrieval improvements over pure vector search on code Q&A tasks.

**Key finding**: File-level granularity is the practical starting point; function-level
adds precision but multiplies build complexity and node count.
**Takeaway for LocalScope**: Start at file level (v1). Function-level is a future upgrade
if R@10 plateaus after graph is working.

### CodeCompass (arXiv 2602.20048)

End-to-end code intelligence system combining graph-based structural retrieval with
LLM-based answer generation. Validates the hybrid approach at production scale.

**Key finding**: The structural graph is most valuable for multi-hop queries — questions
whose answers span files connected by call chains or inheritance hierarchies.
**Takeaway for LocalScope**: The fine_calculation_strategy failure (R@10=0.20 across all
4 embedding models) is exactly this pattern: OverdueFineContext → strategy classes via
INVOKES edges. Graph traversal is the correct fix.

### Microsoft GraphRAG

General graph-augmented RAG framework; not code-specific. Validates the general pattern
of combining semantic and structural retrieval but adds significant indexing complexity
(community detection, summarization) not needed for code navigation.

**Takeaway for LocalScope**: Avoid GraphRAG's full complexity. KGCompass's simpler
formula (no community detection) is sufficient for repository-scale code navigation.

## Technology Decisions

### Graph Storage: networkx (not Neo4j or DGL)

**Options evaluated**: networkx, Neo4j, DGL (Deep Graph Library), igraph

**Decision**: networkx

**Rationale**:
- LocalScope is a local desktop tool; no daemon/server process is acceptable
- networkx is pure Python, zero ops overhead, trivially serialized to JSON
- At library-catalog-app scale (~600 files, ~5k-15k edges) networkx fits in memory
  with sub-millisecond Dijkstra
- Neo4j requires a running server and Cypher query language — wrong fit for a local tool
- DGL is deep-learning-oriented (GNN training), not graph traversal

**Revisit trigger**: If the tool is applied to monorepos with >10k files or >100k edges,
networkx memory footprint may warrant switching to igraph or a lightweight embedded graph DB.

### AST Parsing: tree-sitter

**Options evaluated**: tree-sitter, ANTLR, JavaParser (Java-only), custom regex

**Decision**: tree-sitter

**Rationale**:
- Language-agnostic: one parser framework covers Java, TypeScript, and HTML
- Incremental parsing built-in — fast re-parse on file change
- Grammar packages installable via pip (tree-sitter-java, tree-sitter-typescript,
  tree-sitter-html)
- Battle-tested in production code editors (Neovim, Helix, GitHub)
- JavaParser is Java-only and would require a separate TS parser

**Known limitation**: tree-sitter grammars are syntactic, not semantic. Import resolution
(mapping `import com.example.library.service.BookService` to a file path) requires a
separate resolution step — we implement this as a best-effort path matcher.

### Graph Granularity: File-level (v1)

**Options evaluated**: file-level, class-level, function-level

**Decision**: file-level for v1

**Rationale**:
- LocalScope's existing retrieval unit is the file chunk, not the function
- File-level edges are sufficient to fix the fine_calculation_strategy failure
  (the strategy classes are in separate files, so file-level INVOKES edges suffice)
- Function-level would require mapping chunk IDs to graph nodes — adds complexity
  without clear v1 benefit
- RepoGraph showed file-level already provides substantial improvement over vector-only

**Revisit trigger**: If file-level graph achieves the SC-003 R@10 ≥ 0.70 target but
fine-grained queries still fail, function-level granularity is the next upgrade.

### Embedding Baseline: mxbai-embed-large

From test_09 (four-model comparison on library-catalog-app):

| Model | P@5 | R@10 | MRR |
|---|---|---|---|
| mxbai-embed-large | 0.38 | 0.56 | 0.83 |
| bge-m3 | 0.32 | 0.50 | 0.83 |
| nomic-embed-text | 0.28 | 0.47 | 0.71 |
| snowflake-arctic-embed2 | 0.26 | 0.36 | 0.75 |

mxbai-embed-large wins across P@5 and R@10. Already set as default in config.py.
The graph layer is built on top of this baseline — improvements are additive.

## Known Retrieval Failures (Motivating the Graph Layer)

### fine_calculation_strategy (R@10 = 0.20 across all models)

**Query**: "how does the system calculate overdue fines for different member types"

**Ground truth files**: OverdueFineContext.java, StandardFineStrategy.java,
PremiumFineStrategy.java, StudentFineStrategy.java, FineCalculationStrategy.java

**Why vector search fails**: The strategy implementation files contain the word "fine" but
their content is not semantically similar to the query. The query matches "overdue" and
"member types" content in LoanService and Member entity, not the strategy classes.

**Why graph traversal fixes it**: OverdueFineContext has INVOKES edges to all three
concrete strategy classes. Once the vector search finds OverdueFineContext, Dijkstra
expands outward one hop to recover the strategy files.

**SC-001 target**: R@10 ≥ 0.80 with graph enabled.

### loan_eligibility_chain (R@10 = 0.20–0.40 across models)

**Why vector search underperforms**: The eligibility check spans LoanService →
MemberService → FineService in a call chain. Vector search finds LoanService but
misses the downstream services.

**Why graph traversal fixes it**: INVOKES edges from LoanService to MemberService and
FineService are recovered in one additional Dijkstra hop.

**SC-002 target**: R@10 ≥ 0.80 with graph enabled.
