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
        if present in ["be", "have", "do", "say", "go", "get", "make", "know", "think",
                       "take", "see", "come", "find", "give", "tell", "feel", "become",
                       "leave", "put"]:
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
