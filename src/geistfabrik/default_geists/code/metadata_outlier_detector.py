"""Metadata Outlier Detector geist.

Demonstrates MetadataAnalyser abstraction (Phase 5).
Finds notes with unusual metadata values (outliers) that might warrant attention.
"""

from typing import TYPE_CHECKING

from geistfabrik.metadata_system import MetadataAnalyser
from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.vault_context import VaultContext


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with outlier metadata values.

    Uses MetadataAnalyser to compute statistical distributions and identify
    notes that are unusually high or low on various metadata dimensions.
    """
    notes = vault.notes()
    if len(notes) < 10:
        return []

    # Initialize metadata analyser
    analyser = MetadataAnalyser(vault)

    suggestions = []

    # Check for word_count outliers (unusually long/short notes)
    word_count_outliers = analyser.outliers("word_count", threshold=2.0)
    if word_count_outliers:
        # Get the most extreme outlier (it's already a Note object)
        note = word_count_outliers[0]
        metadata = vault.metadata(note)
        if metadata:
            wc = metadata.get("word_count", 0)
            dist = analyser.distribution("word_count")
            median = dist["p50"]

            if wc > median:
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.obsidian_link}]] is unusually detailed "
                            f"({int(wc)} words vs median {int(median)}). "
                            f"Does this depth signal importance?"
                        ),
                        notes=[note.title],
                        geist_id="metadata_outlier_detector",
                    )
                )
            else:
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.obsidian_link}]] is unusually brief "
                            f"({int(wc)} words vs median {int(median)}). "
                            f"Does this note need development?"
                        ),
                        notes=[note.title],
                        geist_id="metadata_outlier_detector",
                    )
                )

    # Check for link_density outliers (unusually connected/isolated)
    link_density_outliers = analyser.outliers("link_density", threshold=2.0)
    if link_density_outliers and len(suggestions) < 2:
        # Get the most extreme outlier (it's already a Note object)
        note = link_density_outliers[0]
        metadata = vault.metadata(note)
        if metadata:
            density = metadata.get("link_density", 0.0)
            profile = analyser.profile(note)
            link_profile = profile.get("link_density", "moderate")

            if link_profile == "high":
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.obsidian_link}]] has exceptionally high "
                            f"link density ({density:.2f}). "
                            f"Is this a hub or an over-connected note?"
                        ),
                        notes=[note.title],
                        geist_id="metadata_outlier_detector",
                    )
                )
            elif link_profile == "low":
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.obsidian_link}]] has exceptionally low "
                            f"link density ({density:.2f}). "
                            f"Could this isolated note connect to others?"
                        ),
                        notes=[note.title],
                        geist_id="metadata_outlier_detector",
                    )
                )

    # Limit to 2 suggestions
    return suggestions[:2]
