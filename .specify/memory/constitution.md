<!--
SYNC IMPACT REPORT
==================
Version change: (none) → 1.0.0
Bump rationale: Initial ratification — template placeholders replaced with concrete LocalScope principles.

Principles defined:
  I.   Local-First Privacy (new)
  II.  Benchmarking-Driven Quality (new)
  III. Incremental-by-Default (new)
  IV.  Feature Flags for Retrieval Changes (new)

Added sections:
  - Core Principles (I–IV)
  - Quality Gates
  - Development Workflow
  - Governance

Removed sections:
  - Template placeholder slot V (only four principles fit this project)

Templates requiring updates:
  ✅ .specify/templates/plan-template.md  (Constitution Check gate already generic; no edit required)
  ✅ .specify/templates/spec-template.md  (no constitution references; no edit required)
  ✅ .specify/templates/tasks-template.md (test/performance/polish categories align; no edit required)

Follow-up TODOs:
  - None.
-->

# LocalScope Constitution

## Core Principles

### I. Local-First Privacy

LocalScope MUST never transmit source code, embeddings, queries, or any repo content to
an external service. All models, vector storage, and inference run on the developer's machine.

- Every dependency MUST be self-hosted: Ollama for embeddings and chat, ChromaDB for vector
  storage, networkx for graph storage. No API keys, no cloud SDKs, no telemetry.
- New features MUST NOT introduce optional or fallback paths that make network calls without
  explicit, prominent documentation and a hard opt-in config flag.
- The README MUST always accurately state what runs locally and confirm no data leaves the
  machine.

**Rationale**: The primary use case is proprietary codebases where sending source to a
cloud LLM is off the table. The local-only guarantee is not a feature — it is the product.
Any leak, even optional, destroys the value proposition.

### II. Benchmarking-Driven Quality

Retrieval quality changes MUST be validated with the test suite before being considered
complete. Intuition and anecdote are not acceptable evidence.

- The benchmark corpus (library-catalog-app) and ground truth query set (test_04) are the
  authoritative quality signal. P@5, R@10, and MRR are the standard metrics.
- A feature that adds, changes, or replaces retrieval logic MUST ship with a corresponding
  test (e.g., test_10 for graph retrieval) that asserts measurable improvement on at least
  one previously-failing query without regressing currently-passing ones.
- Model selections (embedding and chat) MUST be documented with benchmark results in
  test_suite/ notes; no model change ships without a recorded comparison run.
- "It feels better" is not a valid acceptance criterion. A quantified delta is.

**Rationale**: Retrieval quality is the product's core output. Without a repeatable,
automated measure of quality, every change is a gamble. The test suite exists precisely
to make quality changes safe and reversible.

### III. Incremental-by-Default

Every pipeline stage that processes files MUST support incremental operation — only
changed files are re-processed on subsequent runs.

- The vector indexer and any future pipeline stage (e.g., graph builder) MUST track file
  content hashes and skip unchanged files since the last run.
- Full rebuilds are a fallback for corruption recovery, not the default path.
- Incremental update time for a single changed file MUST remain under 10 seconds for the
  library-catalog-app corpus on a developer laptop. Regressions to this bound must be
  justified and documented.
- New pipeline stages that cannot meet the incremental contract MUST be explicitly
  justified in their feature spec and plan.

**Rationale**: Developers use this tool in a tight edit-query loop. A tool that forces a
full rebuild on every file change breaks that loop. Incremental indexing is what makes
LocalScope usable as a daily driver rather than a one-shot script.

### IV. Feature Flags for Retrieval Changes

Any new retrieval mode or strategy that could affect result quality MUST default to
disabled and ship behind a named config flag until its benchmark gate passes.

- Flags MUST be readable from environment variables with a `LCQ_` prefix (e.g.,
  `LCQ_GRAPH_ENABLED`, `LCQ_GRAPH_ALPHA`).
- The default value for a new flag MUST preserve the behavior of the system before the
  feature was introduced (i.e., `LCQ_GRAPH_ENABLED=false` leaves existing behavior unchanged).
- The benchmark gate for flipping a flag to default-on is: the feature's test suite passes
  its defined success criteria (P@5, R@10, MRR targets) AND no regressions on the
  currently-passing ground truth queries.
- Once the gate passes, the flag default MAY be changed in a dedicated commit with the
  benchmark results cited in the commit message.

**Rationale**: A retrieval change that degrades quality for all queries to fix one query
is not a net win. Feature flags let new strategies be developed and tested in isolation
without risk to existing behavior, and the benchmark gate ensures the flip to default-on
is evidence-based, not aspirational.

## Quality Gates

Before any feature is considered complete:

1. **Privacy gate**: No new external network calls introduced. Only `requests` to the
   local Ollama endpoint (`localhost`) is permitted. New code MUST be checked for imports
   of `boto3`, `openai`, `anthropic`, or any cloud SDK.
2. **Benchmark gate**: The feature's test asserts measurable improvement (or at minimum
   no regression) on P@5, R@10, and MRR vs the vector-only baseline.
3. **Incremental gate**: If the feature touches the indexing pipeline, incremental
   behavior is confirmed: only changed files are re-processed.
4. **Flag gate**: If the feature changes retrieval behavior, it ships behind a `LCQ_`
   flag defaulting to the pre-feature behavior.

## Development Workflow

- Each plan.md task ships as its own commit with a descriptive message.
- Commit messages MUST NOT reference internal company names, client names, or project
  codenames. Use `com.example.*` for any Java package references in commit context.
- No `Co-Authored-By` lines in commits.
- The test suite (`pytest test_suite/`) MUST pass before any commit that touches retrieval
  logic. Full embedding comparison runs (test_09) may be skipped on pure refactors.
- spec.md and plan.md in the feature's specs/ directory are the source of truth for scope.
  Implementation MUST NOT exceed the spec without a spec amendment committed first.

## Governance

The constitution supersedes all other practices. Amendments require:

1. A concrete rationale — what changed and why the principle needed updating.
2. A version bump per the semantic rules: MAJOR for principle removals or redefinitions,
   MINOR for new principles or material expansions, PATCH for clarifications or wording.
3. An update to any templates or docs that reference the changed principle.
4. A commit citing the amended section(s) in the message.

Amendments are made by updating this file and recording the change in the Sync Impact
Report comment at the top.

**Version**: 1.0.0 | **Ratified**: 2026-06-30 | **Last Amended**: 2026-06-30
