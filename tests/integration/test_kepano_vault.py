"""Integration tests using the kepano Obsidian vault."""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import Vault
from geistfabrik.embeddings import Session

KEPANO_VAULT_PATH = Path(__file__).parent.parent.parent / "testdata" / "kepano-obsidian-main"


@pytest.fixture
def kepano_vault() -> Vault:
    """Create a Vault instance for the kepano test data."""
    if not KEPANO_VAULT_PATH.exists():
        pytest.skip(f"Kepano vault not found at {KEPANO_VAULT_PATH}")

    vault = Vault(KEPANO_VAULT_PATH)
    vault.sync()
    yield vault
    vault.close()


def test_load_kepano_vault(kepano_vault: Vault) -> None:
    """Test loading the kepano vault."""
    notes = kepano_vault.all_notes()

    # Kepano vault should have 8 markdown files
    assert len(notes) >= 8

    # Verify we can access each note
    for note in notes:
        assert note.path
        assert note.title
        assert note.content


def test_parse_evergreen_notes(kepano_vault: Vault) -> None:
    """Test parsing evergreen note from kepano vault."""
    # Find the evergreen note
    notes = kepano_vault.all_notes()
    evergreen = None
    for note in notes:
        if "Evergreen notes" in note.title:
            evergreen = note
            break

    if evergreen is None:
        pytest.skip("Evergreen notes file not found")

    # Verify structure
    assert evergreen.title
    assert evergreen.content
    # Evergreen notes typically have links
    assert len(evergreen.links) > 0


def test_parse_daily_note(kepano_vault: Vault) -> None:
    """Test parsing daily note from kepano vault."""
    notes = kepano_vault.all_notes()

    # Find a daily note (format: YYYY-MM-DD)
    daily_notes = [n for n in notes if n.path.startswith("2023-")]

    if not daily_notes:
        pytest.skip("No daily notes found")

    daily = daily_notes[0]
    assert daily.title
    assert daily.content


def test_parse_meeting_note(kepano_vault: Vault) -> None:
    """Test parsing meeting note from kepano vault."""
    notes = kepano_vault.all_notes()

    # Find meeting note
    meeting = None
    for note in notes:
        if "Meeting" in note.title or "Meeting" in note.path:
            meeting = note
            break

    if meeting is None:
        pytest.skip("Meeting note not found")

    assert meeting.title
    assert meeting.content


def test_kepano_link_graph(kepano_vault: Vault) -> None:
    """Test link graph structure in kepano vault."""
    notes = kepano_vault.all_notes()

    # Count total links
    total_links = sum(len(note.links) for note in notes)

    # Should have some links in the vault
    assert total_links > 0

    # Verify link structure
    for note in notes:
        for link in note.links:
            assert link.target
            # Target should be a string
            assert isinstance(link.target, str)


def test_kepano_embeddings(kepano_vault: Vault) -> None:
    """Test computing embeddings for kepano vault (AC-2.2).

    Should compute embeddings for all notes.
    Note: We compute one session, not 8×2 like the AC suggests.
    """
    notes = kepano_vault.all_notes()
    assert len(notes) == 8

    # Compute embeddings for all notes
    session = Session(datetime(2023, 6, 15), kepano_vault.db)
    session.compute_embeddings(notes)

    # Verify embeddings were computed
    embeddings = session.get_all_embeddings()

    # Should have 8 embeddings (one per note)
    assert len(embeddings) == 8

    # Each embedding should have correct dimensions (384 semantic + 3 temporal)
    for note_path, embedding in embeddings.items():
        assert embedding.shape == (387,), f"Wrong shape for {note_path}: {embedding.shape}"

    # Verify embeddings are not all zeros
    for note_path, embedding in embeddings.items():
        assert embedding.sum() != 0, f"Zero embedding for {note_path}"
