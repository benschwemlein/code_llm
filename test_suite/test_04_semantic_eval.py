"""
Semantic retrieval evaluation — ground truth queries for the library-catalog-app corpus.

Metrics
-------
  Precision@5  : fraction of top-5 results that are expected files
  Recall@10    : fraction of expected files found in top-10 results
  MRR          : reciprocal rank of the first expected file hit

Thresholds calibrated to mxbai-embed-large + text_800 chunking.
"""

import pytest
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Ground truth cases — queries grounded in library-catalog-app source
# ---------------------------------------------------------------------------

@dataclass
class GroundTruthCase:
    name: str
    question: str
    expected_files: list[str] = field(default_factory=list)


GROUND_TRUTH: list[GroundTruthCase] = [
    GroundTruthCase(
        name="jwt_authentication",
        question=(
            "How is JWT authentication implemented? "
            "Where is the token validated and how is revocation handled?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/jwt/JwtService.java",
            "src/main/java/com/example/catalog/jwt/JwtAuthenticationFilter.java",
            "src/main/java/com/example/catalog/model/Token.java",
            "src/main/java/com/example/catalog/repo/TokenRepository.java",
        ],
    ),
    GroundTruthCase(
        name="checkout_borrow",
        question=(
            "How does a user check out and return a catalog item? "
            "Where is the borrow and checkin logic?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/controller/BorrowController.java",
            "src/main/java/com/example/catalog/service/CheckoutService.java",
            "src/main/java/com/example/catalog/model/Checkout.java",
        ],
    ),
    GroundTruthCase(
        name="catalog_item_crud",
        question=(
            "Where is catalog item data managed? "
            "How are items created, updated, and retrieved through the API?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/controller/CatalogItemController.java",
            "src/main/java/com/example/catalog/service/CatalogItemService.java",
            "src/main/java/com/example/catalog/model/CatalogItem.java",
        ],
    ),
    GroundTruthCase(
        name="user_registration",
        question=(
            "How does user registration work? "
            "Where is the register endpoint and what user data is persisted?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/controller/AuthenticationController.java",
            "src/main/java/com/example/catalog/service/AuthenticationService.java",
            "src/main/java/com/example/catalog/dto/RegisterRequest.java",
            "src/main/java/com/example/catalog/model/User.java",
        ],
    ),
    GroundTruthCase(
        name="spring_security",
        question=(
            "How is Spring Security configured? "
            "Which endpoints are publicly accessible versus require authentication?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/config/SecurityConfiguration.java",
            "src/main/java/com/example/catalog/config/ApplicationConfig.java",
            "src/main/java/com/example/catalog/jwt/JwtAuthenticationFilter.java",
        ],
    ),
    GroundTruthCase(
        name="role_permissions",
        question=(
            "How are user roles and permissions defined? "
            "What authorities does each role grant?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/model/Role.java",
            "src/main/java/com/example/catalog/model/Permission.java",
        ],
    ),
    GroundTruthCase(
        name="token_revocation",
        question=(
            "How are JWT tokens revoked when a user logs out? "
            "How does the system know a token is no longer valid?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/service/LogoutService.java",
            "src/main/java/com/example/catalog/service/AuthenticationService.java",
            "src/main/java/com/example/catalog/model/Token.java",
            "src/main/java/com/example/catalog/repo/TokenRepository.java",
        ],
    ),
    GroundTruthCase(
        name="catalog_identifiers",
        question=(
            "How are catalog item identifiers like ISBN or barcodes stored and "
            "associated with catalog items?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/model/CatalogId.java",
            "src/main/java/com/example/catalog/model/CatalogIdType.java",
            "src/main/java/com/example/catalog/controller/CatalogIdTypeController.java",
            "src/main/java/com/example/catalog/service/CatalogIdTypeService.java",
        ],
    ),
    GroundTruthCase(
        name="user_management",
        question=(
            "How are users retrieved and managed through the API? "
            "What user data is exposed in responses?"
        ),
        expected_files=[
            "src/main/java/com/example/catalog/controller/UserController.java",
            "src/main/java/com/example/catalog/service/UserService.java",
            "src/main/java/com/example/catalog/model/User.java",
            "src/main/java/com/example/catalog/dto/UserDTO.java",
        ],
    ),
    GroundTruthCase(
        name="angular_auth",
        question=(
            "How does the Angular frontend handle login and authentication state? "
            "Where is the JWT token stored and how is the current user tracked?"
        ),
        expected_files=[
            "catalog-ui/src/app/shared/services/auth.service.ts",
            "catalog-ui/src/app/auth/login/login.component.ts",
            "catalog-ui/src/app/app.component.ts",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Metric helpers (imported by test_05, test_06, test_09)
# ---------------------------------------------------------------------------

def precision_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    top_k = retrieved[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for s in top_k if any(e in s for e in expected))
    return hits / k


def recall_at_k(retrieved: list[str], expected: set[str], k: int) -> float:
    if not expected:
        return 1.0
    top_k = retrieved[:k]
    found = sum(1 for e in expected if any(e in r for r in top_k))
    return found / len(expected)


def mrr(retrieved: list[str], expected: set[str]) -> float:
    for i, source in enumerate(retrieved, start=1):
        if any(e in source for e in expected):
            return 1.0 / i
    return 0.0


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

PRECISION_AT_5_THRESHOLD = 0.35
RECALL_AT_10_THRESHOLD   = 0.50
MRR_THRESHOLD            = 0.40
PER_QUERY_RECALL_FLOOR   = 0.25


# ---------------------------------------------------------------------------
# Session fixture — index once, reuse for all queries
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def query_results(indexed_app) -> dict:
    """Run all ground-truth queries against the indexed app. Results cached for session."""
    from querying.query_engine import run_query

    results = {}
    for case in GROUND_TRUTH:
        result = run_query(
            bug_text=case.question,
            index_dir=indexed_app["index_dir"],
            top_k=10,
            log=lambda _: None,
        )
        results[case.name] = [m.get("source", "") for m in result.get("metas", [])]
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", GROUND_TRUTH, ids=[c.name for c in GROUND_TRUTH])
def test_recall_floor(case, query_results):
    """Every query must find at least one expected file in the top-10 results."""
    sources  = query_results[case.name]
    expected = set(case.expected_files)
    r10 = recall_at_k(sources, expected, 10)
    assert r10 >= PER_QUERY_RECALL_FLOOR, (
        f"{case.name}: recall@10 {r10:.2f} < floor {PER_QUERY_RECALL_FLOOR} — "
        f"expected one of {list(expected)[:2]} in top-10, got {sources[:5]}"
    )


def test_mean_precision_at_5(query_results):
    """Mean precision@5 across all queries must meet threshold."""
    scores = [
        precision_at_k(query_results[c.name], set(c.expected_files), 5)
        for c in GROUND_TRUTH
    ]
    mean = sum(scores) / len(scores)
    assert mean >= PRECISION_AT_5_THRESHOLD, (
        f"Mean P@5 {mean:.2f} < {PRECISION_AT_5_THRESHOLD}"
    )


def test_mean_recall_at_10(query_results):
    """Mean recall@10 across all queries must meet threshold."""
    scores = [
        recall_at_k(query_results[c.name], set(c.expected_files), 10)
        for c in GROUND_TRUTH
    ]
    mean = sum(scores) / len(scores)
    assert mean >= RECALL_AT_10_THRESHOLD, (
        f"Mean R@10 {mean:.2f} < {RECALL_AT_10_THRESHOLD}"
    )


def test_mean_mrr(query_results):
    """Mean MRR across all queries must meet threshold."""
    scores = [
        mrr(query_results[c.name], set(c.expected_files))
        for c in GROUND_TRUTH
    ]
    mean = sum(scores) / len(scores)
    assert mean >= MRR_THRESHOLD, (
        f"Mean MRR {mean:.2f} < {MRR_THRESHOLD}"
    )


def test_semantic_eval_report(query_results):
    """Print a per-query breakdown table. Always passes."""
    print("\n\n=== Semantic Retrieval Evaluation ===\n")
    print(f"{'Query':<30} {'P@5':>6} {'R@10':>6} {'MRR':>6}")
    print("-" * 52)
    p5s, r10s, mrrs = [], [], []
    for case in GROUND_TRUTH:
        sources  = query_results[case.name]
        expected = set(case.expected_files)
        p5  = precision_at_k(sources, expected, 5)
        r10 = recall_at_k(sources, expected, 10)
        m   = mrr(sources, expected)
        p5s.append(p5); r10s.append(r10); mrrs.append(m)
        print(f"  {case.name:<28} {p5:>6.2f} {r10:>6.2f} {m:>6.2f}")
    print("-" * 52)
    mean_p5  = sum(p5s)  / len(p5s)
    mean_r10 = sum(r10s) / len(r10s)
    mean_mrr = sum(mrrs) / len(mrrs)
    print(f"  {'MEAN':<28} {mean_p5:>6.2f} {mean_r10:>6.2f} {mean_mrr:>6.2f}")
    print(f"\n  Thresholds: P@5>={PRECISION_AT_5_THRESHOLD}  "
          f"R@10>={RECALL_AT_10_THRESHOLD}  MRR>={MRR_THRESHOLD}")
    print("=" * 40)
