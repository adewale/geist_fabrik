"""Integration tests for the bundled default geists and the Tracery examples.

These tests verify that all geists in src/geistfabrik/default_geists/ work correctly
with a real vault. Uses stubs (kepano-obsidian-main test vault), not mocks.

Tests cover:
- Every bundled code geist loads and executes cleanly (per the executor's
  execution log, since execute_geist swallows exceptions)
- The harvester geists are deterministic for a fixed seed
- Selected Tracery geists produce well-formed output
- Each extension example in examples/geists/tracery/ (not bundled) still runs
  and demonstrates the API it exists to show

Per-geist behaviour is owned by the per-geist unit tests in tests/unit/,
which use fixtures designed to make each geist fire.
"""

import math
import re
from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik import GeistExecutor, Vault, VaultContext
from geistfabrik.default_geists import CODE_GEIST_COUNT
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.session_time import session_seed
from geistfabrik.tracery import TraceryGeist
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

REPO_ROOT = Path(__file__).parent.parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples" / "geists" / "tracery"
_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


@pytest.fixture(scope="module")
def test_vault_path() -> Path:
    """Get path to test vault."""
    return Path(__file__).parent.parent.parent / "testdata" / "kepano-obsidian-main"


@pytest.fixture(scope="module")
def vault(test_vault_path: Path) -> Vault:
    """Create vault from test data."""
    vault = Vault(str(test_vault_path), ":memory:")
    vault.sync()
    return vault


@pytest.fixture(scope="module")
def session(vault: Vault) -> Session:
    """Create session with embeddings."""
    session_date = datetime(2023, 10, 1)
    session = Session(session_date, vault.db)

    # Compute embeddings for all notes
    notes = vault.all_notes()
    session.compute_embeddings(notes)

    return session


@pytest.fixture(scope="module")
def vault_context(vault: Vault, session: Session) -> VaultContext:
    """Create VaultContext for geist execution."""
    function_registry = FunctionRegistry()
    return VaultContext(
        vault=vault,
        session=session,
        seed=20231001,  # Deterministic seed
        function_registry=function_registry,
    )


@pytest.fixture
def geist_executor(test_vault_path: Path) -> GeistExecutor:
    """Create GeistExecutor for loading code geists."""
    repo_root = Path(__file__).parent.parent.parent
    code_geists_dir = repo_root / "src" / "geistfabrik" / "default_geists" / "code"
    executor = GeistExecutor(code_geists_dir, timeout=5)
    executor.load_geists()
    return executor


# ============================================================================
# Tracery Geists Tests
# ============================================================================


def test_what_if_tracery_geist(vault_context: VaultContext):
    """Test what_if Tracery geist."""
    repo_root = Path(__file__).parent.parent.parent
    geist_path = repo_root / "src" / "geistfabrik" / "default_geists" / "tracery" / "what_if.yaml"

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "what_if"

    suggestions = geist.suggest(vault_context)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0

    for suggestion in suggestions:
        assert hasattr(suggestion, "text")
        assert hasattr(suggestion, "geist_id")
        assert suggestion.geist_id == "what_if"
        # Every template names exactly one note
        assert len(suggestion.notes) == 1
        assert _WIKILINK.findall(suggestion.text) == suggestion.notes


def test_orphan_connector_geist(vault_context: VaultContext):
    """orphan_connector (a code geist) names only notes with no links in or out."""
    from geistfabrik.default_geists.code import orphan_connector

    orphans = {n.link_text for n in vault_context.orphans()}
    suggestions = orphan_connector.suggest(vault_context)

    assert orphans
    assert 1 <= len(suggestions) <= 2
    for suggestion in suggestions:
        assert suggestion.geist_id == "orphan_connector"
        assert suggestion.notes[0] in orphans


def test_hub_explorer_tracery_geist(vault_context: VaultContext):
    """Test hub_explorer Tracery geist."""
    geist_path = (
        Path(__file__).parent.parent.parent
        / "src"
        / "geistfabrik"
        / "default_geists"
        / "tracery"
        / "hub_explorer.yaml"
    )

    geist = TraceryGeist.from_yaml(geist_path, seed=12345)
    assert geist.geist_id == "hub_explorer"
    assert geist.count == 2

    suggestions = geist.suggest(vault_context)

    # Only notes with at least 3 backlinks and 100 words are called
    # "central"; each is named at most once. In this vault the only
    # well-linked note ("Obsidian") is a 19-word stub, which stub_expander
    # asks to expand, so hub_explorer must stay silent.
    central = {
        h.link_text
        for h in vault_context.hubs(5)
        if len(vault_context.backlinks(h)) >= 3 and vault_context.metadata(h)["word_count"] >= 100
    }
    assert central == set()
    assert suggestions == []


# ============================================================================
# Cross-geist Tests
# ============================================================================


def test_all_geists_are_loadable(geist_executor: GeistExecutor):
    """Test that all bundled default code geists can be loaded without errors."""
    geist_executor.load_geists()

    # Use programmatic count from default_geists/__init__.py (single source of truth)
    assert len(geist_executor.geists) == CODE_GEIST_COUNT


