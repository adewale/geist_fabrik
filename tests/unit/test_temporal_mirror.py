"""Unit tests for temporal_mirror geist."""

import os
from datetime import datetime, timedelta

import pytest

from geistfabrik import Vault, VaultContext
from geistfabrik.default_geists.code import temporal_mirror
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
def vault_with_temporal_notes(tmp_path):
    """Create a vault with notes spread across time periods."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    now = datetime.now()

    # Create notes across different time periods (2 years)
    for i in range(50):
        date = now - timedelta(days=i * 15)  # Every 15 days
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nContent from period {i}.")
        # Set file times to distribute across time
        timestamp = date.timestamp()
        os.utime(path, (timestamp, timestamp))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


@pytest.fixture
def vault_insufficient_notes(tmp_path):
    """Create a vault with only 1 note."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    (vault_path / "single.md").write_text("# Single\n\nOnly one note.")

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(datetime.now(), vault.db)
    session.compute_embeddings(vault.all_notes())

    return vault, session


# ============================================================================
# Core Functionality Tests
# ============================================================================


def test_temporal_mirror_returns_suggestion(vault_with_temporal_notes):
    """Test that temporal_mirror returns exactly one suggestion."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    # Should return exactly 1 suggestion
    assert isinstance(suggestions, list)
    assert len(suggestions) == 1


def test_temporal_mirror_suggestion_structure(vault_with_temporal_notes):
    """Test that suggestions have correct structure.

    Setup:
        Vault with temporal patterns.

    Verifies:
        - Has required fields
        - References temporally related notes"""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    # BEHAVIORAL: Verify geist follows output constraints
    # (This is a basic check - deeper assertions added to high-priority geists in Session 2)
    for suggestion in suggestions:
        # Required fields
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "notes")
        assert hasattr(suggestion, "geist_id")

        # Correct types and values
        assert isinstance(suggestion.text, str)
        assert len(suggestion.text) > 0
        assert isinstance(suggestion.notes, list)
        assert suggestion.geist_id == "temporal_mirror"

        # Should reference 2 notes (one from each period)
        assert len(suggestion.notes) == 2

        # Note references should be strings
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


def test_temporal_mirror_uses_obsidian_link(vault_with_temporal_notes):
    """Test that temporal_mirror uses obsidian_link for note references.

    Setup:
        Vault with temporal patterns.

    Verifies:
        - Uses [[wiki-link]] format"""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    for suggestion in suggestions:
        # Check that text uses [[wiki-link]] format
        assert "[[" in suggestion.text
        assert "]]" in suggestion.text

        # Check that text mentions periods
        assert "period" in suggestion.text.lower()

        # Check that notes list contains proper references
        for note_ref in suggestion.notes:
            assert isinstance(note_ref, str)


# ============================================================================
# Edge Case Tests
# ============================================================================


def test_temporal_mirror_empty_vault(tmp_path):
    """Test that temporal_mirror handles empty vault gracefully.

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

    suggestions = temporal_mirror.suggest(context)

    # Should return empty list, not crash
    assert isinstance(suggestions, list)
    assert len(suggestions) == 0


def test_temporal_mirror_insufficient_notes(vault_insufficient_notes):
    """Test that temporal_mirror handles insufficient notes gracefully.

    Setup:
        Vault with < 20 notes.

    Verifies:
        - Returns empty list"""
    vault, session = vault_insufficient_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    # Should return empty list when < 2 notes
    assert len(suggestions) == 0


def test_temporal_mirror_excludes_geist_journal(tmp_path):
    """Test that geist journal notes are excluded from suggestions.

    Setup:
        Vault with journal + regular notes.

    Verifies:
        - No journal in suggestions"""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()

    # Create geist journal directory
    journal_dir = vault_path / "geist journal"
    journal_dir.mkdir()

    now = datetime.now()

    for i in range(5):
        date = now - timedelta(days=i)
        (journal_dir / f"2024-03-{15 + i:02d}.md").write_text(
            f"# Session {i}\n\nTemporal mirroring patterns across different periods."
        )
        # Set file times
        timestamp = (now - timedelta(days=i * 75)).timestamp()
        os.utime(journal_dir / f"2024-03-{15 + i:02d}.md", (timestamp, timestamp))

    # Create regular notes spread across time periods (2 years)
    for i in range(50):
        date = now - timedelta(days=i * 15)  # Every 15 days
        path = vault_path / f"note_{i}.md"
        path.write_text(f"# Note {i}\n\nContent from period {i}.")
        # Set file times to distribute across time
        timestamp = date.timestamp()
        os.utime(path, (timestamp, timestamp))

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    session = Session(now, vault.db)
    session.compute_embeddings(vault.all_notes())

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    # Verify no suggestions reference geist journal notes
    for suggestion in suggestions:
        for note_ref in suggestion.notes:
            assert "geist journal" not in note_ref.lower()
            assert "session" not in note_ref.lower()


def test_temporal_mirror_deterministic_with_seed(vault_with_temporal_notes):
    """Test that temporal_mirror returns same results with same seed.

    Setup:
        Vault tested twice with same seed.

    Verifies:
        - Identical output"""
    vault, session = vault_with_temporal_notes

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

    suggestions1 = temporal_mirror.suggest(context1)
    suggestions2 = temporal_mirror.suggest(context2)

    # Same seed should produce same results
    assert len(suggestions1) == len(suggestions2)
    assert len(suggestions1) == 1

    # Compare suggestion texts
    assert suggestions1[0].text == suggestions2[0].text


def test_temporal_mirror_divides_into_periods(vault_with_temporal_notes):
    """Test that temporal_mirror divides vault into 10 periods."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    # Should return 1 suggestion
    assert len(suggestions) == 1

    # Suggestion should reference period numbers
    text = suggestions[0].text
    assert "period" in text.lower()

    # Period numbers should be 1-10 (1-indexed)
    import re

    period_numbers = re.findall(r"period (\d+)", text, re.IGNORECASE)
    assert len(period_numbers) == 2  # Two different periods

    for period_num in period_numbers:
        period_int = int(period_num)
        assert 1 <= period_int <= 10


def test_temporal_mirror_selects_different_periods(vault_with_temporal_notes):
    """Test that temporal_mirror selects two different periods."""
    vault, session = vault_with_temporal_notes

    context = VaultContext(
        vault=vault,
        session=session,
        seed=20240315,
        function_registry=FunctionRegistry(),
    )

    suggestions = temporal_mirror.suggest(context)

    assert len(suggestions) == 1

    # Extract period numbers from suggestion text
    text = suggestions[0].text
    import re

    period_numbers = re.findall(r"period (\d+)", text, re.IGNORECASE)

    # Should reference 2 different periods
    assert len(period_numbers) == 2
    assert period_numbers[0] != period_numbers[1]
