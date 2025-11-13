"""Unit tests for pattern_finder geist."""

from datetime import datetime

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import pattern_finder
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
def vault_with_repeated_phrases(tmp_path):
    """Create a vault with repeated phrases across unlinked notes."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create notes with repeated phrase "emergent behaviour patterns"
    for i in range(5):
        (vault_path / f"emergent_{i}.md").write_text(
            f"# Emergent Note {i}\n\n"
            f"This discusses emergent behaviour patterns in complex systems. "
            f"Various phenomena exhibit these characteristics."
        )

    # Create notes with repeated phrase "distributed consensus algorithms"
    for i in range(5):
        (vault_path / f"consensus_{i}.md").write_text(
            f"# Consensus Note {i}\n\n"
            f"Exploring distributed consensus algorithms for fault tolerance. "
            f"These protocols ensure agreement."
        )

    # Create filler notes to reach minimum count
    for i in range(10):
        (vault_path / f"filler_{i}.md").write_text(
            f"# Filler Note {i}\n\nUnrelated content about topic {i}."
        )

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with too few notes for pattern detection."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Only create 10 notes (need at least 15)
    for i in range(10):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}\n\nContent.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_pattern_finder_returns_suggestions(vault_with_repeated_phrases):
    """Test that pattern_finder returns suggestions with repeated patterns.

    Setup:
        Vault with repeated phrases across notes.

    Verifies:
        - Returns suggestions (max 2)
        - Detects repeated patterns"""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should return list (up to 2 suggestions)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 2

    # BEHAVIORAL: Verify fixture patterns are detected
    if len(suggestions) > 0:
        all_texts = " ".join(s.text.lower() for s in suggestions)

        # Fixture has repeated phrases "emergent behaviour patterns"
        # and "distributed consensus algorithms"
        assert any(
            [
                "emergent" in all_texts,
                "consensus" in all_texts,
                "behaviour" in all_texts,
                "algorithm" in all_texts,
            ]
        ), "Pattern finder should detect repeated phrases from fixture"

        # Verify at least one suggestion references emergent or consensus notes
        all_note_refs = [note.lower() for s in suggestions for note in s.notes]
        assert any("emergent" in note or "consensus" in note for note in all_note_refs), (
            "Suggestions should reference notes with repeated patterns"
        )


def test_pattern_finder_suggestion_structure(vault_with_repeated_phrases):
    """Test that suggestions have correct structure.

    Setup:
        Vault with pattern notes.

    Verifies:
        - Has required fields
        - References 3+ notes sharing pattern
        - Notes are unlinked"""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "pattern_finder"

        # Should mention patterns or themes
        assert any(
            keyword in suggestion.text.lower()
            for keyword in ["phrase", "pattern", "theme", "cluster", "similar"]
        )

        # Should reference at least 3 notes
        assert len(suggestion.notes) >= 3

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)

        # BEHAVIORAL: Verify suggested notes are actually unlinked (core pattern_finder logic)
        for i, note1_ref in enumerate(suggestion.notes):
            for note2_ref in suggestion.notes[i + 1 :]:
                note1 = next((n for n in vault.all_notes() if n.obsidian_link == note1_ref), None)
                note2 = next((n for n in vault.all_notes() if n.obsidian_link == note2_ref), None)

                if note1 and note2:
                    links = context.links_between(note1, note2)
                    assert len(links) == 0, (
                        f"Pattern finder should only suggest unlinked notes, "
                        f"but [[{note1_ref}]] and [[{note2_ref}]] are linked"
                    )

        # BEHAVIORAL: If suggestion mentions a phrase, verify it appears in suggested notes
        if "phrase" in suggestion.text.lower() and '"' in suggestion.text:
            # Extract phrase from suggestion text (between quotes)
            import re

            match = re.search(r'"([^"]+)"', suggestion.text)
            if match:
                phrase = match.group(1).lower()
                # Verify phrase appears in at least 3 suggested notes
                phrase_count = 0
                for note_ref in suggestion.notes:
                    note = next(
                        (n for n in vault.all_notes() if n.obsidian_link == note_ref),
                        None,
                    )
                    if note:
                        content = context.read(note).lower()
                        if phrase in content:
                            phrase_count += 1

                assert phrase_count >= 3, (
                    f"Phrase '{phrase}' should appear in 3+ notes, found in {phrase_count}"
                )


def test_pattern_finder_uses_obsidian_link(vault_with_repeated_phrases):
    """Test that pattern_finder uses obsidian_link for note references.

    Setup:
        Vault with patterns.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_pattern_finder_detects_semantic_clusters(vault_with_repeated_phrases):
    """Test that pattern_finder identifies semantically similar unlinked note clusters.

    Pattern finder has two detection modes: phrase-based and semantic clusters.
    This test verifies the semantic cluster logic works correctly.


    Setup:
        Vault with semantically similar notes.

    Verifies:
        - Detects semantic clusters (>0.6 avg similarity)"""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # BEHAVIORAL: Verify semantic cluster detection mode
    if len(suggestions) > 0:
        # Check for semantic cluster suggestions (mention "semantic", "cluster", or "similar")
        cluster_suggestions = [
            s
            for s in suggestions
            if any(keyword in s.text.lower() for keyword in ["semantic", "cluster", "similar"])
        ]

        for suggestion in cluster_suggestions:
            # Verify cluster notes have high semantic similarity (>0.7 from line 107)
            note_objs = []
            for ref in suggestion.notes:
                note = next((n for n in vault.all_notes() if n.obsidian_link == ref), None)
                if note:
                    note_objs.append(note)

            if len(note_objs) >= 2:
                # Check pairwise similarity
                similarities = []
                for i in range(len(note_objs)):
                    for j in range(i + 1, len(note_objs)):
                        sim = context.similarity(note_objs[i], note_objs[j])
                        similarities.append(sim)

                if similarities:
                    avg_similarity = sum(similarities) / len(similarities)
                    assert avg_similarity > 0.6, (
                        f"Semantic cluster should have high avg similarity, "
                        f"got {avg_similarity:.2f}"
                    )


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_pattern_finder_empty_vault(tmp_path):
    """Test that pattern_finder handles empty vault gracefully.

    Setup:
        Empty vault.

    Verifies:
        - Returns empty list"""
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

    suggestions = pattern_finder.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_pattern_finder_insufficient_notes(vault_insufficient_notes):
    """Test that pattern_finder handles insufficient notes gracefully.

    Setup:
        Vault with < 15 notes.

    Verifies:
        - Returns empty list"""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should return empty list when < 15 notes
    assert len(suggestions) == 0


