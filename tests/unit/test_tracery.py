"""Tests for Tracery grammar engine and geist loading."""

from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry
from geistfabrik.tracery import TraceryEngine, TraceryGeist, TraceryGeistLoader
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def create_mock_embedding_computer(num_notes: int) -> EmbeddingComputer:
    """Create a mocked EmbeddingComputer for testing.

    Args:
        num_notes: Number of notes to generate embeddings for
    """
    computer = EmbeddingComputer()
    # Create a mock model that returns fixed embeddings
    mock_model = Mock()
    # Return embeddings with correct shape (num_notes, 387)
    mock_model.encode.return_value = np.random.rand(num_notes, 387)  # 384 semantic + 3 temporal
    computer._model = mock_model
    return computer


def create_vault_context(vault: Vault) -> VaultContext:
    """Helper to create VaultContext with Session and FunctionRegistry."""
    session_date = datetime(2025, 1, 15)
    num_notes = len(vault.all_notes())
    mock_computer = create_mock_embedding_computer(num_notes)
    session = Session(session_date, vault.db, computer=mock_computer)
    session.compute_embeddings(vault.all_notes())

    # Create FunctionRegistry with built-in functions
    function_registry = FunctionRegistry()

    return VaultContext(vault, session, function_registry=function_registry)


def test_tracery_engine_basic_expansion() -> None:
    """Test basic Tracery grammar expansion."""
    grammar = {"origin": ["Hello #name#"], "name": ["World", "Universe"]}

    engine = TraceryEngine(grammar, seed=42)
    result = engine.expand("#origin#")

    assert result in ["Hello World", "Hello Universe"]


def test_tracery_engine_deterministic() -> None:
    """Test that Tracery expansion is deterministic with same seed."""
    grammar = {
        "origin": ["#animal# #action#"],
        "animal": ["cat", "dog"],
        "action": ["runs", "jumps"],
    }

    engine1 = TraceryEngine(grammar, seed=42)
    result1 = engine1.expand("#origin#")

    engine2 = TraceryEngine(grammar, seed=42)
    result2 = engine2.expand("#origin#")

    assert result1 == result2


def test_tracery_engine_vault_function_no_args(tmp_path: Path) -> None:
    """Test Tracery vault function call with no arguments."""
    # Create minimal vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create grammar with function call
    grammar = {"origin": ["Notes: $vault.sample_notes()"]}

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    result = engine.expand("#origin#")

    # Should expand without error and contain note reference
    assert "Notes:" in result
    # Result should contain the note title (without brackets - templates add those)
    assert "Test" in result

    vault.close()


def test_tracery_engine_vault_function_with_int_arg(tmp_path: Path) -> None:
    """Test Tracery vault function call with integer argument."""
    # Create minimal vault with multiple notes
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Note 1")
    (vault_path / "note2.md").write_text("# Note 2")
    (vault_path / "note3.md").write_text("# Note 3")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create grammar with function call using integer argument
    grammar = {"origin": ["Sample: $vault.sample_notes(2)"]}

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    result = engine.expand("#origin#")

    # Should expand without error
    assert "Sample:" in result
    # Should contain note references (titles without brackets - templates add those)
    assert "Note" in result  # At least one note title should be present

    vault.close()


def test_tracery_engine_arg_type_conversion() -> None:
    """Test that TraceryEngine correctly converts string arguments to int."""
    grammar = {"origin": ["test"]}
    engine = TraceryEngine(grammar, seed=42)

    # Test integer conversion
    assert engine._convert_arg("5") == 5
    assert engine._convert_arg("42") == 42
    assert engine._convert_arg("0") == 0

    # Test string preservation
    assert engine._convert_arg("hello") == "hello"
    assert engine._convert_arg("note_title") == "note_title"

    # Test that numeric strings with quotes are converted
    assert engine._convert_arg("123") == 123


def test_tracery_engine_orphans_function(tmp_path: Path) -> None:
    """Test that orphans() function works correctly from Tracery with int argument."""
    # Create vault with orphan notes
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "orphan1.md").write_text("# Orphan 1\nNo links here")
    (vault_path / "orphan2.md").write_text("# Orphan 2\nAlso no links")
    (vault_path / "linked.md").write_text("# Linked\nLinks to [[orphan1]]")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create grammar calling orphans function
    grammar = {"origin": ["Orphans: $vault.orphans(2)"]}

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    result = engine.expand("#origin#")

    # Should expand without type error
    assert "Orphans:" in result
    assert "[Error" not in result  # No error messages

    vault.close()


def test_tracery_engine_hubs_function(tmp_path: Path) -> None:
    """Test that hubs() function works correctly from Tracery with int argument."""
    # Create vault with hub notes
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "hub.md").write_text("# Hub\nPopular note")
    (vault_path / "note1.md").write_text("# Note 1\nLinks to [[hub]]")
    (vault_path / "note2.md").write_text("# Note 2\nAlso links to [[hub]]")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create grammar calling hubs function
    grammar = {"origin": ["Hubs: $vault.hubs(1)"]}

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    result = engine.expand("#origin#")

    # Should expand without type error
    assert "Hubs:" in result
    assert "[Error" not in result  # No error messages
    # Should return hub note title (without brackets - templates add those)
    assert "Hub" in result or result == "Hubs: "  # Either has hub title or returns empty

    vault.close()


def test_tracery_geist_from_yaml(tmp_path: Path) -> None:
    """Test loading TraceryGeist from YAML file."""
    yaml_content = """type: geist-tracery
id: test_geist
tracery:
  origin: "Test suggestion"
"""

    yaml_file = tmp_path / "test_geist.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)

    assert geist.geist_id == "test_geist"


