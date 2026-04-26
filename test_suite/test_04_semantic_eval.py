"""
Semantic retrieval evaluation for the RAG indexer and query engine.

Measures Precision@K, Recall@K, and MRR against a hand-curated ground truth
built from the AngularAndSpringSampleApp codebase.

Metrics
-------
precision_at_k  : fraction of the top-K retrieved chunks whose source file is
                  in the expected set.  Rewards ranking good files early.
recall_at_k     : fraction of expected files that appear at least once in the
                  top-K results.  Rewards covering the full relevant set.
mrr             : Mean Reciprocal Rank — 1/rank of the first chunk whose source
                  is in the expected set.  1.0 = relevant file is rank-1.

Thresholds (per-query and aggregate)
-------------------------------------
These are starting points.  Raise them as the system improves.

  Per-query  : recall@10 >= 0.25  (at least 1 in 4 expected files found)
  Aggregate  : mean precision@5  >= 0.35
               mean recall@10    >= 0.50
               mean MRR          >= 0.40
"""

import pytest
from dataclasses import dataclass, field
from typing import Callable

# ---------------------------------------------------------------------------
# Ground truth
# ---------------------------------------------------------------------------

@dataclass
class Case:
    name: str
    question: str
    expected_files: list[str]          # relative paths as produced by the indexer
    min_recall_at_10: float = 0.25     # per-query floor


GROUND_TRUTH: list[Case] = [
    Case(
        name="jwt_authentication",
        question="How is JWT token validation and authentication implemented?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/adapter/config/JwtTokenFilter.java",
            "backend/src/main/java/ch/xxx/trader/usecase/services/JwtTokenService.java",
            "backend/src/main/java/ch/xxx/trader/domain/common/JwtUtils.java",
            "backend/src/main/java/ch/xxx/trader/adapter/config/WebSecurityConfig.java",
            "backend/src/main/java/ch/xxx/trader/usecase/services/MyAuthenticationProvider.java",
        ],
    ),
    Case(
        name="kafka_events",
        question="How does the application produce and consume Kafka events?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/adapter/config/KafkaConfig.java",
            "backend/src/main/java/ch/xxx/trader/adapter/events/EventProducer.java",
            "backend/src/main/java/ch/xxx/trader/adapter/events/EventConsumer.java",
            "backend/src/main/java/ch/xxx/trader/adapter/events/KafkaStreams.java",
            "backend/src/main/java/ch/xxx/trader/domain/services/MyEventProducer.java",
        ],
    ),
    Case(
        name="mongodb_configuration",
        question="How is MongoDB configured and what client classes connect to the database?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/adapter/clients/MongoDbConfiguration.java",
            "backend/src/main/java/ch/xxx/trader/adapter/clients/MongoDbClient.java",
            "backend/src/main/java/ch/xxx/trader/adapter/config/SpringMongoConfig.java",
            "backend/src/main/java/ch/xxx/trader/domain/common/MongoUtils.java",
        ],
    ),
    Case(
        name="user_management",
        question="How does user login, registration and user management work?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/adapter/controller/MyUserController.java",
            "backend/src/main/java/ch/xxx/trader/usecase/services/MyUserServiceBean.java",
            "backend/src/main/java/ch/xxx/trader/domain/model/entity/MyUser.java",
            "backend/src/main/java/ch/xxx/trader/domain/services/MyUserService.java",
            "frontend/src/angular/src/app/overview/login/login.component.ts",
            "frontend/src/angular/src/app/services/myuser.service.ts",
        ],
    ),
    Case(
        name="scheduled_tasks",
        question="What scheduled tasks and cron jobs run in the background?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/adapter/cron/ScheduledTask.java",
            "backend/src/main/java/ch/xxx/trader/adapter/cron/PrepareDataTask.java",
            "backend/src/main/java/ch/xxx/trader/adapter/cron/TaskStarter.java",
            "backend/src/main/java/ch/xxx/trader/adapter/config/SchedulingConfig.java",
        ],
    ),
    Case(
        name="angular_routing",
        question="How is Angular client-side routing configured and what routes exist?",
        expected_files=[
            "frontend/src/angular/src/app/app-routing.ts",
            "frontend/src/angular/src/app/details/details.routes.ts",
            "frontend/src/angular/src/app/overview/overview.routes.ts",
            "frontend/src/angular/src/app/statistics/statistics.routes.ts",
            "frontend/src/angular/src/app/orderbooks/orderbooks.routes.ts",
        ],
    ),
    Case(
        name="statistics",
        question="How are trading statistics calculated and displayed in the UI?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/usecase/services/StatisticService.java",
            "backend/src/main/java/ch/xxx/trader/adapter/controller/StatisticsController.java",
            "frontend/src/angular/src/app/statistics/statistics.component.ts",
            "frontend/src/angular/src/app/services/statistic.service.ts",
            "frontend/src/angular/src/app/statistics/statistic-details/statistic-details.component.ts",
        ],
    ),
    Case(
        name="exception_handling",
        question="How are exceptions and authentication errors handled globally?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/adapter/config/GlobalExceptionHandler.java",
            "backend/src/main/java/ch/xxx/trader/adapter/config/ExceptionLoggingFilter.java",
            "backend/src/main/java/ch/xxx/trader/domain/exceptions/AuthenticationException.java",
            "backend/src/main/java/ch/xxx/trader/domain/exceptions/JwtTokenValidationException.java",
        ],
    ),
    Case(
        name="quote_data_model",
        question="What is the data model for cryptocurrency price quotes and how are they stored?",
        expected_files=[
            "backend/src/main/java/ch/xxx/trader/domain/model/entity/Quote.java",
            "backend/src/main/java/ch/xxx/trader/domain/model/entity/QuoteBf.java",
            "backend/src/main/java/ch/xxx/trader/domain/model/entity/QuoteBs.java",
            "backend/src/main/java/ch/xxx/trader/domain/model/entity/QuoteCb.java",
            "backend/src/main/java/ch/xxx/trader/domain/model/entity/QuoteIb.java",
        ],
    ),
    Case(
        name="angular_exchange_services",
        question="How do the Angular frontend services call the backend exchange APIs?",
        expected_files=[
            "frontend/src/angular/src/app/services/bitfinex.service.ts",
            "frontend/src/angular/src/app/services/bitstamp.service.ts",
            "frontend/src/angular/src/app/services/coinbase.service.ts",
            "frontend/src/angular/src/app/services/itbit.service.ts",
        ],
    ),
]

