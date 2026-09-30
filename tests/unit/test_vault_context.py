"""Tests for VaultContext."""

from datetime import datetime
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.models import Note
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder


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

    assert note is not None
    assert note.title == "AI"
    assert "artificial intelligence" in note.content


def test_read_note(vault_with_notes):
    """Test reading note content."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    note = ctx.get_note("ai.md")
    assert note is not None
    content = ctx.read(note)

    assert content == note.content
    assert "artificial intelligence" in content


def test_neighbours_semantic_search(vault_with_notes):
    """Test finding semantically similar notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    assert ai_note is not None
    neighbours = ctx.neighbours(ai_note, count=2)

    # ml.md should be most similar to ai.md
    assert len(neighbours) >= 1
    assert any(n.path == "ml.md" for n in neighbours)


def test_similarity(vault_with_notes):
    """Test computing similarity between notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    assert ai_note is not None
    ml_note = ctx.get_note("ml.md")
    assert ml_note is not None
    cooking_note = ctx.get_note("cooking.md")
    assert cooking_note is not None

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
    assert ai_note is not None
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

    hubs = ctx.hubs(count=2)

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
        hubs = ctx.hubs(count=5)

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
        hubs = ctx.hubs(count=5)

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


def _unlinked_fixture(tmp_path: Path) -> VaultContext:
    """Six garden notes (three linked pairs) plus two music notes.

    Under the lexical stub, notes sharing vocabulary score ~1.0 and the two
    topics score ~0, so both the similarity threshold and the link filter
    have work to do.
    """
    builder = VaultBuilder(tmp_path)
    garden = "gardens soil compost seedlings"
    builder.note("Garden A", f"{garden} [[Garden B]]")
    builder.note("Garden B", garden)
    builder.note("Garden C", f"{garden} [[Garden D|the plot]]")  # alias link
    builder.note("Garden D", garden)
    builder.note("Garden E", garden)
    builder.note("Garden F", f"{garden} [[Garden E.md]]")  # link by path, F -> E
    builder.note("Music A", "violin concerto orchestra rehearsal")
    builder.note("Music B", "violin concerto orchestra rehearsal")
    return builder.build()


def test_unlinked_pairs_matches_bruteforce_oracle(tmp_path: Path) -> None:
    """unlinked_pairs returns exactly the unlinked pairs with similarity > 0.5,
    most similar first.

    Regressions caught: a wrong similarity matrix (unnormalised, NaN), a link
    filter that misses aliased/path links or only checks one direction, and
    dropped or duplicated pairs.
    """
    ctx = _unlinked_fixture(tmp_path)
    linked = {
        frozenset(("Garden A", "Garden B")),
        frozenset(("Garden C", "Garden D")),
        frozenset(("Garden E", "Garden F")),
    }
    oracle = {
        frozenset((a.title, b.title))
        for a, b in combinations(ctx.notes(), 2)
        if ctx.similarity(a, b) > 0.5 and frozenset((a.title, b.title)) not in linked
    }
    by_title = {n.title: n for n in ctx.notes()}
    assert all(ctx.similarity(*(by_title[t] for t in pair)) > 0.5 for pair in linked)
    assert frozenset(("Music A", "Music B")) in oracle
    assert not any("Music" in a and "Garden" in b for a, b in map(sorted, oracle))

    got = ctx.unlinked_pairs(count=100)

    keys = [frozenset((a.title, b.title)) for a, b in got]
    assert len(keys) == len(set(keys))
    assert set(keys) == oracle
    sims = [ctx.similarity(a, b) for a, b in got]
    assert sims == sorted(sims, reverse=True)
    assert len(ctx.unlinked_pairs(count=3)) == 3


def test_unlinked_pairs_sampling_never_pairs_a_note_with_itself(tmp_path: Path) -> None:
    """With more notes than candidate_limit, the recent + random sample must
    not contain a note twice, or the note is "paired" with itself (sim 1.0,
    trivially unlinked).
    """
    builder = VaultBuilder(tmp_path)
    for i in range(30):
        builder.note(f"Note {i}", "Shared idea about gardens.", modified=datetime(2024, 1, 1 + i))
    ctx = builder.build()

    got = ctx.unlinked_pairs(count=1000, candidate_limit=10)

    assert got, "identical notes are all similar; the sampling branch must yield pairs"
    assert all(a.path != b.path for a, b in got)
    keys = [frozenset((a.path, b.path)) for a, b in got]
    assert len(keys) == len(set(keys))
    # 10 distinct candidates, all mutually similar and unlinked: C(10, 2) pairs.
    assert len(got) == 45


def test_unlinked_pairs_ignores_the_journal_before_the_count_cut(tmp_path: Path) -> None:
    """Templated session notes are near-identical, so their pairs would outrank
    every user pair: journal notes must be gone before the top-``count`` cut,
    not filtered from the result afterwards.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Soil A", "compost soil worms mulch garden")
    builder.note("Soil B", "compost soil worms mulch beds")
    for i in range(6):  # C(6, 2) = 15 identical-journal pairs > count
        builder.journal(f"Session {i}", "geist suggestions for today")
    ctx = builder.build()

    pairs = ctx.unlinked_pairs(count=10)

    assert [{a.title, b.title} for a, b in pairs] == [{"Soil A", "Soil B"}]


