"""Tests for creation_burst geist."""

from datetime import datetime, timedelta

import pytest

from geistfabrik.default_geists.code import creation_burst
from geistfabrik.vault_context import VaultContext


def test_creation_burst_detects_burst_day(tmp_path):
    """Test that burst days with 5+ notes are detected."""
    from geistfabrik import Vault

    # Create test vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst day: 2024-03-15 with 6 notes
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(6):
        note_path = vault_path / f"burst_note_{i}.md"
        note_path.write_text(f"# Burst Note {i}\n\nContent from the burst day.")
        # Set file mtime to burst_date
        note_path.touch()
        timestamp = burst_date.timestamp()
        note_path.stat().st_mtime = timestamp

    # Create normal day: 2024-03-16 with 2 notes
    normal_date = datetime(2024, 3, 16, 10, 0, 0)
    for i in range(2):
        note_path = vault_path / f"normal_note_{i}.md"
        note_path.write_text(f"# Normal Note {i}\n\nRegular note.")
        note_path.touch()
        timestamp = normal_date.timestamp()
        note_path.stat().st_mtime = timestamp

    # Initialize vault and sync
    vault = Vault(str(vault_path))
    vault.sync()

    # Manually set created dates in database (file mtime becomes created)
    # In real vaults, this would come from file metadata
    for i in range(6):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (burst_date.isoformat(), f"Burst Note {i}"),
        )
    for i in range(2):
        vault.db.execute(
            "UPDATE notes SET created = ? WHERE title = ?",
            (normal_date.isoformat(), f"Normal Note {i}"),
        )
    vault.db.commit()

    # Create context and run geist
    context = VaultContext(vault, session_date="2024-03-20")
    suggestions = creation_burst.suggest(context)

    # Should detect the burst day
    assert len(suggestions) == 1
    assert "2024-03-15" in suggestions[0].text
    assert len(suggestions[0].notes) == 6

    # Should mention the notes
    for i in range(6):
        assert f"Burst Note {i}" in suggestions[0].notes


def test_creation_burst_no_bursts(tmp_path):
    """Test that geist returns empty list when no burst days exist."""
    from geistfabrik import Vault

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create only a few notes per day (below threshold)
    base_date = datetime(2024, 3, 1, 10, 0, 0)
    for day in range(5):
        for i in range(3):  # Only 3 notes per day (below 5 threshold)
            note_path = vault_path / f"note_{day}_{i}.md"
            note_path.write_text(f"# Note {day}-{i}\n\nContent.")
            note_date = base_date + timedelta(days=day)
            note_path.touch()

    vault = Vault(str(vault_path))
    vault.sync()

    # Set created dates
    for day in range(5):
        for i in range(3):
            note_date = base_date + timedelta(days=day)
            vault.db.execute(
                "UPDATE notes SET created = ? WHERE title = ?",
                (note_date.isoformat(), f"Note {day}-{i}"),
            )
    vault.db.commit()

    context = VaultContext(vault, session_date="2024-03-20")
    suggestions = creation_burst.suggest(context)

    # Should return empty list (no bursts)
    assert len(suggestions) == 0


def test_creation_burst_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from burst detection."""
    from geistfabrik import Vault

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    # Create 10 journal notes on same day (should be ignored)
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(10):
        note_path = journal_dir / f"2024-03-{15+i:02d}.md"
        note_path.write_text(f"# Session {i}\n\nJournal entry.")

    # Create only 3 regular notes (below threshold)
    for i in range(3):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path))
    vault.sync()

    # Set all to same date
    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    context = VaultContext(vault, session_date="2024-03-20")
    suggestions = creation_burst.suggest(context)

    # Should return empty list (journal notes excluded, only 3 regular notes)
    assert len(suggestions) == 0


def test_creation_burst_handles_many_notes(tmp_path):
    """Test burst with 10+ notes shows 'exceptional burst' message."""
    from geistfabrik import Vault

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create exceptional burst: 12 notes
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(12):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path))
    vault.sync()

    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    context = VaultContext(vault, session_date="2024-03-20")
    suggestions = creation_burst.suggest(context)

    assert len(suggestions) == 1
    # Should use "exceptional burst" language for 10+ notes
    assert "exceptional burst" in suggestions[0].text.lower()
    assert "12 notes" in suggestions[0].text


def test_creation_burst_limits_display_titles(tmp_path):
    """Test that only first 8 titles are shown in suggestion text."""
    from geistfabrik import Vault

    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create burst with 15 notes
    burst_date = datetime(2024, 3, 15, 10, 0, 0)
    for i in range(15):
        note_path = vault_path / f"note_{i}.md"
        note_path.write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path))
    vault.sync()

    vault.db.execute("UPDATE notes SET created = ?", (burst_date.isoformat(),))
    vault.db.commit()

    context = VaultContext(vault, session_date="2024-03-20")
    suggestions = creation_burst.suggest(context)

    # Text should show first 8 + "and 7 more"
    assert "and 7 more" in suggestions[0].text

    # But notes list should contain all 15
    assert len(suggestions[0].notes) == 15
