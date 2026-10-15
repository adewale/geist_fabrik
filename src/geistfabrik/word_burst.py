"""Exact batched-binomial Kleinberg bursts (2002, section 4).

Costs omit the common binomial coefficient and subtract baseline emissions.
Zero-exposure bins are unobserved, not evidence of absence. Upward transitions
cost gamma * log(number of observed bins) per level; downward moves are free.
The initial state is zero. Scores are likelihood gains, never p-values.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, localcontext
from fractions import Fraction
from types import MappingProxyType

import numpy as np


@dataclass(frozen=True)
class BurstInterval:
    """Inclusive original-bin bounds of a maximal elevated episode."""

    start: int
    end: int
    level: int
    gain: float
    gaps: tuple[int, ...]
    left_censored: bool
    open: bool


@dataclass(frozen=True)
class BurstResult:
    """Decoded states, objective relative to baseline, and episodes."""

    states: tuple[int | None, ...]
    objective: float
    intervals: tuple[BurstInterval, ...]
    reason: str


def _parameters(s: float, gamma: float, max_states: int) -> None:
    if (
        isinstance(s, bool)
        or not isinstance(s, (int, float))
        or not 1 < s <= 1_000_000
        or not math.isfinite(s)
    ):
        raise ValueError("s must be finite in (1, 1000000]")
    if (
        isinstance(gamma, bool)
        or not isinstance(gamma, (int, float))
        or not 0 <= gamma <= 1_000_000
        or not math.isfinite(gamma)
    ):
        raise ValueError("gamma must be finite in [0, 1000000]")
    if isinstance(max_states, bool) or not isinstance(max_states, int) or not 1 <= max_states <= 16:
        raise ValueError("max_states must be an integer in [1, 16]")


def _count(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 2**53:
        raise ValueError("counts must be integers in [0, 2**53]")


def _direction(direction: str) -> None:
    if direction not in ("rising", "declining"):
        raise ValueError("direction must be rising or declining")


def _probabilities(
    relevant: int, total: int, s: float, maximum: int, direction: str
) -> list[tuple[float, float, float]]:
    # Exact, tiny state grid; carry both masses and the baseline difference.
    # float(p)==1 must not erase a valid complementary probability near zero.
    base = Fraction(relevant, total)
    probability = base
    multiplier = Fraction(s)
    probabilities = [(float(base), float(1 - base), 0.0)]
    for _ in range(1, maximum):
        candidate = probability * multiplier if direction == "rising" else probability / multiplier
        if not 0 < candidate < 1:
            break
        probabilities.append((float(candidate), float(1 - candidate), float(candidate - base)))
        probability = candidate
    return probabilities


def _emission(
    r: int,
    n: int,
    p: float,
    complement: float,
    delta: float,
    base: float,
    base_complement: float,
) -> float:
    if delta == 0:
        return 0.0
    # Independently computing the complementary baseline preserves tiny failure
    # mass even when relevant/total rounds to 1 after summing valid large bins.
    # Ratios near one lose their sign if rounded before taking a logarithm.
    # Far-apart probabilities use log directly to avoid log1p rounding to -1.
    positive = math.log1p(-delta / p) if p < 2 * base else math.log(base / p)
    negative = (
        math.log1p(delta / complement)
        if complement < 2 * base_complement
        else math.log(base_complement / complement)
    )
    return r * positive + (n - r) * negative


def _sparse_gain_bound(
    counts: Mapping[int, int],
    exposure: Sequence[int],
    total: int,
    penalty: float,
    coefficients: Sequence[tuple[float, float]],
    direction: str,
) -> bool:
    """Necessary-gain bound over validated counts and a compiled exposure."""
    relevant = sum(counts.values())
    if total == 0 or relevant == 0 or relevant == total:
        return True
    if len(coefficients) == 1:
        return True
    bound = math.fsum(
        max(
            0.0,
            *(
                -r * positive - (exposure[i] - r) * negative
                for positive, negative in coefficients[1:]
            ),
        )
        for i, r in counts.items()
        if r
    )
    if direction == "declining":
        # Every zero-count bin can favour a lower-rate state. Account for all
        # that exposure in O(sparse support), without treating missing weeks
        # as zeros or allocating a dense vector for each phrase.
        absent_exposure = total - sum(exposure[i] for i, r in counts.items() if r)
        bound += absent_exposure * -coefficients[-1][1]
    slack = 64 * math.ulp(max(1.0, bound, penalty))
    return bound < penalty - slack


def _decode_bursts(
    counts: Sequence[int],
    exposure: Sequence[int],
    total: int,
    observed: Sequence[int],
    penalty: float,
    coefficients: Sequence[tuple[float, float]],
    precise: Sequence[tuple[Decimal, Decimal]] | None = None,
) -> BurstResult:
    """Exact decoding after boundary validation; shared by dense and sparse callers."""
    states: list[int | None] = [0 if n else None for n in exposure]
    relevant = sum(counts)
    reason = ""
    if not total:
        reason = "no_observations"
    elif not relevant:
        reason = "absent_term"
    elif relevant == total:
        reason = "ubiquitous_term"
    if reason:
        return BurstResult(tuple(states), 0.0, (), reason)
    # Baseline is the per-bin maximum likelihood parameter here. Compare
    # exact integer proportions, avoiding cancellation near s=1/gamma=0.
    if all(counts[i] * total == relevant * exposure[i] for i in observed):
        return BurstResult(tuple(states), 0.0, (), "constant_prevalence")
    size = len(coefficients)
    if size == 1:
        return BurstResult(tuple(states), 0.0, (), "no_alternative_state")
    if size == 2:
        # The default grid needs only two scalar recurrences and two parent
        # bits per observed bin, rather than per-bin prefix/suffix allocations.
        positive, negative = coefficients[1]
        zero, one = 0.0, math.inf
        bits = bytearray()
        for i in observed:
            zero_parent = int(one < zero)
            enter = zero + penalty
            one_parent = int(one < enter)
            next_zero = one if zero_parent else zero
            emission = (
                counts[i] * positive + (exposure[i] - counts[i]) * negative
                if precise is None
                else _precise_emission(counts[i], exposure[i], precise[1])
            )
            one = (one if one_parent else enter) + emission
            zero = next_zero
            bits.append((zero_parent << 1) | one_parent)
        state = int(one < zero)
        objective = one if state else zero
        if objective == 0:
            return BurstResult(tuple(states), 0.0, (), "no_burst")
        for position in range(len(observed) - 1, -1, -1):
            states[observed[position]] = state
            state = bits[position] & 1 if state else bits[position] >> 1
    else:
        previous = [0.0] + [math.inf] * (size - 1)
        parents: list[list[int]] = []
        for i in observed:
            prefix: list[tuple[float, int]] = []
            best = (math.inf, 0)
            for j in range(size):
                best = min(best, (previous[j] - penalty * j, j))
                prefix.append(best)
            suffix = [(math.inf, 0)] * size
            best = (math.inf, 0)
            for j in range(size - 1, -1, -1):
                best = min(best, (previous[j], j))
                suffix[j] = best
            current, parent = [], []
            for j, (positive, negative) in enumerate(coefficients):
                cost, predecessor = min((prefix[j][0] + penalty * j, prefix[j][1]), suffix[j])
                emission = (
                    counts[i] * positive + (exposure[i] - counts[i]) * negative
                    if precise is None
                    else _precise_emission(counts[i], exposure[i], precise[j])
                )
                current.append(cost + emission)
                parent.append(predecessor)
            previous = current
            parents.append(parent)
        objective, state = min((cost, j) for j, cost in enumerate(previous))
        for position in range(len(observed) - 1, -1, -1):
            states[observed[position]] = state
            state = parents[position][state]
    return _interval_result(counts, exposure, observed, coefficients, states, objective, precise)


def _precise_emission(r: int, n: int, coefficients: tuple[Decimal, Decimal]) -> float:
    with localcontext() as context:
        context.prec = 400
        return float(Decimal(r) * coefficients[0] + Decimal(n - r) * coefficients[1])


def _interval_result(
    counts: Sequence[int],
    exposure: Sequence[int],
    observed: Sequence[int],
    coefficients: Sequence[tuple[float, float]],
    states: list[int | None],
    objective: float,
    precise: Sequence[tuple[Decimal, Decimal]] | None = None,
) -> BurstResult:
    """One episode/provenance owner for scalar and batched traceback."""
    intervals: list[BurstInterval] = []
    start = 0
    while start < len(observed):
        if not states[observed[start]]:
            start += 1
            continue
        stop = start
        while stop + 1 < len(observed) and states[observed[stop + 1]]:
            stop += 1
        first, last = observed[start], observed[stop]
        gain = -math.fsum(
            (
                counts[i] * coefficients[int(states[i] or 0)][0]
                + (exposure[i] - counts[i]) * coefficients[int(states[i] or 0)][1]
                if precise is None
                else _precise_emission(counts[i], exposure[i], precise[int(states[i] or 0)])
            )
            for i in observed[start : stop + 1]
        )
        intervals.append(
            BurstInterval(
                first,
                last,
                max(int(states[i] or 0) for i in observed[start : stop + 1]),
                gain,
                tuple(i for i in range(first, last + 1) if not exposure[i]),
                start == 0,
                stop == len(observed) - 1,
            )
        )
        start = stop + 1
    return BurstResult(
        tuple(states), objective, tuple(intervals), "burst" if intervals else "no_burst"
    )


@dataclass(frozen=True)
class PreparedBurstSeries:
    """Immutable, validated counts owned by one compiled exposure model."""

    _owner: "BurstModel"
    _counts: Mapping[int, int]
    _relevant: int = field(init=False)

    def __post_init__(self) -> None:
        copied = dict(self._counts)
        self._owner._validate_sparse(copied)
        object.__setattr__(self, "_counts", MappingProxyType(copied))
        object.__setattr__(self, "_relevant", sum(copied.values()))


class BurstModel:
    """Compile shared exposure/configuration once for full-vocabulary analysis.

    Exposure is copied and validated at construction. Every counts entry point
    validates its own input. Dense and sparse decoders use the same exact state
    grid/traceback. Grids depend on total term prevalence, not its weekly layout.
    """

    def __init__(
        self, exposure: Sequence[int], *, s: float = 2.0, gamma: float = 1.0, max_states: int = 2
    ) -> None:
        _parameters(s, gamma, max_states)
        self._exposure = tuple(exposure)
        for n in self._exposure:
            _count(n)
        self._total = sum(self._exposure)
        self._observed = tuple(i for i, n in enumerate(self._exposure) if n)
        self._penalty = gamma * math.log(len(self._observed)) if self._observed else 0.0
        self._s, self._maximum = s, max_states
        self._grids: dict[tuple[int, str], tuple[tuple[float, float], ...]] = {}
        self._precise_grids: dict[tuple[int, str], tuple[tuple[Decimal, Decimal], ...]] = {}
        self._global_prunes: dict[tuple[int, str], bool] = {}

    def prepare(self, counts: Mapping[int, int] | PreparedBurstSeries) -> PreparedBurstSeries:
        """Validate/copy once; a prepared series cannot be reused with another model."""
        if isinstance(counts, PreparedBurstSeries):
            if counts._owner is not self:
                raise ValueError("prepared series belongs to another exposure model")
            return counts
        return PreparedBurstSeries(self, counts)

    def _precision(
        self, relevant: int, direction: str
    ) -> tuple[tuple[Decimal, Decimal], ...] | None:
        # Rare near-one multipliers can lose a real gain through cancellation
        # of opposite coefficient products. Default s=2 keeps the fast path.
        if self._s - 1 > 1e-8 or not self._total or relevant in (0, self._total):
            return None
        key = (relevant, direction)
        if key not in self._precise_grids:
            base = Fraction(relevant, self._total)
            multiplier = Fraction(self._s)
            coefficients = []
            with localcontext() as context:
                context.prec = 400
                for level in range(len(self._grid(relevant, direction))):
                    p = base * multiplier ** (level if direction == "rising" else -level)
                    positive, negative = base / p, (1 - base) / (1 - p)
                    coefficients.append(
                        (
                            (Decimal(positive.numerator) / Decimal(positive.denominator)).ln(),
                            (Decimal(negative.numerator) / Decimal(negative.denominator)).ln(),
                        )
                    )
            self._precise_grids[key] = tuple(coefficients)
        return self._precise_grids[key]

    def _grid(self, relevant: int, direction: str) -> tuple[tuple[float, float], ...]:
        key = (relevant, direction)
        if key not in self._grids:
            if not self._total or relevant in (0, self._total):
                grid: tuple[tuple[float, float], ...] = ((0.0, 0.0),)
            else:
                base = relevant / self._total
                complement = (self._total - relevant) / self._total
                grid = tuple(
                    (
                        _emission(1, 1, p, q, delta, base, complement),
                        _emission(0, 1, p, q, delta, base, complement),
                    )
                    for p, q, delta in _probabilities(
                        relevant, self._total, self._s, self._maximum, direction
                    )
                )
            self._grids[key] = grid
        return self._grids[key]

    def _validate_sparse(self, counts: Mapping[int, int]) -> None:
        for i, r in counts.items():
            if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(self._exposure):
                raise ValueError("count bin is outside exposure")
            _count(r)
            if r > self._exposure[i]:
                raise ValueError("term count exceeds exposure")

    def cannot_burst(
        self, counts: Mapping[int, int] | PreparedBurstSeries, *, direction: str = "rising"
    ) -> bool:
        """Conservative sparse bound; True guarantees baseline is optimal."""
        _direction(direction)
        prepared = self.prepare(counts)
        relevant = prepared._relevant
        grid = self._grid(relevant, direction)
        if self._s - 1 <= 1e-8 and len(grid) > 1:
            return False
        key = (relevant, direction)
        if key not in self._global_prunes:
            if len(grid) == 1:
                self._global_prunes[key] = True
            else:
                upper = (
                    relevant * max(-positive for positive, _ in grid[1:])
                    if direction == "rising"
                    else (self._total - relevant) * max(-negative for _, negative in grid[1:])
                )
                slack = 64 * math.ulp(max(1.0, upper, self._penalty))
                self._global_prunes[key] = upper < self._penalty - slack
        if self._global_prunes[key]:
            return True
        return _sparse_gain_bound(
            prepared._counts,
            self._exposure,
            self._total,
            self._penalty,
            grid,
            direction,
        )

    def detect(self, counts: Sequence[int], *, direction: str = "rising") -> BurstResult:
        """Decode dense counts against this immutable exposure snapshot."""
        _direction(direction)
        if len(counts) != len(self._exposure):
            raise ValueError("counts and exposure must have the same length")
        for r, n in zip(counts, self._exposure, strict=True):
            _count(r)
            if r > n:
                raise ValueError("term count exceeds exposure")
        return _decode_bursts(
            counts,
            self._exposure,
            self._total,
            self._observed,
            self._penalty,
            self._grid(sum(counts), direction),
            self._precision(sum(counts), direction),
        )

    def detect_sparse(
        self, counts: Mapping[int, int] | PreparedBurstSeries, *, direction: str = "rising"
    ) -> BurstResult:
        """Decode sparse counts, treating omitted exposed bins as zero mentions."""
        _direction(direction)
        prepared = self.prepare(counts)
        dense = [prepared._counts.get(i, 0) for i in range(len(self._exposure))]
        return _decode_bursts(
            dense,
            self._exposure,
            self._total,
            self._observed,
            self._penalty,
            self._grid(prepared._relevant, direction),
            self._precision(prepared._relevant, direction),
        )

    def detect_many(
        self,
        series: Sequence[Mapping[int, int] | PreparedBurstSeries],
        *,
        direction: str = "rising",
    ) -> list[BurstResult]:
        """Same exact decoding in batches of at most 1,024 independent series.

        Two-state recurrences run across series with NumPy. Larger grids use
        the scalar path. No vocabulary sampling or result truncation.
        """
        _direction(direction)
        results = []
        for offset in range(0, len(series), 1024):
            results.extend(self._detect_batch(series[offset : offset + 1024], direction))
        return results

    def _detect_batch(
        self, series: Sequence[Mapping[int, int] | PreparedBurstSeries], direction: str
    ) -> list[BurstResult]:
        if self._s - 1 <= 1e-8:
            return [self.detect_sparse(counts, direction=direction) for counts in series]
        results: dict[int, BurstResult] = {}
        selected = []
        grids = []
        prepared = [self.prepare(counts) for counts in series]
        for index, item in enumerate(prepared):
            sparse = item._counts
            relevant = item._relevant
            grid = self._grid(relevant, direction)
            if len(grid) != 2 or all(
                sparse.get(i, 0) * self._total == relevant * self._exposure[i]
                for i in self._observed
            ):
                results[index] = self.detect_sparse(item, direction=direction)
            else:
                selected.append(index)
                grids.append(grid)
        if not selected:
            return [results[i] for i in range(len(series))]
        dense = np.asarray(
            [[prepared[index]._counts.get(i, 0) for i in self._observed] for index in selected],
            dtype=np.float64,
        )
        coefficients = np.asarray([grid[1] for grid in grids], dtype=np.float64)
        exposure = np.asarray([self._exposure[i] for i in self._observed], dtype=np.float64)
        emissions = dense * coefficients[:, :1] + (exposure - dense) * coefficients[:, 1:]
        zero = np.zeros(len(selected), dtype=np.float64)
        one = np.full(len(selected), np.inf, dtype=np.float64)
        parents = np.empty((len(self._observed), len(selected)), dtype=np.uint8)
        for position in range(len(self._observed)):
            zero_parent = one < zero
            enter = zero + self._penalty
            one_parent = one < enter
            next_zero = np.where(zero_parent, one, zero)
            one = np.where(one_parent, one, enter) + emissions[:, position]
            zero = next_zero
            parents[position] = (zero_parent.astype(np.uint8) << 1) | one_parent
        baseline = tuple(0 if n else None for n in self._exposure)
        for column, index in enumerate(selected):
            state = int(one[column] < zero[column])
            objective = float(one[column] if state else zero[column])
            if objective == 0:
                results[index] = BurstResult(baseline, 0.0, (), "no_burst")
                continue
            states = list(baseline)
            for position in range(len(self._observed) - 1, -1, -1):
                states[self._observed[position]] = state
                bits = int(parents[position, column])
                state = bits & 1 if state else bits >> 1
            results[index] = _interval_result(
                [prepared[index]._counts.get(i, 0) for i in range(len(self._exposure))],
                self._exposure,
                self._observed,
                grids[column],
                states,
                objective,
            )
        return [results[i] for i in range(len(series))]


def detect_bursts(
    counts: Sequence[int],
    exposure: Sequence[int],
    *,
    s: float = 2.0,
    gamma: float = 1.0,
    max_states: int = 2,
    direction: str = "rising",
) -> BurstResult:
    """Exact O(bins * states) global minimum-cost path, with lower-state tie breaks.

    Rising probabilities are base*s**level; declining probabilities are
    base/s**level. State zero is baseline. Departures cost gamma*log(observed
    bins) per level; returning towards baseline is free. Missing exposure stays
    unobserved. Declines extend Kleinberg's original rising-only model.
    """
    return BurstModel(exposure, s=s, gamma=gamma, max_states=max_states).detect(
        counts, direction=direction
    )


def sparse_gain_cannot_burst(
    counts: Mapping[int, int],
    exposure: Sequence[int],
    *,
    s: float = 2.0,
    gamma: float = 1.0,
    max_states: int = 2,
    direction: str = "rising",
) -> bool:
    """True only when even optimistic per-bin gains cannot pay the first step."""
    return BurstModel(exposure, s=s, gamma=gamma, max_states=max_states).cannot_burst(
        counts, direction=direction
    )