# ---------------------------------------------------------------------------
# Aggregate thresholds
# ---------------------------------------------------------------------------

THRESHOLD_MEAN_PRECISION_AT_5 = 0.35
THRESHOLD_MEAN_RECALL_AT_10   = 0.50
THRESHOLD_MEAN_MRR            = 0.40

# ---------------------------------------------------------------------------
# Metric computation
# ---------------------------------------------------------------------------

def precision_at_k(retrieved_sources: list[str], expected: set[str], k: int) -> float:
    """Fraction of top-k retrieved chunks whose source is in the expected set."""
    top = retrieved_sources[:k]
    if not top:
        return 0.0
    hits = sum(1 for s in top if s in expected)
    return hits / len(top)


def recall_at_k(retrieved_sources: list[str], expected: set[str], k: int) -> float:
    """Fraction of expected files that appear at least once in the top-k chunks."""
    if not expected:
        return 1.0
    top = set(retrieved_sources[:k])
    found = sum(1 for f in expected if f in top)
    return found / len(expected)


def mrr(retrieved_sources: list[str], expected: set[str]) -> float:
    """Reciprocal rank of the first retrieved chunk whose source is in the expected set."""
    for rank, source in enumerate(retrieved_sources, start=1):
        if source in expected:
            return 1.0 / rank
    return 0.0


def run_case(case: Case, indexed_app: dict, top_k: int = 10) -> dict:
    """Run a single ground-truth case and return computed metrics."""
    from querying.query_engine import run_query
    logs = []
    result = run_query(
        bug_text=case.question,
        index_dir=indexed_app["index_dir"],
        top_k=top_k,
        log=logs.append,
    )
    sources = [m.get("source", "") for m in result.get("metas", [])]
    expected = set(case.expected_files)
    return {
        "case": case,
        "sources": sources,
        "answer": result.get("answer", ""),
        "p@5":  precision_at_k(sources, expected, 5),
        "r@5":  recall_at_k(sources, expected, 5),
        "r@10": recall_at_k(sources, expected, 10),
        "mrr":  mrr(sources, expected),
        "logs": logs,
    }

# ---------------------------------------------------------------------------
# Session-level results cache so each case runs only once
# ---------------------------------------------------------------------------

_results_cache: dict[str, dict] = {}

@pytest.fixture(scope="session", autouse=True)
def eval_results(indexed_app):
    """Run all ground-truth cases once and cache results for the session."""
    for case in GROUND_TRUTH:
        _results_cache[case.name] = run_case(case, indexed_app, top_k=10)
    return _results_cache


