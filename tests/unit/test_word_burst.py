"""Independent objective oracle and invalid-domain proof for the detector."""

import itertools
import math
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.word_burst import BurstModel, detect_bursts, sparse_gain_cannot_burst


@st.composite
def series(draw: st.DrawFn) -> tuple[list[int], list[int]]:
    exposure = draw(st.lists(st.integers(0, 12), max_size=6))
    counts = [draw(st.integers(0, n)) for n in exposure]
    return counts, exposure


def oracle(
    counts: list[int],
    exposure: list[int],
    s: float,
    gamma: float,
    maximum: int,
    direction: str = "rising",
) -> float:
    """Enumerate every path using direct negative log likelihood and transitions."""
    pairs = [(r, n) for r, n in zip(counts, exposure, strict=True) if n]
    relevant, total = sum(counts), sum(exposure)
    if not total or relevant in (0, total):
        return 0.0
    base = relevant / total
    factor = s if direction == "rising" else 1 / s
    probabilities = [base * factor**k for k in range(maximum) if 0 < base * factor**k < 1]
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


@given(
    data=series(),
    s=st.sampled_from([1.125, 1.5, 2.0, 3.0]),
    gamma=st.floats(0, 10),
    maximum=st.integers(1, 3),
)
@settings(max_examples=1000, deadline=None)
@pytest.mark.parametrize("direction", ["rising", "declining"])
def test_decoder_matches_global_exhaustive_objective(data, s, gamma, maximum, direction):
    """A greedy/local transition bug changes the globally optimal objective."""
    counts, exposure = data
    result = detect_bursts(
        counts, exposure, s=s, gamma=gamma, max_states=maximum, direction=direction
    )
    assert result.objective == pytest.approx(
        oracle(counts, exposure, s, gamma, maximum, direction), abs=2e-12, rel=0
    )
    model = BurstModel(exposure, s=s, gamma=gamma, max_states=maximum)
    sparse = {i: r for i, r in enumerate(counts) if r}
    assert model.detect_sparse(sparse, direction=direction) == result
    assert model.detect(counts, direction=direction) == result
    batch = model.detect_many([sparse, {}, sparse], direction=direction)
    assert batch[0] == batch[2] == result
    assert batch[1].states == tuple(0 if n else None for n in exposure)
    assert batch[1].objective == 0
    prepared = model.prepare(sparse)
    assert model.cannot_burst(prepared, direction=direction) == model.cannot_burst(
        sparse, direction=direction
    )
    sparse.clear()
    assert model.detect_sparse(prepared, direction=direction) == result
    assert model.detect_many([prepared], direction=direction) == [result]
    if sum(counts) not in (0, sum(exposure)):
        base = sum(counts) / sum(exposure)
        previous = 0
        costs = []
        for r, n, state in zip(counts, exposure, result.states, strict=True):
            if not n:
                assert state is None
                continue
            assert state is not None
            p = base * s ** (state if direction == "rising" else -state)
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
        base = Decimal(sum(counts)) / Decimal(sum(exposure))
        elevated = base * Decimal.from_float(s)
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


def test_large_summed_exposure_keeps_tiny_baseline_complement():
    counts, exposure = [0, 2**53, 2**53], [1, 2**53, 2**53]
    with localcontext() as context:
        context.prec = 80
        base = Decimal(sum(counts)) / Decimal(sum(exposure))
        # The representable alternative is 0.5; baseline failure mass must
        # survive even though floating-point sum(counts)/sum(exposure) is 1.
        expected = float(((1 - base) / Decimal("0.5")).ln())
    result = detect_bursts(counts, exposure, direction="declining", gamma=0)
    assert result.states == (1, 0, 0)
    assert result.objective == pytest.approx(expected, abs=0, rel=1e-14)
    assert not sparse_gain_cannot_burst(
        {1: 2**53, 2: 2**53}, exposure, direction="declining", gamma=0
    )


