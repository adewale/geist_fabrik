"""Prepared directions, canonical scores and certified NumPy/BLAS decisions.

Canonical APIs retain fixed per-pair binary64 reductions. Decision APIs enclose
the canonical result and refine ambiguous cells; no arbitrary threshold epsilon
or approximate neighbour index changes the answer.
"""

import hashlib
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


def _paired_scores(
    left: np.ndarray,
    right: np.ndarray,
    left_keys: Sequence[bytes | None],
    right_keys: Sequence[bytes | None],
) -> np.ndarray:
    """One canonical pair kernel shared by paired and sparse refinement paths."""
    result: np.ndarray = np.einsum("ij,ij->i", left, right, optimize=False)
    np.clip(result, -1.0, 1.0, out=result)
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
    disposable metadata. A digest match alone never establishes vector identity.
    """

    _data: bytes = field(repr=False)
    _shape: tuple[int, int]
    _start: int
    _keys: tuple[bytes | None, ...] = field(repr=False)
    _identities: Mapping[bytes, tuple[tuple[int, ...], ...]] = field(repr=False)
    _zeros: tuple[int, ...] = field(repr=False)

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
        norms = np.sqrt(np.einsum("ij,ij->i", matrix, matrix, optimize=False))[:, None]
        matrix /= np.where(norms == 0, 1.0, norms)
        matrix[matrix == 0] = 0.0
        keys = tuple(
            hashlib.blake2b(row.tobytes(), digest_size=16).digest() if scales[i, 0] else None
            for i, row in enumerate(matrix)
        )
        self._install(matrix, keys)

    def _install(self, matrix: np.ndarray, keys: tuple[bytes | None, ...]) -> None:
        groups: dict[bytes, list[list[int]]] = {}
        for i, key in enumerate(keys):
            if key is None:
                continue
            bucket = groups.setdefault(key, [])
            for group in bucket:
                if np.array_equal(matrix[i], matrix[group[0]]):
                    group.append(i)
                    break
            else:
                bucket.append([i])
        object.__setattr__(self, "_data", matrix.tobytes())
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
        for name in ("_data", "_keys", "_identities", "_zeros"):
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

    def _identical(self, other: "UnitRows", result: np.ndarray) -> None:
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
        zeros_a = [i - self._start for i in self._zeros if self._start <= i < left_end]
        zeros_b = [j - other._start for j in other._zeros if other._start <= j < right_end]
        result[zeros_a, :] = 0.0
        result[:, zeros_b] = 0.0

    def cosine(self, other: "UnitRows") -> np.ndarray:
        """Canonical scores, identical to scalar and chunked calls."""
        self._compatible(other)
        result: np.ndarray = np.einsum("ik,jk->ij", self.values, other.values, optimize=False)
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
        for start in range(0, len(rows), size):
            left, right = rows[start : start + size], columns[start : start + size]
            result[start : start + size] = _paired_scores(
                self.values[left],
                other.values[right],
                [self._keys[self._start + int(i)] for i in left],
                [other._keys[other._start + int(j)] for j in right],
            )
        return result

    def _estimate(self, other: "UnitRows") -> np.ndarray:
        self._compatible(other)
        result: np.ndarray = self.values @ other.values.T
        np.clip(result, -1.0, 1.0, out=result)
        self._identical(other, result)
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
        estimates = self._estimate(other)
        error = self.score_error
        low = np.nextafter(estimates - error, -np.inf)
        high = np.nextafter(estimates + error, np.inf)
        result = low >= threshold if inclusive else low > threshold
        uncertain = ~(result | (high < threshold if inclusive else high <= threshold))
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

    def nearest(
        self, queries: "UnitRows", count: int, *, work: SimilarityWork | None = None
    ) -> list[list[tuple[int, float]]]:
        """Batched exact top-k; ties preserve collection row order.

        Keep every candidate whose upper enclosure reaches the kth lower
        enclosure. Canonical rescoring certifies selection and returned scores;
        a true tie can require all rows, never an arbitrary candidate cutoff.
        """
        self._compatible(queries)
        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError("neighbour count must be an integer")
        count = min(max(0, count), len(self))
        if not count:
            return [[] for _ in range(len(queries))]
        result: list[list[tuple[int, float]]] = []
        query_rows = max(1, min(len(queries), 128, SCORE_BLOCK_BYTES // 8))
        columns = max(1, SCORE_BLOCK_BYTES // (8 * query_rows))
        for start in range(0, len(queries), query_rows):
            query = queries._view(start, min(start + query_rows, len(queries)))
            keep: list[list[tuple[int, float]]] = [[] for _ in range(len(query))]
            for column in range(0, len(self), columns):
                peers = self._view(column, min(column + columns, len(self)))
                estimates = query._estimate(peers)
                error = self.score_error
                local_count = min(count, len(peers))
                lower = np.nextafter(estimates - error, -np.inf)
                kth = len(peers) - local_count
                cutoff = np.partition(lower, kth, axis=1)[:, kth]
                rows, candidates = np.nonzero(
                    np.nextafter(estimates + error, np.inf) >= cutoff[:, None]
                )
                # Certify all queries' candidates together, retaining O(tile)
                # score/index arrays and only dimension-bounded vector copies.
                scores = query._selected_pairs(peers, rows, candidates)
                ends = np.searchsorted(rows, np.arange(len(query) + 1))
                for offset in range(len(query)):
                    first, stop = int(ends[offset]), int(ends[offset + 1])
                    order = np.argsort(-scores[first:stop], kind="stable")[:local_count] + first
                    keep[offset].extend(
                        (column + int(candidates[i]), float(scores[i])) for i in order
                    )
                    keep[offset].sort(key=lambda item: (-item[1], item[0]))
                    del keep[offset][count:]
                if work is not None:
                    work.refined_pairs += len(candidates)
                if work is not None:
                    work.fast_pairs += estimates.size
                    work.blocks += 1
            result.extend(keep)
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
