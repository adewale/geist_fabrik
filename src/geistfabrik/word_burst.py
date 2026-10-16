"""Exact batched-binomial Kleinberg bursts (2002, section 4).

Costs omit the common binomial coefficient and subtract baseline emissions.
Zero-exposure bins are unobserved, not evidence of absence. Upward transitions
cost gamma * log(number of observed bins) per level; downward moves are free.
The initial state is zero. Scores are likelihood gains, never p-values.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal, localcontext
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


def _log_bounds(ratio: Fraction, precision: int = 80) -> tuple[Decimal, Decimal]:
    """Enclose ln(exact rational) using correctly rounded Decimal logarithms.

    Taking integer logarithms avoids first rounding the ratio. Adjacent Decimal
    values enclose each correctly rounded ln; subtraction rounds outwards.
    These bounds describe coefficient error before float products cancel.
    """
    if ratio == 1:
        return Decimal(0), Decimal(0)
    with localcontext() as context:
        context.prec = precision
        numerator = Decimal(ratio.numerator).ln()
        denominator = Decimal(ratio.denominator).ln()
        context.rounding = ROUND_FLOOR
        lower = numerator.next_minus() - denominator.next_plus()
        context.rounding = ROUND_CEILING
        upper = numerator.next_plus() - denominator.next_minus()
    return lower, upper


def _float_enclosure(lower: Decimal, upper: Decimal) -> tuple[float, float]:
    """A float approximation and outward-rounded absolute error enclosure."""
    with localcontext() as context:
        context.prec = 80
        value = float((lower + upper) / 2)
        context.rounding = ROUND_CEILING
        error = max(Decimal.from_float(value) - lower, upper - Decimal.from_float(value))
        return value, math.nextafter(float(error), math.inf) if error else 0.0


class _LogCost:
    """Integer-weighted logarithms of exact rationals for ambiguous decisions.

    Gamma's rational denominator scales all costs to integer weights. Decimal
    enclosures decide unequal costs adaptively; gcd reduction proves exact ties
    without constructing integers raised to enormous observation counts.
    """

    def __init__(
        self,
        terms: Mapping[Fraction, int],
        cache: dict[tuple[Fraction, int], tuple[Decimal, Decimal]],
    ) -> None:
        self.terms = {ratio: weight for ratio, weight in terms.items() if ratio != 1 and weight}
        self.cache = cache

    def plus(self, other: "_LogCost", factor: int = 1) -> "_LogCost":
        terms = dict(self.terms)
        for ratio, weight in other.terms.items():
            terms[ratio] = terms.get(ratio, 0) + factor * weight
        return _LogCost(terms, self.cache)

    def _reduced(self) -> "_LogCost":
        factors: dict[int, int] = {}

        def add(base: int, weight: int) -> None:
            if base != 1:
                factors[base] = factors.get(base, 0) + weight
                if not factors[base]:
                    del factors[base]

        for ratio, weight in self.terms.items():
            add(ratio.numerator, weight)
            add(ratio.denominator, -weight)
        while True:
            bases = list(factors)
            for i, a in enumerate(bases):
                for b in bases[i + 1 :]:
                    divisor = math.gcd(a, b)
                    if divisor != 1:
                        left, right = factors.pop(a), factors.pop(b)
                        add(divisor, left + right)
                        add(a // divisor, left)
                        add(b // divisor, right)
                        break
                else:
                    continue
                break
            else:
                return _LogCost(
                    {Fraction(base): weight for base, weight in factors.items()}, self.cache
                )

    def _bounds(self, precision: int) -> tuple[Decimal, Decimal]:
        with localcontext() as context:
            context.prec = precision
            lower, upper = Decimal(0), Decimal(0)
            for ratio, weight in self.terms.items():
                key = (ratio, precision)
                if key not in self.cache:
                    self.cache[key] = _log_bounds(ratio, precision)
                lo, hi = self.cache[key]
                context.rounding = ROUND_FLOOR
                lower += Decimal(weight) * (lo if weight > 0 else hi)
                context.rounding = ROUND_CEILING
                upper += Decimal(weight) * (hi if weight > 0 else lo)
        return lower, upper

    def compare(self, other: "_LogCost") -> int:
        if self.terms == other.terms:
            return 0
        difference = self.plus(other, -1)
        precision = 80
        while True:
            lower, upper = difference._bounds(precision)
            if lower > 0:
                return 1
            if upper < 0:
                return -1
            if precision == 80:
                difference = difference._reduced()
                if not difference.terms:
                    return 0
            precision *= 2

    def value(self, denominator: int) -> float:
        cost = self
        precision = 80
        while True:
            lower, upper = cost._bounds(precision)
            with localcontext() as context:
                context.prec = precision
                context.rounding = ROUND_FLOOR
                lo = float(lower / Decimal(denominator))
                context.rounding = ROUND_CEILING
                hi = float(upper / Decimal(denominator))
            if lo == hi:
                return lo
            if precision == 80:
                cost = cost._reduced()
                if not cost.terms:
                    return 0.0
            precision *= 2


def _best_log_cost(
    left: tuple[_LogCost, int] | None, right: tuple[_LogCost, int] | None
) -> tuple[_LogCost, int] | None:
    if left is None:
        return right
    if right is None:
        return left
    order = left[0].compare(right[0])
    return left if order < 0 or (order == 0 and left[1] <= right[1]) else right


def _ambiguous(a: float, b: float, uncertainty: float) -> bool:
    return math.isfinite(a) and math.isfinite(b) and abs(a - b) <= 2 * uncertainty


def _sparse_gain_bound(
    counts: Mapping[int, int],
    exposure: Sequence[int],
    total: int,
    penalty: float,
    coefficients: Sequence[tuple[float, float]],
    direction: str,
    uncertainty: float,
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
    # Uncertainty includes the original coefficient products, not just their
    # potentially tiny difference. Ambiguity must never remove a candidate.
    return bound < penalty - uncertainty


def _decode_bursts(
    counts: Sequence[int],
    exposure: Sequence[int],
    total: int,
    observed: Sequence[int],
    penalty: float,
    coefficients: Sequence[tuple[float, float]],
    uncertainty: float,
) -> BurstResult | None:
    """Float DP, or None when a deciding comparison needs Decimal arithmetic."""
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
    if math.isinf(uncertainty):
        return None
    if size == 2:
        # The default grid needs only two scalar recurrences and two parent
        # bits per observed bin, rather than per-bin prefix/suffix allocations.
        positive, negative = coefficients[1]
        zero, one = 0.0, math.inf
        bits = bytearray()
        for i in observed:
            enter = zero + penalty
            if _ambiguous(one, zero, uncertainty) or _ambiguous(one, enter, uncertainty):
                return None
            zero_parent = int(one < zero)
            one_parent = int(one < enter)
            next_zero = one if zero_parent else zero
            emission = counts[i] * positive + (exposure[i] - counts[i]) * negative
            one = (one if one_parent else enter) + emission
            zero = next_zero
            bits.append((zero_parent << 1) | one_parent)
        if _ambiguous(one, zero, uncertainty):
            return None
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
                candidate = (previous[j] - penalty * j, j)
                if _ambiguous(best[0], candidate[0], uncertainty):
                    return None
                best = min(best, candidate)
                prefix.append(best)
            suffix = [(math.inf, 0)] * size
            best = (math.inf, 0)
            for j in range(size - 1, -1, -1):
                if _ambiguous(best[0], previous[j], uncertainty):
                    return None
                best = min(best, (previous[j], j))
                suffix[j] = best
            current, parent = [], []
            for j, (positive, negative) in enumerate(coefficients):
                entering = (prefix[j][0] + penalty * j, prefix[j][1])
                if entering[1] == suffix[j][1] == j and math.isfinite(entering[0]):
                    cost, predecessor = previous[j], j
                else:
                    if _ambiguous(entering[0], suffix[j][0], uncertainty):
                        return None
                    cost, predecessor = min(entering, suffix[j])
                emission = counts[i] * positive + (exposure[i] - counts[i]) * negative
                current.append(cost + emission)
                parent.append(predecessor)
            previous = current
            parents.append(parent)
        objective, state = min((cost, j) for j, cost in enumerate(previous))
        if any(
            j != state and _ambiguous(cost, objective, uncertainty)
            for j, cost in enumerate(previous)
        ):
            return None
        for position in range(len(observed) - 1, -1, -1):
            states[observed[position]] = state
            state = parents[position][state]
    return _interval_result(counts, exposure, observed, coefficients, states, objective)


def _interval_result(
    counts: Sequence[int],
    exposure: Sequence[int],
    observed: Sequence[int],
    coefficients: Sequence[tuple[float, float]],
    states: list[int | None],
    objective: float,
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
            counts[i] * coefficients[int(states[i] or 0)][0]
            + (exposure[i] - counts[i]) * coefficients[int(states[i] or 0)][1]
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
        with localcontext() as context:
            context.prec = 80
            lower, upper = _log_bounds(Fraction(len(self._observed) or 1))
            context.rounding = ROUND_FLOOR
            lower *= Decimal.from_float(float(gamma))
            context.rounding = ROUND_CEILING
            upper *= Decimal.from_float(float(gamma))
            self._penalty, self._penalty_error = _float_enclosure(lower, upper)
        self._gamma = gamma
        self._s, self._maximum = s, max_states
        self._grids: dict[tuple[int, str], tuple[tuple[float, float], ...]] = {}
        self._errors: dict[tuple[int, str], tuple[tuple[float, float], ...]] = {}
        self._budgets: dict[tuple[int, str], float] = {}
        self._ratios: dict[tuple[int, str], tuple[tuple[Fraction, Fraction], ...]] = {}
        self._logs: dict[tuple[Fraction, int], tuple[Decimal, Decimal]] = {}
        self._global_prunes: dict[tuple[int, str], bool] = {}

    def prepare(self, counts: Mapping[int, int] | PreparedBurstSeries) -> PreparedBurstSeries:
        """Validate/copy once; a prepared series cannot be reused with another model."""
        if isinstance(counts, PreparedBurstSeries):
            if counts._owner is not self:
                raise ValueError("prepared series belongs to another exposure model")
            return counts
        return PreparedBurstSeries(self, counts)

    def _grid(self, relevant: int, direction: str) -> tuple[tuple[float, float], ...]:
        key = (relevant, direction)
        if key not in self._grids:
            if not self._total or relevant in (0, self._total):
                grid: tuple[tuple[float, float], ...] = ((0.0, 0.0),)
            else:
                base = Fraction(relevant, self._total)
                multiplier = Fraction(self._s)
                values, errors = [(0.0, 0.0)], [(0.0, 0.0)]
                ratios = [(Fraction(1), Fraction(1))]
                for level in range(1, self._maximum):
                    p = base * multiplier ** (level if direction == "rising" else -level)
                    if not 0 < p < 1:
                        break
                    pair = (base / p, (1 - base) / (1 - p))
                    ratios.append(pair)
                    for ratio in pair:
                        if (ratio, 80) not in self._logs:
                            self._logs[(ratio, 80)] = _log_bounds(ratio)
                    positive, positive_error = _float_enclosure(*self._logs[(pair[0], 80)])
                    negative, negative_error = _float_enclosure(*self._logs[(pair[1], 80)])
                    values.append((positive, negative))
                    errors.append((positive_error, negative_error))
                grid = tuple(values)
                self._errors[key] = tuple(errors)
                self._ratios[key] = tuple(ratios)
            self._grids[key] = grid
            self._errors.setdefault(key, ((0.0, 0.0),))
        return self._grids[key]

    def _uncertainty(self, relevant: int, direction: str) -> float:
        """Bound coefficient and DP rounding error before cancellation.

        Each path uses at most R successes, N-R failures and B*(K-1)
        transition levels. Eight rounding operations per observed bin bound
        products, prefix/suffix rebasing and cumulative additions. The absolute
        operation scale bounds every intermediate, even if final cost is tiny.
        This layout-independent budget is cached with the prevalence grid.
        """
        key = (relevant, direction)
        if key not in self._budgets:
            grid = self._grid(relevant, direction)
            errors = self._errors[key]
            bins = len(self._observed)
            scale = math.fsum(
                (
                    relevant * max(abs(a) for a, _ in grid),
                    (self._total - relevant) * max(abs(b) for _, b in grid),
                    (bins + 2) * self._maximum * self._penalty,
                )
            )
            error = math.fsum(
                (
                    relevant * max(a for a, _ in errors),
                    (self._total - relevant) * max(b for _, b in errors),
                    bins * self._maximum * self._penalty_error,
                    8 * (bins + 1) * math.ulp(scale),
                )
            )
            self._budgets[key] = math.nextafter(error, math.inf)
        return self._budgets[key]

    def _decode(self, counts: Sequence[int], relevant: int, direction: str) -> BurstResult:
        grid = self._grid(relevant, direction)
        budget = math.inf if self._s - 1 <= 1e-8 else self._uncertainty(relevant, direction)
        result = _decode_bursts(
            counts, self._exposure, self._total, self._observed, self._penalty, grid, budget
        )
        if result is not None:
            return self._score_result(counts, relevant, direction, result)
        gamma = Fraction(self._gamma)
        denominator = gamma.denominator
        penalty = _LogCost({Fraction(len(self._observed)): gamma.numerator}, self._logs)
        zero = _LogCost({}, self._logs)
        previous: list[_LogCost | None] = [zero] + [None] * (len(grid) - 1)
        parents = []
        ratios = self._ratios[(relevant, direction)]

        def emission(i: int, state: int) -> _LogCost:
            positive, negative = ratios[state]
            terms = {positive: counts[i] * denominator}
            terms[negative] = terms.get(negative, 0) + (self._exposure[i] - counts[i]) * denominator
            return _LogCost(terms, self._logs)

        for i in self._observed:
            prefix = []
            best = None
            for j, cost in enumerate(previous):
                candidate = (cost.plus(penalty, -j), j) if cost is not None else None
                best = _best_log_cost(best, candidate)
                prefix.append(best)
            suffix: list[tuple[_LogCost, int] | None] = [None] * len(grid)
            best = None
            for j in range(len(grid) - 1, -1, -1):
                cost = previous[j]
                best = _best_log_cost(best, (cost, j) if cost is not None else None)
                suffix[j] = best
            current: list[_LogCost | None] = []
            parent = []
            for j in range(len(grid)):
                entering = prefix[j]
                candidate = (
                    (entering[0].plus(penalty, j), entering[1]) if entering is not None else None
                )
                selected = _best_log_cost(candidate, suffix[j])
                assert selected is not None
                current.append(selected[0].plus(emission(i, j)))
                parent.append(selected[1])
            previous = current
            parents.append(parent)
        best = None
        for j, cost in enumerate(previous):
            best = _best_log_cost(best, (cost, j) if cost is not None else None)
        assert best is not None
        objective, state = best
        states: list[int | None] = [0 if n else None for n in self._exposure]
        for position in range(len(self._observed) - 1, -1, -1):
            states[self._observed[position]] = state
            state = parents[position][state]
        result = _interval_result(
            counts, self._exposure, self._observed, grid, states, objective.value(denominator)
        )
        intervals = []
        for interval in result.intervals:
            gain = zero
            for i in range(interval.start, interval.end + 1):
                if self._exposure[i]:
                    gain = gain.plus(emission(i, int(states[i] or 0)))
            intervals.append(replace(interval, gain=-gain.value(denominator)))
        return replace(result, intervals=tuple(intervals))

    def _score_result(
        self, counts: Sequence[int], relevant: int, direction: str, result: BurstResult
    ) -> BurstResult:
        """Report the chosen path without cancellation in its scalar score.

        Certified float decisions can still have a tiny relative-cost score.
        Aggregate exact counts once; only a few weighted logs need evaluation,
        rather than rerunning a whole high-precision recurrence.
        """
        if not result.intervals:
            return result
        gamma = Fraction(self._gamma)
        denominator = gamma.denominator
        ratios = self._ratios[(relevant, direction)]

        def emissions(indices: Sequence[int]) -> _LogCost:
            terms: dict[Fraction, int] = {}
            for i in indices:
                level = result.states[i]
                if level:
                    positive, negative = ratios[level]
                    terms[positive] = terms.get(positive, 0) + counts[i] * denominator
                    terms[negative] = (
                        terms.get(negative, 0) + (self._exposure[i] - counts[i]) * denominator
                    )
            return _LogCost(terms, self._logs)

        previous, steps = 0, 0
        for i in self._observed:
            state = int(result.states[i] or 0)
            steps += max(0, state - previous)
            previous = state
        penalty = _LogCost({Fraction(len(self._observed)): gamma.numerator * steps}, self._logs)
        objective = emissions(self._observed).plus(penalty).value(denominator)
        intervals = tuple(
            replace(
                interval,
                gain=-emissions(range(interval.start, interval.end + 1)).value(denominator),
            )
            for interval in result.intervals
        )
        return replace(result, objective=objective, intervals=intervals)

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
                self._global_prunes[key] = upper < self._penalty - self._uncertainty(
                    relevant, direction
                )
        if self._global_prunes[key]:
            return True
        return _sparse_gain_bound(
            prepared._counts,
            self._exposure,
            self._total,
            self._penalty,
            grid,
            direction,
            self._uncertainty(relevant, direction),
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
        return self._decode(counts, sum(counts), direction)

    def detect_sparse(
        self, counts: Mapping[int, int] | PreparedBurstSeries, *, direction: str = "rising"
    ) -> BurstResult:
        """Decode sparse counts, treating omitted exposed bins as zero mentions."""
        _direction(direction)
        prepared = self.prepare(counts)
        dense = [prepared._counts.get(i, 0) for i in range(len(self._exposure))]
        return self._decode(dense, prepared._relevant, direction)

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
        budgets = np.asarray(
            [self._uncertainty(prepared[index]._relevant, direction) for index in selected]
        )
        ambiguous = np.zeros(len(selected), dtype=np.bool_)
        zero = np.zeros(len(selected), dtype=np.float64)
        one = np.full(len(selected), np.inf, dtype=np.float64)
        parents = np.empty((len(self._observed), len(selected)), dtype=np.uint8)
        for position in range(len(self._observed)):
            zero_parent = one < zero
            enter = zero + self._penalty
            ambiguous |= np.isfinite(one) & (
                (np.abs(one - zero) <= 2 * budgets) | (np.abs(one - enter) <= 2 * budgets)
            )
            one_parent = one < enter
            next_zero = np.where(zero_parent, one, zero)
            one = np.where(one_parent, one, enter) + emissions[:, position]
            zero = next_zero
            parents[position] = (zero_parent.astype(np.uint8) << 1) | one_parent
        ambiguous |= np.isfinite(one) & (np.abs(one - zero) <= 2 * budgets)
        baseline = tuple(0 if n else None for n in self._exposure)
        for column, index in enumerate(selected):
            if ambiguous[column]:
                results[index] = self.detect_sparse(prepared[index], direction=direction)
                continue
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
            dense_counts = [prepared[index]._counts.get(i, 0) for i in range(len(self._exposure))]
            result = _interval_result(
                dense_counts,
                self._exposure,
                self._observed,
                grids[column],
                states,
                objective,
            )
            results[index] = self._score_result(
                dense_counts, prepared[index]._relevant, direction, result
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
