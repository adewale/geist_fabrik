"""Tests for the temporal_mirror geist.

Trigger: >= 2 non-journal notes. Notes sorted by ``created`` are split into
10 periods of ``max(1, total // 10)`` notes (the last period takes the
remainder); the geist samples two different periods and one note from each
and returns ONE suggestion "From period N: [[A]]. From period M: [[B]]. ...".
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

from geistfabrik.default_geists.code import temporal_mirror
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

FIRST_DAY = datetime(2022, 1, 1, 9, 0)


def _vault(root: Path, count: int, *, journal: int = 0) -> VaultContext:
    """``count`` notes "Note 00".. created one week apart, oldest first."""
    builder = VaultBuilder(root)
    for i in range(count):
        builder.note(f"Note {i:02d}", f"Entry {i}.", created=FIRST_DAY + timedelta(weeks=i))
    for i in range(journal):
        builder.journal(f"2023-06-{i + 1:02d}", "Session output.", created=datetime(2023, 6, i + 1))
    return builder.build()


def _periods(text: str) -> dict[str, int]:
    return {title: int(n) for n, title in re.findall(r"From period (\d+): \[\[([^\]]+)\]\]", text)}


def test_temporal_mirror_labels_each_note_with_its_creation_period(tmp_path):
    # Trigger arithmetic: 20 notes -> period_size 2, so "Note 2k" and
    # "Note 2k+1" (k-th oldest pair) are period k+1.
    ctx = _vault(tmp_path, 20)

    suggestions = temporal_mirror.suggest(ctx)

    assert_valid_suggestions(suggestions, "temporal_mirror")
    [suggestion] = suggestions
    periods = _periods(suggestion.text)
    assert len(periods) == 2, suggestion.text
    assert len(set(periods.values())) == 2, "the two notes must come from different periods"
    for title, period in periods.items():
        assert period == int(title.split()[1]) // 2 + 1, suggestion.text
    assert sorted(suggestion.notes) == sorted(periods)


def test_temporal_mirror_needs_two_notes(tmp_path):
    """Boundary pair: 1 note -> no suggestion; 2 notes -> the two are juxtaposed."""
    assert temporal_mirror.suggest(_vault(tmp_path / "one", 1)) == []

    suggestions = temporal_mirror.suggest(_vault(tmp_path / "two", 2))

    assert_valid_suggestions(suggestions, "temporal_mirror")
    assert _periods(suggestions[0].text) == {"Note 00": 1, "Note 01": 2}


def test_temporal_mirror_excludes_geist_journal(tmp_path):
    """Both directions: with 2 notes and 5 session notes, only the 2 notes are mirrored."""
    ctx = _vault(tmp_path, 2, journal=5)

    suggestions = temporal_mirror.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "temporal_mirror",
        must_reference=["Note 00", "Note 01"],
        must_not_reference=["geist journal", "2023-06-"],
    )


def test_temporal_mirror_is_deterministic_for_a_seed(tmp_path):
    first = temporal_mirror.suggest(_vault(tmp_path / "a", 20))
    second = temporal_mirror.suggest(_vault(tmp_path / "b", 20))

    assert len(first) == 1
    assert [s.text for s in first] == [s.text for s in second]
