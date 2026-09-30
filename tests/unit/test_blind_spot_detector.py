"""Unit tests for the blind_spot_detector geist.

blind_spot_detector takes the most recently modified non-journal notes
(needs >= 2), and for each of the top 3 finds its most contrarian note
(least similar, via the ``contrarian_to`` vault function). The contrarian is
a blind spot when it was last modified more than 180 days before the session
or has no backlinks. At most 2 suggestions are returned.

Fixtures use the bag-of-words test stub (disjoint vocabulary -> cosine ~0)
and pinned modification dates relative to SESSION_DATE.
"""

from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

from geistfabrik.default_geists.code import blind_spot_detector
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SEED, SESSION_DATE, VaultBuilder, assert_valid_suggestions

CAP = 2
RECENT = SESSION_DATE - timedelta(days=5)
OLD = SESSION_DATE - timedelta(days=400)
TOPICS = {
    "Garden": "garden compost seedling trowel mulch",
    "Glacier": "glacier moraine crevasse serac firn",
    "Violin": "violin rosin bowing luthier vibrato",
}


def _days_ago(days: int) -> datetime:
    return SESSION_DATE - timedelta(days=days)


def test_blind_spot_detector_flags_stale_or_unlinked_opposites(tmp_path: Path) -> None:
    """Contract: a recent note's contrarian is a blind spot if stale OR unlinked.

    Trigger: "Garden" (modified 5 days ago) and "Glacier" (400 days ago),
    disjoint vocabulary, no links, are each other's only contrarian: Glacier
    is a blind spot for Garden (400 > 180 days) and Garden one for Glacier
    (no backlinks, although fresh).
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Garden", TOPICS["Garden"], created=RECENT)
    builder.note("Glacier", TOPICS["Glacier"], created=OLD)
    ctx = builder.build()

    suggestions = blind_spot_detector.suggest(ctx)

    assert_valid_suggestions(
        suggestions, "blind_spot_detector", must_reference=["Garden", "Glacier"]
    )
    by_pair = {tuple(s.notes): s.text for s in suggestions}
    assert set(by_pair) == {("Garden", "Glacier"), ("Glacier", "Garden")}
    assert "it's been 400 days since you touched it" in by_pair[("Garden", "Glacier")]
    assert "it's been 5 days since you touched it" in by_pair[("Glacier", "Garden")]


def test_blind_spot_detector_caps_at_two(tmp_path: Path) -> None:
    """Contract: 3 recent notes each with an unlinked contrarian -> exactly 2 suggestions."""
    builder = VaultBuilder(tmp_path)
    for i, (title, body) in enumerate(TOPICS.items()):
        builder.note(title, body, created=_days_ago(i + 1))
    ctx = builder.build()

    suggestions = blind_spot_detector.suggest(ctx)

    assert_valid_suggestions(suggestions, "blind_spot_detector", min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.notes[0] for s in suggestions}) == CAP


@pytest.mark.parametrize(("stale_days", "fires"), [(180, False), (181, True)])
def test_blind_spot_detector_staleness_threshold(
    tmp_path: Path, stale_days: int, fires: bool
) -> None:
    """Contract: a linked contrarian is a blind spot only if untouched > 180 days.

    The two notes link to each other, so neither qualifies via "no
    backlinks"; only the older note's age can make it a blind spot.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Garden", f"{TOPICS['Garden']} [[Glacier]]", created=RECENT)
    builder.note("Glacier", f"{TOPICS['Glacier']} [[Garden]]", created=_days_ago(stale_days))
    ctx = builder.build()

    suggestions = blind_spot_detector.suggest(ctx)

    if fires:
        assert_valid_suggestions(suggestions, "blind_spot_detector")
        assert [s.notes for s in suggestions] == [["Garden", "Glacier"]]
    else:
        assert suggestions == []


def _with_embedding(ctx: VaultContext, path: str, vector: np.ndarray) -> VaultContext:
    """Overwrite one session embedding and return a fresh context that sees it."""
    ctx.db.execute(
        "UPDATE session_embeddings SET embedding = ? WHERE session_id = ? AND note_path = ?",
        (vector.astype(np.float32).tobytes(), ctx.session.session_id, path),
    )
    ctx.db.commit()
    session = Session(SESSION_DATE, ctx.vault.db)
    return VaultContext(ctx.vault, session, seed=SEED, function_registry=FunctionRegistry())


def test_blind_spot_detector_skips_journal_contrarians(tmp_path: Path) -> None:
    """Contract: a journal note is never the blind spot; the next contrarian is used.

    The journal note's embedding is set opposite to both regular notes
    (cosine ~ -0.7), making it the MOST contrarian note for each of them.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Garden", TOPICS["Garden"], created=RECENT)
    builder.note("Glacier", TOPICS["Glacier"], created=OLD)
    journal_path = builder.journal("Session Echo", TOPICS["Violin"], created=OLD)
    ctx = builder.build()
    garden, glacier = ctx.get_embedding("Garden.md"), ctx.get_embedding("Glacier.md")
    assert garden is not None and glacier is not None
    opposite = -(garden + glacier)
    ctx = _with_embedding(ctx, journal_path, opposite / np.linalg.norm(opposite))
    # By embedding the journal note is the most contrarian; the shared lookup
    # must still never offer it.
    assert ctx.call_function("contrarian_to", "Garden", 1) == ["[[Glacier]]"]

    suggestions = blind_spot_detector.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "blind_spot_detector",
        must_reference=["Garden", "Glacier"],
        must_not_reference=["geist journal", "Session Echo"],
    )