def test_near_one_rising_grid_retains_valid_complementary_probability():
    counts, exposure = [2**53, 2**53 - 5], [2**53, 2**53]
    s = math.nextafter(1.0, math.inf)
    with localcontext() as context:
        context.prec = 80
        base = Decimal(sum(counts)) / Decimal(sum(exposure))
        elevated = base * Decimal.from_float(s)
        expected = float(Decimal(counts[0]) * (base / elevated).ln())
    result = detect_bursts(counts, exposure, s=s, gamma=0)
    assert result.states == (1, 0)
    assert result.objective == pytest.approx(expected, abs=0, rel=1e-14)
    assert not sparse_gain_cannot_burst(dict(enumerate(counts)), exposure, s=s, gamma=0)


def test_near_one_large_coefficient_products_keep_sub_ulp_gain():
    counts = [8463726215890284, 8463726215890282]
    exposure = [2**53, 2**53]
    s = math.nextafter(1.0, math.inf)
    with localcontext() as context:
        context.prec = 80
        base = Decimal(sum(counts)) / Decimal(sum(exposure))
        elevated = base * Decimal.from_float(s)
        expected = float(
            Decimal(counts[0]) * (base / elevated).ln()
            + Decimal(exposure[0] - counts[0]) * ((1 - base) / (1 - elevated)).ln()
        )
    model = BurstModel(exposure, s=s, gamma=0)
    result = model.detect(counts)
    assert result.states == (1, 0)
    assert result.objective == pytest.approx(expected, abs=0, rel=1e-13)
    assert model.detect_many([dict(enumerate(counts))]) == [result]


@given(st.integers(1, 2**53), st.integers(1, 12), st.integers(2, 8))
@settings(max_examples=250, deadline=None)
def test_declining_extreme_counts_agree_with_independent_decimal_likelihood(unit, missing, repeats):
    counts, exposure = [0] + [unit] * repeats, [missing] + [unit] * repeats
    with localcontext() as context:
        context.prec = 80
        base = Decimal(sum(counts)) / Decimal(sum(exposure))
        lower = base / 2
        expected = float(missing * ((1 - base) / (1 - lower)).ln())
    result = detect_bursts(counts, exposure, direction="declining", gamma=0)
    assert result.states == (1,) + (0,) * repeats
    assert result.objective == pytest.approx(expected, rel=1e-13, abs=0)


@given(
    data=series(),
    s=st.floats(1.0000000000000002, 1_000_000),
    gamma=st.floats(0, 1_000_000),
    maximum=st.integers(1, 16),
)
@settings(max_examples=1000, deadline=None)
@pytest.mark.parametrize("direction", ["rising", "declining"])
def test_gain_pruning_never_discards_a_beneficial_path(data, s, gamma, maximum, direction):
    """Every claimed prune has the same baseline optimum as full decoding."""
    counts, exposure = data
    if sparse_gain_cannot_burst(
        {i: r for i, r in enumerate(counts) if r},
        exposure,
        s=s,
        gamma=gamma,
        max_states=maximum,
        direction=direction,
    ):
        assert (
            detect_bursts(
                counts, exposure, s=s, gamma=gamma, max_states=maximum, direction=direction
            ).objective
            == 0
        )


def test_disappearance_has_a_declining_state_even_when_absence_is_already_common():
    result = detect_bursts([6] * 4 + [0] * 4, [10] * 8, direction="declining")
    assert result.states == (0, 0, 0, 0, 1, 1, 1, 1)
    assert [(i.start, i.end, i.open) for i in result.intervals] == [(4, 7, True)]


@pytest.mark.parametrize(
    "counts,states,objective",
    [
        ([542823286867086, 207776651027996], (0, 0), 0.0),
        ([5375475922601571, 1664885876232855], (1, 0), -0.5275703420874939),
    ],
)
def test_large_counts_preserve_transition_decisions_and_safe_pruning(counts, states, objective):
    model = BurstModel([2**53, 2**53])
    sparse = dict(enumerate(counts))
    for result in (
        model.detect(counts),
        model.detect_sparse(sparse),
        model.detect_many([sparse])[0],
    ):
        assert result.states == states
        assert result.objective == pytest.approx(objective, rel=1e-12, abs=0)
    if objective < 0:
        assert not model.cannot_burst(sparse)