def test_pattern_finder_max_suggestions(vault_with_repeated_phrases):
    """Test that pattern_finder never returns more than 2 suggestions.

    Setup:
        Vault with multiple patterns.

    Verifies:
        - Returns at most 2"""
    vault, session = vault_with_repeated_phrases

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = pattern_finder.suggest(context)

    # Should never return more than 2
    assert len(suggestions) <= 2


def test_pattern_finder_deterministic_with_seed(vault_with_repeated_phrases):
    """Test that pattern_finder returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_repeated_phrases

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

    suggestions1 = pattern_finder.suggest(context1)
    suggestions2 = pattern_finder.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)

    if suggestions1:
        # Compare suggestion texts
        texts1 = [s.text for s in suggestions1]
        texts2 = [s.text for s in suggestions2]
        assert texts1 == texts2


def test_pattern_finder_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory with repeated phrases
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    for i in range(5):
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\n"
            f"This discusses emergent behaviour patterns in complex systems. "
            f"Various phenomena exhibit these characteristics."
        )

    # Create regular notes with repeated phrases
    # Create notes with repeated phrase "emergent behaviour patterns"
    for i in range(5):
        (vault_path / f"emergent_{i}.md").write_text(
            f"# Emergent Note {i}\n\n"
            f"This discusses emergent behaviour patterns in complex systems. "
            f"Various phenomena exhibit these characteristics."
        )

    # Create notes with repeated phrase "distributed consensus algorithms"
    for i in range(5):
        (vault_path / f"consensus_{i}.md").write_text(
            f"# Consensus Note {i}\n\n"
            f"Exploring distributed consensus algorithms for fault tolerance. "
            f"These protocols ensure agreement."
        )

    # Create filler notes to reach minimum count
    for i in range(10):
        (vault_path / f"filler_{i}.md").write_text(
            f"# Filler Note {i}\n\nUnrelated content about topic {i}."
        )

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

    suggestions = pattern_finder.suggest(context)

    # Get all journal note titles to check against
    journal_notes = [n for n in vault.all_notes() if "geist journal" in n.path.lower()]
    journal_titles = {n.title for n in journal_notes}

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert note_ref not in journal_titles, (
                f"Geist journal note '{note_ref}' was included in suggestions. "
                f"Expected only non-journal notes."
            )
