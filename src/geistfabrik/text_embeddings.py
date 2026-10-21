"""Bounded exact-text embedding reuse shared by encoding and cluster labelling."""

import sys
from collections import OrderedDict
from collections.abc import Callable

import numpy as np


class TextEmbeddingCache:
    """LRU with immutable payloads, exact text keys and a retained-byte budget.

    The budget includes keys and entry payload/metadata; transient inputs,
    model allocations and the caller's requested output are separate. Oversized
    entries are returned but not retained. Returned arrays cannot alias cache data.
    """

    def __init__(self, max_bytes: int = 8 * 1024 * 1024) -> None:
        if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 0:
            raise ValueError("embedding cache budget must be a nonnegative integer")
        self._max_bytes = max_bytes
        self.retained_bytes = 0
        self.hits = 0
        self.misses = 0
        self._rows: OrderedDict[str, tuple[bytes, np.dtype, int, int]] = OrderedDict()
        self._identity: object = None

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    @max_bytes.setter
    def max_bytes(self, value: int) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("embedding cache budget must be a nonnegative integer")
        self._max_bytes = value
        while self._rows and self.retained_bytes > value:
            _key, (_blob, _dtype, _width, cost) = self._rows.popitem(last=False)
            self.retained_bytes -= cost

    def clear(self) -> None:
        """Release retained text/vector data without changing the budget."""
        self._rows.clear()
        self.retained_bytes = 0

    def encode(
        self,
        texts: list[str],
        encode: Callable[[list[str]], np.ndarray],
        *,
        identity: object = None,
    ) -> np.ndarray:
        """Batch only unique misses, preserving caller order and duplicate rows."""
        if identity != self._identity:
            self.clear()
            self._identity = identity
        if not texts:
            return np.array([])
        resolved: dict[str, np.ndarray] = {}
        missing: list[str] = []
        for text in dict.fromkeys(texts):
            cached = self._rows.get(text)
            if cached is None:
                missing.append(text)
                self.misses += 1
            else:
                blob, dtype, width, _cost = cached
                resolved[text] = np.frombuffer(blob, dtype=dtype, count=width)
                self._rows.move_to_end(text)
                self.hits += 1
        if missing:
            encoded = np.asarray(encode(missing))
            if encoded.ndim != 2 or len(encoded) != len(missing) or not np.isfinite(encoded).all():
                raise ValueError("encoder must return finite rows, one per input text")
            for text, row in zip(missing, encoded):
                blob = row.tobytes()
                # Conservative metadata allowance covers tuple, dtype, shape
                # and the OrderedDict link; keys are counted as Python strings.
                cost = sys.getsizeof(text) + sys.getsizeof(blob) + 256
                resolved[text] = np.frombuffer(blob, dtype=row.dtype, count=row.size)
                if cost <= self.max_bytes:
                    while self._rows and self.retained_bytes + cost > self.max_bytes:
                        _key, (_blob, _dtype, _width, evicted_cost) = self._rows.popitem(last=False)
                        self.retained_bytes -= evicted_cost
                    self._rows[text] = blob, row.dtype, row.size, cost
                    self.retained_bytes += cost
        return np.stack([resolved[text] for text in texts])
