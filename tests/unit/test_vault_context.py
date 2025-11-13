"""Tests for VaultContext."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.function_registry import _GLOBAL_REGISTRY
from geistfabrik.models import Note
from geistfabrik.vault_context import VaultContext


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


@pytest.fixture
def vault_with_notes():
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


def test_vault_context_initialization(vault_with_notes):
    """Test VaultContext initialisation."""
    vault, session = vault_with_notes

    ctx = VaultContext(vault, session)

    assert ctx.vault is vault
    assert ctx.session is session
    assert ctx.db is vault.db
    assert ctx.rng is not None


def test_vault_context_deterministic_seed(vault_with_notes):
    """Test that same seed produces same random results."""
    vault, session = vault_with_notes

    ctx1 = VaultContext(vault, session, seed=42)
    ctx2 = VaultContext(vault, session, seed=42)

    items = list(range(100))
    sample1 = ctx1.sample(items, 10)
    sample2 = ctx2.sample(items, 10)

    assert sample1 == sample2


def test_notes_access(vault_with_notes):
    """Test accessing all notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    notes = ctx.notes()

    assert len(notes) == 5
    assert all(isinstance(n, Note) for n in notes)


def test_get_note(vault_with_notes):
    """Test getting specific note."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    note = ctx.get_note("ai.md")

    assert note is not None
    assert note.title == "AI"
    assert "artificial intelligence" in note.content


def test_read_note(vault_with_notes):
    """Test reading note content."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    note = ctx.get_note("ai.md")
    content = ctx.read(note)

    assert content == note.content
    assert "artificial intelligence" in content


def test_neighbors_semantic_search(vault_with_notes):
    """Test finding semantically similar notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    neighbours = ctx.neighbours(ai_note, k=2)

    # ml.md should be most similar to ai.md
    assert len(neighbours) >= 1
    assert any(n.path == "ml.md" for n in neighbours)


def test_similarity(vault_with_notes):
    """Test computing similarity between notes."""
    vault, session = vault_with_notes
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


def test_backlinks(vault_with_notes):
    """Test finding notes that link to a note."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    backlinks = ctx.backlinks(ai_note)

    # ml.md links to ai.md
    assert any(n.path == "ml.md" for n in backlinks)


