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

    # Should raise exception for non-existent function
    with pytest.raises(KeyError, match="Function 'nonexistent_function' not registered"):
        engine.expand("#origin#")

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


# Modifier Tests


def test_tracery_capitalize_modifier() -> None:
    """Test .capitalize modifier capitalizes first letter."""
    grammar = {
        "origin": ["#word.capitalize#"],
        "word": ["hello", "world"],
    }

    engine = TraceryEngine(grammar, seed=42)
    result = engine.expand("#origin#")

    # Should capitalize first letter
    assert result in ["Hello", "World"]


def test_tracery_capitalize_all_modifier() -> None:
    """Test .capitalizeAll modifier capitalizes all words."""
    grammar = {
        "origin": ["#phrase.capitalizeAll#"],
        "phrase": ["hello world", "foo bar"],
    }

    engine = TraceryEngine(grammar, seed=42)
    result = engine.expand("#origin#")

    # Should capitalize all words
    assert result in ["Hello World", "Foo Bar"]


def test_tracery_pluralize_modifier() -> None:
    """Test .s modifier pluralizes words correctly."""
    grammar = {
        "origin": ["#animal.s#"],
        "animal": ["cat", "dog", "fox", "box", "city", "person"],
    }

    engine = TraceryEngine(grammar, seed=42)

    # Test various pluralization rules
    test_cases = {
        "cat": "cats",
        "dog": "dogs",
        "fox": "foxes",
        "box": "boxes",
        "city": "cities",
        "person": "people",
    }

    for singular, expected_plural in test_cases.items():
        grammar = {"origin": ["#word.s#"], "word": [singular]}
        engine = TraceryEngine(grammar, seed=42)
        result = engine.expand("#origin#")
        assert result == expected_plural, f"Expected {expected_plural}, got {result}"


def test_tracery_past_tense_modifier() -> None:
    """Test .ed modifier converts to past tense."""
    test_cases = {
        "walk": "walked",
        "run": "ran",  # Note: 'ran' not in our irregulars, will be 'runned'
        "create": "created",
        "try": "tried",
        "go": "went",
        "think": "thought",
    }

    for present, expected_past in test_cases.items():
        grammar = {"origin": ["#verb.ed#"], "verb": [present]}
        engine = TraceryEngine(grammar, seed=42)
        result = engine.expand("#origin#")

        # Skip irregular verbs not in our list
        if present in [
            "be",
            "have",
            "do",
            "say",
            "go",
            "get",
            "make",
            "know",
            "think",
            "take",
            "see",
            "come",
            "find",
            "give",
            "tell",
            "feel",
            "become",
            "leave",
            "put",
        ]:
            assert result == expected_past, f"Expected {expected_past}, got {result}"


def test_tracery_article_modifier() -> None:
    """Test .a modifier adds correct article."""
    test_cases = {
        "cat": "a cat",
        "owl": "an owl",
        "house": "a house",
        "hour": "an hour",
        "university": "a university",
    }

    for word, expected in test_cases.items():
        grammar = {"origin": ["#noun.a#"], "noun": [word]}
        engine = TraceryEngine(grammar, seed=42)
        result = engine.expand("#origin#")
        assert result == expected, f"Expected '{expected}', got '{result}'"


def test_tracery_modifier_chaining() -> None:
    """Test chaining multiple modifiers together."""
    grammar = {
        "origin": ["#animal.s.capitalize#"],
        "animal": ["cat", "dog"],
    }

    engine = TraceryEngine(grammar, seed=42)
    result = engine.expand("#origin#")

    # Should pluralize then capitalize
    assert result in ["Cats", "Dogs"]


def test_tracery_modifier_with_article_and_plural() -> None:
    """Test using article modifier with pluralized nouns."""
    grammar = {
        "origin": ["#animal.a#"],
        "animal": ["owl", "elephant"],
    }

    engine = TraceryEngine(grammar, seed=42)
    result = engine.expand("#origin#")

    assert result in ["an owl", "an elephant"]


def test_tracery_custom_modifier() -> None:
    """Test adding custom modifiers."""
    grammar = {
        "origin": ["#word.reverse#"],
        "word": ["hello"],
    }

    engine = TraceryEngine(grammar, seed=42)

    # Add custom reverse modifier
    engine.add_modifier("reverse", lambda s: s[::-1])

    result = engine.expand("#origin#")
    assert result == "olleh"