@given(
    rise_power=st.integers(1, 7),
    fall_power=st.integers(1, 7),
    maximum=st.integers(2, 16),
    gap=st.booleans(),
)
@settings(max_examples=100, deadline=None)
@pytest.mark.parametrize("direction", ["rising", "declining"])
def test_exact_likelihood_ties_keep_baseline(rise_power, fall_power, maximum, gap, direction):
    # -fall_power*ln(2**rise_power) + rise_power*ln(2**fall_power) is exactly zero.
    total, relevant = 2 ** (rise_power + fall_power) - 1, 2**fall_power - 1
    exposure = [rise_power + fall_power, total - rise_power - fall_power]
    counts = [fall_power, relevant - fall_power]
    s = 2**rise_power
    if direction == "declining":
        counts = [n - r for r, n in zip(counts, exposure, strict=True)]
        s = 2**fall_power
    if gap:
        counts.insert(1, 0)
        exposure.insert(1, 0)
    model = BurstModel(exposure, s=s, gamma=0, max_states=maximum)
    sparse = dict(enumerate(counts))
    for result in (
        model.detect(counts, direction=direction),
        model.detect_sparse(sparse, direction=direction),
        model.detect_many([sparse], direction=direction)[0],
    ):
        assert result.states == tuple(0 if n else None for n in exposure)
        assert result.objective == 0
        assert result.intervals == ()


def decimal_paths(counts, exposure, s, gamma, maximum, direction):
    """Independent short-series enumeration, without production grids/costs."""
    with localcontext() as context:
        context.prec = 180
        base = Fraction(sum(counts), sum(exposure))
        probabilities = [base]
        for level in range(1, maximum):
            p = base * Fraction(s) ** (level if direction == "rising" else -level)
            if not 0 < p < 1:
                break
            probabilities.append(p)
        emissions = []
        observed = [i for i, n in enumerate(exposure) if n]
        for i in observed:
            costs = []
            for p in probabilities:
                a, b = base / p, (1 - base) / (1 - p)
                costs.append(
                    Decimal(counts[i]) * (Decimal(a.numerator) / Decimal(a.denominator)).ln()
                    + Decimal(exposure[i] - counts[i])
                    * (Decimal(b.numerator) / Decimal(b.denominator)).ln()
                )
            emissions.append(costs)
        penalty = Decimal.from_float(float(gamma)) * Decimal(len(observed)).ln()
        paths = []
        for path in itertools.product(range(len(probabilities)), repeat=len(observed)):
            previous, cost = 0, Decimal(0)
            for state, costs in zip(path, emissions, strict=True):
                cost += costs[state] + max(0, state - previous) * penalty
                previous = state
            paths.append((cost, path))
        return sorted(paths)


