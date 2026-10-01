"""Integration tests using the kepano Obsidian vault."""

from collections.abc import Generator
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from geistfabrik import Vault
from geistfabrik.embeddings import Session
from geistfabrik.models import Note

KEPANO_VAULT_PATH = Path(__file__).parent.parent.parent / "testdata" / "kepano-obsidian-main"
EVERGREEN = "Evergreen notes turn ideas into objects that you can manipulate.md"


@pytest.fixture
def kepano_vault() -> Generator[Vault, None, None]:
    """Create a Vault instance for the kepano test data."""
    assert KEPANO_VAULT_PATH.is_dir(), f"Committed vault missing: {KEPANO_VAULT_PATH}"

    vault = Vault(KEPANO_VAULT_PATH)
    vault.sync()
    yield vault
    vault.close()


KEPANO_TITLES = {
    "2023 Japan Trip",
    "2023-09-12 Meeting with Steph",
    "2023-09-12",
    "2023-09-30",
    "Evergreen notes turn ideas into objects that you can manipulate",
    "Isolated thought",
    "Minimal Theme",
    "Obsidian",
    "Product usage analysis",
    "Readme",
}


def test_load_kepano_vault(kepano_vault: Vault) -> None:
    """Every committed note loads, titled after its file, with its body."""
    notes = kepano_vault.all_notes()

    assert {note.title for note in notes} == KEPANO_TITLES
    assert all(note.content.strip() for note in notes)
    assert not any(note.is_virtual for note in notes)


def _note(vault: Vault, title: str) -> Note:
    return next(n for n in vault.all_notes() if n.title == title)


def test_parse_evergreen_notes(kepano_vault: Vault) -> None:
    """A clipping keeps its frontmatter links and its emoji and plain tags."""
    note = _note(kepano_vault, Path(EVERGREEN).stem)

    targets = {link.target for link in note.links}
    assert {"Clippings", "Steph Ango", "Evergreen", "Obsidian"} <= targets
    assert note.tags == ["0🌲", "clippings"]


def test_parse_daily_note(kepano_vault: Vault) -> None:
    """A date-titled daily note is an ordinary note (no H2 date sections)."""
    note = _note(kepano_vault, "2023-09-12")

    assert not note.is_virtual
    assert [link.target for link in note.links] == ["Daily.base"]
    assert note.tags == ["daily"]


def test_parse_meeting_note(kepano_vault: Vault) -> None:
    note = _note(kepano_vault, "2023-09-12 Meeting with Steph")

    assert {"Meetings", "Steph Ango", "Emergence", "Out of Control"} <= {
        link.target for link in note.links
    }
    assert note.tags == ["meetings"]


def test_kepano_link_graph(kepano_vault: Vault) -> None:
    """Body links, frontmatter property links and heading anchors all become links."""
    targets = {n.title: {link.target for link in n.links} for n in kepano_vault.all_notes()}

    # A body "Related:" line alongside frontmatter property links.
    assert {"Tools", "Active", "Minimal Theme", Path(EVERGREEN).stem} <= targets["Obsidian"]
    assert {"Trips", "Kyoto", "Japan"} <= targets["2023 Japan Trip"]
    # Heading anchors stay part of the target.
    assert "Products.base#Cost per use" in targets["Product usage analysis"]
    assert targets["Isolated thought"] == set()


def test_kepano_embeddings(kepano_vault: Vault) -> None:
    """Test computing embeddings for kepano vault (AC-2.2).

    Should compute embeddings for all notes.
    Note: We compute one session, not 8×2 like the AC suggests.
    """
    notes = kepano_vault.all_notes()
    assert len(notes) == 10

    # Compute embeddings for all notes
    session = Session(datetime(2023, 6, 15), kepano_vault.db)
    session.compute_embeddings(notes)

    # Verify embeddings were computed
    cursor = kepano_vault.db.execute(
        """
        SELECT note_path, embedding FROM session_embeddings
        WHERE session_id = ?
        """,
        (session.session_id,),
    )
    embeddings = {}
    for row in cursor.fetchall():
        note_path, embedding_bytes = row
        embeddings[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

    # Should have 10 embeddings (one per note)
    assert len(embeddings) == 10

    # Each embedding should have correct dimensions (384 semantic + 3 temporal)
    for note_path, embedding in embeddings.items():
        assert embedding.shape == (387,), f"Wrong shape for {note_path}: {embedding.shape}"

    # Verify embeddings are not all zeros
    for note_path, embedding in embeddings.items():
        assert embedding.sum() != 0, f"Zero embedding for {note_path}"
