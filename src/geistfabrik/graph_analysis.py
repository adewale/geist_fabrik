"""Graph analysis abstractions for GeistFabrik.

Provides unified graph pattern detection for note link structures.
Supports finding hubs, orphans, bridges, paths, and connected components.

Replaces ad-hoc graph traversal code duplicated across bridge_builder,
island_hopper, hidden_hub, and other geists.
"""

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext


def _are_linked(a: "Note", b: "Note") -> bool:
    """True if either note links directly to the other.

    Uses the canonical link-target resolution (models.link_target_forms);
    previously this module matched titles only, so path-form links were
    invisible to bridge detection.
    """
    a_forms = a.link_target_forms()
    b_forms = b.link_target_forms()
    return any(link.target in b_forms for link in a.links) or any(
        link.target in a_forms for link in b.links
    )


class GraphPatternFinder:
    """Unified graph pattern detection for note link structures.

    Provides high-level operations for finding structural patterns in the
    note graph: hubs, orphans, bridges, paths, and connected components.

    Example:
        >>> finder = GraphPatternFinder(vault)
        >>> hubs = finder.find_hubs(min_backlinks=10)
        >>> orphans = finder.find_orphans()
        >>> bridges = finder.find_bridges(min_similarity=0.6)
    """

    def __init__(self, vault: "VaultContext"):
        """Initialize graph pattern finder.

        Args:
            vault: VaultContext for note and link access
        """
        self.vault = vault

    def find_hubs(self, min_backlinks: int = 10) -> list["Note"]:
        """Find notes with many incoming links.

        A hub is a note that many other notes link to, indicating it's
        a central reference or concept in the vault.

        Args:
            min_backlinks: Minimum number of incoming links to be a hub

        Returns:
            List of hub notes sorted by backlink count (descending)
        """
        notes = self.vault.notes()

        # Count backlinks once per note (the sort below reuses these counts
        # instead of re-querying backlinks() inside the sort key).
        counted = []
        for note in notes:
            backlink_count = len(self.vault.backlinks(note))
            if backlink_count >= min_backlinks:
                counted.append((note, backlink_count))

        # Sort by backlink count (descending)
        counted.sort(key=lambda pair: pair[1], reverse=True)

        return [note for note, _ in counted]

    def find_orphans(self) -> list["Note"]:
        """Find notes with no incoming or outgoing links.

        Orphans are isolated notes that aren't connected to the rest
        of the vault through links.

        Returns:
            List of orphan notes
        """
        notes = self.vault.notes()
        orphans = []

        for note in notes:
            backlinks = self.vault.backlinks(note)
            outgoing = self.vault.outgoing_links(note)

            if len(backlinks) == 0 and len(outgoing) == 0:
                orphans.append(note)

        return orphans

    def find_bridges(self, min_similarity: float = 0.6) -> list[tuple["Note", "Note", "Note"]]:
        """Find (note_a, bridge, note_b) where bridge connects high-sim unlinked notes.

        A bridge is a note that links to (or is linked by) two other notes
        that are semantically similar but not directly linked to each other.

        Args:
            min_similarity: Minimum similarity for unlinked notes

        Returns:
            List of (note_a, bridge_note, note_b) tuples
        """
        notes = self.vault.notes()
        bridges = []

        for bridge_candidate in notes:
            # Get all notes connected to this candidate (both directions)
            connected = set()

            # Add outgoing links
            outgoing = self.vault.outgoing_links(bridge_candidate)
            connected.update(outgoing)

            # Add backlinks
            backlinks = self.vault.backlinks(bridge_candidate)
            connected.update(backlinks)

            if len(connected) < 2:
                continue  # Need at least 2 connections to bridge

            connected_list = list(connected)

            # One vectorised similarity matrix for the whole neighbourhood
            # instead of O(degree^2) individual similarity() calls - for a
            # super-hub with degree 200 that is one matrix op vs ~20k calls.
            sim_matrix = self.vault.batch_similarity(connected_list, connected_list)

            # Check all pairs of connected notes
            for i, note_a in enumerate(connected_list):
                for j in range(i + 1, len(connected_list)):
                    note_b = connected_list[j]
                    # Cheap link check first, similarity lookup second
                    if _are_linked(note_a, note_b):
                        continue
                    if float(sim_matrix[i, j]) >= min_similarity:
                        # Found a bridge!
                        bridges.append((note_a, bridge_candidate, note_b))

        return bridges

    def shortest_path(self, source: "Note", target: "Note") -> list["Note"] | None:
        """Find shortest path from source to target via links.

        Uses breadth-first search to find the shortest path through
        the link graph (treating links as directed edges).

        Args:
            source: Starting note
            target: Destination note

        Returns:
            List of notes forming path from source to target (inclusive),
            or None if no path exists
        """
        if source.path == target.path:
            return [source]

        # BFS for shortest path
        queue: deque[tuple[Note, list[Note]]] = deque([(source, [source])])
        visited: set[str] = {source.path}

        while queue:
            current, path = queue.popleft()

            # Get outgoing links
            outgoing = self.vault.outgoing_links(current)

            for next_note in outgoing:
                if next_note.path == target.path:
                    return path + [next_note]

                if next_note.path not in visited:
                    visited.add(next_note.path)
                    queue.append((next_note, path + [next_note]))

        return None  # No path found

    def k_hop_neighbourhood(self, note: "Note", k: int) -> list["Note"]:
        """Get all notes within k link hops.

        Uses breadth-first traversal to find all notes reachable
        within k link hops (following outgoing links).

        Args:
            note: Starting note
            k: Maximum number of hops

        Returns:
            List of notes within k hops (excludes source note)
        """
        if k <= 0:
            return []

        visited: set[str] = {note.path}
        current_level = [note]

        for _ in range(k):
            next_level: list[Note] = []

            for current in current_level:
                outgoing = self.vault.outgoing_links(current)

                for next_note in outgoing:
                    if next_note.path not in visited:
                        visited.add(next_note.path)
                        next_level.append(next_note)

            current_level = next_level

        # Return all visited except source
        all_notes = self.vault.notes()
        return [n for n in all_notes if n.path in visited and n.path != note.path]

    def find_connected_components(self) -> list[list["Note"]]:
        """Find disconnected subgraphs (connected components).

        Uses undirected graph interpretation (links work both ways)
        to find groups of notes that are connected to each other but
        isolated from other groups.

        Returns:
            List of connected components (each is a list of notes)
        """
        notes = self.vault.notes()
        visited: set[str] = set()
        components: list[list[Note]] = []

        for note in notes:
            if note.path in visited:
                continue

            # BFS to find all notes in this component
            component: list[Note] = []
            queue: deque[Note] = deque([note])
            component_visited: set[str] = {note.path}

            while queue:
                current = queue.popleft()
                component.append(current)
                visited.add(current.path)

                # Add both outgoing links and backlinks (undirected)
                connected = set()
                connected.update(self.vault.outgoing_links(current))
                connected.update(self.vault.backlinks(current))

                for next_note in connected:
                    if next_note.path not in component_visited:
                        component_visited.add(next_note.path)
                        queue.append(next_note)

            components.append(component)

        return components

    def detect_structural_holes(
        self, min_similarity: float = 0.6, candidate_limit: int | None = 200
    ) -> list[tuple["Note", "Note"]]:
        """Find high-similarity pairs in different connected components.

        A structural hole exists when two notes are semantically similar
        but belong to disconnected parts of the vault graph. These represent
        opportunities for cross-pollination.

        Cost is O(C^2) over the candidate set, computed as one vectorised
        similarity matrix. By default candidates are capped (deterministic
        sample via vault.sample) so a large vault cannot blow the geist
        timeout; pass candidate_limit=None for an exhaustive scan.

        Args:
            min_similarity: Minimum similarity for structural holes
            candidate_limit: Max notes to consider (None = all notes)

        Returns:
            List of (note_a, note_b) pairs forming structural holes
        """
        # Get connected components
        components = self.find_connected_components()

        if len(components) < 2:
            return []  # Need at least 2 components

        # Build component membership lookup
        note_to_component: dict[str, int] = {}
        for i, component in enumerate(components):
            for note in component:
                note_to_component[note.path] = i

        # Bound the candidate set (sample, don't rank - deterministic per session)
        candidates = self.vault.notes()
        if candidate_limit is not None and len(candidates) > candidate_limit:
            candidates = self.vault.sample(candidates, candidate_limit)

        # One vectorised matrix instead of O(C^2) individual similarity calls
        sim_matrix = self.vault.batch_similarity(candidates, candidates)

        structural_holes: list[tuple[Note, Note]] = []
        for i, note_a in enumerate(candidates):
            comp_a = note_to_component.get(note_a.path)
            if comp_a is None:
                continue
            for j in range(i + 1, len(candidates)):
                note_b = candidates[j]
                comp_b = note_to_component.get(note_b.path)

                if comp_b is not None and comp_a != comp_b:
                    # Different components - check similarity (matrix lookup)
                    if float(sim_matrix[i, j]) >= min_similarity:
                        structural_holes.append((note_a, note_b))

        return structural_holes
