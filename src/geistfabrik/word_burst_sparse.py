"""Compact, bounded preparation of exact weekly document-presence counts.

A sparse column owns NumPy integer arrays, not Python dictionaries per term.
Source presence is consumed in bounded batches; only weekly sufficient statistics
survive collection. Stable term IDs are mapped to a dense selected dictionary, so
sparse or very large persistent IDs cannot force a max-ID-sized allocation.
"""

import sqlite3
from array import array
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

import numpy as np
from numpy.typing import NDArray

from .lexical_presence import decode_presence, presence_terms

_SOURCE_BATCH_TERMS = 262_144
_SOURCE_BATCH_ROWS = 256


@dataclass(frozen=True)
class SparsePopulation:
    """CSC-style exact integer counts, preserving the original candidate order."""

    stable_ids: NDArray[np.uint64]
    order: NDArray[np.intp]
    indptr: NDArray[np.intp]
    bins: NDArray[np.intp]
    counts: NDArray[np.int64]

    def column(self, term_id: int) -> dict[int, int]:
        start, end = self.indptr[term_id : term_id + 2]
        return dict(
            zip(self.bins[start:end].tolist(), self.counts[start:end].tolist(), strict=True)
        )


def selected_presence(blob: bytes, stable_ids: NDArray[np.uint64]) -> NDArray[np.intp]:
    """Return positions of present IDs in a sorted selected dictionary."""
    return _selected(decode_presence(blob), stable_ids)


def _selected(source: NDArray[np.uint64], stable_ids: NDArray[np.uint64]) -> NDArray[np.intp]:
    if not stable_ids.size:
        return np.empty(0, dtype=np.intp)
    positions = np.searchsorted(stable_ids, source)
    within = positions < len(stable_ids)
    positions, source = positions[within], source[within]
    return np.asarray(positions[stable_ids[positions] == source], dtype=np.intp)


def _merge(
    old_ids: NDArray[np.intp],
    old_counts: NDArray[np.int64],
    sources: list[NDArray[np.intp]],
) -> tuple[NDArray[np.intp], NDArray[np.int64]]:
    if not sources:
        return old_ids, old_counts
    ids, counts = np.unique(np.concatenate(sources), return_counts=True)
    if not old_ids.size:
        return ids.astype(np.intp, copy=False), counts.astype(np.int64, copy=False)
    combined_ids = np.concatenate((old_ids, ids))
    combined_counts = np.concatenate((old_counts, counts)).astype(np.int64, copy=False)
    order = np.argsort(combined_ids, kind="stable")
    unique_ids, starts = np.unique(combined_ids[order], return_index=True)
    return unique_ids, np.add.reduceat(combined_counts[order], starts)


def collect_population(
    db: sqlite3.Connection,
    rows: Iterator[tuple[str, str, bytes, str]],
    *,
    first: date,
    weeks: int,
    min_documents: int,
) -> SparsePopulation:
    """Read each selected body once and discard document presence after each batch.

    ``min_documents`` is the conservative current-text document-frequency bound;
    observed history passes zero because the current corpus cannot bound history.
    Candidate traversal remains first source path, then lexical term ordering.
    """
    lexical_ids = array(
        "Q", (term_id for term_id, _ in presence_terms(db, min_documents=min_documents))
    )
    lexical = np.frombuffer(lexical_ids, dtype=np.uint64)
    lexical_rank = np.argsort(lexical, kind="stable")
    stable_ids = lexical[lexical_rank]
    first_source = np.full(len(stable_ids), -1, dtype=np.intp)
    weekly_ids = [np.empty(0, dtype=np.intp) for _ in range(weeks)]
    weekly_counts = [np.empty(0, dtype=np.int64) for _ in range(weeks)]
    pending: list[list[NDArray[np.intp]]] = [[] for _ in range(weeks)]
    seen: set[tuple[int, str]] = set()

    def flush() -> None:
        for i in range(weeks):
            weekly_ids[i], weekly_counts[i] = _merge(weekly_ids[i], weekly_counts[i], pending[i])
            pending[i].clear()

    buffered = 0
    buffered_rows = 0
    for ordinal, (_, stamp, blob, body) in enumerate(rows):
        i = (date.fromisoformat(stamp) - first).days // 7
        if not 0 <= i < weeks or (i, body) in seen:
            continue
        seen.add((i, body))
        selected = selected_presence(blob, stable_ids)
        unseen = selected[first_source[selected] < 0]
        first_source[unseen] = ordinal
        if selected.size:
            pending[i].append(selected)
            buffered += selected.size
            buffered_rows += 1
        if buffered >= _SOURCE_BATCH_TERMS or buffered_rows >= _SOURCE_BATCH_ROWS:
            flush()
            buffered = 0
            buffered_rows = 0
    flush()
    columns = np.flatnonzero(first_source >= 0)
    order = columns[np.lexsort((lexical_rank[columns], first_source[columns]))]
    # Concatenate compact weekly sufficient statistics once, then stable-sort
    # by column. Every column's bin indices remain ascending for exact reuse.
    column_ids = np.concatenate(weekly_ids)
    counts = np.concatenate(weekly_counts)
    bins = np.repeat(np.arange(weeks, dtype=np.intp), [len(ids) for ids in weekly_ids])
    positions = np.argsort(column_ids, kind="stable")
    sorted_columns = column_ids[positions]
    indptr = np.searchsorted(sorted_columns, np.arange(len(stable_ids) + 1))
    return SparsePopulation(stable_ids, order, indptr, bins[positions], counts[positions])