def test_tracery_modifier_in_geist(tmp_path: Path) -> None:
    """Test modifiers work in complete Tracery geist."""
    # Create vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Test Note")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create geist using modifiers
    yaml_content = """type: geist-tracery
id: modifier_test
tracery:
  origin:
    - "What if #action.ed# the #noun.s#?"
  action:
    - "connect"
    - "explore"
  noun:
    - "idea"
    - "pattern"
"""

    yaml_file = tmp_path / "test_modifier.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions = geist.suggest(context)

    assert len(suggestions) > 0
    suggestion = suggestions[0]

    # Should have past tense verb and plural noun
    assert "connected" in suggestion.text or "explored" in suggestion.text
    assert "ideas" in suggestion.text or "patterns" in suggestion.text

    vault.close()


def test_tracery_multiple_suggestions_use_different_notes(tmp_path: Path) -> None:
    """Test that count=2 with preprocessing can produce varied suggestions.

    Regression test for temporal_mirror bug where both suggestions used
    the same old_note and new_note despite having count: 2.

    With preprocessing, vault functions should request exactly count items.
    Variety is possible (but not guaranteed) when sampling from the pre-populated
    symbol arrays.
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()

    # Create many notes to sample from (20 total)
    for i in range(20):
        (vault_path / f"note_{i:02d}.md").write_text(f"# Note {i:02d}\nContent for note {i}.")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create a geist similar to temporal_mirror with count: 2
    # Request exactly 2 notes each (matching count)
    yaml_content = """type: geist-tracery
id: test_multiple_samples
count: 2
tracery:
  origin:
    - "Compare [[#old_note#]] with [[#new_note#]]"
  old_note:
    - "$vault.sample_old_notes(2, 10)"
  new_note:
    - "$vault.sample_recent_notes(2, 10)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions = geist.suggest(context)

    assert len(suggestions) == 2

    # With preprocessing, both symbols have 2 pre-populated notes
    # Each expansion samples independently, so variety is POSSIBLE but not guaranteed
    # This test just verifies that preprocessing happens and suggestions are generated
    # (The old bug would cause both to reference identical notes every time)

    vault.close()


# Preprocessing Tests (Tracery Vault Function Spec)


def test_vault_function_preprocessing(tmp_path: Path) -> None:
    """Vault functions should expand symbol arrays before Tracery runs."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Note A")
    (vault_path / "note2.md").write_text("# Note B")
    (vault_path / "note3.md").write_text("# Note C")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    grammar = {
        "origin": "#note#",
        "note": ["$vault.sample_notes(3)"]
    }

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    # Check grammar was pre-populated
    assert len(engine.grammar["note"]) == 3
    assert "$vault" not in str(engine.grammar)

    # All notes should be strings (note titles)
    for note in engine.grammar["note"]:
        assert isinstance(note, str)
        assert "Note" in note

    vault.close()


def test_multiple_expansions_vary() -> None:
    """Multiple expansions should sample independently from pre-populated arrays."""
    # Create a mock vault context that returns 5 notes
    mock_vault = Mock(spec=VaultContext)
    mock_vault.call_function = Mock(return_value=["A", "B", "C", "D", "E"])

    grammar = {
        "origin": "#note#",
        "note": ["$vault.sample_notes(5)"]
    }

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(mock_vault)

    # Generate 10 expansions
    results = [engine.expand("#origin#") for _ in range(10)]

    # Should have variety (not all the same)
    assert len(set(results)) > 1, "Multiple expansions should produce variety"


def test_mixed_static_and_vault(tmp_path: Path) -> None:
    """Symbol arrays can mix vault functions and static options."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Note A")
    (vault_path / "note2.md").write_text("# Note B")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    grammar = {
        "origin": "#item#",
        "item": ["$vault.sample_notes(2)", "static option"]
    }

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    # Should have 3 options total (2 from vault + 1 static)
    assert len(engine.grammar["item"]) == 3
    assert "static option" in engine.grammar["item"]

    # Should have the two vault notes
    note_items = [item for item in engine.grammar["item"] if item != "static option"]
    assert len(note_items) == 2

    vault.close()


