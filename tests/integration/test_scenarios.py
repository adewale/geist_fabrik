"""End-to-end scenarios: sync, invoke, and the session journal on disk.

The invoke scenarios drive the real CLI command (``geistfabrik invoke``) on a
temporary vault and read back what it writes. They own the acceptance
criteria for writing session notes (AC-5.3/5.4), multi-day sessions (AC-5.6),
Tracery geists on a real vault (AC-6.6) and temporal geists (AC-7.5).
"""

import os
import re
import time
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import Vault
from geistfabrik.cli import create_parser
from geistfabrik.commands.invoke import InvokeCommand

# Lists every note the geist can see, so a leak of session output into the
# user's notes shows up verbatim in the next session.
LISTER_GEIST = """from geistfabrik import Suggestion


def suggest(vault):
    titles = sorted(n.title for n in vault.notes())
    links = ", ".join(f"[[{t}]]" for t in titles)
    return [Suggestion(text=f"What if {links} met?", notes=titles, geist_id="lister")]
"""

LINKER_TRACERY = """type: geist-tracery
id: linker
tracery:
  origin: "What would #note# say to its future self?"
  note: ["$vault.sample_notes(1)"]
"""


def _vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Alpha.md").write_text("# Alpha\n\nOrchard pruning and cider apples.")
    (vault / "Beta.md").write_text("# Beta\n\nGlacier moraines and crevasses.")
    code = vault / "_geistfabrik" / "geists" / "code"
    tracery = vault / "_geistfabrik" / "geists" / "tracery"
    code.mkdir(parents=True)
    tracery.mkdir(parents=True)
    (code / "lister.py").write_text(LISTER_GEIST)
    (tracery / "linker.yaml").write_text(LINKER_TRACERY)
    return vault


def _invoke(vault: Path, *args: str) -> int:
    parsed = create_parser().parse_args(["invoke", str(vault), "--quiet", *args])
    return InvokeCommand(parsed).run()


def _journal(vault: Path, date: str) -> str:
    return (vault / "geist journal" / f"{date}.md").read_text()


@pytest.mark.integration
@pytest.mark.benchmark
def test_scenario_first_time_setup(tmp_path: Path) -> None:
    """Test first-time setup scenario with kepano vault.

    AC-1.7: 10 notes should sync in <5 seconds.
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
    assert len(notes) == 10, f"Expected 10 notes, got {len(notes)}"

    # Performance target: <5 seconds
    assert elapsed < 5.0, f"Sync took {elapsed:.2f}s, expected <5s"

    print(f"Synced {len(notes)} notes in {elapsed:.2f}s")


@pytest.mark.integration
@pytest.mark.benchmark
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


@pytest.mark.integration
def test_scenario_daily_invocation_writes_the_session_note(tmp_path: Path) -> None:
    """AC-5.3/5.4: ``invoke --write`` writes geist journal/<date>.md with a
    dated title, the geist's heading and a ^gYYYYMMDD-NNN block ID."""
    vault = _vault(tmp_path)

    assert _invoke(vault, "--geist", "lister", "--date", "2025-01-15", "--write") == 0

    note = _journal(vault, "2025-01-15")
    assert note.startswith("# GeistFabrik Session – January 15, 2025\n")
    assert re.search(r"^## lister \^g20250115-001$", note, re.MULTILINE)
    assert "What if [[Alpha]], [[Beta]] met?" in note
    # Preview (no --write) leaves the journal untouched.
    assert _invoke(vault, "--geist", "lister", "--date", "2025-01-16") == 0
    assert not (vault / "geist journal" / "2025-01-16.md").exists()


@pytest.mark.integration
def test_scenario_multi_day_sessions_do_not_read_their_own_journal(tmp_path: Path) -> None:
    """AC-5.6: consecutive days write separate session notes, and a later
    session never treats earlier session notes as the user's notes."""
    vault = _vault(tmp_path)

    for date in ("2025-01-15", "2025-01-16", "2025-01-17"):
        assert _invoke(vault, "--geist", "lister", "--date", date, "--write", "--no-filter") == 0

    assert sorted(p.name for p in (vault / "geist journal").iterdir()) == [
        "2025-01-15.md",
        "2025-01-16.md",
        "2025-01-17.md",
    ]
    for date in ("2025-01-16", "2025-01-17"):
        assert "What if [[Alpha]], [[Beta]] met?" in _journal(vault, date)
        assert "GeistFabrik Session" not in _journal(vault, date).split("\n", 1)[1]
    # Re-writing an existing day is refused without --force.
    assert _invoke(vault, "--geist", "lister", "--date", "2025-01-15", "--write") != 0


@pytest.mark.integration
def test_scenario_tracery_geist_links_a_real_note(tmp_path: Path) -> None:
    """AC-6.6: a vault's Tracery geist calls a vault function and its
    expansion links an existing note (never a session note)."""
    vault = _vault(tmp_path)
    assert _invoke(vault, "--geist", "lister", "--date", "2025-01-15", "--write") == 0

    assert _invoke(vault, "--geist", "linker", "--date", "2025-01-16", "--write") == 0

    note = _journal(vault, "2025-01-16")
    match = re.search(r"What would \[\[(.+?)\]\] say to its future self\?", note)
    assert match, note
    assert match.group(1) in {"Alpha", "Beta"}


@pytest.mark.integration
def test_scenario_temporal_geist_finds_last_years_note(tmp_path: Path) -> None:
    """AC-7.5: a bundled temporal geist sees note ages from the vault's files
    (a note written on this date last year) and names it in the journal."""
    vault = _vault(tmp_path)
    old = vault / "Resolutions.md"
    old.write_text("# Resolutions\n\nPlant the orchard and learn to prune.")
    written = datetime(2024, 1, 15, 9, 0).timestamp()
    os.utime(old, (written, written))

    code = _invoke(vault, "--geist", "this_time_last_year", "--date", "2025-01-15", "--write")

    assert code == 0
    note = _journal(vault, "2025-01-15")
    assert "One year ago today" in note and "[[Resolutions]]" in note
