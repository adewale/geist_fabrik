"""Integration tests for complete scenarios."""

import time
from pathlib import Path

import pytest

from geistfabrik import Vault


@pytest.mark.integration
def test_scenario_first_time_setup(tmp_path: Path) -> None:
    """Test first-time setup scenario with kepano vault.

    AC-1.7: 8 notes should sync in <5 seconds.
    """
    vault_path = Path("testdata/kepano-obsidian-main")
    db_path = tmp_path / "vault.db"

    # Measure sync time
    start = time.time()
    vault = Vault(str(vault_path), str(db_path))
    vault.sync()
    elapsed = time.time() - start

    # Verify results
    notes = vault.all_notes()
    assert len(notes) == 8, f"Expected 8 notes, got {len(notes)}"

    # Performance target: <5 seconds
    assert elapsed < 5.0, f"Sync took {elapsed:.2f}s, expected <5s"

    print(f"Synced {len(notes)} notes in {elapsed:.2f}s")


@pytest.mark.integration
def test_scenario_incremental_sync(tmp_path: Path) -> None:
    """Test incremental sync is faster than full sync."""
    vault_path = Path("testdata/kepano-obsidian-main")
    db_path = tmp_path / "vault.db"

    # First sync
    vault = Vault(str(vault_path), str(db_path))
    vault.sync()

    # Second sync (no changes)
    start = time.time()
    vault.sync()
    incremental_time = time.time() - start

    # Incremental sync should be very fast (<1s)
    assert incremental_time < 1.0, f"Incremental sync took {incremental_time:.2f}s"

    print(f"Incremental sync (no changes) in {incremental_time:.2f}s")


@pytest.mark.integration
def test_scenario_empty_vault(tmp_path: Path) -> None:
    """Test handling of empty vault (AC-1.9)."""
    empty_vault_path = tmp_path / "empty_vault"
    empty_vault_path.mkdir()
    db_path = tmp_path / "vault.db"

    # Should not crash
    vault = Vault(str(empty_vault_path), str(db_path))
    vault.sync()

    notes = vault.all_notes()
    assert len(notes) == 0