def test_notes_excludes_only_the_session_journal(tmp_path: Path) -> None:
    """Session output under "geist journal/" is not the user's writing; every
    user note, including one whose name merely starts with "geist journal", is
    kept, and a journal note is still reachable when asked for by path.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Ideas", "garden plans")
    builder.note("geist journal ideas", "notes about the journal, written by the user")
    builder.note("Daily", "a nested note", folder="Archive")
    builder.journal("2024-03-14", "yesterday's suggestions")
    journal = builder.journal("2024-03-15", "today's suggestions")
    ctx = builder.build()

    kept = {n.path for n in ctx.notes()}

    assert kept == {"Ideas.md", "geist journal ideas.md", "Archive/Daily.md"}
    assert ctx.notes_excluding_journal() == ctx.notes()
    assert ctx.get_note(journal) is not None


def test_no_vault_wide_lookup_returns_a_journal_note(tmp_path: Path) -> None:
    """Every lookup that ranges over the vault skips session journal notes.

    The journal note is built to win each lookup were it visible: it shares
    all of Seed's vocabulary (nearest neighbour, unlinked pair, cluster
    member, contrarian candidate), links to Seed and Target (backlinks, hub
    count, graph neighbours), is the oldest and newest edit in turn, and is
    linked from Seed (outgoing link). The user's link to it still resolves.
    """
    old, new = datetime(2020, 1, 1), datetime(2024, 3, 1)
    builder = VaultBuilder(tmp_path)
    builder.note("Seed", "orchard cider apples pruning [[Target]] [[Echo]]", created=new)
    builder.note("Twin", "orchard cider apples pruning grafting", created=new)
    builder.note("Target", "glacier moraine crevasse", created=new)
    for i in range(3):
        builder.note(f"Cluster {i}", "violin bow rosin strings", created=new)
    for i in range(3):
        builder.note(f"More {i}", "orchard cider apples pruning", created=new)
    builder.journal(
        "Echo", "orchard cider apples pruning [[Seed]] [[Target]]", created=old, modified=old
    )
    ctx = builder.build()
    by_title = {n.title: n for n in ctx.notes()}
    seed, target = by_title["Seed"], by_title["Target"]

    def journal(notes: list[Note]) -> list[str]:
        return [n.path for n in notes if n.path.startswith("geist journal/")]

    assert "Echo" not in by_title
    assert journal(ctx.neighbours(seed, count=20)) == []
    assert journal([n for n, _ in ctx.neighbours(seed, count=20, return_scores=True)]) == []
    assert len(ctx.neighbours(seed, count=5)) == 5
    assert journal(ctx.backlinks(target)) == [] and ctx.backlinks(target) == [seed]
    assert journal(ctx.backlinks(seed)) == []
    assert journal(ctx.outgoing_links(seed)) == [] and ctx.outgoing_links(seed) == [target]
    assert journal(ctx.graph_neighbours(seed)) == []
    assert journal(ctx.hubs(10)) == [] and journal(ctx.orphans()) == []
    assert journal(ctx.old_notes(1)) == [] and journal(ctx.recent_notes(20)) == []
    assert journal(ctx.random_notes(20)) == []
    assert journal([n for pair in ctx.unlinked_pairs(count=100) for n in pair]) == []
    assert not any(p.startswith("geist journal/") for p in ctx.get_all_embeddings())
    assert not any(p.startswith("geist journal/") for p in ctx.surprisal_scores(k_neighbours=3))
    clustered = [n for c in ctx.get_clusters(min_size=3).values() for n in c.notes]
    assert clustered and journal(clustered) == []
    assert ctx.call_function("contrarian_to", "Target", 20)
    assert not any("Echo" in ref for ref in ctx.call_function("contrarian_to", "Target", 20))
    # Explicit access still works: a user's link to a session note resolves.
    echo = ctx.resolve_link_target("Echo", seed.path)
    assert echo is not None and echo.path == "geist journal/Echo.md"


def test_links_between(vault_with_notes):
    """Test finding links between notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ml_note = ctx.get_note("ml.md")
    assert ml_note is not None
    ai_note = ctx.get_note("ai.md")
    assert ai_note is not None

    links = ctx.links_between(ml_note, ai_note)

    # ml.md has a link to ai.md
    assert len(links) > 0


