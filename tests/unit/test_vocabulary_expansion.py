"""Tests for the vocabulary_expansion geist.

Trigger: >= 3 of the latest 5 sessions (up to the session date) each hold
>= 10 note vectors. Per session, coverage = mean Euclidean distance of the
SEMANTIC vectors from their centroid. Comparing the mean of the last two
sessions with the mean of the first two: < 0.8x -> "lower", > 1.2x ->
"higher". At most one suggestion, with no note references.

"Card i" notes share only the title word "card" (digits are ignored by the
stub), so ten cards with the SAME body have identical vectors (coverage 0)
and ten cards with unique bodies are spread out (coverage ~0.85).
"""

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from geistfabrik.config import SEMANTIC_DIM, TOTAL_DIM
from geistfabrik.default_geists.code import vocabulary_expansion
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import drop_from_session, set_session_text

H1, H2 = datetime(2023, 10, 1), datetime(2023, 12, 1)
SAME = "compost worms soil"
HIGHER = "The mean semantic distance of note vectors from their session centroid is higher"
LOWER = "The mean semantic distance of note vectors from their session centroid is lower"


def _unique(i: int) -> str:
    return f"topic{i}alpha topic{i}bravo topic{i}charlie"


def _cards(
    root: Path,
    *,
    now: str,
    before: str,
    count: int = 10,
    history: list[datetime] | None = None,
    builder: VaultBuilder | None = None,
) -> VaultContext:
    """``count`` cards whose current body is ``now`` and whose body in every
    history session was ``before`` ("same" or "unique" per card)."""
    builder = builder or VaultBuilder(root)
    history = [H1, H2] if history is None else history
    for i in range(count):
        builder.note(
            f"Card {i}", SAME if now == "same" else _unique(i), created=datetime(2023, 1, 1)
        )
    ctx = builder.build(history=history)
    for i in range(count):
        body = SAME if before == "same" else _unique(i)
        for when in history:
            set_session_text(ctx, f"Card {i}.md", when, f"# Card {i}\n\n{body}")
    return ctx


def test_vocabulary_expansion_reports_spreading_notes(tmp_path):
    # Trigger arithmetic: coverage H1 = H2 = 0 (identical bodies), current
    # ~0.85: last-two mean 0.43 > 1.2 x first-two mean 0.
    ctx = _cards(tmp_path, before="same", now="unique")

    suggestions = vocabulary_expansion.suggest(ctx)

    assert_valid_suggestions(suggestions, "vocabulary_expansion")
    assert suggestions[0].text == (
        f"{HIGHER} in recent snapshots (through 2024-03-15) than in earlier ones "
        "(around 2023-10-01). Do the source notes show a useful change in topic mix?"
    )
    assert suggestions[0].notes == []


def test_vocabulary_expansion_reports_converging_notes(tmp_path):
    # Coverage H1 = H2 ~0.85, current 0: last-two mean 0.43 < 0.8 x 0.85.
    ctx = _cards(tmp_path, before="unique", now="same")

    suggestions = vocabulary_expansion.suggest(ctx)

    assert_valid_suggestions(suggestions, "vocabulary_expansion")
    assert suggestions[0].text.startswith(LOWER)


def test_vocabulary_expansion_is_silent_without_a_change(tmp_path):
    ctx = _cards(tmp_path, before="unique", now="unique")

    assert vocabulary_expansion.suggest(ctx) == []


def test_vocabulary_expansion_needs_three_sessions(tmp_path):
    """Boundary pair: 2 sessions -> no trend; 3 -> reported."""
    two = _cards(tmp_path / "two", before="same", now="unique", history=[H2])
    three = _cards(tmp_path / "three", before="same", now="unique")

    assert vocabulary_expansion.suggest(two) == []
    assert_valid_suggestions(vocabulary_expansion.suggest(three), "vocabulary_expansion")


