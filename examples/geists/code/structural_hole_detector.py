"""Structural Hole Detector - example geist using GraphPatternFinder.

Finds pairs of notes that are semantically similar but live in DISCONNECTED
parts of the link graph: the same thought living on different islands. Burt's
structural-holes theory calls the person who spans such a gap a broker - the
one who profits from connecting what others keep apart. Here the broker is a
note you haven't written yet.

Grounding:
- specs/reuse_abstractions_spec.md ("What New Geists Are Unlocked?" item 25:
  "Structural Hole Detector: High-similarity pairs in disconnected components")
- Gordon Brander, "Knowledge structures": networks win because "the
  cross-connections among the myriad topics of this world simply cannot be
  divided up neatly" - this geist hunts the cross-connections your current
  graph partitioning suppresses.

This is a LEARNING EXAMPLE (not installed by default). To use it, copy to
<vault>/_geistfabrik/geists/code/.
"""

from typing import TYPE_CHECKING

from geistfabrik.graph_analysis import GraphPatternFinder
from geistfabrik.similarity_analysis import SimilarityLevel

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Surface semantically similar notes stranded on different graph islands.

    Returns:
        Up to 2 suggestions, or [] when the vault has a single component
        or no holes above the similarity bar.
    """
    from geistfabrik import Suggestion

    notes = vault.notes_excluding_journal()
    if len(notes) < 10:
        return []

    finder = GraphPatternFinder(vault)

    # candidate_limit keeps this bounded on large vaults (deterministic
    # sample per session - "sample, don't rank").
    holes = finder.detect_structural_holes(min_similarity=SimilarityLevel.HIGH, candidate_limit=200)
    if not holes:
        return []

    suggestions = []
    for note_a, note_b in vault.sample(holes, min(2, len(holes))):
        text = (
            f"[[{note_a.obsidian_link}]] and [[{note_b.obsidian_link}]] keep "
            f"saying similar things, yet no chain of links connects them - "
            f"they live on different islands of your vault. What if they are "
            f"the same thought in two dialects? What note would close the "
            f"hole between them?"
        )
        suggestions.append(
            Suggestion(
                text=text,
                notes=[note_a.obsidian_link, note_b.obsidian_link],
                geist_id="structural_hole_detector",
            )
        )

    return suggestions
