"""Congruence Mirror - reveals explicit and implicit structure in your vault.

Shows four types of relationships between semantic similarity and linking:
- Explicit: Semantically similar + linked (question)
- Implicit: Semantically similar + not linked (statement)
- Connected: Semantically distant + linked (question)
- Detached: Semantically distant + not linked (statement)
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Generate 4 provocations about vault structure.

    Examines relationship between semantic similarity and linking:

    - Explicit: Semantically similar + linked (asks question)
    - Implicit: Semantically similar + not linked (statement)
    - Connected: Semantically distant + linked (asks question)
    - Detached: Semantically distant + not linked (statement)

    Returns:
        Four suggestions, one per quadrant (when examples exist)
    """
    from geistfabrik import Suggestion

    suggestions = []

    # Find examples from each quadrant
    explicit = find_explicit_pair(vault)
    implicit = find_implicit_pair(vault)
    connected = find_connected_pair(vault)
    detached = find_detached_pair(vault)

    # Explicit: Question
    if explicit:
        suggestions.append(
            Suggestion(
                text=f"[[{explicit[0].title}]] and [[{explicit[1].title}]] are "
                f"explicitly linked—what's the third point of this triangle?",
                notes=[explicit[0].title, explicit[1].title],
                geist_id="congruence_mirror",
            )
        )

    # Implicit: Statement
    if implicit:
        suggestions.append(
            Suggestion(
                text=f"[[{implicit[0].title}]] and [[{implicit[1].title}]] relate implicitly.",
                notes=[implicit[0].title, implicit[1].title],
                geist_id="congruence_mirror",
            )
        )

    # Connected: Question
    if connected:
        suggestions.append(
            Suggestion(
                text=f"[[{connected[0].title}]] and [[{connected[1].title}]] are "
                f"connected despite distance. What connects them?",
                notes=[connected[0].title, connected[1].title],
                geist_id="congruence_mirror",
            )
        )

    # Detached: Statement
    if detached:
        suggestions.append(
            Suggestion(
                text=f"[[{detached[0].title}]] and [[{detached[1].title}]] are detached.",
                notes=[detached[0].title, detached[1].title],
                geist_id="congruence_mirror",
            )
        )

    return suggestions


def find_explicit_pair(vault: "VaultContext") -> tuple["Note", "Note"] | None:
    """Find pair that is semantically similar AND linked (EXPLICIT).

    Args:
        vault: VaultContext with notes and embeddings

    Returns:
        Tuple of (note_a, note_b) with highest similarity, or None
    """
    candidates = []
    processed = set()

    all_notes = vault.notes()
    for note in all_notes:
        for link in note.links:
            target = vault.resolve_link_target(link.target)
            if not target:
                continue

            pair_key = tuple(sorted([note.path, target.path]))
            if pair_key in processed:
                continue
            processed.add(pair_key)

            similarity = vault.similarity(note, target)

            # High similarity + linked = explicit
            if similarity > 0.65:
                candidates.append((note, target, similarity))

    if not candidates:
        return None

    # Return most similar explicit pair
    candidates.sort(key=lambda x: x[2], reverse=True)
    return (candidates[0][0], candidates[0][1])


def find_implicit_pair(vault: "VaultContext") -> tuple["Note", "Note"] | None:
    """Find pair that is semantically similar but NOT linked (IMPLICIT).

    Args:
        vault: VaultContext with notes and embeddings

    Returns:
        Tuple of (note_a, note_b) with highest similarity, or None
    """
    candidates = []
    processed = set()

    all_notes = vault.notes()
    for note in all_notes:
        neighbors = vault.neighbours(note, k=20)

        for neighbor in neighbors:
            pair_key = tuple(sorted([note.path, neighbor.path]))
            if pair_key in processed:
                continue
            processed.add(pair_key)

            similarity = vault.similarity(note, neighbor)

            # Check if linked (using helper - links_between is already bidirectional)
            is_linked = vault.has_link(note, neighbor)

            # High similarity + not linked = implicit
            if similarity > 0.70 and not is_linked:
                candidates.append((note, neighbor, similarity))

    if not candidates:
        return None

    # Return most similar implicit pair
    candidates.sort(key=lambda x: x[2], reverse=True)
    return (candidates[0][0], candidates[0][1])


def find_connected_pair(vault: "VaultContext") -> tuple["Note", "Note"] | None:
    """Find pair that is semantically distant but linked (CONNECTED).

    Connected despite distance - the link bridges semantic gap.

    Args:
        vault: VaultContext with notes and embeddings

    Returns:
        Tuple of (note_a, note_b) with lowest similarity, or None
    """
    candidates = []
    processed = set()

    all_notes = vault.notes()
    for note in all_notes:
        for link in note.links:
            target = vault.resolve_link_target(link.target)
            if not target:
                continue

            pair_key = tuple(sorted([note.path, target.path]))
            if pair_key in processed:
                continue
            processed.add(pair_key)

            similarity = vault.similarity(note, target)

            # Low similarity + linked = connected despite distance
            if similarity < 0.45:
                candidates.append((note, target, similarity))

    if not candidates:
        return None

    # Return most distant connected pair (biggest bridge)
    candidates.sort(key=lambda x: x[2])
    return (candidates[0][0], candidates[0][1])


def find_detached_pair(vault: "VaultContext") -> tuple["Note", "Note"] | None:
    """Find pair that is semantically distant and NOT linked (DETACHED).

    Args:
        vault: VaultContext with notes and embeddings

    Returns:
        Tuple of (note_a, note_b) with lowest similarity, or None
    """
    all_notes = vault.notes()
    if len(all_notes) < 10:
        return None

    # Sample random pairs and find most distant unlinked pair
    max_attempts = 50
    candidates = []

    for _ in range(max_attempts):
        pair = vault.sample(all_notes, k=2)
        note_a, note_b = pair[0], pair[1]

        # Check if linked (using helper - links_between is already bidirectional)
        if vault.has_link(note_a, note_b):
            continue

        similarity = vault.similarity(note_a, note_b)

        # Low similarity + not linked = detached
        if similarity < 0.30:
            candidates.append((note_a, note_b, similarity))

    if not candidates:
        return None

    # Return most detached pair
    candidates.sort(key=lambda x: x[2])
    return (candidates[0][0], candidates[0][1])
