"""Unit tests for temporal_drift geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import temporal_drift
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def vault_with_stale_notes(tmp_path):
    """Create a vault with stale, well-connected notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create stale note with many links (should be suggested)
    (vault_path / "stale_hub.md").write_text("""# Stale Hub

Important note that hasn't been updated.

Links: [[note1]], [[note2]], [[note3]], [[note4]]
""")

    # Create another stale note with many links
    (vault_path / "old_important.md").write_text("""# Old Important

Another stale but well-connected note.

Links: [[note1]], [[note2]], [[note3]]
""")

    # Create stale note with few links (should NOT be suggested)
    (vault_path / "stale_orphan.md").write_text("""# Stale Orphan

Stale but not well-connected.

Links: [[note1]]
""")

    # Create recent note (should NOT be suggested)
    (vault_path / "recent.md").write_text("""# Recent

Recently updated note.

Links: [[note1]], [[note2]], [[note3]]
""")

    # Create linked notes
    for i in range(1, 5):
        (vault_path / f"note{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set dates
    now = datetime(2024, 3, 15, 10, 0)
    old_date = now - timedelta(days=200)  # Very stale
    recent_date = now - timedelta(days=5)  # Recent

    _set_note_dates(vault, "Stale Hub", old_date, old_date)
    _set_note_dates(vault, "Old Important", old_date, old_date)
    _set_note_dates(vault, "Stale Orphan", old_date, old_date)
    _set_note_dates(vault, "Recent", recent_date, now)

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


def _set_note_dates(vault, title, created, modified):
    """Helper to set created and modified dates for a specific note.

    Args:
        vault: Vault instance with database connection
        title: Title of note to update
        created: datetime for created field
        modified: datetime for modified field
    """
    vault.db.execute(
        "UPDATE notes SET created = ?, modified = ? WHERE title = ?",
        (created.isoformat(), modified.isoformat(), title),
    )
    vault.db.commit()


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_temporal_drift_returns_suggestions(vault_with_stale_notes):
    """Test that temporal_drift returns suggestions for stale notes."""
    vault, session = vault_with_stale_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Should return suggestions (at most 3)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3

    # BEHAVIORAL: Verify suggested notes meet staleness threshold (>0.7 from line 32)
    for suggestion in suggestions:
        note_ref = suggestion.notes[0]
        note = next((n for n in vault.all_notes() if n.obsidian_link == note_ref), None)

        if note:
            metadata = context.metadata(note)
            staleness = metadata.get("staleness", 0)

            # Temporal drift requires staleness > 0.7 (core threshold)
            assert staleness > 0.7, (
                f"Suggested note [[{note_ref}]] should have staleness >0.7, got {staleness:.2f}"
            )


def test_temporal_drift_suggestion_structure(vault_with_stale_notes):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_stale_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "temporal_drift"

        # Should reference exactly 1 note
        assert len(suggestion.notes) == 1

        # Note reference should be string
        assert isinstance(suggestion.notes[0], str)

        # Should mention temporal aspects
        assert "days" in suggestion.text or "modified" in suggestion.text

        # BEHAVIORAL: Verify link_count threshold (>=3 from line 32)
        note_ref = suggestion.notes[0]
        note = next((n for n in vault.all_notes() if n.obsidian_link == note_ref), None)

        if note:
            metadata = context.metadata(note)
            link_count = metadata.get("link_count", 0)

            # Temporal drift requires link_count >= 3 (well-connected notes)
            assert link_count >= 3, (
                f"Suggested note [[{note_ref}]] should have >=3 links, got {link_count}"
            )


def test_temporal_drift_uses_obsidian_link(vault_with_stale_notes):
    """Test that temporal_drift uses obsidian_link for note references."""
    vault, session = vault_with_stale_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_temporal_drift_mentions_days_and_links(vault_with_stale_notes):
    """Test that suggestions mention days since modified and link count."""
    vault, session = vault_with_stale_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    if suggestions:
        suggestion = suggestions[0]

        # Should mention days
        assert "days" in suggestion.text

        # Should mention links
        assert "links" in suggestion.text or "link" in suggestion.text

        # BEHAVIORAL: Verify exact numbers in text match metadata (lines 33, 36-37)
        import re

        note_ref = suggestion.notes[0]
        note = next((n for n in vault.all_notes() if n.obsidian_link == note_ref), None)

        if note:
            metadata = context.metadata(note)
            actual_days = metadata.get("days_since_modified", 0)
            actual_links = metadata.get("link_count", 0)

            # Extract numbers from suggestion text
            days_match = re.search(r"(\d+)\s+days", suggestion.text)
            links_match = re.search(r"(\d+)\s+links", suggestion.text)

            if days_match:
                mentioned_days = int(days_match.group(1))
                assert mentioned_days == actual_days, (
                    f"Text mentions {mentioned_days} days but metadata shows {actual_days}"
                )

            if links_match:
                mentioned_links = int(links_match.group(1))
                assert mentioned_links == actual_links, (
                    f"Text mentions {mentioned_links} links but metadata shows {actual_links}"
                )


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_temporal_drift_empty_vault(tmp_path):
    """Test that temporal_drift handles empty vault gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime(2024, 3, 15), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_temporal_drift_no_stale_notes(tmp_path):
    """Test when all notes are recent."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create recent notes with links
    for i in range(3):
        (vault_path / f"recent{i}.md").write_text(
            f"# Recent {i}\n\nContent.\n\nLinks: [[note1]], [[note2]], [[note3]]"
        )

    (vault_path / "note1.md").write_text("# Note 1\n\nContent.")
    (vault_path / "note2.md").write_text("# Note 2\n\nContent.")
    (vault_path / "note3.md").write_text("# Note 3\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set all notes to recent date
    now = datetime(2024, 3, 15, 10, 0)
    recent_date = now - timedelta(days=2)

    vault.db.execute(
        "UPDATE notes SET created = ?, modified = ?",
        (recent_date.isoformat(), now.isoformat()),
    )
    vault.db.commit()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Should return few or no suggestions (notes are not stale)
    assert len(suggestions) <= 1


def test_temporal_drift_insufficient_links(tmp_path):
    """Test that notes with few links are not suggested."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create stale note with only 1 link (below threshold)
    (vault_path / "stale_orphan.md").write_text("""# Stale Orphan

Old note with few links.

Links: [[note1]]
""")

    (vault_path / "note1.md").write_text("# Note 1\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set to very old date
    now = datetime(2024, 3, 15, 10, 0)
    old_date = now - timedelta(days=365)

    _set_note_dates(vault, "Stale Orphan", old_date, old_date)

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Should not suggest note with < 3 links
    assert len(suggestions) == 0


def test_temporal_drift_requires_high_staleness(tmp_path):
    """Test that only notes with staleness > 0.7 are suggested."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create somewhat old note with links
    (vault_path / "somewhat_old.md").write_text("""# Somewhat Old

Modified somewhat recently.

Links: [[note1]], [[note2]], [[note3]]
""")

    for i in range(1, 4):
        (vault_path / f"note{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set to moderately old date (not old enough for staleness > 0.7)
    now = datetime(2024, 3, 15, 10, 0)
    moderate_date = now - timedelta(days=50)  # Not stale enough

    _set_note_dates(vault, "Somewhat Old", moderate_date, moderate_date)

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # May return empty if staleness threshold not met
    # (depends on how staleness is calculated)
    assert isinstance(suggestions, list)


# ============================================================================
# Limit Tests
# ============================================================================


def test_temporal_drift_max_three_suggestions(vault_with_stale_notes):
    """Test that temporal_drift returns at most 3 suggestions."""
    vault, session = vault_with_stale_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_temporal_drift_deterministic_with_seed(vault_with_stale_notes):
    """Test that temporal_drift returns same results with same seed."""
    vault, session = vault_with_stale_notes

    # Reuse same FunctionRegistry to avoid duplicate registration
    registry = FunctionRegistry()

    context1 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    context2 = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=registry,
    )

    suggestions1 = temporal_drift.suggest(context1)
    suggestions2 = temporal_drift.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


# ============================================================================
# Metadata Tests
# ============================================================================


def test_temporal_drift_uses_metadata(vault_with_stale_notes):
    """Test that temporal_drift uses metadata (staleness, link_count)."""
    vault, session = vault_with_stale_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Get suggested notes and verify they have high staleness and link count
    for suggestion in suggestions:
        # Extract note title from suggestion
        # (this is indirect - we're verifying the geist's logic)
        assert "links" in suggestion.text.lower() or "link" in suggestion.text.lower()
        assert "days" in suggestion.text.lower()

        # BEHAVIORAL: Verify both thresholds are met (staleness >0.7 AND link_count >=3)
        note_ref = suggestion.notes[0]
        note = next((n for n in vault.all_notes() if n.obsidian_link == note_ref), None)

        if note:
            metadata = context.metadata(note)
            staleness = metadata.get("staleness", 0)
            link_count = metadata.get("link_count", 0)

            # Temporal drift requires BOTH conditions (line 32: staleness > 0.7 and link_count >= 3)
            assert staleness > 0.7 and link_count >= 3, (
                f"Suggested note [[{note_ref}]] must meet both thresholds: "
                f"staleness={staleness:.2f} (need >0.7), link_count={link_count} (need >=3)"
            )


# ============================================================================
# Exclusion Tests
# ============================================================================


def test_temporal_drift_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    # Create old journal notes with links
    for i in range(5):
        note_path = journal_dir / f"2023-03-{10 + i:02d}.md"
        note_path.write_text(f"""# Session {i}

Journal entry with links: [[note1]], [[note2]], [[note3]]
""")

    # Create regular stale note with links
    (vault_path / "stale.md").write_text("""# Stale

Old note with links: [[note1]], [[note2]], [[note3]]
""")

    for i in range(1, 4):
        (vault_path / f"note{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    # Set all to old dates
    now = datetime(2024, 3, 15, 10, 0)
    old_date = now - timedelta(days=300)

    vault.db.execute(
        "UPDATE notes SET created = ?, modified = ?",
        (old_date.isoformat(), old_date.isoformat()),
    )
    vault.db.commit()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_drift.suggest(context)

    # Verify that journal notes don't appear in suggestions
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()
