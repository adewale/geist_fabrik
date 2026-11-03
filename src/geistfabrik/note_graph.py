"""Canonical session graph with dense note IDs and flat adjacency arrays."""

from __future__ import annotations

from array import array
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass

from .models import Note


def _flatten(rows: Sequence[Sequence[int]]) -> tuple[array[int], array[int]]:
    offsets = array("Q", [0])
    edges = array("Q")
    for row in rows:
        edges.extend(row)
        offsets.append(len(edges))
    return offsets, edges


@dataclass(frozen=True)
class NoteGraph:
    """IDs follow note order; directed rows retain link/source traversal order."""

    notes: tuple[Note, ...]
    ids: dict[str, int]
    outgoing_offsets: array[int]
    outgoing: array[int]
    incoming_offsets: array[int]
    incoming: array[int]
    neighbour_offsets: array[int]
    neighbours: array[int]

    @classmethod
    def build(cls, notes: list[Note], outgoing: list[list[int]]) -> NoteGraph:
        incoming: list[list[int]] = [[] for _ in notes]
        for source, targets in enumerate(outgoing):
            for target in targets:
                incoming[target].append(source)
        neighbours = [sorted(set(a) | set(b)) for a, b in zip(outgoing, incoming, strict=True)]
        return cls(
            tuple(notes),
            {note.path: i for i, note in enumerate(notes)},
            *_flatten(outgoing),
            *_flatten(incoming),
            *_flatten(neighbours),
        )

    def connected(self, a: int, b: int) -> bool:
        """Test adjacency without strings, hashing, resolution, or allocation."""
        start, stop = self.neighbour_offsets[a], self.neighbour_offsets[a + 1]
        position = bisect_left(self.neighbours, b, start, stop)
        return position < stop and self.neighbours[position] == b

    def isolated_members(self, members: list[int], marks: list[int], generation: int) -> list[int]:
        """Inspect real edges rather than all pairs in a phrase's posting list."""
        for member in members:
            marks[member] = generation
        return [
            member
            for member in members
            if not any(
                marks[self.neighbours[position]] == generation
                for position in range(
                    self.neighbour_offsets[member], self.neighbour_offsets[member + 1]
                )
            )
        ]
