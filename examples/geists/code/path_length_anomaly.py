"""Path Length Anomaly - example geist using GraphPatternFinder.

Finds note pairs that are semantically close but link-distant: the ideas sit
one step apart, yet the shortest chain of links between them is many hops
long (or absent). The missing direct link is the provocation.

Grounding:
- specs/reuse_abstractions_spec.md ("What New Geists Are Unlocked?" item 26:
  "Path Length Anomaly: Semantically close but link-distant notes")
- Gordon Brander, "All you need is links": "Before reaching for features, my
  goal is to explore, to the fullest extent, the creative potential of plain
  old links." This geist measures where your links lag behind your thinking.

This is a LEARNING EXAMPLE (not installed by default). To use it, copy to
<vault>/_geistfabrik/geists/code/.
"""

from typing import TYPE_CHECKING

from geistfabrik.graph_analysis import GraphPatternFinder
from geistfabrik.similarity_analysis import SimilarityLevel

if TYPE_CHECKING:
    from geistfabrik import Suggestion, VaultContext

# Path lengths >= this count as "far" in link space (None = unreachable).
FAR_HOPS = 4
# How many semantically close pairs to examine per session.
MAX_PAIRS = 15


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Surface pairs that are near in meaning but far in the link graph.

    Returns:
        Up to 2 suggestions, or [] when no anomalies are found.
    """
    from geistfabrik import Suggestion

    notes = vault.notes_excluding_journal()
    if len(notes) < 10:
        return []

    finder = GraphPatternFinder(vault)

    # Sample seeds deterministically, then take each seed's nearest
    # neighbour as a semantically-close candidate pair.
    seeds = vault.sample(notes, min(MAX_PAIRS, len(notes)))

    suggestions = []
    for seed in seeds:
        neighbours = vault.neighbours(seed, count=1, return_scores=True)
        if not neighbours:
            continue
        other, similarity = neighbours[0]
        if similarity < SimilarityLevel.HIGH:
            continue  # only genuinely close pairs are interesting

        path = finder.shortest_path(seed, other)
        hops = len(path) - 1 if path else None

        if hops is not None and hops < FAR_HOPS:
            continue  # links already reflect the closeness

        if hops is None:
            distance_phrase = "no chain of links connects them at all"
        else:
            distance_phrase = f"the shortest link path between them is {hops} hops long"

        text = (
            f"[[{seed.link_text}]] and [[{other.link_text}]] sit one "
            f"step apart in meaning, but {distance_phrase}. What is the "
            f"missing direct link you have never written down?"
        )
        suggestions.append(
            Suggestion(
                text=text,
                notes=[seed.link_text, other.link_text],
                geist_id="path_length_anomaly",
            )
        )
        if len(suggestions) >= 4:
            break

    return vault.sample(suggestions, min(2, len(suggestions)))