def test_all_geists_execute_without_crashing(
    vault_context: VaultContext, geist_executor: GeistExecutor
):
    """Every bundled code geist runs to completion on a real vault.

    GeistExecutor.execute_geist swallows exceptions and timeouts and returns
    [], so the return value cannot reveal a crash. The execution log can:
    a geist that raises or times out records status "error" instead of
    "success". Regression caught: any bundled geist that crashes, returns a
    non-list, emits malformed suggestions, or exceeds the timeout.
    """
    for geist_id in geist_executor.geists:
        geist_executor.execute_geist(geist_id, vault_context)

    log = geist_executor.get_execution_log()
    failures = {
        entry["geist_id"]: entry.get("error", entry.get("reason", entry["status"]))
        for entry in log
        if entry["status"] != "success"
    }
    assert not failures, f"geists did not execute cleanly: {failures}"
    succeeded = {entry["geist_id"] for entry in log}
    assert succeeded == set(geist_executor.geists)


def test_geist_determinism(vault_context: VaultContext):
    """Test that geists produce deterministic output with same seed."""
    geist_path = REPO_ROOT / "src" / "geistfabrik" / "default_geists" / "tracery" / "what_if.yaml"

    # Create two identical geists with same seed
    geist1 = TraceryGeist.from_yaml(geist_path, seed=12345)
    geist2 = TraceryGeist.from_yaml(geist_path, seed=12345)

    suggestions1 = geist1.suggest(vault_context)
    suggestions2 = geist2.suggest(vault_context)

    # Same seed should produce same suggestions (and some, or this is vacuous)
    assert suggestions1
    assert [s.text for s in suggestions1] == [s.text for s in suggestions2]


# ============================================================================
# Harvester Family Determinism
# ============================================================================


def _harvestable_vault(root: Path) -> VaultContext:
    """Every note carries four questions, four TODOs and four blockquotes.

    Whichever note a harvester samples, it has more candidates than it shows
    (the 3-suggestion cap; question_harvester reads three of a question-dense
    note's questions back in one suggestion), so both the note choice and the
    candidate sample are exercised by the seeded RNG.
    """
    builder = VaultBuilder(root)
    for i in range(6):
        builder.note(
            f"Garden Log {i}",
            f"Why does bed {i} grow faster in spring rain?\n"
            f"How might soil in plot {i} change over decades?\n"
            f"What would happen if clover covered row {i} entirely?\n"
            f"Where do the earthworms of patch {i} shelter in winter?\n\n"
            f"TODO: measure the soil acidity of bed {i} carefully\n"
            f"TODO: order heritage tomato seeds for plot {i} soon\n"
            f"FIXME: repair the irrigation valve beside row {i}\n"
            f"TODO: sketch a planting map for herb spiral {i}\n\n"
            f"> Garden {i} teaches patience through every slow season.\n\n"
            f"> Plot {i} is autobiography written in soil and water.\n\n"
            f"> Row {i} reminds us that planting means trusting tomorrow.\n\n"
            f"> Patch {i} shows nature never hurries yet finishes everything.\n",
        )
    return builder.build()


@pytest.mark.parametrize(
    ("geist_id", "count"),
    [("question_harvester", 1), ("todo_harvester", 3), ("quote_harvester", 3)],
)
def test_harvester_is_deterministic_for_a_fixed_seed(
    tmp_path: Path, geist_executor: GeistExecutor, geist_id: str, count: int
) -> None:
    """Same vault + same seed gives the same harvested suggestions.

    Two independently built contexts with the same seed must agree on both
    which note is harvested and which of its candidates are sampled.
    Regression caught: a harvester drawing from an unseeded RNG (e.g. the
    global ``random`` module) instead of the VaultContext's seeded one.
    """
    first = geist_executor.execute_geist(geist_id, _harvestable_vault(tmp_path / "a"))
    second = geist_executor.execute_geist(geist_id, _harvestable_vault(tmp_path / "b"))

    assert_valid_suggestions(first, geist_id, min_count=count, must_reference=("Garden Log",))
    assert len(first) == count
    assert [(s.text, s.notes) for s in first] == [(s.text, s.notes) for s in second]


# ============================================================================
# Extension examples (examples/geists/tracery/, not bundled)
# ============================================================================


def _example(geist_id: str, seed: int) -> TraceryGeist:
    return TraceryGeist.from_yaml(EXAMPLES_DIR / f"{geist_id}.yaml", seed=seed)