@given(
    n=st.integers(1, 2**53),
    fraction=st.fractions(min_value=Fraction(0), max_value=Fraction(1), max_denominator=2**53),
    s=st.one_of(
        st.sampled_from([math.nextafter(1.0, math.inf), 1.00000002, 1.125, 2.0, 3.0, 1e6]),
        st.floats(min_value=math.nextafter(1.0, math.inf), max_value=1e6),
    ),
    gamma=st.floats(0, 1e6),
    neighbor=st.integers(-2, 2),
    side=st.sampled_from(["given", "below", "above"]),
    maximum=st.integers(1, 3),
    gap=st.booleans(),
)
@settings(max_examples=150, deadline=None)
@pytest.mark.parametrize("direction", ["rising", "declining"])
def test_decision_boundaries_match_independent_decimal_paths(
    n, fraction, s, gamma, neighbor, side, maximum, gap, direction
):
    relevant = min(2 * n - 1, max(1, int(2 * n * fraction)))
    first = min(n, relevant)
    with localcontext() as context:
        context.prec = 180
        base = Decimal(relevant) / Decimal(2 * n)
        p = base * Decimal.from_float(s) ** (1 if direction == "rising" else -1)
        if 0 < p < 1:
            a, b = (base / p).ln(), ((1 - base) / (1 - p)).ln()
            crossover = (n * b + Decimal.from_float(gamma) * Decimal(2).ln()) / (b - a)
            first = min(n, relevant, max(0, relevant - n, int(crossover) + neighbor))
            critical_gamma = -(first * a + (n - first) * b) / Decimal(2).ln()
            if side != "given" and 0 < critical_gamma < 1e6:
                gamma = math.nextafter(float(critical_gamma), 0.0 if side == "below" else math.inf)
    counts, exposure = [first, relevant - first], [n, n]
    if gap:
        counts.insert(1, 0)
        exposure.insert(1, 0)
    paths = decimal_paths(counts, exposure, s, gamma, maximum, direction)
    expected = float(paths[0][0])
    model = BurstModel(exposure, s=s, gamma=gamma, max_states=maximum)
    sparse = dict(enumerate(counts))
    for result in (
        model.detect(counts, direction=direction),
        model.detect_sparse(sparse, direction=direction),
        model.detect_many([sparse], direction=direction)[0],
    ):
        # 180-digit oracle log rounding times <=2**54 observations is <1e-150.
        assert result.objective == pytest.approx(expected, rel=1e-12, abs=1e-150)
        if len(paths) > 1 and paths[1][0] - paths[0][0] > Decimal("1e-150"):
            assert tuple(state for state in result.states if state is not None) == paths[0][1]
    if model.cannot_burst(sparse, direction=direction):
        assert expected >= -1e-150


@pytest.mark.parametrize("direction", ["falling", "", None, True])
def test_both_decoder_and_pruner_reject_unknown_directions(direction):
    with pytest.raises(ValueError, match="direction"):
        detect_bursts([1, 0], [2, 2], direction=direction)
    with pytest.raises(ValueError, match="direction"):
        sparse_gain_cannot_burst({0: 1}, [2, 2], direction=direction)
    model = BurstModel([2, 2])
    for operation in (
        lambda: model.detect([1, 0], direction=direction),
        lambda: model.detect_sparse({0: 1}, direction=direction),
        lambda: model.cannot_burst({0: 1}, direction=direction),
        lambda: model.detect_many([{0: 1}], direction=direction),
    ):
        with pytest.raises(ValueError, match="direction"):
            operation()


def test_prepared_counts_cannot_cross_exposure_models():
    original = BurstModel([2, 2])
    prepared = original.prepare({0: 1})
    foreign = BurstModel([2, 2], s=3)
    for operation in (
        lambda: foreign.prepare(prepared),
        lambda: foreign.cannot_burst(prepared),
        lambda: foreign.detect_sparse(prepared),
        lambda: foreign.detect_many([prepared]),
    ):
        with pytest.raises(ValueError, match="another exposure"):
            operation()


@pytest.mark.parametrize("counts", [{True: 1}, {-1: 0}, {2: 0}, {0: True}, {0: -1}, {0: 3}])
def test_compiled_sparse_surfaces_reject_malformed_counts(counts):
    model = BurstModel([2, 2])
    for operation in (model.detect_sparse, model.cannot_burst):
        with pytest.raises(ValueError):
            operation(counts)
    with pytest.raises(ValueError):
        model.detect_many([counts])


def test_batched_decoding_preserves_order_across_work_chunks():
    results = BurstModel([10] * 8).detect_many([{6: 8, 7: 8}] * 1024 + [{0: 8, 1: 8}])
    assert len(results) == 1025
    assert [(i.start, i.end) for i in results[0].intervals] == [(6, 7)]
    assert [(i.start, i.end) for i in results[-1].intervals] == [(0, 1)]


@given(series())
def test_compiled_exposure_owns_its_snapshot(data):
    counts, exposure = data
    model = BurstModel(exposure)
    expected = model.detect(counts)
    exposure.append(100)
    assert model.detect(counts) == expected


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
