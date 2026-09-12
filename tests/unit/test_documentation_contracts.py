"""Keep maintained user-facing examples aligned with the supported interface."""

import inspect
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from geistfabrik.function_registry import FunctionRegistry

REPO = Path(__file__).resolve().parents[2]
MAINTAINED_GUIDES = (
    REPO / "README.md",
    REPO / "README_EARLY_ADOPTERS.md",
    REPO / "examples" / "README.md",
    REPO / "docs" / "CONFIGURATION.md",
    REPO / "docs" / "TROUBLESHOOTING.md",
    REPO / "docs" / "WRITING_GOOD_GEISTS.md",
    REPO / "docs" / "TEMPORAL_EMBEDDINGS_EXAMPLES.md",
)

OBSOLETE_PATTERNS = {
    "the CLI takes the vault as a positional argument": re.compile(
        r"geistfabrik\s+(?:invoke|test|test-all)\b[^\n]*\s--vault\b"
    ),
    "the supported flag is --no-filter": re.compile(r"--nofilter\b"),
    "VaultContext count parameters are named count": re.compile(
        r"vault\.(?:sample|neighbours|old_notes|recent_notes|random_notes)\([^\n)]*\bk="
    ),
    "the public API uses British graph_neighbours spelling": re.compile(
        r"\b(?:vault\.)?graph_neighbors\b"
    ),
    "managed plugin roots reject symlinks": re.compile(r"ln\s+-s[^\n]*_geistfabrik"),
    "preview updates managed state": re.compile(r"read-only,\s*no files created", re.I),
}


def test_maintained_guides_use_current_cli_and_extension_api() -> None:
    failures: list[str] = []
    for document in MAINTAINED_GUIDES:
        content = document.read_text()
        for contract, pattern in OBSOLETE_PATTERNS.items():
            if match := pattern.search(content):
                line = content.count("\n", 0, match.start()) + 1
                failures.append(f"{document.relative_to(REPO)}:{line}: {contract}")
    assert not failures, "Stale maintained documentation:\n" + "\n".join(failures)


def test_privacy_guide_discloses_persisted_note_content() -> None:
    content = (REPO / "README_EARLY_ADOPTERS.md").read_text()
    assert "full Markdown content" in content
    assert "personal information present in the vault" in content
    assert "Full note content (read on-demand)" not in content


def test_operational_guides_match_current_runtime_contracts() -> None:
    readme = (REPO / "README.md").read_text()
    early = (REPO / "README_EARLY_ADOPTERS.md").read_text()
    examples = (REPO / "examples" / "README.md").read_text()
    status = (REPO / "STATUS.md").read_text()
    journal = (REPO / "specs" / "JOURNAL_FILES.md").read_text()
    stats = (REPO / "specs" / "STATS_COMMAND_SPEC.md").read_text()
    authoring = (REPO / "docs" / "WRITING_GOOD_GEISTS.md").read_text()

    assert "geistfabrik test my_geist`" not in early
    assert "uv run geistfabrik test $geist\n" not in early
    assert "5s default" not in early
    assert "rm ~/MyVault/_geistfabrik/geists/code/temporal_drift.py" not in early
    assert "temporal_drift: false" in early
    assert "**Current Version**: v10" in status
    assert "Consolidate clustering pipeline" not in status
    assert "Daily Journal - 2025-01-15" not in journal
    assert "within 0.01s tolerance" not in journal
    assert "At least **2 H2 headings**" in journal
    assert "Never modifies files or computes new embeddings" not in stats
    assert '"hdbscan>=0.8.0"' not in stats
    assert "The current default is `keybert`" in stats
    assert "get_representatives(cluster_id, count=" not in authoring
    assert "$vault.neighbours(#seed#, 3)" not in authoring
    assert "$vault.semantic_clusters(2, 3)" in authoring
    assert "$vault.find_questions(count=" not in readme
    assert "$vault.sample_notes(count=" not in readme
    assert "#question.title#" not in readme
    assert "[[#note1.title#]]" not in readme
    assert "example_contrarian_to" in examples
    assert 'note:\n    - "[[My Note]]"' in examples


def test_shipped_vault_function_examples_match_the_documented_api() -> None:
    registry = FunctionRegistry(REPO / "examples" / "vault_functions")
    registry.load_modules()

    for name in ("find_questions", "notes_with_metadata", "example_contrarian_to"):
        assert "count" in inspect.signature(registry.functions[name]).parameters

    class FakeVault:
        def __init__(self) -> None:
            self.question = SimpleNamespace(title="Why?", link_text="Why?", path="Why.md")
            self.answer = SimpleNamespace(title="Answer", link_text="Answer", path="Answer.md")

        def notes(self) -> list[Any]:
            return [self.question, self.answer]

        def sample(self, values: list[Any], count: int) -> list[Any]:
            return values[:count]

        def metadata(self, note: Any) -> dict[str, str]:
            return {"kind": "question"}

        def resolve_link_target(self, title: str) -> Any | None:
            return self.question if title == "Why?" else None

        def similarity(self, first: Any, second: Any) -> float:
            return 0.25

    vault: Any = FakeVault()
    assert registry.call("find_questions", vault, 1) == ["[[Why?]]"]
    assert registry.call("notes_with_metadata", vault, "kind", "question", 1) == ["[[Why?]]"]
    assert registry.call("example_contrarian_to", vault, "Why?", 1) == ["[[Answer]]"]
