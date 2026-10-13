"""Exact batched-binomial Kleinberg bursts (2002, section 4).

Costs omit the common binomial coefficient and subtract baseline emissions.
Zero-exposure bins are unobserved, not evidence of absence. Upward transitions
cost gamma * log(number of observed bins) per level; downward moves are free.
The initial state is zero. Scores are likelihood gains, never p-values.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


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


def _probabilities(base: float, s: float, maximum: int) -> list[float]:
    probabilities = [base]
    for _ in range(1, maximum):
        candidate = probabilities[-1] * s
        if not candidate < 1 or candidate <= probabilities[-1]:
            break
        probabilities.append(candidate)
    return probabilities


def _emission(r: int, n: int, p: float, base: float) -> float:
    return r * math.log(base / p) + (n - r) * (math.log1p(-base) - math.log1p(-p))


def sparse_gain_cannot_burst(
    counts: Mapping[int, int],
    exposure: Sequence[int],
    *,
    s: float = 2.0,
    gamma: float = 1.0,
    max_states: int = 2,
) -> bool:
    """Conservative necessary-gain bound; True guarantees no beneficial burst.

    Ignores all negative gains and transition costs except the first upward
    step. Floating point slack keeps equality/near-boundary cases in the DP.
    """
    _parameters(s, gamma, max_states)
    for n in exposure:
        _count(n)
    for i, r in counts.items():
        if isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < len(exposure):
            raise ValueError("count bin is outside exposure")
        _count(r)
        if r > exposure[i]:
            raise ValueError("term count exceeds exposure")
    total, relevant = sum(exposure), sum(counts.values())
    if total == 0 or relevant == 0 or relevant == total:
        return True
    base = relevant / total
    probabilities = _probabilities(base, s, max_states)
    if len(probabilities) == 1:
        return True
    penalty = gamma * math.log(sum(n > 0 for n in exposure))
    bound = math.fsum(
        max(0.0, *(-_emission(r, exposure[i], p, base) for p in probabilities[1:]))
        for i, r in counts.items()
        if r
    )
    slack = 64 * math.ulp(max(1.0, bound, penalty))
    return bound < penalty - slack


def detect_bursts(
    counts: Sequence[int],
    exposure: Sequence[int],
    *,
    s: float = 2.0,
    gamma: float = 1.0,
    max_states: int = 2,
) -> BurstResult:
    """Find the globally minimum-cost state sequence in O(bins * states).

    Equal costs prefer the lower predecessor/final state. Valid probabilities
    are base*s**level strictly below one; invalid states are omitted, not clipped.
    max_states includes the baseline. Empty and degenerate series abstain.
    """
    _parameters(s, gamma, max_states)
    if len(counts) != len(exposure):
        raise ValueError("counts and exposure must have the same length")
    for r, n in zip(counts, exposure, strict=True):
        _count(r)
        _count(n)
        if r > n:
            raise ValueError("term count exceeds exposure")
    observed = [i for i, n in enumerate(exposure) if n]
    states: list[int | None] = [0 if n else None for n in exposure]
    total, relevant = sum(exposure), sum(counts)
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
    base = relevant / total
    probabilities = _probabilities(base, s, max_states)
    size = len(probabilities)
    if size == 1:
        return BurstResult(tuple(states), 0.0, (), "no_elevated_state")
    penalty = gamma * math.log(len(observed))
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
        for j, p in enumerate(probabilities):
            cost, predecessor = min((prefix[j][0] + penalty * j, prefix[j][1]), suffix[j])
            current.append(cost + _emission(counts[i], exposure[i], p, base))
            parent.append(predecessor)
        previous = current
        parents.append(parent)
    objective, state = min((cost, j) for j, cost in enumerate(previous))
    for position in range(len(observed) - 1, -1, -1):
        states[observed[position]] = state
        state = parents[position][state]
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
            _emission(counts[i], exposure[i], probabilities[int(states[i] or 0)], base)
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