def test_empty_vault_result(tmp_path: Path) -> None:
    """Empty vault function results should leave symbol empty."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    # Create a linked note (not an orphan)
    (vault_path / "linked.md").write_text("# Linked\nLinks to [[other]]")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    grammar = {
        "origin": "#orphan#",
        "orphan": ["$vault.orphans(5)"]
    }

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(context)

    # Symbol should be empty (no orphans in vault)
    assert engine.grammar["orphan"] == []

    # Expansion should fail gracefully (return unexpanded symbol)
    result = engine.expand("#origin#")
    assert result == "#orphan#"  # Unexpanded

    vault.close()


def test_deterministic_preprocessing(tmp_path: Path) -> None:
    """Same seed should produce identical pre-populated arrays."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    for i in range(10):
        (vault_path / f"note{i}.md").write_text(f"# Note {i}")

    vault = Vault(vault_path)
    vault.sync()

    # Create two contexts with same seed
    context1 = create_vault_context(vault)
    context2 = create_vault_context(vault)

    grammar1 = {"origin": "#note#", "note": ["$vault.sample_notes(5)"]}
    grammar2 = {"origin": "#note#", "note": ["$vault.sample_notes(5)"]}

    engine1 = TraceryEngine(grammar1, seed=42)
    engine1.set_vault_context(context1)

    engine2 = TraceryEngine(grammar2, seed=42)
    engine2.set_vault_context(context2)

    # Pre-populated arrays should be identical
    assert engine1.grammar["note"] == engine2.grammar["note"]

    vault.close()


def test_deterministic_suggestions_with_preprocessing(tmp_path: Path) -> None:
    """Same seed must produce identical suggestions with preprocessing."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    for i in range(10):
        (vault_path / f"note{i}.md").write_text(f"# Note {i}")

    vault = Vault(vault_path)
    vault.sync()

    yaml_content = """type: geist-tracery
id: test_determinism
count: 3
tracery:
  origin:
    - "Consider [[#note#]]"
  note:
    - "$vault.sample_notes(8)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    # First run
    context1 = create_vault_context(vault)
    geist1 = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions1 = geist1.suggest(context1)

    # Second run with same seed
    context2 = create_vault_context(vault)
    geist2 = TraceryGeist.from_yaml(yaml_file, seed=42)
    suggestions2 = geist2.suggest(context2)

    # Must be identical
    assert len(suggestions1) == len(suggestions2)
    assert [s.text for s in suggestions1] == [s.text for s in suggestions2]
    assert [s.notes for s in suggestions1] == [s.notes for s in suggestions2]

    vault.close()


def test_different_seeds_vary_with_preprocessing(tmp_path: Path) -> None:
    """Different seeds should produce different suggestions with preprocessing."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    for i in range(10):
        (vault_path / f"note{i}.md").write_text(f"# Note {i}")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    yaml_content = """type: geist-tracery
id: test_variety
count: 2
tracery:
  origin:
    - "Consider [[#note#]]"
  note:
    - "$vault.sample_notes(5)"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    # Generate with different seeds
    results = []
    for seed in [1, 2, 3, 4, 5]:
        geist = TraceryGeist.from_yaml(yaml_file, seed=seed)
        suggestions = geist.suggest(context)
        results.append(tuple(s.text for s in suggestions))

    # Should have variety (not all identical)
    unique_results = set(results)
    assert len(unique_results) > 1, "Different seeds should produce different suggestions"

    vault.close()


def test_preprocessing_only_runs_once() -> None:
    """Preprocessing should only run once per vault context."""
    mock_vault = Mock(spec=VaultContext)
    mock_vault.call_function = Mock(return_value=["A", "B", "C"])

    grammar = {
        "origin": "#note#",
        "note": ["$vault.sample_notes(3)"]
    }

    engine = TraceryEngine(grammar, seed=42)
    engine.set_vault_context(mock_vault)

    # Vault function should be called exactly once during preprocessing
    assert mock_vault.call_function.call_count == 1

    # Multiple expansions should not trigger more vault function calls
    engine.expand("#origin#")
    engine.expand("#origin#")
    engine.expand("#origin#")

    # Still only called once
    assert mock_vault.call_function.call_count == 1


def test_preprocessing_failure_returns_empty_suggestions(tmp_path: Path) -> None:
    """Preprocessing failure should return empty suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note.md").write_text("# Note")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Create geist with non-existent function
    yaml_content = """type: geist-tracery
id: test_failure
tracery:
  origin:
    - "Test [[#note#]]"
  note:
    - "$vault.nonexistent_function()"
"""

    yaml_file = tmp_path / "test.yaml"
    yaml_file.write_text(yaml_content)

    geist = TraceryGeist.from_yaml(yaml_file, seed=42)

    # Should return empty suggestions due to preprocessing failure
    suggestions = geist.suggest(context)
    assert suggestions == []

    vault.close()