@pytest.mark.parametrize("note_count", [2, 3, 6])
def test_note_combinations_example_always_pairs_two_different_notes(
    tmp_path: Path, note_count: int
) -> None:
    """The note_pairs + save-action example pairs two DIFFERENT notes.

    Regression: note1 and note2 came from two independent sample_notes()
    draws, so a suggestion could read "What if you combined [[A]] with [[A]]?".
    The pair now comes from one note_pairs() expansion saved as `picked` and
    split by .split_seed/.split_neighbours. Small vaults make a self-pairing
    likely on every draw; the loops vary the session date and the geist seed.
    """
    builder = VaultBuilder(tmp_path)
    titles = [f"Topic {chr(ord('A') + i)}" for i in range(note_count)]
    for i, title in enumerate(titles):
        builder.note(title, f"Distinct words {title.lower()}.", created=datetime(2024, 1, 1 + i))

    pairs = set()
    for day in (1, 9, 20):
        session_date = datetime(2024, 3, day)
        ctx = builder.build(session_date=session_date, seed=session_seed(session_date))
        for seed in range(25):
            suggestions = _example("note_combinations", seed).suggest(ctx)
            # Two notes make one distinct pair, which is offered only once.
            assert_valid_suggestions(
                suggestions, "note_combinations", min_count=min(2, math.comb(note_count, 2))
            )
            for suggestion in suggestions:
                assert len(suggestion.notes) == 2, suggestion.text
                assert suggestion.notes[0] != suggestion.notes[1], suggestion.text
                assert set(suggestion.notes) <= set(titles), suggestion.text
                pairs.add(frozenset(suggestion.notes))

    # The pairing still varies: over these draws every possible pair is offered.
    assert len(pairs) == math.comb(note_count, 2)


def test_semantic_neighbours_example_splits_one_saved_cluster(tmp_path: Path) -> None:
    """The cluster-pattern example names ONE cluster: a seed and its own neighbours.

    Contract: ``$vault.semantic_clusters`` bundles "[[Seed]]|||[[N1]], ..." so
    that one cluster can be split into its two halves. The grammar must split
    a single saved expansion of ``#cluster#``, not re-draw a cluster for the
    seed and another for the neighbours.

    Regression: with ``seed: #cluster.split_seed#`` and
    ``neighbours: #cluster.split_neighbours#`` each reference re-expands
    ``#cluster#`` independently, pairing seed A with seed B's neighbours.

    Fixture: three groups of four notes with disjoint vocabulary, so each
    note's three nearest neighbours are exactly the rest of its group.
    """
    vocab = {
        "Astronomy": "telescope galaxy nebula comet starlight orbit",
        "Baking": "flour yeast dough oven crust knead",
        "Sailing": "mast rudder harbour tide keel anchor",
    }
    builder = VaultBuilder(tmp_path)
    group_of: dict[str, set[str]] = {}
    for topic, words in vocab.items():
        titles = {f"{topic} {label}" for label in ("One", "Two", "Three", "Four")}
        for title in titles:
            builder.note(title, f"{words} {words}", created=datetime(2024, 1, 1))
            group_of[title] = titles

    for day in (1, 9, 20):
        context = builder.build(session_date=datetime(2024, 3, day))
        # Fixture sanity: the lexical stub puts each note's neighbours in its group.
        for note in context.notes():
            found = {n.title for n in context.neighbours(note, 3)}
            assert found == group_of[note.title] - {note.title}, note.title

        for seed in range(30):
            suggestions = _example("semantic_neighbours", seed).suggest(context)
            assert_valid_suggestions(suggestions, "semantic_neighbours", min_count=2)

            for suggestion in suggestions:
                links = _WIKILINK.findall(suggestion.text)
                assert suggestion.text.count("[[") == suggestion.text.count("]]") == 4
                seed_title, neighbours = links[0], links[1:]
                assert seed_title not in neighbours, suggestion.text
                assert set(neighbours) == group_of[seed_title] - {seed_title}, (
                    f"neighbours drawn from another cluster: {suggestion.text}"
                )
                assert suggestion.notes == links


def test_transformation_suggester_example_renders_every_modifier(tmp_path: Path) -> None:
    """The modifier showcase renders each modifier's output, never a raw symbol.

    Over 60 seeds on a one-note vault: .capitalizeAll ("Hidden Pattern"),
    chained .s.capitalize ("Gaps"), .s ("into three questions"), an irregular
    .ed ("grew"), and .a ("an organism"); no '#' survives expansion and every
    suggestion names the note.
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Seed Note", "Some content.", created=datetime(2024, 1, 1))
    ctx = builder.build()

    texts = []
    for seed in range(60):
        for suggestion in _example("transformation_suggester", seed).suggest(ctx):
            assert suggestion.notes == ["Seed Note"], suggestion.text
            texts.append(suggestion.text)

    assert len(texts) == 60
    assert [t for t in texts if "#" in t] == []
    joined = " ".join(texts)
    checks = {
        ".capitalizeAll": r"\b(Hidden Pattern|Emerging Theme|Key Insight|Missing Link): could",
        ".s.capitalize": r"the (Assumptions|Connections|Gaps|Threads) in",
        ".s": r"into (three|five|seven) (insights|questions|perspectives|directions)",
        ".ed (irregular)": r"\]\] grew into",
        ".a": r"\ban (organism|ecosystem|experiment|archive|origin|end|anchor|opening)\b",
    }
    missing = [name for name, pattern in checks.items() if not re.search(pattern, joined)]
    assert missing == []
