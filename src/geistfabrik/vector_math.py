"""Canonical, scale-safe cosine arithmetic for semantic decisions.

Storage may be float32. Computation uses validated float64 unit directions,
one fixed reduction order, and exact identity for equal nonzero directions.
"""

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True, init=False)
class UnitRows:
    """Immutable finite unit directions and zero rows; array views are disposable."""

    _data: bytes = field(repr=False)
    _shape: tuple[int, int]
    keys: tuple[bytes | None, ...] = field(repr=False)

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
        # Scaling first preserves nonzero directions at subnormal/huge magnitudes.
        matrix /= np.where(scales == 0, 1.0, scales)
        norms = np.sqrt(np.einsum("ij,ij->i", matrix, matrix, optimize=False))[:, None]
        matrix /= np.where(norms == 0, 1.0, norms)
        matrix[matrix == 0] = 0.0  # One representation for signed zero.
        keys = tuple(row.tobytes() if scales[i, 0] else None for i, row in enumerate(matrix))
        # Bytes own the storage: callers cannot re-enable writes and stale keys.
        object.__setattr__(self, "_data", matrix.tobytes())
        object.__setattr__(self, "_shape", matrix.shape)
        object.__setattr__(self, "keys", keys)

    @property
    def values(self) -> np.ndarray:
        """A read-only view whose mutable NumPy metadata cannot alter this object."""
        return np.frombuffer(self._data, dtype=np.float64).reshape(self._shape)

    def cosine(self, other: "UnitRows") -> np.ndarray:
        """Compare directions independently of batch shape, with exact identity.

        Unoptimized einsum keeps the same per-pair reduction instead of choosing
        a different BLAS algorithm for scalar, chunked and matrix invocations.
        Row keys bound identity work to O((N+M)*dimensions), without an N*M*D
        equality array. Zero has similarity zero, including with itself.
        """
        if self._shape[1] != other._shape[1]:
            raise ValueError("embedding dimensions must match")
        result: np.ndarray = np.clip(
            np.einsum("ik,jk->ij", self.values, other.values, optimize=False), -1.0, 1.0
        )
        identities: dict[bytes, list[int]] = {}
        for j, key in enumerate(other.keys):
            if key is not None:
                identities.setdefault(key, []).append(j)
        for i, key in enumerate(self.keys):
            if key is not None and key in identities:
                result[i, identities[key]] = 1.0
        return result


def cosine_matrix(left: np.ndarray, right: np.ndarray | None = None) -> np.ndarray:
    """Validated canonical cosine for real row matrices; omitted right means self."""
    a = UnitRows(left)
    b = a if right is None else UnitRows(right)
    return a.cosine(b)
