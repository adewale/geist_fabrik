"""Certified decisions preserve canonical scores; reductions bound intermediate work.

Canonical cosine has its independent scalar oracle in test_property_embeddings.
Here the distinct contract is exact agreement of optimized decision/reduction
paths with that canonical API, including adjacent representable thresholds.
"""

import math
from decimal import Decimal, localcontext
from unittest.mock import patch

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.extra.numpy import arrays

from geistfabrik.vector_math import SimilarityWork, UnitRows

finite = st.floats(allow_nan=False, allow_infinity=False, width=64)


@st.composite
def populations(draw):
    # Keep scalar domains whole; cap only materialized shapes/work.
    dimension = min(draw(st.integers(min_value=0)), 64)
    left_count = min(draw(st.integers(min_value=0)), 7)
    right_count = min(draw(st.integers(min_value=0)), 7)
    left = draw(arrays(np.float64, (left_count, dimension), elements=finite))
    right = draw(arrays(np.float64, (right_count, dimension), elements=finite))
    if left_count and right_count and draw(st.booleans()):
        right = right.copy()
        right[0] = left[0]
    return UnitRows(left), UnitRows(right)


def threshold_near(data, scores):
    value = data.draw(finite)
    if scores.size and data.draw(st.booleans()):
        value = float(scores.flat[data.draw(st.integers(0, scores.size - 1))])
        value = float(np.nextafter(value, data.draw(st.sampled_from([-np.inf, np.inf]))))
    return value


@settings(max_examples=100, deadline=None)
@given(
    pair=populations(),
    data=st.data(),
    inclusive=st.booleans(),
    budget=st.sampled_from([64, 256, 1024 * 1024]),
)
def test_certified_thresholds_equal_canonical(pair, data, inclusive, budget):
    left, right = pair
    scores = left.cosine(right)
    threshold = threshold_near(data, scores)
    expected = scores >= threshold if inclusive else scores > threshold
    with patch("geistfabrik.vector_math.SCORE_BLOCK_BYTES", budget):
        assert np.array_equal(left.compare(right, threshold, inclusive=inclusive), expected)


@settings(max_examples=80, deadline=None)
@given(pair=populations(), data=st.data())
def test_any_matches_equal_canonical(pair, data):
    left, right = pair
    scores = left.cosine(right)
    threshold = threshold_near(data, scores)
    assert np.array_equal(left.any_matches(right, threshold), (scores >= threshold).any(axis=1))


@settings(max_examples=80, deadline=None)
@given(
    pair=populations(),
    count=st.integers(),
    budget=st.sampled_from([64, 256, 1024 * 1024]),
)
def test_topk_is_exact_and_stable(pair, count, budget):
    peers, queries = pair
    count = min(count, len(peers) + 1)
    scores = queries.cosine(peers)
    expected = [
        [(int(i), float(row[i])) for i in np.argsort(-row, kind="stable")[: max(0, count)]]
        for row in scores
    ]
    with patch("geistfabrik.vector_math.SCORE_BLOCK_BYTES", budget):
        assert peers.nearest(queries, count) == expected
        indices = peers.nearest_indices(queries, count)
        assert indices.shape == (len(queries), min(max(0, count), len(peers)))
        assert indices.tolist() == [[i for i, _score in row] for row in expected]


@settings(max_examples=80, deadline=None)
@given(pair=populations())
def test_paired_scores_equal_canonical_diagonal(pair):
    left, right = pair
    count = min(len(left), len(right))
    left, right = left.take(list(range(count))), right.take(list(range(count)))
    assert np.array_equal(left.paired(right), np.diag(left.cosine(right)))


@settings(max_examples=80, deadline=None)
@given(pair=populations(), data=st.data(), inclusive=st.booleans())
def test_streamed_pairs_equal_canonical_row_order(pair, data, inclusive):
    left, _right = pair
    scores = left.cosine(left)
    threshold = threshold_near(data, scores)
    expected = [
        (i, j)
        for i in range(len(left))
        for j in range(i + 1, len(left))
        if (scores[i, j] >= threshold if inclusive else scores[i, j] > threshold)
    ]
    assert list(left.matching_pairs(threshold, inclusive=inclusive)) == expected


