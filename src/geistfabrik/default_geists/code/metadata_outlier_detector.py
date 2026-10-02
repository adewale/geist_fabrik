"""Metadata Outlier Detector geist.

Demonstrates MetadataAnalyser abstraction (Phase 5).
Finds notes with unusual metadata values (outliers) that might warrant attention.
"""

import math
from typing import TYPE_CHECKING

from geistfabrik.metadata_system import MetadataAnalyser
from geistfabrik.models import Suggestion

if TYPE_CHECKING:
    from geistfabrik.models import Note
    from geistfabrik.vault_context import VaultContext

# Notes shorter than this are left out of the link-density distribution
# (same floor as link_density_analyser).
MIN_WORDS_FOR_DENSITY = 50


def _word_count_outliers(
    vault: "VaultContext", notes: list["Note"], threshold: float
) -> list["Note"]:
    """Notes whose log word count is > threshold SDs from the mean, most extreme first.

    Word counts are right-skewed (many short notes, a few very long ones), so
    a z-score on raw counts can almost never flag a short note: mean - 2 SD is
    usually below zero. On log1p(word_count) the scale is symmetric enough
    that a stub among substantial notes stands out as far as a treatise does.
    """
    logs: dict[str, float] = {}
    for note in notes:
        value = vault.metadata(note).get("word_count")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0:
            logs[note.path] = math.log1p(value)
    if not logs:
        return []
    mean = sum(logs.values()) / len(logs)
    std = math.sqrt(sum((v - mean) ** 2 for v in logs.values()) / len(logs))
    if std < 1e-10:
        return []
    scored = [(abs(logs[n.path] - mean) / std, n) for n in notes if n.path in logs]
    outliers = [(z, n) for z, n in scored if z > threshold]
    outliers.sort(key=lambda pair: (-pair[0], pair[1].path))
    return [n for _, n in outliers]


def suggest(vault: "VaultContext") -> list["Suggestion"]:
    """Find notes with outlier metadata values.

    Uses MetadataAnalyser to compute statistical distributions and identify
    notes that are unusually high or low on various metadata dimensions.
    """
    # Require minimum notes for meaningful statistics
    notes = vault.notes()
    if len(notes) < 10:
        return []

    # Initialize metadata analyser
    analyser = MetadataAnalyser(vault)
    suggestions = []

    # Check for word_count outliers (unusually long/short notes), on a log
    # scale so that "unusually brief" is reachable
    word_count_outliers = _word_count_outliers(vault, notes, threshold=2.0)

    if word_count_outliers:
        # Any outlier is "unusual"; sample one so the same most-extreme note
        # is not named every session.
        note = vault.sample(word_count_outliers, 1)[0]
        metadata = vault.metadata(note)
        wc = metadata.get("word_count", 0)
        dist = analyser.distribution("word_count")
        median = dist["p50"]

        if wc > median:
            suggestions.append(
                Suggestion(
                    text=(
                        f"[[{note.link_text}]] is unusually detailed "
                        f"({int(wc)} words vs median {int(median)}). "
                        f"Does this depth signal importance?"
                    ),
                    notes=[note.link_text],
                    geist_id="metadata_outlier_detector",
                )
            )
        else:
            suggestions.append(
                Suggestion(
                    text=(
                        f"[[{note.link_text}]] is unusually brief "
                        f"({int(wc)} words vs median {int(median)}). "
                        f"Does this note need development?"
                    ),
                    notes=[note.link_text],
                    geist_id="metadata_outlier_detector",
                )
            )

    # Check for link_density outliers (unusually connected/isolated). Density
    # is only meaningful once a note has some prose: a three-word note with
    # one link would otherwise dominate the distribution.
    if len(suggestions) < 2:
        prose_notes = [
            n for n in notes if vault.metadata(n).get("word_count", 0) >= MIN_WORDS_FOR_DENSITY
        ]
        link_density_outliers = analyser.outliers("link_density", threshold=2.0, notes=prose_notes)

        if link_density_outliers:
            note = vault.sample(link_density_outliers, 1)[0]
            metadata = vault.metadata(note)
            per_100 = float(metadata.get("link_density", 0.0)) * 100
            dist = analyser.distribution("link_density", notes=prose_notes)
            median_per_100 = dist["p50"] * 100
            counts = (
                f"{int(metadata.get('link_count', 0))} links in {int(metadata['word_count'])} words"
            )

            if per_100 > median_per_100:
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.link_text}]] is unusually dense with links "
                            f"({counts}: {per_100:.1f} per 100 words vs median "
                            f"{median_per_100:.1f}). Is this a hub or an over-connected note?"
                        ),
                        notes=[note.link_text],
                        geist_id="metadata_outlier_detector",
                    )
                )
            else:
                suggestions.append(
                    Suggestion(
                        text=(
                            f"[[{note.link_text}]] is unusually sparse in links "
                            f"({counts}: {per_100:.1f} per 100 words vs median "
                            f"{median_per_100:.1f}). Could this isolated note connect to others?"
                        ),
                        notes=[note.link_text],
                        geist_id="metadata_outlier_detector",
                    )
                )

    # Limit to 2 suggestions
    return suggestions[:2]
