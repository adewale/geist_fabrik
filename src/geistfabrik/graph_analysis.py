"""Graph analysis abstractions for GeistFabrik.

Provides unified graph pattern detection for note link structures.
Supports finding hubs, orphans, bridges, paths, and connected components.

Replaces ad-hoc graph traversal code duplicated across bridge_builder,
island_hopper, hidden_hub, and other geists.
"""

from collections import deque
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext


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

    def find_hubs(self, min_backlinks: int = 10) -> List["Note"]:
        """Find notes with many incoming links.

        A hub is a note that many other notes link to, indicating it's
        a central reference or concept in the vault.

        Args:
            min_backlinks: Minimum number of incoming links to be a hub

        Returns:
            List of hub notes sorted by backlink count (descending)
        """
        notes = self.vault.notes()
        hubs = []

        for note in notes:
            backlinks = self.vault.backlinks(note)
            if len(backlinks) >= min_backlinks:
                hubs.append(note)

        # Sort by backlink count (descending)
        hubs.sort(key=lambda n: len(self.vault.backlinks(n)), reverse=True)

        return hubs

    def find_orphans(self) -> List["Note"]:
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

    def find_bridges(
        self, min_similarity: float = 0.6
    ) -> List[Tuple["Note", "Note", "Note"]]:
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

            # Check all pairs of connected notes
            for i, note_a in enumerate(connected_list):
                for note_b in connected_list[i + 1 :]:
                    # Check if note_a and note_b are NOT directly linked
                    a_links = {link.target for link in note_a.links}
                    b_links = {link.target for link in note_b.links}

                    if note_b.title not in a_links and note_a.title not in b_links:
                        # They're unlinked - check similarity
                        sim = self.vault.similarity(note_a, note_b)
                        if sim >= min_similarity:
                            # Found a bridge!
                            bridges.append((note_a, bridge_candidate, note_b))

        return bridges

    def shortest_path(
        self, source: "Note", target: "Note"
    ) -> Optional[List["Note"]]:
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
        queue: deque[Tuple[Note, List[Note]]] = deque([(source, [source])])
        visited: Set[str] = {source.path}

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

    def k_hop_neighborhood(self, note: "Note", k: int) -> List["Note"]:
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

        visited: Set[str] = {note.path}
        current_level = [note]

        for _ in range(k):
            next_level: List[Note] = []

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

    def find_connected_components(self) -> List[List["Note"]]:
        """Find disconnected subgraphs (connected components).

        Uses undirected graph interpretation (links work both ways)
        to find groups of notes that are connected to each other but
        isolated from other groups.

        Returns:
            List of connected components (each is a list of notes)
        """
        notes = self.vault.notes()
        visited: Set[str] = set()
        components: List[List[Note]] = []

        for note in notes:
            if note.path in visited:
                continue

            # BFS to find all notes in this component
            component: List[Note] = []
            queue: deque[Note] = deque([note])
            component_visited: Set[str] = {note.path}

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
        self, min_similarity: float = 0.6
    ) -> List[Tuple["Note", "Note"]]:
        """Find high-similarity pairs in different connected components.

        A structural hole exists when two notes are semantically similar
        but belong to disconnected parts of the vault graph. These represent
        opportunities for cross-pollination.

        Args:
            min_similarity: Minimum similarity for structural holes

        Returns:
            List of (note_a, note_b) pairs forming structural holes
        """
        # Get connected components
        components = self.find_connected_components()

        if len(components) < 2:
            return []  # Need at least 2 components

        # Build component membership lookup
        note_to_component: Dict[str, int] = {}
        for i, component in enumerate(components):
            for note in component:
                note_to_component[note.path] = i

        # Find high-similarity pairs across components
        structural_holes: List[Tuple[Note, Note]] = []
        all_notes = self.vault.notes()

        for i, note_a in enumerate(all_notes):
            for note_b in all_notes[i + 1 :]:
                # Check if in different components
                comp_a = note_to_component.get(note_a.path)
                comp_b = note_to_component.get(note_b.path)

                if comp_a is not None and comp_b is not None and comp_a != comp_b:
                    # Different components - check similarity
                    sim = self.vault.similarity(note_a, note_b)
                    if sim >= min_similarity:
                        structural_holes.append((note_a, note_b))

        return structural_holes