@settings(max_examples=80, deadline=None)
@given(
    pair=populations(),
    data=st.data(),
    inclusive=st.booleans(),
    budget=st.sampled_from([64, 256, 1024 * 1024]),
)
def test_scored_matching_pairs_equal_canonical(pair, data, inclusive, budget):
    left, _right = pair
    scores = left.cosine(left)
    threshold = threshold_near(data, scores)
    expected = [
        (i, j, float(scores[i, j]))
        for i in range(len(left))
        for j in range(i + 1, len(left))
        if (scores[i, j] >= threshold if inclusive else scores[i, j] > threshold)
    ]
    with patch("geistfabrik.vector_math.SCORE_BLOCK_BYTES", budget):
        assert list(left.scored_matching_pairs(threshold, inclusive=inclusive)) == expected


@settings(max_examples=80, deadline=None)
@given(pair=populations(), within=st.booleans())
def test_streamed_mean_equals_canonical_fsum(pair, within):
    left, right = pair
    scores = np.clip(left.cosine(left if within else right), 0, 1)
    values = [
        float(scores[i, j])
        for i in range(len(left))
        for j in range(i + 1 if within else 0, scores.shape[1])
    ]
    expected = math.fsum(values) / len(values) if values else 0.0
    assert left.mean_similarity(None if within else right) == expected


@settings(max_examples=100, deadline=None)
@given(pair=populations(), within=st.booleans(), inclusive=st.booleans(), data=st.data())
def test_mean_decisions_equal_canonical_mean(pair, within, inclusive, data):
    left, right = pair
    peer = None if within else right
    value = left.mean_similarity(peer)
    threshold = data.draw(
        st.one_of(
            finite,
            st.sampled_from(
                [value, math.nextafter(value, -math.inf), math.nextafter(value, math.inf)]
            ),
        )
    )
    expected = value >= threshold if inclusive else value > threshold
    assert left.mean_compare(threshold, peer, inclusive=inclusive) == expected


@settings(max_examples=50, deadline=None)
@given(pair=populations())
def test_score_enclosure_contains_independent_exact_dot(pair):
    left, right = pair
    estimate = left._estimate(right)
    # Exact arithmetic on the already prepared binary64 inputs: this proof
    # owns the enclosure, separately from normalization/scalar cosine proofs.
    with localcontext() as context:
        context.prec = 2300
        for i, a in enumerate(left.values):
            for j, b in enumerate(right.values):
                exact = sum(
                    (Decimal(float(x)) * Decimal(float(y)) for x, y in zip(a, b)), Decimal(0)
                )
                exact = max(Decimal(-1), min(Decimal(1), exact))
                error = abs(Decimal(float(estimate[i, j])) - exact)
                assert error <= Decimal(left.score_error)


@pytest.mark.parametrize("method", ["mean_similarity", "mean_compare"])
def test_wide_mean_respects_score_tile_budget(monkeypatch, method):
    import geistfabrik.vector_math as vm

    monkeypatch.setattr(vm, "SCORE_BLOCK_BYTES", 256)
    left, right = UnitRows(np.zeros((1, 0))), UnitRows(np.zeros((257, 0)))
    sizes = []
    original = UnitRows.cosine if method == "mean_similarity" else UnitRows._estimate

    def record(self, other, **kwargs):
        result = original(self, other, **kwargs)
        sizes.append(result.nbytes)
        return result

    monkeypatch.setattr(UnitRows, "cosine" if method == "mean_similarity" else "_estimate", record)
    if method == "mean_similarity":
        assert left.mean_similarity(right) == 0
    else:
        assert not left.mean_compare(0.5, right)
    assert sizes and max(sizes) <= 256


def test_tied_topk_refinement_is_bounded_by_dimension(monkeypatch):
    import geistfabrik.vector_math as vm

    monkeypatch.setattr(vm, "SCORE_BLOCK_BYTES", 4096)
    raw = np.zeros((257, 16))
    raw[:, :2] = [0.8, 0.6]
    peers = UnitRows(raw)
    query = UnitRows(np.eye(1, 16))
    allocations = []
    original = np.einsum

    def record(expression, *operands, **kwargs):
        if expression == "ij,ij->i":
            allocations.append(sum(operand.nbytes for operand in operands))
        return original(expression, *operands, **kwargs)

    monkeypatch.setattr(np, "einsum", record)
    assert peers.nearest(query, 3) == [[(0, 0.8), (1, 0.8), (2, 0.8)]]
    assert allocations and max(allocations) <= 4096