def test_orphans(vault_with_notes):
    """Test finding orphan notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    orphans = ctx.orphans()

    # orphan.md should be in the list
    assert any(n.path == "orphan.md" for n in orphans)


def test_orphans_detects_exactly_two_orphans():
    """Test that orphan detection correctly identifies exactly 2 orphan notes.

    This test verifies the orphan detection logic by creating a vault with:
    - 2 orphan notes (no incoming or outgoing links)
    - 2 connected notes (with links between them)
    - 1 note with outgoing link only
    - 1 note with incoming link only (hub)

    Only the 2 orphan notes should be detected as orphans.
    """
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create test notes
        notes_data = [
            # Two orphan notes - no links at all
            ("orphan_one.md", "# Orphan One\nCompletely isolated note."),
            ("orphan_two.md", "# Orphan Two\nAnother isolated note."),
            # Two connected notes - link to each other
            ("connected_a.md", "# Connected A\nLinks to [[Connected B]]."),
            ("connected_b.md", "# Connected B\nLinks to [[Connected A]]."),
            # Note with outgoing link only - links to hub
            ("linker.md", "# Linker\nLinks to [[Hub]]."),
            # Note with incoming link only - hub
            ("hub.md", "# Hub\nReceives links but doesn't link out."),
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

        # Create context
        ctx = VaultContext(vault, session)

        # Get orphans
        orphans = ctx.orphans()

        # Should detect exactly 2 orphans
        assert len(orphans) == 2, (
            f"Expected exactly 2 orphans, but found {len(orphans)}: {[n.path for n in orphans]}"
        )

        # Should be the correct orphans
        orphan_paths = {n.path for n in orphans}
        assert orphan_paths == {"orphan_one.md", "orphan_two.md"}, (
            f"Expected orphan_one.md and orphan_two.md, but got {orphan_paths}"
        )

        # Verify the non-orphans are not included
        assert not any(n.path == "connected_a.md" for n in orphans)
        assert not any(n.path == "connected_b.md" for n in orphans)
        assert not any(n.path == "linker.md" for n in orphans)
        assert not any(n.path == "hub.md" for n in orphans)

        vault.close()


def test_hubs(vault_with_notes):
    """Test finding hub notes."""
    vault, session = vault_with_notes
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
    """Test that neighbours vault function works as adapter layer.

    This verifies that the neighbours() vault function (adapter layer):
    - Accepts string (title) from Tracery
    - Resolves string → Note internally
    - Returns strings (titles) back to Tracery

    Real-world scenario: semantic_neighbours.yaml does:
        seed: $vault.sample_notes(1)      # Returns strings (titles)
        neighbours: $vault.neighbours(#seed#, 3)  # Receives string, returns strings

    NOTE: This test only verifies the adapter layer logic, not actual semantic
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

        # Test 1: VaultContext (domain layer) works with Note objects
        ai_note = ctx.resolve_link_target("Artificial Intelligence")
        assert ai_note is not None, "resolve_link_target should find note by title"
        assert ai_note.title == "Artificial Intelligence"
        assert ai_note.path == "ai-note.md", "Should resolve to correct file"

        # Test 2: resolve_link_target() also works with path
        ai_note_by_path = ctx.resolve_link_target("ai-note.md")
        assert ai_note_by_path is not None, "Should also work with path"
        assert ai_note_by_path.title == "Artificial Intelligence"

        # Test 3: Vault functions (adapter layer) accept and return strings
        # This simulates what Tracery does when passing note titles
        from geistfabrik.function_registry import FunctionRegistry

        registry = FunctionRegistry()

        # Call with title string - vault function resolves it internally
        # (no embeddings computed, so will return empty list, but shouldn't error)
        result = registry.call("neighbours", ctx, "Artificial Intelligence", 3)

        # Adapter layer should return strings (titles), not Note objects
        assert isinstance(result, list), "Should return list"
        assert all(isinstance(item, str) for item in result), "Should return strings, not Notes"

        # Test 4: Non-existent title returns empty list
        result_missing = registry.call("neighbours", ctx, "Nonexistent Note", 3)
        assert result_missing == [], "Should return empty list for missing note"

        vault.close()


def test_vault_functions_adapter_layer():
    """Test that all vault functions work as proper adapter layer.

    Verifies that vault functions (adapter layer) correctly:
    - Accept strings from Tracery
    - Work with Note objects internally (VaultContext methods)
    - Return strings back to Tracery

    This ensures clean separation: TraceryEngine only sees strings,
    VaultContext only sees Notes, and vault functions bridge the two.
    """
    with TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create test notes
        (vault_path / "old.md").write_text("# Old Note\nOld content.")
        (vault_path / "recent.md").write_text("# Recent Note\nRecent content.")
        (vault_path / "hub.md").write_text("# Hub Note\nHub content.")
        (vault_path / "orphan.md").write_text("# Orphan Note\nOrphan content.")
        (vault_path / "note1.md").write_text("# Note 1\nLinks to [[Hub Note]].")

        vault = Vault(vault_path)
        vault.sync()

        # Make old.md actually old
        import time

        time.sleep(0.01)

        session_date = datetime(2023, 6, 15)
        session = Session(session_date, vault.db)
        ctx = VaultContext(vault, session, seed=42)

        # Create FunctionRegistry with built-in functions
        from geistfabrik.function_registry import FunctionRegistry

        registry = FunctionRegistry()

        # Test sample_notes: List[Note] → List[str]
        result = registry.call("sample_notes", ctx, 2)
        assert isinstance(result, list), "sample_notes should return list"
        assert all(isinstance(item, str) for item in result), "Should return strings"
        assert len(result) <= 2, "Should return at most k items"

        # Test old_notes: List[Note] → List[str]
        result = registry.call("old_notes", ctx, 1)
        assert isinstance(result, list), "old_notes should return list"
        assert all(isinstance(item, str) for item in result), "Should return strings"

        # Test recent_notes: List[Note] → List[str]
        result = registry.call("recent_notes", ctx, 1)
        assert isinstance(result, list), "recent_notes should return list"
        assert all(isinstance(item, str) for item in result), "Should return strings"

        # Test orphans: List[Note] → List[str]
        result = registry.call("orphans", ctx, 1)
        assert isinstance(result, list), "orphans should return list"
        assert all(isinstance(item, str) for item in result), "Should return strings"

        # Test hubs: List[Note] → List[str] (with brackets)
        result = registry.call("hubs", ctx, 5)
        assert isinstance(result, list), "hubs should return list"
        assert all(isinstance(item, str) for item in result), "Should return strings"
        if result:  # If we found hubs
            assert "[[Hub Note]]" in result, "Should find hub by title with brackets"

        # Test random_note_title: Note → str
        result = registry.call("random_note_title", ctx)
        assert isinstance(result, str), "random_note_title should return string"
        assert len(result) > 0, "Should return non-empty title"

        # Test determinism: same seed = same result (use fresh contexts)
        ctx_fresh1 = VaultContext(vault, session, seed=999)
        ctx_fresh2 = VaultContext(vault, session, seed=999)
        result1 = registry.call("random_note_title", ctx_fresh1)
        result2 = registry.call("random_note_title", ctx_fresh2)
        assert result1 == result2, "Same seed should give same random note"

        vault.close()


def test_unlinked_pairs(vault_with_notes):
    """Test finding similar but unlinked note pairs."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    pairs = ctx.unlinked_pairs(k=3)

    assert len(pairs) <= 3
    for a, b in pairs:
        assert isinstance(a, Note)
        assert isinstance(b, Note)
        # Verify no links between them
        assert len(ctx.links_between(a, b)) == 0


def test_links_between(vault_with_notes):
    """Test finding links between notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ml_note = ctx.get_note("ml.md")
    ai_note = ctx.get_note("ai.md")

    links = ctx.links_between(ml_note, ai_note)

    # ml.md has a link to ai.md
    assert len(links) > 0


def test_old_notes(vault_with_notes):
    """Test finding oldest notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    old = ctx.old_notes(k=2)

    assert len(old) <= 2
    # Should be sorted by modification time ascending
    if len(old) >= 2:
        assert old[0].modified <= old[1].modified


def test_recent_notes(vault_with_notes):
    """Test finding most recent notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    recent = ctx.recent_notes(k=2)

    assert len(recent) <= 2
    # Should be sorted by modification time descending
    if len(recent) >= 2:
        assert recent[0].modified >= recent[1].modified


def test_metadata(vault_with_notes):
    """Test metadata access."""
    vault, session = vault_with_notes
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


def test_metadata_caching(vault_with_notes):
    """Test that metadata is cached."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")

    metadata1 = ctx.metadata(ai_note)
    metadata2 = ctx.metadata(ai_note)

    # Should be the same object (cached)
    assert metadata1 is metadata2


def test_sample(vault_with_notes):
    """Test deterministic sampling."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session, seed=42)

    items = list(range(10))
    sample1 = ctx.sample(items, 5)
    sample2 = ctx.sample(items, 5)

    # Different calls produce different samples (RNG advances)
    # But with same seed, sequence is deterministic
    assert len(sample1) == 5
    assert len(sample2) == 5


def test_random_notes(vault_with_notes):
    """Test random note sampling."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session, seed=42)

    random_notes = ctx.random_notes(k=3)

    assert len(random_notes) == 3
    assert all(isinstance(n, Note) for n in random_notes)


def test_function_registry(vault_with_notes):
    """Test function registration and calling."""
    vault, session = vault_with_notes
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


def test_call_nonexistent_function(vault_with_notes):
    """Test that calling nonexistent function raises KeyError."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    with pytest.raises(KeyError, match="not registered"):
        ctx.call_function("nonexistent")


def test_vault_context_with_date_seed(vault_with_notes):
    """Test that date is used as default seed."""
    vault, session = vault_with_notes

    # Create two contexts for same date
    ctx1 = VaultContext(vault, session)  # Uses session date as seed
    ctx2 = VaultContext(vault, session)

    items = list(range(100))
    sample1 = ctx1.sample(items, 10)
    sample2 = ctx2.sample(items, 10)

    # Should produce same samples since same date
    assert sample1 == sample2


# Cache Integration Tests for batch_similarity


def test_batch_similarity_uses_cache(test_vault_with_notes):
    """Verify batch_similarity integrates with session cache."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)
    notes = ctx.notes()[:5]

    # First call: cold cache
    result1 = ctx.batch_similarity(notes[:3], notes[2:])

    # Verify cache was populated
    cache_size_before = len(ctx._similarity_cache)
    assert cache_size_before > 0, "Cache should be populated after batch_similarity"

    # Second call: should hit cache
    result2 = ctx.batch_similarity(notes[:3], notes[2:])

    # Results should be identical
    import numpy as np

    np.testing.assert_array_almost_equal(result1, result2)

    # Cache size shouldn't change (all hits)
    assert len(ctx._similarity_cache) == cache_size_before


def test_batch_similarity_populates_cache(test_vault_with_notes):
    """Verify batch_similarity populates cache for all computed pairs."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)
    notes = ctx.notes()[:4]

    # Clear cache
    ctx._similarity_cache.clear()

    # Compute 4×4 matrix = 16 pairs (but 4×3 / 2 = 6 unique pairs since symmetric)
    # Actually 4×4 = 16 total pairs in the matrix
    result = ctx.batch_similarity(notes[:2], notes[2:])

    # Should have cached 2×2 = 4 pairs
    cache_size = len(ctx._similarity_cache)
    assert cache_size == 4, f"Expected 4 cached pairs, got {cache_size}"

    # Verify each pair is cached
    for i, note_a in enumerate(notes[:2]):
        for j, note_b in enumerate(notes[2:]):
            sorted_paths = sorted([note_a.path, note_b.path])
            cache_key = (sorted_paths[0], sorted_paths[1])
            assert cache_key in ctx._similarity_cache
            import numpy as np

            np.testing.assert_almost_equal(
                ctx._similarity_cache[cache_key], result[i, j], decimal=6
            )


def test_batch_similarity_cache_consistency_with_individual(test_vault_with_notes):
    """Verify batch_similarity and similarity() use same cache."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)
    notes = ctx.notes()[:4]

    # Compute some pairs individually
    ctx.similarity(notes[0], notes[1])
    ctx.similarity(notes[2], notes[3])

    cache_size_after_individual = len(ctx._similarity_cache)

    # Batch compute matrix including some cached pairs
    result = ctx.batch_similarity(notes[:2], notes[2:])

    # The batch call should have added 2 more pairs (0,2), (0,3), (1,2), (1,3)
    # We already had (0,1) and (2,3) from individual calls
    # But (0,1) and (2,3) are not in the batch matrix [:2] × [2:]
    # So batch should add 4 new pairs
    assert len(ctx._similarity_cache) > cache_size_after_individual

    # Now compute one of the batch pairs individually - should hit cache
    sim_02_individual = ctx.similarity(notes[0], notes[2])
    import numpy as np

    np.testing.assert_almost_equal(sim_02_individual, result[0, 0], decimal=6)

    # Cache shouldn't grow (was already cached by batch call)
    cache_size_after = len(ctx._similarity_cache)
    ctx.similarity(notes[0], notes[2])  # Same pair again
    assert len(ctx._similarity_cache) == cache_size_after


def test_batch_similarity_100_percent_cache_hit(test_vault_with_notes):
    """Verify fast path when all pairs cached."""
    from unittest.mock import patch

    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)
    notes = ctx.notes()[:3]

    # Warm cache with individual calls
    for i in range(len(notes)):
        for j in range(len(notes)):
            ctx.similarity(notes[i], notes[j])

    # Batch call should be instant (no backend calls)
    with patch.object(ctx._backend, "get_embedding") as mock_get:
        result = ctx.batch_similarity(notes, notes)
        mock_get.assert_not_called()  # No embeddings fetched!

    # Results should still be correct
    assert result.shape == (3, 3)
    # Diagonal should be 1.0 (note similar to itself)
    for i in range(3):
        diagonal_val = result[i, i]
        assert diagonal_val > 0.95, f"Diagonal element [{i},{i}] should be ~1.0, got {diagonal_val}"


def test_batch_similarity_partial_cache_hit(test_vault_with_notes):
    """Verify behavior when some pairs cached, some not."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)
    notes = ctx.notes()[:4]

    # Warm cache with some individual calls
    ctx.similarity(notes[0], notes[2])  # Cache this pair
    ctx.similarity(notes[1], notes[3])  # Cache this pair

    cache_size_before = len(ctx._similarity_cache)

    # Batch compute 2×2 matrix (4 pairs total, 2 already cached)
    result = ctx.batch_similarity(notes[:2], notes[2:])

    # Should have added 2 more pairs to cache
    assert len(ctx._similarity_cache) == cache_size_before + 2

    # Verify cached pairs match
    import numpy as np

    cached_sim_02 = ctx.similarity(notes[0], notes[2])
    np.testing.assert_almost_equal(cached_sim_02, result[0, 0], decimal=6)

    cached_sim_13 = ctx.similarity(notes[1], notes[3])
    np.testing.assert_almost_equal(cached_sim_13, result[1, 1], decimal=6)


def test_batch_similarity_empty_input(test_vault_with_notes):
    """Verify batch_similarity handles empty inputs gracefully."""
    vault, session = test_vault_with_notes
    ctx = VaultContext(vault, session)
    notes = ctx.notes()

    # Empty first set
    result = ctx.batch_similarity([], notes[:3])
    assert result.shape == (0, 0)

    # Empty second set
    result = ctx.batch_similarity(notes[:3], [])
    assert result.shape == (0, 0)

    # Both empty
    result = ctx.batch_similarity([], [])
    assert result.shape == (0, 0)
