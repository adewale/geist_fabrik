"""Tests for similarity_analysis over a real VaultContext.

Exact SimilarityProfile/SimilarityFilter semantics (inclusive bounds,
percentiles, caching, bridges) are owned by
test_analysis_selection_contracts.py with injected scores. This file checks
the named thresholds and that a profile computed through the real
VaultContext.similarity() path finds a designed lexical neighbour.
"""

from pathlib import Path

from geistfabrik.similarity_analysis import SimilarityLevel, SimilarityProfile
from tests.fixtures.helpers import VaultBuilder


def test_thresholds_are_distinct_strictly_decreasing_and_in_unit_interval() -> None:
    """Geists read VERY_HIGH > HIGH > MODERATE > WEAK > NOISE as an ordered scale."""
    levels = [
        SimilarityLevel.VERY_HIGH,
        SimilarityLevel.HIGH,
        SimilarityLevel.MODERATE,
        SimilarityLevel.WEAK,
        SimilarityLevel.NOISE,
    ]
    assert levels == sorted(set(levels), reverse=True)
    assert all(0.0 <= level <= 1.0 for level in levels)


def test_profile_over_real_context_finds_the_lexical_neighbour(tmp_path: Path) -> None:
    """Only "ML" shares words with "AI" (similarity ~0.60, between MODERATE and
    HIGH); the rest share none (~0.02)."""
    builder = VaultBuilder(tmp_path)
    builder.note("AI", "Artificial intelligence and machine learning concepts.")
    builder.note("ML", "Machine learning concepts, deep learning and neural networks.")
    builder.note("Cooking", "Recipes, food and meal preparation.")
    builder.note("Baking", "Bread, pastries and dough techniques.")
    builder.note("Travel", "Trains, flights and itineraries.")
    context = builder.build()
    ai = next(n for n in context.notes() if n.title == "AI")

    profile = SimilarityProfile(context, ai)

    assert profile.count_above(-1.0) == 4  # every other note, never itself
    assert profile.count_above(SimilarityLevel.MODERATE) == 1
    assert profile.count_above(SimilarityLevel.HIGH) == 0
    assert profile.count_above(SimilarityLevel.NOISE) == 1
    assert profile.is_hub(threshold=SimilarityLevel.MODERATE, min_count=1)
    assert not profile.is_hub(threshold=SimilarityLevel.MODERATE, min_count=2)