def _get(name: str) -> dict:
    return _results_cache[name]

# ---------------------------------------------------------------------------
# Per-query recall floor tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GROUND_TRUTH, ids=lambda c: c.name)
def test_per_query_recall_at_10(case, eval_results):
    """Each query must achieve its per-query recall@10 floor."""
    r = _get(case.name)
    score = r["r@10"]
    assert score >= case.min_recall_at_10, (
        f"[{case.name}] recall@10 = {score:.2f}, threshold = {case.min_recall_at_10:.2f}\n"
        f"Expected files: {case.expected_files}\n"
        f"Retrieved sources: {r['sources']}"
    )

# ---------------------------------------------------------------------------
# Per-query answer presence
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GROUND_TRUTH, ids=lambda c: c.name)
def test_per_query_answer_non_empty(case, eval_results):
    """Every query must produce a non-empty LLM answer."""
    r = _get(case.name)
    assert r["answer"].strip(), f"[{case.name}] LLM returned an empty answer."

# ---------------------------------------------------------------------------
# Aggregate threshold tests
# ---------------------------------------------------------------------------

def test_aggregate_mean_precision_at_5(eval_results):
    scores = [_get(c.name)["p@5"] for c in GROUND_TRUTH]
    mean = sum(scores) / len(scores)
    detail = "\n".join(
        f"  {c.name:<30} p@5={_get(c.name)['p@5']:.2f}"
        for c in GROUND_TRUTH
    )
    assert mean >= THRESHOLD_MEAN_PRECISION_AT_5, (
        f"Mean precision@5 = {mean:.3f}, threshold = {THRESHOLD_MEAN_PRECISION_AT_5}\n{detail}"
    )


def test_aggregate_mean_recall_at_10(eval_results):
    scores = [_get(c.name)["r@10"] for c in GROUND_TRUTH]
    mean = sum(scores) / len(scores)
    detail = "\n".join(
        f"  {c.name:<30} r@10={_get(c.name)['r@10']:.2f}"
        for c in GROUND_TRUTH
    )
    assert mean >= THRESHOLD_MEAN_RECALL_AT_10, (
        f"Mean recall@10 = {mean:.3f}, threshold = {THRESHOLD_MEAN_RECALL_AT_10}\n{detail}"
    )


def test_aggregate_mean_mrr(eval_results):
    scores = [_get(c.name)["mrr"] for c in GROUND_TRUTH]
    mean = sum(scores) / len(scores)
    detail = "\n".join(
        f"  {c.name:<30} mrr={_get(c.name)['mrr']:.2f}"
        for c in GROUND_TRUTH
    )
    assert mean >= THRESHOLD_MEAN_MRR, (
        f"Mean MRR = {mean:.3f}, threshold = {THRESHOLD_MEAN_MRR}\n{detail}"
    )


# ---------------------------------------------------------------------------
# Summary report (always printed, even when tests pass)
# ---------------------------------------------------------------------------

def test_print_semantic_eval_report(eval_results):
    """Print a full per-query breakdown. Always passes — for visibility."""
    header = f"\n{'Query':<30} {'p@5':>5} {'r@5':>5} {'r@10':>6} {'MRR':>5}"
    rows = []
    p5s, r10s, mrrs = [], [], []
    for case in GROUND_TRUTH:
        r = _get(case.name)
        p5, r10, m = r["p@5"], r["r@10"], r["mrr"]
        p5s.append(p5);  r10s.append(r10);  mrrs.append(m)
        rows.append(f"  {case.name:<30} {p5:>5.2f} {r['r@5']:>5.2f} {r10:>6.2f} {m:>5.2f}")

    mean_p5  = sum(p5s)  / len(p5s)
    mean_r10 = sum(r10s) / len(r10s)
    mean_mrr = sum(mrrs) / len(mrrs)

    sep = "-" * 58
    report = (
        "\n\n=== Semantic Retrieval Evaluation Report ===\n"
        + header + "\n" + sep + "\n"
        + "\n".join(rows) + "\n" + sep + "\n"
        + f"  {'MEAN':<30} {mean_p5:>5.2f} {'':>5} {mean_r10:>6.2f} {mean_mrr:>5.2f}\n"
        + f"\n  Thresholds:  p@5 >= {THRESHOLD_MEAN_PRECISION_AT_5}  "
        + f"r@10 >= {THRESHOLD_MEAN_RECALL_AT_10}  MRR >= {THRESHOLD_MEAN_MRR}\n"
        + "=" * 46
    )
    print(report)
    # This test always passes — it's for the report output only
