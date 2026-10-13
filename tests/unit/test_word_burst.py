"""Independent objective oracle and invalid-domain proof for the detector."""

import itertools
import math
from decimal import Decimal, localcontext

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.word_burst import detect_bursts, sparse_gain_cannot_burst


@st.composite
def series(draw: st.DrawFn) -> tuple[list[int], list[int]]:
    exposure = draw(st.lists(st.integers(0, 12), max_size=6))
    counts = [draw(st.integers(0, n)) for n in exposure]
    return counts, exposure


def oracle(counts: list[int], exposure: list[int], s: float, gamma: float, maximum: int) -> float:
    """Enumerate every path using direct negative log likelihood and transitions."""
    pairs = [(r, n) for r, n in zip(counts, exposure, strict=True) if n]
    relevant, total = sum(counts), sum(exposure)
    if not total or relevant in (0, total):
        return 0.0
    base = relevant / total
    probabilities = [base * s**k for k in range(maximum) if base * s**k < 1]
    penalty = gamma * math.log(len(pairs))
    baseline = sum(-r * math.log(base) - (n - r) * math.log(1 - base) for r, n in pairs)
    costs = []
    for path in itertools.product(range(len(probabilities)), repeat=len(pairs)):
        previous, cost = 0, 0.0
        for level, (r, n) in zip(path, pairs, strict=True):
            p = probabilities[level]
            cost += -r * math.log(p) - (n - r) * math.log(1 - p)
            cost += max(0, level - previous) * penalty
            previous = level
        costs.append(cost - baseline)
    return min(costs)


@given(series(), st.sampled_from([1.125, 1.5, 2.0, 3.0]), st.floats(0, 10), st.integers(1, 3))
@settings(max_examples=1000, deadline=None)
def test_decoder_matches_global_exhaustive_objective(data, s, gamma, maximum):
    """A greedy/local transition bug changes the globally optimal objective."""
    counts, exposure = data
    result = detect_bursts(counts, exposure, s=s, gamma=gamma, max_states=maximum)
    assert result.objective == pytest.approx(
        oracle(counts, exposure, s, gamma, maximum), abs=2e-12, rel=0
    )
    if sum(counts) not in (0, sum(exposure)):
        base = sum(counts) / sum(exposure)
        previous = 0
        costs = []
        for r, n, state in zip(counts, exposure, result.states, strict=True):
            if not n:
                assert state is None
                continue
            assert state is not None
            p = base * s**state
            costs.append(-r * math.log(p) - (n - r) * math.log(1 - p))
            costs.append(r * math.log(base) + (n - r) * math.log(1 - base))
            costs.append(max(0, state - previous) * gamma * math.log(sum(n > 0 for n in exposure)))
            previous = state
        assert math.fsum(costs) == pytest.approx(result.objective, abs=2e-12, rel=0)
    covered = {i for interval in result.intervals for i in range(interval.start, interval.end + 1)}
    assert {i for i, state in enumerate(result.states) if state} == {
        i for i in covered if exposure[i]
    }


def test_near_one_nonconstant_series_matches_high_precision_bin_costs():
    counts, exposure = [2] * 4 + [3] * 4, [9] * 8
    s = 1.0000000000000002
    with localcontext() as context:
        context.prec = 80
        base = Decimal.from_float(sum(counts) / sum(exposure))
        elevated = Decimal.from_float(float(base) * s)
        costs = [
            r * (base / elevated).ln() + (n - r) * ((1 - base) / (1 - elevated)).ln()
            for r, n in zip(counts, exposure, strict=True)
        ]
        expected_states = tuple(int(cost < 0) for cost in costs)
        expected_objective = float(sum(min(Decimal(0), cost) for cost in costs))
    result = detect_bursts(counts, exposure, s=s, gamma=0)
    assert result.states == expected_states == (0, 0, 0, 0, 1, 1, 1, 1)
    assert result.objective == pytest.approx(expected_objective, rel=1e-12, abs=0)
    assert [
        (interval.start, interval.end, interval.left_censored) for interval in result.intervals
    ] == [(4, 7, False)]


@given(
    series(), st.floats(1.0000000000000002, 1_000_000), st.floats(0, 1_000_000), st.integers(1, 16)
)
@settings(max_examples=1000, deadline=None)
def test_gain_pruning_never_discards_a_beneficial_path(data, s, gamma, maximum):
    """Every claimed prune has the same baseline optimum as full decoding."""
    counts, exposure = data
    if sparse_gain_cannot_burst(
        {i: r for i, r in enumerate(counts) if r}, exposure, s=s, gamma=gamma, max_states=maximum
    ):
        assert detect_bursts(counts, exposure, s=s, gamma=gamma, max_states=maximum).objective == 0


@given(series())
@settings(max_examples=300, deadline=None)
def test_missing_exposure_is_unobserved(data):
    """Adding an empty week cannot change the observed-state sequence."""
    r, n = data
    original = detect_bursts(r, n)
    expanded = detect_bursts([0] + r + [0], [0] + n + [0])
    assert expanded.states[1:-1] == original.states


@pytest.mark.parametrize(
    "counts,exposure",
    [([True], [1]), ([-1], [1]), ([2], [1]), ([0], []), ([1], [1.0]), ([2**54], [2**54])],
)
def test_invalid_count_domains_are_rejected(counts, exposure):
    with pytest.raises(ValueError):
        detect_bursts(counts, exposure)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"s": 1},
        {"s": float("nan")},
        {"gamma": -1},
        {"gamma": float("inf")},
        {"max_states": True},
        {"max_states": 17},
    ],
)
def test_invalid_parameter_domains_are_rejected(kwargs):
    with pytest.raises(ValueError):
        detect_bursts([0, 1], [2, 2], **kwargs)


def test_known_episode_preserves_gap_and_boundaries():
    result = detect_bursts([0, 0, 8, 0, 8, 0], [10, 10, 10, 0, 10, 10])
    assert result.states == (0, 0, 1, None, 1, 0)
    assert [(i.start, i.end, i.gaps, i.open) for i in result.intervals] == [(2, 4, (3,), False)]


def test_large_iterative_series():
    result = detect_bursts([0] * 100_000 + [5] * 100_000, [10] * 200_000)
    assert len(result.states) == 200_000
    assert result.intervals[0].start == 100_000


@pytest.mark.parametrize("r,n,s", [(1, 3, 1.00000001), (2**52, 2**53, 1.000000000001)])
def test_constant_prevalence_is_never_a_burst(r, n, s):
    result = detect_bursts([r] * 5, [n] * 5, s=s, gamma=0, max_states=16)
    assert result.states == (0,) * 5


def test_huge_invalid_integer_parameters_are_rejected():
    with pytest.raises(ValueError):
        detect_bursts([1], [3], s=10**1000)


@given(
    st.integers(1, 2**40),
    st.lists(st.integers(0, 8192), max_size=20),
    st.floats(1.0000000000000002, 1_000_000),
    st.integers(1, 16),
)
@settings(max_examples=1000, deadline=None)
def test_constant_proportions_abstain_across_gaps_and_state_limits(unit, multipliers, s, maximum):
    exposure = [unit * m for m in multipliers]
    counts = [(unit // 2) * m for m in multipliers]
    result = detect_bursts(counts, exposure, s=s, gamma=0, max_states=maximum)
    assert result.states == tuple(0 if n else None for n in exposure)
