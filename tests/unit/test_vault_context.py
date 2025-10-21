"""Tests for VaultContext."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.models import Note
from geistfabrik.vault_context import VaultContext


@pytest.fixture
def test_vault_with_notes():
    """Create a test vault with sample notes."""
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create test notes
        notes_data = [
            ("ai.md", "# AI\nThis is about artificial intelligence and machine learning."),
            ("ml.md", "# Machine Learning\nDeep learning and [[ai|neural networks]]."),
            (
                "cooking.md",
                "# Cooking\nRecipes and food preparation. #food\nSee also [[baking]].",
            ),
            ("baking.md", "# Baking\nBread and pastries. #food #recipes"),
            ("orphan.md", "# Orphan\nA lonely note with no connections."),
        ]

        for filename, content in notes_data:
            (vault_path / filename).write_text(content)

        # Create vault and sync
        vault = Vault(vault_path)
        vault.sync()

        # Create session and compute embeddings
        session_date = datetime(2023, 6, 15)
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())

        yield vault, session

        vault.close()


def test_vault_context_initialization(test_vault_with_notes):
    """Test VaultContext initialization."""
    vault, session = test_vault_with_notes

    ctx = VaultContext(vault, session)

    assert ctx.vault is vault
    assert ctx.session is session
    assert ctx.db is vault.db
    assert ctx.rng is not None


def test_vault_context_deterministic_seed(test_vault_with_notes):
    """Test that same seed produces same random results."""
    vault, session = test_vault_with_notes

    ctx1 = VaultContext(vault, session, seed=42)
    ctx2 = VaultContext(vault, session, seed=42)

    items = list(range(100))
    sample1 = ctx1.sample(items, 10)
    sample2 = ctx2.sample(items, 10)

    assert sample1 == sample2


def test_notes_access(test_vault_with_notes):
    """Test accessing all notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    notes = ctx.notes()

    assert len(notes) == 5
    assert all(isinstance(n, Note) for n in notes)


def test_get_note(test_vault_with_notes):
    """Test getting specific note."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    note = ctx.get_note("ai.md")

    assert note is not None
    assert note.title == "AI"
    assert "artificial intelligence" in note.content


def test_read_note(test_vault_with_notes):
    """Test reading note content."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    note = ctx.get_note("ai.md")
    content = ctx.read(note)

    assert content == note.content
    assert "artificial intelligence" in content


def test_neighbors_semantic_search(test_vault_with_notes):
    """Test finding semantically similar notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    neighbors = ctx.neighbours(ai_note, k=2)

    # ml.md should be most similar to ai.md
    assert len(neighbors) >= 1
    assert any(n.path == "ml.md" for n in neighbors)


def test_similarity(test_vault_with_notes):
    """Test computing similarity between notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    ml_note = ctx.get_note("ml.md")
    cooking_note = ctx.get_note("cooking.md")

    # AI and ML should be more similar than AI and Cooking
    sim_ai_ml = ctx.similarity(ai_note, ml_note)
    sim_ai_cooking = ctx.similarity(ai_note, cooking_note)

    assert sim_ai_ml > sim_ai_cooking
    assert 0 <= sim_ai_ml <= 1
    assert 0 <= sim_ai_cooking <= 1


def test_backlinks(test_vault_with_notes):
    """Test finding notes that link to a note."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    backlinks = ctx.backlinks(ai_note)

    # ml.md links to ai.md
    assert any(n.path == "ml.md" for n in backlinks)


def test_orphans(test_vault_with_notes):
    """Test finding orphan notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    orphans = ctx.orphans()

    # orphan.md should be in the list
    assert any(n.path == "orphan.md" for n in orphans)


def test_hubs(test_vault_with_notes):
    """Test finding hub notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    hubs = ctx.hubs(k=2)

    # Should find notes that are linked to
    assert len(hubs) <= 2


def test_unlinked_pairs(test_vault_with_notes):
    """Test finding similar but unlinked note pairs."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    pairs = ctx.unlinked_pairs(k=3)

    assert len(pairs) <= 3
    for a, b in pairs:
        assert isinstance(a, Note)
        assert isinstance(b, Note)
        # Verify no links between them
        assert len(ctx.links_between(a, b)) == 0


def test_links_between(test_vault_with_notes):
    """Test finding links between notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    ml_note = ctx.get_note("ml.md")
    ai_note = ctx.get_note("ai.md")

    links = ctx.links_between(ml_note, ai_note)

    # ml.md has a link to ai.md
    assert len(links) > 0


def test_old_notes(test_vault_with_notes):
    """Test finding oldest notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    old = ctx.old_notes(k=2)

    assert len(old) <= 2
    # Should be sorted by modification time ascending
    if len(old) >= 2:
        assert old[0].modified <= old[1].modified


def test_recent_notes(test_vault_with_notes):
    """Test finding most recent notes."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    recent = ctx.recent_notes(k=2)

    assert len(recent) <= 2
    # Should be sorted by modification time descending
    if len(recent) >= 2:
        assert recent[0].modified >= recent[1].modified


def test_metadata(test_vault_with_notes):
    """Test metadata access."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    metadata = ctx.metadata(ai_note)

    assert "word_count" in metadata
    assert "link_count" in metadata
    assert "tag_count" in metadata
    assert "age_days" in metadata

    assert metadata["word_count"] > 0
    assert metadata["link_count"] == 0  # ai.md has no outgoing links
    assert metadata["tag_count"] == 0  # ai.md has no tags


def test_metadata_caching(test_vault_with_notes):
    """Test that metadata is cached."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")

    metadata1 = ctx.metadata(ai_note)
    metadata2 = ctx.metadata(ai_note)

    # Should be the same object (cached)
    assert metadata1 is metadata2


def test_sample(test_vault_with_notes):
    """Test deterministic sampling."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session, seed=42)

    items = list(range(10))
    sample1 = ctx.sample(items, 5)
    sample2 = ctx.sample(items, 5)

    # Different calls produce different samples (RNG advances)
    # But with same seed, sequence is deterministic
    assert len(sample1) == 5
    assert len(sample2) == 5


def test_random_notes(test_vault_with_notes):
    """Test random note sampling."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session, seed=42)

    random_notes = ctx.random_notes(k=3)

    assert len(random_notes) == 3
    assert all(isinstance(n, Note) for n in random_notes)


def test_function_registry(test_vault_with_notes):
    """Test function registration and calling."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    # Register a test function
    def test_func(vault_ctx, multiplier=2):
        return len(vault_ctx.notes()) * multiplier

    ctx.register_function("test_func", test_func)

    # Test function is listed
    assert "test_func" in ctx.list_functions()

    # Test calling function
    result = ctx.call_function("test_func", multiplier=3)
    assert result == 15  # 5 notes * 3


def test_call_nonexistent_function(test_vault_with_notes):
    """Test that calling nonexistent function raises KeyError."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)

    with pytest.raises(KeyError, match="not registered"):
        ctx.call_function("nonexistent")


def test_vault_context_with_date_seed(test_vault_with_notes):
    """Test that date is used as default seed."""
    vault, session = test_vault_with_notes

    # Create two contexts for same date
    ctx1 = VaultContext(vault, session)  # Uses session date as seed
    ctx2 = VaultContext(vault, session)

    items = list(range(100))
    sample1 = ctx1.sample(items, 10)
    sample2 = ctx2.sample(items, 10)

    # Should produce same samples since same date
    assert sample1 == sample2
