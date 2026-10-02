"""Tests for transformation_suggester geist showcasing all Tracery modifiers."""

import re
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.tracery import TraceryGeist
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

GEIST_PATH = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")
GRAMMAR: dict[str, list[str]] = yaml.safe_load(GEIST_PATH.read_text())["tracery"]


class MockEmbeddingModel:
    """EmbeddingModel test double with deterministic output dimensions."""

    def __init__(self, num_notes: int) -> None:
        self.num_notes = num_notes

    def encode(
        self,
        sentences: str | list[str],
        *,
        convert_to_numpy: bool = True,
        show_progress_bar: bool = False,
        batch_size: int = 32,
        **kwargs: Any,
    ) -> np.ndarray:
        del convert_to_numpy, show_progress_bar, batch_size, kwargs
        rows = len(sentences) if isinstance(sentences, list) else self.num_notes
        return np.random.rand(rows, 387)


def create_mock_embedding_computer(num_notes: int) -> EmbeddingComputer:
    """Create a mocked EmbeddingComputer for testing."""
    return EmbeddingComputer(model=MockEmbeddingModel(num_notes))


def create_vault_context(vault: Vault) -> VaultContext:
    """Helper to create VaultContext with Session and FunctionRegistry."""
    session_date = datetime(2025, 1, 15)
    num_notes = len(vault.all_notes())
    mock_computer = create_mock_embedding_computer(num_notes)
    session = Session(session_date, vault.db, computer=mock_computer)
    session.compute_embeddings(vault.all_notes())

    function_registry = FunctionRegistry()
    return VaultContext(vault, session, function_registry=function_registry)


def test_transformation_suggester_generates_suggestions(tmp_path: Path) -> None:
    """Test that the geist generates valid suggestions."""
    # Create vault with test notes
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Test Note\nContent here")
    (vault_path / "note2.md").write_text("# Another Note\nMore content")
    (vault_path / "note3.md").write_text("# Third Note\nEven more content")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    # Load and execute geist
    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")
    geist = TraceryGeist.from_yaml(geist_path, seed=42)

    suggestions = geist.suggest(context)

    # Should generate 3 suggestions (as specified in count)
    assert len(suggestions) == 3

    # All suggestions should have text
    for suggestion in suggestions:
        assert suggestion.text
        assert suggestion.geist_id == "transformation_suggester"
        # Should reference at least one note
        assert len(suggestion.notes) >= 1

    vault.close()


def test_transformation_suggester_capitalize_modifier(tmp_path: Path) -> None:
    """Test that .capitalize modifier works in suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")
    geist = TraceryGeist.from_yaml(geist_path, seed=42)

    suggestions = geist.suggest(context)

    # At least one suggestion should start with capital letter
    # (from #opening.capitalize#, #observation.capitalize#, etc.)
    capital_starts = [s for s in suggestions if s.text[0].isupper()]
    assert len(capital_starts) > 0, "Expected at least one suggestion to start with capital letter"

    vault.close()


def _suggestion_texts(tmp_path: Path, seeds: range) -> list[str]:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")
    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)
    try:
        return [
            s.text
            for seed in seeds
            for s in TraceryGeist.from_yaml(GEIST_PATH, seed=seed).suggest(context)
        ]
    finally:
        vault.close()


def test_transformation_suggester_plural_modifier(tmp_path: Path) -> None:
    """#element.s# renders a pluralised grammar noun, not the raw singular.

    Checked on the "it has <count> <element.s>" template: the word after the
    count must be a grammar element plus "s". If .s were skipped, the raw
    singular would appear and fail.
    """
    elements = set(GRAMMAR["element"])
    counts = "|".join(GRAMMAR["count"])
    texts = _suggestion_texts(tmp_path, range(40))

    rendered = [m.group(1) for t in texts for m in re.finditer(rf"it has (?:{counts}) (\w+)", t)]

    assert rendered, "no suggestion used the '.s' element template"
    for word in rendered:
        assert word not in elements, f"unpluralised element {word!r}"
        assert word.endswith("s") and word[:-1] in elements, word


def test_transformation_suggester_past_tense_modifier(tmp_path: Path) -> None:
    """#action.ed# / #verb.ed# render past tenses, not the raw grammar verbs.

    Checked on the "you <verb.ed> [[note]]" templates: the verb must differ
    from every raw grammar verb, so skipping .ed would fail.
    """
    raw_verbs = set(GRAMMAR["action"]) | set(GRAMMAR["verb"])
    texts = _suggestion_texts(tmp_path, range(40))

    rendered = [m.group(1) for t in texts for m in re.finditer(r"\byou (\w+) \[\[", t)]

    assert rendered, "no suggestion used a '.ed' verb template"
    for word in rendered:
        assert word not in raw_verbs, f"raw verb {word!r} was not put in the past tense"
    assert "wrote" in rendered or "thought" in rendered or "built" in rendered, (
        "expected at least one irregular past tense across 40 seeds"
    )


def test_transformation_suggester_article_modifier(tmp_path: Path) -> None:
    """Test that .a modifier adds correct articles."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")
    geist = TraceryGeist.from_yaml(geist_path, seed=789)

    # Generate many suggestions
    suggestions = []
    for _ in range(15):
        suggestions.extend(geist.suggest(context))

    all_text = " ".join(s.text for s in suggestions)

    # Should contain articles
    # The geist uses #metaphor.a#, #descriptor.a#, #insight.a#, #treatment.a#, etc.

    # Check for "a " or "an " followed by common words from the geist
    has_article_a = " a " in all_text.lower()
    has_article_an = " an " in all_text.lower()

    assert has_article_a or has_article_an, (
        f"Expected to find articles 'a' or 'an'. Got: {all_text[:200]}"
    )

    vault.close()


