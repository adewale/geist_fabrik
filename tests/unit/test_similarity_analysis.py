"""Unit tests for similarity_analysis (SimilarityLevel + SimilarityProfile).

SimilarityLevel thresholds are pure constants. SimilarityProfile computes over
real (mocked) embeddings, so the assertions here are structural invariants
(counts are monotonic in the threshold, percentiles are ordered, etc.) rather
than exact similarity values - which keeps the tests robust to the embedding
backend while still exercising the code paths.
"""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.similarity_analysis import SimilarityLevel, SimilarityProfile
from geistfabrik.vault_context import VaultContext


class TestSimilarityLevel:
    def test_thresholds_strictly_decreasing(self):
        levels = [
            SimilarityLevel.VERY_HIGH,
            SimilarityLevel.HIGH,
            SimilarityLevel.MODERATE,
            SimilarityLevel.WEAK,
            SimilarityLevel.NOISE,
        ]
        assert levels == sorted(levels, reverse=True)
        assert len(set(levels)) == len(levels)  # all distinct

    def test_thresholds_in_unit_interval(self):
        for level in (
            SimilarityLevel.VERY_HIGH,
            SimilarityLevel.HIGH,
            SimilarityLevel.MODERATE,
            SimilarityLevel.WEAK,
            SimilarityLevel.NOISE,
        ):
            assert 0.0 <= level <= 1.0


@pytest.fixture
def context():
    """A VaultContext over a small vault with mocked embeddings."""
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)
        notes = {
            "ai.md": "# AI\nArtificial intelligence and machine learning concepts.",
            "ml.md": "# ML\nMachine learning, deep learning and neural networks.",
            "cooking.md": "# Cooking\nRecipes, food and meal preparation.",
            "baking.md": "# Baking\nBread, pastries and dough techniques.",
            "travel.md": "# Travel\nTrains, flights and itineraries.",
        }
        for name, content in notes.items():
            (vault_path / name).write_text(content)

        vault = Vault(vault_path)
        vault.sync()
        session = Session(datetime(2023, 6, 15), vault.db)
        session.compute_embeddings(vault.all_notes())
        try:
            yield VaultContext(vault, session)
        finally:
            vault.close()


class TestSimilarityProfile:
    def test_count_above_is_monotonic_in_threshold(self, context):
        note = context.notes()[0]
        profile = SimilarityProfile(context, note)
        n_others = len(context.notes()) - 1

        # Every similarity lies in [-1, 1] and excludes self.
        assert profile.count_above(-1.0) == n_others
        assert profile.count_above(2.0) == 0
        # Higher threshold cannot count more candidates.
        assert profile.count_above(SimilarityLevel.HIGH) <= profile.count_above(
            SimilarityLevel.NOISE
        )

    def test_count_in_range_full_range_counts_all(self, context):
        note = context.notes()[0]
        profile = SimilarityProfile(context, note)
        n_others = len(context.notes()) - 1
        assert profile.count_in_range(-1.0, 1.0) == n_others
        assert profile.count_in_range(2.0, 3.0) == 0

    def test_percentiles_are_ordered(self, context):
        note = context.notes()[0]
        profile = SimilarityProfile(context, note)
        assert profile.percentile(0) <= profile.percentile(50) <= profile.percentile(100)

    def test_percentile_empty_candidates_returns_zero(self, context):
        note = context.notes()[0]
        profile = SimilarityProfile(context, note, candidates=[note])  # only self -> excluded
        assert profile.percentile(50) == 0.0

    def test_is_hub_threshold_extremes(self, context):
        note = context.notes()[0]
        profile = SimilarityProfile(context, note)
        # min_count=0 is always satisfiable; an impossibly high count never is.
        assert profile.is_hub(threshold=SimilarityLevel.NOISE, min_count=0) is True
        assert profile.is_hub(threshold=SimilarityLevel.VERY_HIGH, min_count=10_000) is False
