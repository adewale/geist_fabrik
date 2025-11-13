"""Unit tests for bridge_builder geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import bridge_builder
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
def vault_with_hubs(tmp_path):
    """Create a vault with hub notes and potential bridge connections."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create hub A (index note) with several links
    (vault_path / "ai_hub.md").write_text(
        """# AI Hub

This is a hub for AI topics.

[[neural_networks]]
[[machine_learning]]
[[algorithms]]
"""
    )

    # Create notes linked to hub A
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning with neural networks."
    )
    (vault_path / "machine_learning.md").write_text("# Machine Learning\n\nLearning from data.")
    (vault_path / "algorithms.md").write_text("# Algorithms\n\nComputational algorithms.")

    # Create hub B with different links
    (vault_path / "cognitive_hub.md").write_text(
        """# Cognitive Hub

This is a hub for cognition topics.

[[thinking]]
[[reasoning]]
[[mental_models]]
"""
    )

    (vault_path / "thinking.md").write_text("# Thinking\n\nCognitive processes.")
    (vault_path / "reasoning.md").write_text("# Reasoning\n\nLogical reasoning.")
    (vault_path / "mental_models.md").write_text("# Mental Models\n\nFrameworks for thought.")

    # Create a semantically related note to hub A but not linked
    (vault_path / "deep_learning.md").write_text(
        "# Deep Learning\n\nNeural networks, machine learning, and artificial intelligence."
    )

    # Create a semantically related note to hub B but not linked
    (vault_path / "cognition.md").write_text(
        "# Cognition\n\nThinking, reasoning, and mental models."
    )

    # Add some unrelated notes
    for i in range(10):
        (vault_path / f"random_{i}.md").write_text(f"# Random Note {i}\n\nUnrelated content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_hubs(tmp_path):
    """Create a vault with no clear hub structure."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create a few isolated notes without hub structure
    for i in range(5):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_bridge_builder_returns_suggestions(vault_with_hubs):
    """Test that bridge_builder returns suggestions with hub structure."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # Should return list (up to 3 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3

    # BEHAVIORAL: Verify suggestions involve hubs (bridge_builder works with hubs)
    if len(suggestions) > 0:
        all_hubs = context.hubs(k=10)
        hub_links = {h.obsidian_link for h in all_hubs}

        for suggestion in suggestions:
            # At least one note in each suggestion should be a hub
            assert any(note in hub_links for note in suggestion.notes), (
                f"Bridge builder should suggest connections involving hubs, got {suggestion.notes}"
            )


def test_bridge_builder_suggestion_structure(vault_with_hubs):
    """Test that suggestions have correct structure."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "bridge_builder"

        # Should reference 2 notes (hub and potential bridge)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)

        # BEHAVIORAL: Verify similarity threshold logic (>0.6 from line 38)
        note1_ref, note2_ref = suggestion.notes[0], suggestion.notes[1]

        note1 = next((n for n in vault.all_notes() if n.obsidian_link == note1_ref), None)
        note2 = next((n for n in vault.all_notes() if n.obsidian_link == note2_ref), None)

        if note1 and note2:
            similarity = context.similarity(note1, note2)

            # Bridge builder requires similarity > 0.6 (core threshold)
            assert similarity > 0.6, (
                f"Bridge notes must have >0.6 similarity, "
                f"got {similarity:.2f} for [[{note1_ref}]] and [[{note2_ref}]]"
            )

            # Verify notes are NOT linked (that's the whole point of a bridge)
            links = context.links_between(note1, note2)
            assert len(links) == 0, (
                f"Bridge suggestions should be unlinked, "
                f"but [[{note1_ref}]] and [[{note2_ref}]] are linked"
            )


def test_bridge_builder_uses_obsidian_link(vault_with_hubs):
    """Test that bridge_builder uses obsidian_link for note references."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_bridge_builder_suggests_semantically_related_notes(vault_with_hubs):
    """Test that bridge_builder detects semantically similar but unlinked notes.

    The fixture includes:
    - deep_learning.md: Semantically similar to ai_hub but NOT linked
    - cognition.md: Semantically similar to cognitive_hub but NOT linked

    This test verifies the geist detects these semantic relationships.
    """
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # BEHAVIORAL: Verify fixture's semantic pairs are detected
    if len(suggestions) > 0:
        # Collect all note pairs from suggestions
        all_note_pairs = [tuple(sorted(s.notes)) for s in suggestions]

        # Check if semantic pairs appear (fixture setup)
        # "Deep Learning" should be suggested (semantically similar to AI Hub notes)
        # "Cognition" should be suggested (semantically similar to Cognitive Hub notes)
        all_notes_mentioned = [note.lower() for pair in all_note_pairs for note in pair]

        has_deep_learning = any(
            "deep" in note and "learning" in note for note in all_notes_mentioned
        )
        has_cognition = any("cognition" in note for note in all_notes_mentioned)

        # Verify at least one semantic pair was detected
        assert has_deep_learning or has_cognition, (
            f"Bridge builder should detect semantic pairs from fixture "
            f"(Deep Learning or Cognition unlinked but similar notes), "
            f"got pairs: {all_note_pairs}"
        )


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_bridge_builder_empty_vault(tmp_path):
    """Test that bridge_builder handles empty vault gracefully."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_bridge_builder_insufficient_hubs(vault_insufficient_hubs):
    """Test that bridge_builder handles vaults without clear hub structure."""
    vault, session = vault_insufficient_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # May return empty list or few suggestions without hub structure
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_bridge_builder_max_suggestions(vault_with_hubs):
    """Test that bridge_builder never returns more than 3 suggestions."""
    vault, session = vault_with_hubs

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # Should never return more than 3
    assert len(suggestions) <= 3


def test_bridge_builder_deterministic_with_seed(vault_with_hubs):
    """Test that bridge_builder returns same results with same seed."""
    vault, session = vault_with_hubs

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

    suggestions1 = bridge_builder.suggest(context1)
    suggestions2 = bridge_builder.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_bridge_builder_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with hub-like structure
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n[[ai_topic]] [[ml_topic]] [[dl_topic]]"
        )

    # Create hub A (index note) with several links
    (vault_path / "ai_hub.md").write_text(
        """# AI Hub

This is a hub for AI topics.

[[neural_networks]]
[[machine_learning]]
[[algorithms]]
"""
    )

    # Create notes linked to hub A
    (vault_path / "neural_networks.md").write_text(
        "# Neural Networks\n\nDeep learning with neural networks."
    )
    (vault_path / "machine_learning.md").write_text("# Machine Learning\n\nLearning from data.")
    (vault_path / "algorithms.md").write_text("# Algorithms\n\nComputational algorithms.")

    # Create a semantically related note to hub A but not linked
    (vault_path / "deep_learning.md").write_text(
        "# Deep Learning\n\nNeural networks, machine learning, and artificial intelligence."
    )

    # Add some unrelated notes
    for i in range(10):
        (vault_path / f"random_{i}.md").write_text(f"# Random Note {i}\n\nUnrelated content {i}.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = bridge_builder.suggest(context)

    # Verify no suggestions reference geist journal notes
    # Build title-to-path mapping to check note paths
    cursor = vault.db.execute("SELECT title, path FROM notes")
    title_to_path = {row[0]: row[1] for row in cursor.fetchall()}

    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            # Look up path by title or use note_ref as path
            note_path = title_to_path.get(note_ref, note_ref)
            assert "geist journal" not in note_path.lower(), (
                f"Geist journal note '{note_path}' was included in suggestions"
            )