def test_transformation_suggester_capitalize_all_modifier(tmp_path: Path) -> None:
    """Test that .capitalizeAll modifier works."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")

    # Use specific seed that will select the .capitalizeAll template
    # (third origin option uses #concept.capitalizeAll#)
    for seed in range(100, 200):  # Try different seeds
        geist = TraceryGeist.from_yaml(geist_path, seed=seed)
        suggestions = geist.suggest(context)

        all_text = " ".join(s.text for s in suggestions)

        # The geist has multi-word concepts that should be capitalized
        # "hidden pattern" -> "Hidden Pattern"
        # "emerging theme" -> "Emerging Theme"
        # "key insight" -> "Key Insight"
        # "missing link" -> "Missing Link"
        capitalized_concepts = ["Hidden Pattern", "Emerging Theme", "Key Insight", "Missing Link"]

        if any(concept in all_text for concept in capitalized_concepts):
            # Found at least one capitalizeAll usage
            vault.close()
            return

    # If we exhausted all seeds without finding capitalizeAll usage, fail
    vault.close()
    assert False, "No capitalizeAll modifier usage found across 100 seeds"


def test_transformation_suggester_modifier_chaining(tmp_path: Path) -> None:
    """Test that modifier chaining works (.s.capitalize)."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")

    # Try multiple seeds to find chained modifier usage
    for seed in range(50, 150):
        geist = TraceryGeist.from_yaml(geist_path, seed=seed)
        suggestions = geist.suggest(context)

        all_text = " ".join(s.text for s in suggestions)

        # The geist uses #pattern.s.capitalize# which creates capitalized plurals
        # "assumption" -> "Assumptions"
        # "connection" -> "Connections"
        # "gap" -> "Gaps"
        # "thread" -> "Threads"
        capitalized_plurals = ["Assumptions", "Connections", "Gaps", "Threads"]

        if any(plural in all_text for plural in capitalized_plurals):
            vault.close()
            return

    vault.close()
    # If we exhausted all seeds without finding chained modifier usage, fail
    assert False, "No chained modifier (.s.capitalize) usage found across 100 seeds"


def test_transformation_suggester_deterministic_output(tmp_path: Path) -> None:
    """Test that the same seed produces the same output."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "test.md").write_text("# Test\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")

    # Generate suggestions with same seed twice
    geist1 = TraceryGeist.from_yaml(geist_path, seed=999)
    suggestions1 = geist1.suggest(context)

    geist2 = TraceryGeist.from_yaml(geist_path, seed=999)
    suggestions2 = geist2.suggest(context)

    # Should produce identical results
    assert len(suggestions1) == len(suggestions2)
    for s1, s2 in zip(suggestions1, suggestions2):
        assert s1.text == s2.text
        assert s1.notes == s2.notes

    vault.close()


def test_transformation_suggester_all_modifiers_in_output(tmp_path: Path) -> None:
    """Integration test: verify all modifier types appear in generated suggestions."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    (vault_path / "note1.md").write_text("# Note One\nContent")
    (vault_path / "note2.md").write_text("# Note Two\nMore content")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")

    # Generate many suggestions with different seeds
    all_suggestions = []
    for seed in range(50):
        geist = TraceryGeist.from_yaml(geist_path, seed=seed)
        all_suggestions.extend(geist.suggest(context))

    all_text = " ".join(s.text for s in all_suggestions).lower()

    # Verify we hit different modifier types across all suggestions

    # 1. Capitalization - all suggestions should have capital letters
    has_capitals = any(char.isupper() for s in all_suggestions for char in s.text)
    assert has_capitals, "Expected capitalized text"

    # 2. Plurals - should appear in many suggestions
    common_plurals = [
        "connections",
        "assumptions",
        "patterns",
        "ideas",
        "notes",
        "questions",
        "insights",
        "perspectives",
    ]
    has_plurals = any(plural in all_text for plural in common_plurals)
    assert has_plurals, "Expected plural forms in output"

    # 3. Past tense - should appear in suggestions
    past_tense = [
        "viewed",
        "approached",
        "explored",
        "created",
        "thought",
        "made",
        "wrote",
        "found",
        "built",
    ]
    has_past_tense = any(verb in all_text for verb in past_tense)
    assert has_past_tense, "Expected past tense verbs"

    # 4. Articles - should appear with nouns
    has_articles = " a " in all_text or " an " in all_text
    assert has_articles, "Expected articles 'a' or 'an'"

    # 5. All suggestions should reference notes
    for s in all_suggestions[:10]:  # Check first 10
        assert len(s.notes) > 0, f"Expected note references in: {s.text}"

    vault.close()


def test_transformation_suggester_no_errors(tmp_path: Path) -> None:
    """Test that the geist runs without errors across many iterations.

    Four notes, so the three suggestions can name three different notes (a
    note is not suggested twice in one session).
    """
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    for i in range(4):
        (vault_path / f"test{i}.md").write_text(f"# Test {i}\nContent")

    vault = Vault(vault_path)
    vault.sync()
    context = create_vault_context(vault)

    geist_path = Path("src/geistfabrik/default_geists/tracery/transformation_suggester.yaml")

    # Run many times with different seeds to test robustness
    error_count = 0
    for seed in range(100):
        try:
            geist = TraceryGeist.from_yaml(geist_path, seed=seed)
            suggestions = geist.suggest(context)
            assert len(suggestions) == 3
            assert all(s.text for s in suggestions)
        except Exception as e:
            error_count += 1
            print(f"Error with seed {seed}: {e}")

    # Should have very few or no errors
    assert error_count == 0, f"Had {error_count} errors out of 100 runs"

    vault.close()
