"""Prepared directions, canonical scores and certified NumPy/BLAS decisions.

Canonical APIs retain fixed per-pair binary64 reductions. Decision APIs enclose
the canonical result and refine ambiguous cells; no arbitrary threshold epsilon
or approximate neighbour index changes the answer.
"""

import math
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

# Score-tile budget, not a whole-process limit. Prepared inputs and explicitly
# requested outputs are separate. Reduced operations never request an N*N output.
SCORE_BLOCK_BYTES = 1024 * 1024
_EPS = np.finfo(np.float64).eps
_TINY = np.finfo(np.float64).tiny


def _gamma(operations: int) -> float:
    product = operations * _EPS
    return math.inf if product >= 1 else math.nextafter(product / (1 - product), math.inf)


def _threshold(value: float) -> float:
    if isinstance(value, bool):
        raise ValueError("similarity threshold must be finite")
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("similarity threshold must be finite") from exc
    if not math.isfinite(result):
        raise ValueError("similarity threshold must be finite")
    return result


def _row_dots(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Fixed adjacent-pair binary64 tree, independent of population shape.

    Inputs are equally shaped rows, or one left row broadcast over right rows.
    Materialized products and separate elementwise additions prescribe every
    rounding operation: neither iterator buffering nor BLAS can reorder them or
    fuse multiplication with addition. Odd trailing components carry unchanged.
    The same tree normalizes rows and scores every canonical/refinement path.
    """
    count, dimension = right.shape
    result = np.zeros(count, dtype=np.float64)
    if not dimension:
        return result
    # Products plus a half-width scratch array fit this allowance, except for
    # the unavoidable single pair when its dimension alone exceeds the budget.
    size = max(1, SCORE_BLOCK_BYTES // (16 * dimension))
    for start in range(0, count, size):
        stop = min(count, start + size)
        work = np.multiply(left if len(left) == 1 else left[start:stop], right[start:stop])
        scratch = np.empty((stop - start, (dimension + 1) // 2), dtype=np.float64)
        width = dimension
        while width > 1:
            pairs = width // 2
            np.add(work[:, : 2 * pairs : 2], work[:, 1 : 2 * pairs : 2], out=scratch[:, :pairs])
            if width % 2:
                scratch[:, pairs] = work[:, width - 1]
            work, scratch = scratch, work
            width = pairs + width % 2
        result[start:stop] = work[:, 0]
        # Release both alternating arrays before allocating the next chunk.
        del work, scratch
    return result


def _paired_scores(
    left: np.ndarray,
    right: np.ndarray,
    left_keys: Sequence[int | None],
    right_keys: Sequence[int | None],
    identity_ids: tuple[np.ndarray, np.ndarray] | None = None,
) -> np.ndarray:
    """One canonical pair kernel shared by paired and sparse refinement paths."""
    result = _row_dots(left, right)
    np.clip(result, -1.0, 1.0, out=result)
    if identity_ids is not None:
        a_ids, b_ids = identity_ids
        result[(a_ids == b_ids) & (a_ids >= 0)] = 1.0
        result[(a_ids < 0) | (b_ids < 0)] = 0.0
        return result
    for i, (a, b) in enumerate(zip(left_keys, right_keys, strict=True)):
        if a is None or b is None:
            result[i] = 0.0
        elif a == b and np.array_equal(left[i], right[i]):
            result[i] = 1.0
    return result


@dataclass
class SimilarityWork:
    """Optional work diagnostics; never contains vectors, paths or note text."""

    fast_pairs: int = 0
    refined_pairs: int = 0
    blocks: int = 0


@dataclass(frozen=True, init=False)
class UnitRows:
    """Immutable validated directions with cached collision-checked identity.

    Contiguous slices share bytes and prepared metadata. Array views have
    disposable metadata. A hash match alone never establishes vector identity.
    """

    _data: bytes = field(repr=False)
    _shape: tuple[int, int]
    _start: int
    _keys: tuple[int | None, ...] = field(repr=False)
    _identities: Mapping[int, tuple[tuple[int, ...], ...]] = field(repr=False)
    _zeros: tuple[int, ...] = field(repr=False)
    _identity_data: bytes = field(repr=False)
    _distinct_nonzero: bool = field(repr=False)

    def __init__(self, values: np.ndarray) -> None:
        matrix = np.array(values, dtype=np.float64, order="C", copy=True)
        if matrix.ndim != 2:
            raise ValueError("embedding matrices must have two dimensions")
        if not np.isfinite(matrix).all():
            raise ValueError("embeddings must contain only finite values")
        scales = (
            np.max(np.abs(matrix), axis=1, keepdims=True)
            if matrix.shape[1]
            else np.zeros((len(matrix), 1))
        )
        matrix /= np.where(scales == 0, 1.0, scales)
        norms = np.sqrt(_row_dots(matrix, matrix))[:, None]
        matrix /= np.where(norms == 0, 1.0, norms)
        matrix[matrix == 0] = 0.0
        data = matrix.tobytes()
        payload = memoryview(data)
        width = matrix.shape[1] * 8
        # Salted process-local hashes are only bucket indexes. Every collision
        # is checked against actual rows; keys are never persisted or scored.
        keys = tuple(
            hash(payload[i * width : (i + 1) * width]) if scales[i, 0] else None
            for i in range(len(matrix))
        )
        self._install(matrix, keys, data)

    def _install(
        self, matrix: np.ndarray, keys: tuple[int | None, ...], data: bytes | None = None
    ) -> None:
        groups: dict[int, list[list[int]]] = {}
        identities = np.full(len(matrix), -1, dtype=np.intp)
        for i, key in enumerate(keys):
            if key is None:
                continue
            bucket = groups.setdefault(key, [])
            for group in bucket:
                if np.array_equal(matrix[i], matrix[group[0]]):
                    group.append(i)
                    identities[i] = group[0]
                    break
            else:
                bucket.append([i])
                identities[i] = i
        object.__setattr__(self, "_data", matrix.tobytes() if data is None else data)
        object.__setattr__(self, "_identity_data", identities.tobytes())
        object.__setattr__(
            self, "_distinct_nonzero", bool(np.array_equal(identities, np.arange(len(matrix))))
        )
        object.__setattr__(self, "_shape", matrix.shape)
        object.__setattr__(self, "_start", 0)
        object.__setattr__(self, "_keys", keys)
        object.__setattr__(self, "_zeros", tuple(i for i, key in enumerate(keys) if key is None))
        object.__setattr__(
            self,
            "_identities",
            MappingProxyType(
                {key: tuple(tuple(group) for group in bucket) for key, bucket in groups.items()}
            ),
        )

    @property
    def values(self) -> np.ndarray:
        """Disposable read-only view; changing its shape cannot alter this object."""
        return np.frombuffer(
            self._data,
            dtype=np.float64,
            count=self._shape[0] * self._shape[1],
            offset=self._start * self._shape[1] * 8,
        ).reshape(self._shape)

    def __len__(self) -> int:
        return self._shape[0]

    def _view(self, start: int, stop: int) -> "UnitRows":
        result = object.__new__(UnitRows)
        for name in (
            "_data",
            "_keys",
            "_identities",
            "_zeros",
            "_identity_data",
            "_distinct_nonzero",
        ):
            object.__setattr__(result, name, getattr(self, name))
        object.__setattr__(result, "_shape", (stop - start, self._shape[1]))
        object.__setattr__(result, "_start", self._start + start)
        return result

    def take(self, indices: Sequence[int]) -> "UnitRows":
        """Select prepared rows without revalidation or renormalization."""
        if any(
            isinstance(i, (bool, np.bool_)) or not isinstance(i, (int, np.integer)) for i in indices
        ):
            raise ValueError("row indices must be integers")
        try:
            array = np.asarray(indices, dtype=np.intp)
        except (OverflowError, ValueError) as exc:
            raise ValueError("row indices must identify prepared rows") from exc
        if array.ndim != 1 or ((array < 0) | (array >= len(self))).any():
            raise ValueError("row indices must identify prepared rows")
        if not len(array):
            return self._view(0, 0)
        if np.array_equal(array, np.arange(array[0], array[0] + len(array))):
            return self._view(int(array[0]), int(array[0]) + len(array))
        result = object.__new__(UnitRows)
        result._install(self.values[array], tuple(self._keys[self._start + int(i)] for i in array))
        return result

    def _compatible(self, other: "UnitRows") -> None:
        if self._shape[1] != other._shape[1]:
            raise ValueError("embedding dimensions must match")

    @property
    def _identity_ids(self) -> np.ndarray:
        return np.frombuffer(
            self._identity_data,
            dtype=np.intp,
            count=len(self),
            offset=self._start * np.dtype(np.intp).itemsize,
        )

    def _identical(
        self, other: "UnitRows", result: np.ndarray, exact: np.ndarray | None = None
    ) -> None:
        if self._data is other._data and self._distinct_nonzero:
            # Verified distinct directions can match only at the same root row.
            # Disjoint slices need no mask or identity work at all.
            start = max(self._start, other._start)
            stop = min(self._start + len(self), other._start + len(other))
            if start < stop:
                positions = np.arange(start, stop)
                root_rows, root_columns = positions - self._start, positions - other._start
                result[root_rows, root_columns] = 1.0
                if exact is not None:
                    exact[root_rows, root_columns] = True
            return
        if self._data is other._data:
            left_ids, right_ids = self._identity_ids, other._identity_ids
            identical = left_ids[:, None] == right_ids[None, :]
            identical &= left_ids[:, None] >= 0
            result[identical] = 1.0
            zeros = (left_ids[:, None] < 0) | (right_ids[None, :] < 0)
            result[zeros] = 0.0
            if exact is not None:
                np.logical_or(identical, zeros, out=exact)
            return
        left, right = self.values, other.values
        left_end, right_end = self._start + len(self), other._start + len(other)
        for key in set(self._keys[self._start : left_end]):
            if key is None or key not in other._identities:
                continue
            for own in self._identities[key]:
                rows = [i - self._start for i in own if self._start <= i < left_end]
                if not rows:
                    continue
                for peer in other._identities[key]:
                    columns = [j - other._start for j in peer if other._start <= j < right_end]
                    if columns and np.array_equal(left[rows[0]], right[columns[0]]):
                        result[np.ix_(rows, columns)] = 1.0
                        if exact is not None:
                            exact[np.ix_(rows, columns)] = True
        zeros_a = [i - self._start for i in self._zeros if self._start <= i < left_end]
        zeros_b = [j - other._start for j in other._zeros if other._start <= j < right_end]
        result[zeros_a, :] = 0.0
        result[:, zeros_b] = 0.0
        if exact is not None:
            exact[zeros_a, :] = True
            exact[:, zeros_b] = True

    def cosine(self, other: "UnitRows") -> np.ndarray:
        """Canonical scores, identical to scalar and chunked calls."""
        self._compatible(other)
        left, right = self.values, other.values
        result = np.empty((len(self), len(other)), dtype=np.float64)
        for i in range(len(self)):
            result[i] = _row_dots(left[i : i + 1], right)
        np.clip(result, -1.0, 1.0, out=result)
        self._identical(other, result)
        return result

    def paired(self, other: "UnitRows") -> np.ndarray:
        """Canonical row i versus row i scores, O(N*D) without an N*N output."""
        self._compatible(other)
        if len(self) != len(other):
            raise ValueError("paired comparisons require equal row counts")
        return _paired_scores(
            self.values,
            other.values,
            self._keys[self._start : self._start + len(self)],
            other._keys[other._start : other._start + len(other)],
        )

    def _selected_pairs(
        self, other: "UnitRows", rows: np.ndarray, columns: np.ndarray
    ) -> np.ndarray:
        """Canonical refinement with a dimension-aware temporary-vector bound."""
        result = np.empty(len(rows), dtype=np.float64)
        size = max(1, SCORE_BLOCK_BYTES // (32 * max(1, self._shape[1])))
        left_values, right_values = self.values, other.values
        shared = self._data is other._data
        own_ids, peer_ids = self._identity_ids, other._identity_ids
        for start in range(0, len(rows), size):
            left, right = rows[start : start + size], columns[start : start + size]
            if shared:
                a_ids, b_ids = own_ids[left], peer_ids[right]
                zero = (a_ids < 0) | (b_ids < 0)
                same = (a_ids == b_ids) & ~zero
                target = result[start : start + len(left)]
                target[zero], target[same] = 0.0, 1.0
                unknown = ~(zero | same)
                target[unknown] = _paired_scores(
                    left_values[left[unknown]],
                    right_values[right[unknown]],
                    (),
                    (),
                    (a_ids[unknown], b_ids[unknown]),
                )
            else:
                result[start : start + size] = _paired_scores(
                    left_values[left],
                    right_values[right],
                    [self._keys[self._start + int(i)] for i in left],
                    [other._keys[other._start + int(j)] for j in right],
                )
        return result

    def _estimate(self, other: "UnitRows", *, exact: np.ndarray | None = None) -> np.ndarray:
        self._compatible(other)
        if exact is None:
            result: np.ndarray = self.values @ other.values.T
            np.clip(result, -1.0, 1.0, out=result)
            self._identical(other, result)
            return result
        result = np.empty((len(self), len(other)), dtype=np.float64)
        self._identical(other, result, exact)
        if exact.all():
            return result
        known = result[exact]
        np.matmul(self.values, other.values.T, out=result)
        np.clip(result, -1.0, 1.0, out=result)
        result[exact] = known
        return result

    @property
    def score_error(self) -> float:
        """Absolute enclosure of BLAS versus canonical on prepared rows.

        Each component has magnitude <=1. For d terms sum(abs(a*b))<=d;
        either binary64 reduction has at most 2d rounded operations along a
        dependency path. Combined error <=2*gamma(2d)*d. The additive normal
        minimum term covers underflow/flush-to-zero. Clipping is 1-Lipschitz.
        Both paths apply exactly the same identity and zero corrections.
        """
        dimension = self._shape[1]
        return min(
            2.0,
            math.nextafter(2 * _gamma(2 * dimension) * dimension + 4 * dimension * _TINY, math.inf),
        )

    def _compare_block(
        self, other: "UnitRows", threshold: float, inclusive: bool, work: SimilarityWork | None
    ) -> np.ndarray:
        exact = np.zeros((len(self), len(other)), dtype=np.bool_)
        estimates = self._estimate(other, exact=exact)
        if exact.all():
            if work is not None:
                work.blocks += 1
            return estimates >= threshold if inclusive else estimates > threshold
        error = self.score_error
        low = np.nextafter(estimates - error, -np.inf)
        high = np.nextafter(estimates + error, np.inf)
        result = low >= threshold if inclusive else low > threshold
        uncertain = ~(result | (high < threshold if inclusive else high <= threshold))
        uncertain &= ~exact
        result[exact] = estimates[exact] >= threshold if inclusive else estimates[exact] > threshold
        i, j = np.nonzero(uncertain)
        refined = len(i)
        if len(i):
            if len(i) > max(1, SCORE_BLOCK_BYTES // (16 * max(1, self._shape[1]))):
                # A dense ambiguous tile is cheaper and smaller to recompute
                # directly than to materialize one D-dimensional row per cell.
                canonical = self.cosine(other)
                result[uncertain] = (
                    canonical[uncertain] >= threshold
                    if inclusive
                    else canonical[uncertain] > threshold
                )
                refined = estimates.size
            else:
                scores = self._selected_pairs(other, i, j)
                result[i, j] = scores >= threshold if inclusive else scores > threshold
        if work is not None:
            work.fast_pairs += estimates.size
            work.refined_pairs += refined
            work.blocks += 1
        return result

    def compare(
        self,
        other: "UnitRows",
        threshold: float,
        *,
        inclusive: bool = True,
        work: SimilarityWork | None = None,
    ) -> np.ndarray:
        """Certified canonical >=/> decisions, using bounded score tiles."""
        self._compatible(other)
        threshold = _threshold(threshold)
        result = np.empty((len(self), len(other)), dtype=np.bool_)
        size = max(1, int(math.sqrt(SCORE_BLOCK_BYTES // 8)))
        for start in range(0, len(self), size):
            for column in range(0, len(other), size):
                a = self._view(start, min(start + size, len(self)))
                b = other._view(column, min(column + size, len(other)))
                result[start : start + len(a), column : column + len(b)] = a._compare_block(
                    b, threshold, inclusive, work
                )
        return result

    def any_matches(
        self, other: "UnitRows", threshold: float, *, work: SimilarityWork | None = None
    ) -> np.ndarray:
        """One decision per query row; stop history work once a row matches."""
        self._compatible(other)
        threshold = _threshold(threshold)
        found = np.zeros(len(self), dtype=np.bool_)
        size = max(1, int(math.sqrt(SCORE_BLOCK_BYTES // 8)))
        for start in range(0, len(self), size):
            a = self._view(start, min(start + size, len(self)))
            for column in range(0, len(other), size):
                if found[start : start + len(a)].all():
                    break
                b = other._view(column, min(column + size, len(other)))
                found[start : start + len(a)] |= a._compare_block(b, threshold, True, work).any(
                    axis=1
                )
        return found

    def matching_pairs(
        self, threshold: float, *, inclusive: bool = True, work: SimilarityWork | None = None
    ) -> Iterator[tuple[int, int]]:
        """Unique i<j matches in row-major order, without a full score matrix."""
        threshold = _threshold(threshold)
        rows = max(1, SCORE_BLOCK_BYTES // (8 * max(1, len(self))))
        for start in range(0, len(self), rows):
            stop = min(start + rows, len(self))
            right = self._view(start + 1, len(self))
            matches = self._view(start, stop).compare(
                right, threshold, inclusive=inclusive, work=work
            )
            for offset, row in enumerate(matches):
                for column in np.flatnonzero(row[offset:]):
                    yield start + offset, start + 1 + offset + int(column)

    def scored_matching_pairs(
        self, threshold: float, *, inclusive: bool = True, work: SimilarityWork | None = None
    ) -> Iterator[tuple[int, int, float]]:
        """Stream canonical scores for matches, with bounded pair refinement."""
        size = max(1, SCORE_BLOCK_BYTES // (32 * max(1, self._shape[1])))
        pending: list[tuple[int, int]] = []

        def scored() -> Iterator[tuple[int, int, float]]:
            rows = np.fromiter((i for i, _j in pending), dtype=np.intp)
            columns = np.fromiter((j for _i, j in pending), dtype=np.intp)
            scores = self._selected_pairs(self, rows, columns)
            if work is not None:
                work.refined_pairs += len(pending)
            yield from ((i, j, float(score)) for (i, j), score in zip(pending, scores, strict=True))

        for pair in self.matching_pairs(threshold, inclusive=inclusive, work=work):
            pending.append(pair)
            if len(pending) == size:
                yield from scored()
                pending.clear()
        if pending:
            yield from scored()

    @staticmethod
    def _stable_top(scores: np.ndarray, count: int) -> np.ndarray:
        """Exact top-k positions; only sort the winning frontier, preserving ties."""
        if len(scores) <= 2 * count:
            return np.argsort(-scores, kind="stable")[:count]
        cutoff = np.partition(scores, len(scores) - count)[len(scores) - count]
        above = np.flatnonzero(scores > cutoff)
        equal = np.flatnonzero(scores == cutoff)[: count - len(above)]
        chosen = np.concatenate((above, equal))
        return np.asarray(chosen[np.lexsort((chosen, -scores[chosen]))])

    def _nearest_blocks(
        self, queries: "UnitRows", count: int, work: SimilarityWork | None
    ) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        self._compatible(queries)
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("neighbour count must be an integer")
        count = min(max(0, count), len(self))
        query_rows = max(1, min(len(queries), 128, SCORE_BLOCK_BYTES // 8))
        columns = max(1, SCORE_BLOCK_BYTES // (8 * query_rows))
        for start in range(0, len(queries), query_rows):
            query = queries._view(start, min(start + query_rows, len(queries)))
            best_scores = np.full((len(query), count), -np.inf)
            best_indices = np.full((len(query), count), len(self), dtype=np.intp)
            if count:
                for column in range(0, len(self), columns):
                    peers = self._view(column, min(column + columns, len(self)))
                    exact = np.zeros((len(query), len(peers)), dtype=np.bool_)
                    estimates = query._estimate(peers, exact=exact)
                    local_count = min(count, len(peers))
                    pivot = np.partition(estimates, len(peers) - local_count, axis=1)[
                        :, len(peers) - local_count
                    ]
                    # The uniform enclosure is monotone: partition its centre,
                    # then bound just the row's kth value instead of a full lower matrix.
                    cutoff = np.nextafter(pivot - self.score_error, -np.inf)
                    upper = np.nextafter(estimates + self.score_error, np.inf)
                    np.minimum(upper, 1.0, out=upper)
                    upper[exact] = estimates[exact]
                    possible = upper >= cutoff[:, None]
                    # All previous blocks have smaller row indexes. A later exact
                    # tie cannot replace the current kth winner, hence strict >.
                    possible &= upper > best_scores[:, -1, None]
                    rows, candidates = np.nonzero(possible)
                    scores = estimates[rows, candidates]
                    refine = ~exact[rows, candidates]
                    scores[refine] = query._selected_pairs(peers, rows[refine], candidates[refine])
                    ends = np.searchsorted(rows, np.arange(len(query) + 1))
                    for offset in np.flatnonzero(ends[1:] > ends[:-1]):
                        first, stop = int(ends[offset]), int(ends[offset + 1])
                        order = self._stable_top(scores[first:stop], local_count) + first
                        merged_scores = np.concatenate((best_scores[offset], scores[order]))
                        merged_indices = np.concatenate(
                            (best_indices[offset], column + candidates[order])
                        )
                        winners = np.lexsort((merged_indices, -merged_scores))[:count]
                        best_scores[offset] = merged_scores[winners]
                        best_indices[offset] = merged_indices[winners]
                    if work is not None:
                        work.refined_pairs += int(refine.sum())
                        work.fast_pairs += 0 if exact.all() else estimates.size
                        work.blocks += 1
            yield best_indices, best_scores

    def nearest(
        self, queries: "UnitRows", count: int, *, work: SimilarityWork | None = None
    ) -> list[list[tuple[int, float]]]:
        """Batched canonical top-k, stable ties, with certified global pruning.

        Exact identities/zeros need no dot-product refinement. Other candidates
        whose upper bounds can beat the retained kth score are canonically scored.
        There is no approximate cutoff, including for a completely tied frontier.
        """
        return [
            [(int(i), float(score)) for i, score in zip(indices, scores, strict=True)]
            for block_indices, block_scores in self._nearest_blocks(queries, count, work)
            for indices, scores in zip(block_indices, block_scores, strict=True)
        ]

    def nearest_indices(
        self, queries: "UnitRows", count: int, *, work: SimilarityWork | None = None
    ) -> np.ndarray:
        """Canonical top-k indices without materializing Python score tuples."""
        result = None
        offset = 0
        for indices, _scores in self._nearest_blocks(queries, count, work):
            if result is None:
                result = np.empty((len(queries), indices.shape[1]), dtype=np.intp)
            result[offset : offset + len(indices)] = indices
            offset += len(indices)
        if result is None:
            return np.empty((0, min(max(0, count), len(self))), dtype=np.intp)
        return result

    def mean_similarity(self, other: "UnitRows | None" = None) -> float:
        """Canonical nonnegative mean: i<j within, or all cross pairs.

        Uses fsum and bounded score strips. Empty comparison populations have
        mean zero. Nonnegative projection preserves the VaultContext contract.
        """
        peer = self if other is None else other
        self._compatible(peer)
        count = len(self) * (len(self) - 1) // 2 if other is None else len(self) * len(peer)
        if not count:
            return 0.0

        def values() -> Iterator[float]:
            # Row-major traversal keeps canonical fsum independent of tiles,
            # including collections wider than a single score-tile budget.
            columns = max(1, SCORE_BLOCK_BYTES // 8)
            for row in range(len(self)):
                for column in range(row + 1 if other is None else 0, len(peer), columns):
                    block = self._view(row, row + 1).cosine(
                        peer._view(column, min(column + columns, len(peer)))
                    )
                    np.clip(block, 0.0, 1.0, out=block)
                    yield from (float(value) for value in block[0])

        return math.fsum(values()) / count

    def mean_compare(
        self,
        threshold: float,
        other: "UnitRows | None" = None,
        *,
        inclusive: bool = True,
        work: SimilarityWork | None = None,
    ) -> bool:
        """Certified nonnegative mean >=/>; ambiguous means use canonical fsum."""
        threshold = _threshold(threshold)
        peer = self if other is None else other
        self._compatible(peer)
        count = len(self) * (len(self) - 1) // 2 if other is None else len(self) * len(peer)
        if not count:
            return 0.0 >= threshold if inclusive else 0.0 > threshold
        rows = max(1, min(len(self), 128, SCORE_BLOCK_BYTES // 8))
        columns = max(1, SCORE_BLOCK_BYTES // (8 * rows))
        total = 0.0
        for start in range(0, len(self), rows):
            stop = min(start + rows, len(self))
            for column in range(start + 1 if other is None else 0, len(peer), columns):
                block = self._view(start, stop)._estimate(
                    peer._view(column, min(column + columns, len(peer)))
                )
                np.clip(block, 0.0, 1.0, out=block)
                for offset, row in enumerate(block):
                    skip = max(0, start + offset + 1 - column) if other is None else 0
                    total += float(row[skip:].sum())
                if work is not None:
                    work.fast_pairs += block.size
                    work.blocks += 1
        value = total / count
        error = math.nextafter(
            self.score_error + 2 * _gamma(2 * count) + 4 * count * _TINY, math.inf
        )
        low, high = (
            math.nextafter(value - error, -math.inf),
            math.nextafter(value + error, math.inf),
        )
        if low >= threshold if inclusive else low > threshold:
            return True
        if high < threshold if inclusive else high <= threshold:
            return False
        if work is not None:
            work.refined_pairs += count
        reference = self.mean_similarity(other)
        return reference >= threshold if inclusive else reference > threshold


def cosine_matrix(left: np.ndarray, right: np.ndarray | None = None) -> np.ndarray:
    """Canonical compatibility API; new decision callers use prepared methods."""
    a = UnitRows(left)
    return a.cosine(a if right is None else UnitRows(right))