def test_tracery_geist_loader(tmp_path: Path) -> None:
    """Test TraceryGeistLoader loads multiple geists."""
    geists_dir = tmp_path / "geists"
    geists_dir.mkdir()

    # Create two test geists
    (geists_dir / "geist1.yaml").write_text(
        """type: geist-tracery
id: geist1
tracery:
  origin: "Geist 1"
"""
    )

    (geists_dir / "geist2.yaml").write_text(
        """type: geist-tracery
id: geist2
tracery:
  origin: "Geist 2"
"""
    )

    loader = TraceryGeistLoader(geists_dir, seed=42)
    geists = loader.load_all()

    assert len(geists) == 2
    assert any(g.geist_id == "geist1" for g in geists)
    assert any(g.geist_id == "geist2" for g in geists)


def test_tracery_geist_with_vault_function_call(tmp_path: Path) -> None:
    """Test TraceryGeist can call vault functions and generate suggestions."""
    # Create vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Note 1")
    (vault_path / "note2.md").write_text("# Note 2")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create geist with vault function call
    yaml_content = """type: geist-tracery
id: test_function_call
tracery:
  origin:
    - "Consider $vault.sample_notes(1)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions = geist.suggest(context)

    assert len(suggestions) > 0
    suggestion = suggestions[0]
    assert "Consider" in suggestion.text
    assert suggestion.geist_id == "test_function_call"
    # Should not have error messages
    assert "[Error" not in suggestion.text

    vault.close()


def test_tracery_engine_handles_function_errors_gracefully(tmp_path: Path) -> None:
    """Test that function call errors are caught and displayed in output."""
    # Create minimal vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create grammar calling non-existent function
    grammar = {"origin": ["Result: $vault.nonexistent_function()"]}

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    result = engine.expand("#origin#")

    # Should contain error message
    assert "[Error calling nonexistent_function:" in result

    vault.close()


def test_tracery_geist_count_parameter_recognized(tmp_path: Path) -> None:
    """Test that 'count' parameter is correctly read from YAML."""
    yaml_content = """type: geist-tracery
id: test_count
count: 3
tracery:
  origin: "Test suggestion"
"""

    yaml_file = tmp_path / "test_count.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)

    assert geist.count == 3


def test_tracery_geist_generates_multiple_suggestions_when_count_set(tmp_path: Path) -> None:
    """Test that geist generates the correct number of suggestions."""
    # Create vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Note 1")
    (vault_path / "note2.md").write_text("# Note 2")
    (vault_path / "note3.md").write_text("# Note 3")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    yaml_content = """type: geist-tracery
id: test_multiple
count: 3
tracery:
  origin:
    - "Suggestion about $vault.sample_notes(1)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions = geist.suggest(context)

    assert len(suggestions) == 3

    vault.close()


def test_tracery_deterministic_functions_produce_same_notes_with_multiple_count(
    tmp_path: Path,
) -> None:
    """Test that deterministic functions return same notes across expansions (Bug #2).

    This test documents how deterministic vault functions like old_notes() and
    recent_notes() return the same notes when a geist has count > 1, creating
    redundant suggestions.
    """
    # Create vault with multiple notes
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create notes with different modification times
    import time

    (vault_path / "old_note.md").write_text("# Old Note")
    time.sleep(0.01)  # Small delay to ensure different mtimes
    (vault_path / "middle_note.md").write_text("# Middle Note")
    time.sleep(0.01)
    (vault_path / "recent_note.md").write_text("# Recent Note")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create geist using deterministic functions with count: 2
    yaml_content = """type: geist-tracery
id: temporal_test
count: 2
tracery:
  origin:
    - "$vault.old_notes(1) and $vault.recent_notes(1)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions = geist.suggest(context)

    assert len(suggestions) == 2

    # BUG: Both suggestions should reference the same notes because
    # old_notes(1) and recent_notes(1) are deterministic
    notes1 = suggestions[0].notes
    notes2 = suggestions[1].notes

    # This demonstrates the bug - both suggestions have identical note references
    assert notes1 == notes2  # Both should be ["Old Note", "Recent Note"]

    vault.close()


def test_tracery_sample_notes_produces_variety_across_expansions(tmp_path: Path) -> None:
    """Test that sample_notes() produces variety across multiple expansions.

    The vault's RNG should advance between calls, creating different samples
    each time. This follows the "Sample, don't rank" principle - same seed
    means same sequence (reproducible), but not identical duplicates.
    """
    # Create vault with many notes
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    for i in range(20):
        (vault_path / f"note_{i}.md").write_text(f"# Note {i}")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create geist using sample_notes with count: 5
    # Note: Must wrap vault function results in [[...]] for note extraction
    yaml_content = """type: geist-tracery
id: sample_test
count: 5
tracery:
  origin:
    - "Consider [[#note1#]] and [[#note2#]]"
  note1:
    - "$vault.sample_notes(1)"
  note2:
    - "$vault.sample_notes(1)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions = geist.suggest(context)

    assert len(suggestions) == 5

    # Collect all note references
    all_note_sets = [set(s.notes) for s in suggestions]

    # Should have SOME variety (not all identical)
    # The RNG should advance between expansions
    unique_sets = len(set(frozenset(ns) for ns in all_note_sets))

    # With 20 notes and sampling 2 at a time, RNG should produce variety
    assert unique_sets > 1, (
        "sample_notes() should create variety as RNG advances between expansions"
    )

    vault.close()