def test_ambiguous_decisions_bound_prepared_refinement_copies(monkeypatch):
    import geistfabrik.vector_math as vm

    monkeypatch.setattr(vm, "SCORE_BLOCK_BYTES", 4096)
    raw = np.zeros((40, 16))
    raw[:, 0] = 1
    left = UnitRows(raw)
    raw[:, :2] = [0.8, 0.6]
    right = UnitRows(raw)
    expected = left.cosine(right) >= 0.8
    allocations = []
    original = np.einsum

    def record(expression, *operands, **kwargs):
        if expression == "ij,ij->i":
            allocations.append(sum(operand.nbytes for operand in operands))
        return original(expression, *operands, **kwargs)

    monkeypatch.setattr(np, "einsum", record)
    work = SimilarityWork()
    assert np.array_equal(left.compare(right, 0.8, work=work), expected)
    assert max(allocations, default=0) <= 4096
    assert work.refined_pairs == 1600


@pytest.mark.parametrize("budget", [64, 256, 1024 * 1024])
def test_exact_topk_spans_query_batch_boundary(monkeypatch, budget):
    import geistfabrik.vector_math as vm

    monkeypatch.setattr(vm, "SCORE_BLOCK_BYTES", budget)
    raw = np.tile(np.eye(3), (45, 1))
    peers = UnitRows(raw)
    queries = UnitRows(raw[:129])
    scores = queries.cosine(peers)
    expected = [
        [(int(i), float(row[i])) for i in np.argsort(-row, kind="stable")[:3]] for row in scores
    ]
    sizes = []
    original = UnitRows._estimate

    def record(self, other, **kwargs):
        result = original(self, other, **kwargs)
        sizes.append(result.nbytes)
        return result

    monkeypatch.setattr(UnitRows, "_estimate", record)
    assert peers.nearest(queries, 3) == expected
    assert peers.nearest_indices(queries, 3).tolist() == [
        [i for i, _score in row] for row in expected
    ]
    assert sizes and max(sizes) <= budget


@pytest.mark.parametrize("threshold", [True, float("nan"), float("inf"), -float("inf")])
@pytest.mark.parametrize(
    "method", ["compare", "any_matches", "matching_pairs", "scored_matching_pairs", "mean_compare"]
)
def test_decision_thresholds_reject_invalid_values(threshold, method):
    rows = UnitRows(np.eye(2))
    with pytest.raises(ValueError, match="finite"):
        if method in {"compare", "any_matches"}:
            getattr(rows, method)(rows, threshold)
        elif method in {"matching_pairs", "scored_matching_pairs"}:
            list(getattr(rows, method)(threshold))
        else:
            rows.mean_compare(threshold)


@pytest.mark.parametrize("indices", [[True], [-1], [2], [0.5], [10**100]])
def test_prepared_selection_rejects_invalid_indices(indices):
    with pytest.raises(ValueError, match="indices"):
        UnitRows(np.eye(2)).take(indices)


def test_digest_collision_never_establishes_direction_identity(monkeypatch):
    import geistfabrik.vector_math as vm

    monkeypatch.setattr(vm, "hash", lambda _value: 0, raising=False)
    left = UnitRows(np.array([[1.0, 0], [0, 1.0]]))
    right = UnitRows(np.array([[0.0, 1], [1, 0.0]]))
    assert np.array_equal(left.cosine(right), [[0.0, 1.0], [1.0, 0.0]])
    assert left.paired(right).tolist() == [0.0, 0.0]
    assert np.array_equal(left.compare(right, 1), [[False, True], [True, False]])


@pytest.mark.parametrize("inclusive", [False, True])
@pytest.mark.parametrize("threshold", [0.0, 1.0])
def test_exact_identity_and_zero_decisions_need_no_numeric_kernel(
    inclusive, threshold, monkeypatch
):
    rows = UnitRows(np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 0.0]]))
    work = SimilarityWork()
    canonical = rows.cosine(rows)
    expected = canonical >= threshold if inclusive else canonical > threshold

    def forbidden(*args, **kwargs):
        raise AssertionError("exact identity/zero work must bypass numeric kernels")

    monkeypatch.setattr(np, "matmul", forbidden)
    monkeypatch.setattr(np, "einsum", forbidden)
    assert np.array_equal(rows.compare(rows, threshold, inclusive=inclusive, work=work), expected)
    assert work.fast_pairs == work.refined_pairs == 0
    work = SimilarityWork()
    assert rows.nearest_indices(rows, 2, work=work).tolist() == [[0, 1], [1, 2], [1, 2]]
    assert work.fast_pairs == work.refined_pairs == 0


@pytest.mark.parametrize("method", ["nearest", "nearest_indices"])
@pytest.mark.parametrize("count", [True, 1.5, float("nan"), "2"])
def test_topk_rejects_non_integer_counts_even_for_empty_queries(method, count):
    rows = UnitRows(np.empty((0, 2)))
    with pytest.raises(ValueError, match="integer"):
        getattr(rows, method)(rows, count)
