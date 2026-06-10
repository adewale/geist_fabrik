"""Load-Bearing Bridge - example geist using GraphPatternFinder.

Examines the bridges in your vault - notes that connect semantically similar
but unlinked pairs - and asks about their redundancy. A pair held together by
a SINGLE bridge is fragile: delete that note and the two ideas may never find
each other again. A pair with MANY bridges is a theme asking to become its
own note.

Grounding:
- specs/reuse_abstractions_spec.md ("What New Geists Are Unlocked?" item 27:
  "Bridge Redundancy: Multiple bridges between same clusters")
- Gordon Brander, "Centralization is inevitable": "Hubs are efficient...
  Flat networks perform poorly" - and hub-dependence is exactly what makes a
  single load-bearing bridge worth noticing.

This is a LEARNING EXAMPLE (not installed by default). To use it, copy to
<vault>/_geistfabrik/geists/code/.
"""

from collections import defaultdict
from typing import TYPE_CHECKING

from geistfabrik.graph_analysis import GraphPatternFinder
from geistfabrik.similarity_analysis import SimilarityLevel

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Ask about bridge fragility (one bridge) and bridge density (many).

    Returns:
        Up to 2 suggestions, or [] when the vault has no bridges.
    """
    from geistfabrik import Suggestion

    notes = vault.notes_excluding_journal()
    if len(notes) < 10:
        return []

    finder = GraphPatternFinder(vault)
    bridges = finder.find_bridges(min_similarity=SimilarityLevel.MODERATE)
    if not bridges:
        return []

    # Group bridge notes by the (unlinked, similar) pair they connect.
    pair_bridges: dict[tuple[str, str], list[str]] = defaultdict(list)
    pair_notes = {}
    for note_a, bridge, note_b in bridges:
        key = tuple(sorted((note_a.path, note_b.path)))
        pair_bridges[key].append(bridge.obsidian_link)
        pair_notes[key] = (note_a, note_b)

    suggestions = []

    # Fragile: exactly one bridge holds the pair together.
    fragile = [(k, v[0]) for k, v in pair_bridges.items() if len(v) == 1]
    if fragile:
        key, bridge_link = vault.sample(fragile, 1)[0]
        note_a, note_b = pair_notes[key]
        suggestions.append(
            Suggestion(
                text=(
                    f"[[{bridge_link}]] is the only thing holding "
                    f"[[{note_a.obsidian_link}]] and [[{note_b.obsidian_link}]] "
                    f"together - if you deleted it tomorrow, would those two "
                    f"ideas ever find each other again? What if they deserve "
                    f"a direct link of their own?"
                ),
                notes=[bridge_link, note_a.obsidian_link, note_b.obsidian_link],
                geist_id="load_bearing_bridge",
            )
        )

    # Dense: several distinct bridges between the same pair = a latent theme.
    dense = [(k, v) for k, v in pair_bridges.items() if len(set(v)) >= 3]
    if dense:
        key, bridge_links = vault.sample(dense, 1)[0]
        note_a, note_b = pair_notes[key]
        named = ", ".join(f"[[{b}]]" for b in sorted(set(bridge_links))[:3])
        suggestions.append(
            Suggestion(
                text=(
                    f"{len(set(bridge_links))} different notes ({named}, ...) all "
                    f"bridge [[{note_a.obsidian_link}]] and "
                    f"[[{note_b.obsidian_link}]]. What if that recurring "
                    f"in-between is a concept asking for its own note?"
                ),
                notes=[note_a.obsidian_link, note_b.obsidian_link],
                geist_id="load_bearing_bridge",
            )
        )

    return suggestions[:2]