def test_vocabulary_expansion_needs_ten_notes_per_session(tmp_path):
    """Boundary pair: 9 notes per session are too few to measure; 10 are enough."""
    nine = _cards(tmp_path / "nine", before="same", now="unique", count=9)
    ten = _cards(tmp_path / "ten", before="same", now="unique", count=10)

    assert vocabulary_expansion.suggest(nine) == []
    assert_valid_suggestions(vocabulary_expansion.suggest(ten), "vocabulary_expansion")


def test_vocabulary_expansion_uses_only_the_latest_five_sessions(tmp_path):
    """Seven sessions: the two oldest (spread out) fall outside the 5-session
    window; the five inside are identical, so there is no trend."""
    history = [datetime(2023, month, 1) for month in (2, 4, 6, 8, 10, 12)]
    builder = VaultBuilder(tmp_path)
    ctx = _cards(tmp_path, before="same", now="same", history=history, builder=builder)
    for i in range(10):
        for when in history[:2]:
            set_session_text(ctx, f"Card {i}.md", when, f"# Card {i}\n\n{_unique(i)}")

    assert vocabulary_expansion.suggest(ctx) == []


def test_vocabulary_expansion_excludes_geist_journal(tmp_path):
    """Session notes accumulate: each is written after its session, so later
    sessions hold more of them. They must not manufacture a trend.

    Both directions: ten identical cards plus accumulating (distinct) session
    notes -> no trend; the same session notes alongside cards that really do
    spread out -> "higher".
    """

    def with_journal(root: Path, now: str) -> VaultContext:
        builder = VaultBuilder(root)
        for i, title in enumerate(("2023-10-01", "2023-12-01")):
            builder.journal(title, _unique(100 + i), created=datetime(2023, 1, 1))
        ctx = _cards(root, before="same", now=now, builder=builder)
        # The H1 session note exists from H2 on; the H2 one only in the current session.
        drop_from_session(ctx, "geist journal/2023-10-01.md", H1)
        for when in (H1, H2):
            drop_from_session(ctx, "geist journal/2023-12-01.md", when)
        return ctx

    stable = with_journal(tmp_path / "stable", now="same")
    spreading = with_journal(tmp_path / "spreading", now="unique")

    assert vocabulary_expansion.suggest(stable) == []
    suggestions = vocabulary_expansion.suggest(spreading)
    assert_valid_suggestions(suggestions, "vocabulary_expansion")
    assert suggestions[0].text.startswith(HIGHER)


def _synthetic_sessions(semantic_spread: bool) -> Any:
    """Four sessions of ten orthogonal vectors whose calendar tail grows with
    the session index; with ``semantic_spread`` the semantic part also spreads."""
    sessions = []
    for session_index in range(4):
        embeddings = []
        for note_index in range(10):
            vector = np.zeros(TOTAL_DIM, dtype=np.float32)
            vector[note_index] = 0.9 * (1 + session_index if semantic_spread else 1)
            vector[SEMANTIC_DIM:] = session_index * note_index
            embeddings.append(vector)
        sessions.append((session_index, f"2025-01-0{session_index + 1}", embeddings))
    return SimpleNamespace(
        session_embeddings_by_session=lambda: sessions,
        sample=lambda values, count: values[:count],
    )


def test_vocabulary_expansion_ignores_calendar_only_vector_changes():
    """Regression guard: the 3 calendar dimensions spread further apart every
    session, but coverage is measured on the semantic dimensions only, so there
    is no trend. The positive twin below shows the same shape does fire when
    the semantic dimensions spread."""
    assert vocabulary_expansion.suggest(_synthetic_sessions(semantic_spread=False)) == []


def test_vocabulary_expansion_reports_semantic_spread_in_the_same_shape():
    suggestions = vocabulary_expansion.suggest(_synthetic_sessions(semantic_spread=True))

    assert_valid_suggestions(suggestions, "vocabulary_expansion")
    assert suggestions[0].text.startswith(HIGHER)