def test_old_notes(vault_with_notes):
    """Test finding oldest notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    old = ctx.old_notes(count=2)

    assert len(old) <= 2
    # Should be sorted by modification time ascending
    if len(old) >= 2:
        assert old[0].modified <= old[1].modified


def test_recent_notes(vault_with_notes):
    """Test finding most recent notes."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    recent = ctx.recent_notes(count=2)

    assert len(recent) <= 2
    # Should be sorted by modification time descending
    if len(recent) >= 2:
        assert recent[0].modified >= recent[1].modified


def test_metadata(vault_with_notes):
    """Test metadata access."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)

    ai_note = ctx.get_note("ai.md")
    assert ai_note is not None
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
    assert ai_note is not None

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

    random_notes = ctx.random_notes(count=3)

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


def test_batch_similarity_uses_cache(vault_with_notes):
    """Verify batch_similarity integrates with session cache."""
    vault, session = vault_with_notes
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


def test_batch_similarity_populates_cache(vault_with_notes):
    """Verify batch_similarity populates cache for all computed pairs."""
    vault, session = vault_with_notes
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


def test_batch_similarity_cache_consistency_with_individual(vault_with_notes):
    """Verify batch_similarity and similarity() use same cache."""
    vault, session = vault_with_notes
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


def test_batch_similarity_matches_scalar_similarity_on_cold_caches(vault_with_notes):
    """batch_similarity's matrix equals similarity() computed independently.

    Two fresh contexts, so neither result can come from the other's cache.
    Stored embeddings are not unit-norm (0.9-weighted semantic + temporal),
    so a matrix that skips normalisation on either side fails here. A note
    absent from the session scores 0.0 in both APIs (a zero row, never NaN).
    """
    import numpy as np

    vault, session = vault_with_notes
    batch_ctx = VaultContext(vault, session)
    scalar_ctx = VaultContext(vault, session)
    notes = batch_ctx.notes()
    ghost = Note(
        path="ghost.md",
        title="Ghost",
        content="# Ghost",
        links=[],
        tags=[],
        created=datetime(2023, 1, 1),
        modified=datetime(2023, 1, 1),
    )
    rows = [*notes, ghost]

    result = batch_ctx.batch_similarity(rows, notes)

    expected = np.array([[scalar_ctx.similarity(a, b) for b in notes] for a in rows])
    np.testing.assert_allclose(result, expected, rtol=0, atol=1e-6)
    assert np.all(result[-1] == 0.0)
    assert np.any((expected > 0.05) & (expected < 0.95)), "fixture must not be all 0/1"


def test_batch_similarity_100_percent_cache_hit(vault_with_notes):
    """Verify fast path when all pairs cached."""
    from unittest.mock import patch

    vault, session = vault_with_notes
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


def test_batch_similarity_partial_cache_hit(vault_with_notes):
    """Verify behavior when some pairs cached, some not."""
    vault, session = vault_with_notes
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


def test_batch_similarity_empty_input(vault_with_notes):
    """Verify batch_similarity handles empty inputs gracefully."""
    vault, session = vault_with_notes
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


def test_call_function_local_fallback_passes_positional_args(vault_with_notes):
    """Regression: the local-function fallback dropped *args entirely."""
    vault, session = vault_with_notes
    ctx = VaultContext(vault, session)  # no registry attached

    ctx.register_function("combine", lambda vault, a, b=0: (a, b))

    assert ctx.call_function("combine", 1, b=2) == (1, 2)
    assert ctx.call_function("combine", 7) == (7, 0)


def test_list_functions_includes_registry_builtins(vault_with_notes):
    """Regression: list_functions() returned [] whenever a registry was
    attached (it only consulted the local dict)."""
    from geistfabrik.function_registry import FunctionRegistry

    vault, session = vault_with_notes
    ctx = VaultContext(vault, session, function_registry=FunctionRegistry())

    names = ctx.list_functions()
    assert "sample_notes" in names  # a builtin
    assert "orphans" in names

    ctx.register_function("my_local", lambda vault: [])
    assert "my_local" in ctx.list_functions()
