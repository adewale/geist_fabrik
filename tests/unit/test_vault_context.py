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


def test_hubs_returns_actual_notes_not_empty():
    """Test that hubs() returns actual Note objects with titles, not empty results.

    Regression test for bug where hubs() would return empty list because
    it couldn't resolve link targets (which are note titles) to file paths.
    """
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create a hub note
        (vault_path / "hub.md").write_text("# Hub Note\nA central note.")

        # Create several notes that link to the hub using its title
        (vault_path / "note1.md").write_text("# Note 1\nSee [[Hub Note]] for more.")
        (vault_path / "note2.md").write_text("# Note 2\nCheck out [[Hub Note]].")
        (vault_path / "note3.md").write_text("# Note 3\n[[Hub Note]] is important.")

        # Create vault and sync
        vault = Vault(vault_path)
        vault.sync()

        # Create session (no embeddings needed for link resolution test)
        session_date = datetime(2023, 6, 15)
        session = Session(session_date, vault.db)

        # Create context
        ctx = VaultContext(vault, session)

        # Get hubs - should find the hub note
        hubs = ctx.hubs(k=5)

        # Verify we got actual notes back
        assert len(hubs) > 0, "hubs() should find linked-to notes"

        # Verify the hub note is in the results
        hub_titles = [h.title for h in hubs]
        assert "Hub Note" in hub_titles, f"Expected 'Hub Note' in hubs, got: {hub_titles}"

        # Verify the note has a non-empty title (not [[]])
        for hub in hubs:
            assert hub.title, f"Hub note should have non-empty title, got: '{hub.title}'"
            assert hub.path, f"Hub note should have non-empty path, got: '{hub.path}'"

        vault.close()


def test_hubs_resolves_title_based_links():
    """Test that hubs() correctly resolves wiki-links that use note titles.

    This verifies that hubs() uses resolve_link_target() which tries:
    1. Exact path match
    2. Path + .md
    3. Title lookup

    Real-world scenario: Obsidian wiki-links like [[My Note Title]] get stored
    as "My Note Title" in the links table, not "my-note-title.md"
    """
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create notes with titles that differ from filenames
        (vault_path / "hub-note.md").write_text("# Central Hub\nThe main hub.")
        (vault_path / "other.md").write_text("# Another Note\nContent here.")

        # Links use the TITLE, not the filename
        (vault_path / "note1.md").write_text("# Note 1\nSee [[Central Hub]] for more.")
        (vault_path / "note2.md").write_text("# Note 2\nAlso [[Central Hub]] is key.")
        (vault_path / "note3.md").write_text("# Note 3\n[[Central Hub]] and [[Another Note]]")

        vault = Vault(vault_path)
        vault.sync()

        session_date = datetime(2023, 6, 15)
        session = Session(session_date, vault.db)
        ctx = VaultContext(vault, session)

        # Get top hubs
        hubs = ctx.hubs(k=5)

        # Verify we found the hubs
        assert len(hubs) >= 2, f"Expected at least 2 hubs, got {len(hubs)}"

        # Verify "Central Hub" is the top hub (3 links)
        hub_titles = [h.title for h in hubs]
        assert "Central Hub" in hub_titles, f"Expected 'Central Hub' in {hub_titles}"
        assert "Another Note" in hub_titles, f"Expected 'Another Note' in {hub_titles}"

        # Verify the most-linked hub is first
        first_hub = hubs[0].title
        assert first_hub == "Central Hub", f"Expected 'Central Hub' first, got '{first_hub}'"

        vault.close()


def test_neighbours_resolves_by_title():
    """Test that neighbours vault function resolves notes by title.

    This verifies that the neighbours() vault function (used by Tracery geists)
    can accept a note title string and resolve it to a Note object.

    Real-world scenario: semantic_neighbours.yaml does:
        seed: $vault.sample_notes(1)      # Returns Note, formatted as title string
        neighbours: $vault.neighbours(#seed#, 3)  # Receives title string

    NOTE: This test only verifies title resolution logic, not actual semantic
    similarity (which requires embeddings and network access to download models).
    """
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create notes with titles that differ from filenames
        (vault_path / "ai-note.md").write_text("# Artificial Intelligence\nContent about AI.")
        (vault_path / "ml-note.md").write_text("# Machine Learning\nContent about ML.")
        (vault_path / "cooking.md").write_text("# Cooking\nRecipes and food.")

        vault = Vault(vault_path)
        vault.sync()

        session_date = datetime(2023, 6, 15)
        session = Session(session_date, vault.db)
        ctx = VaultContext(vault, session, seed=42)

        # Test 1: resolve_link_target() works with title (not path)
        ai_note = ctx.resolve_link_target("Artificial Intelligence")
        assert ai_note is not None, "resolve_link_target should find note by title"
        assert ai_note.title == "Artificial Intelligence"
        assert ai_note.path == "ai-note.md", "Should resolve to correct file"

        # Test 2: resolve_link_target() also works with path
        ai_note_by_path = ctx.resolve_link_target("ai-note.md")
        assert ai_note_by_path is not None, "Should also work with path"
        assert ai_note_by_path.title == "Artificial Intelligence"

        # Test 3: neighbours VAULT FUNCTION resolves title to Note
        # This simulates what Tracery does when passing note titles
        from geistfabrik.function_registry import FunctionRegistry
        registry = FunctionRegistry()

        # Call with title string - should resolve, even if no neighbors found
        # (no embeddings computed, so will return empty list, but shouldn't error)
        result = registry.call("neighbours", ctx, "Artificial Intelligence", 3)

        assert isinstance(result, list), "Should return list (empty if no embeddings)"
        # If embeddings were computed, we'd get neighbors, but without them we get []
        # The important thing is it doesn't crash when resolving the title

        # Test 4: Non-existent title returns empty list
        result_missing = registry.call("neighbours", ctx, "Nonexistent Note", 3)
        assert result_missing == [], "Should return empty list for missing note"

        vault.close()


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
