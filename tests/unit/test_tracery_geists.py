"""Behavioural tests for the bundled Tracery geists.

Every test runs real YAML through TraceryGeist.suggest() on a VaultBuilder
vault (pinned dates, lexical embedding stub), so outputs are deterministic and
the assertions name the notes a designed fixture must produce. Engine
mechanics (modifiers, save actions, preprocessing) are owned by
tests/unit/test_tracery.py; the reflective lens geists' known answers are owned
by tests/unit/test_reflective_tracery_geists.py.
"""

import math
import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from geistfabrik.default_geists import DEFAULT_TRACERY_GEISTS
from geistfabrik.session_time import session_seed
from geistfabrik.tracery import TraceryGeist
from geistfabrik.validator import GeistValidator
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEISTS_DIR = (
    Path(__file__).parent.parent.parent / "src" / "geistfabrik" / "default_geists" / "tracery"
)

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")

# Minimum wikilinks every suggestion of a note-referencing geist must carry.
# Geists absent from this table may or may not name notes (random_prompts
# never does; what_if only in some templates).
MIN_WIKILINKS = {
    "contradictor": 1,
    "hub_explorer": 1,
    "note_combinations": 2,
    "orphan_connector": 1,
    "perspective_shifter": 1,
    "questioning_mind": 1,
    "semantic_neighbours": 2,
    "temporal_contrast": 1,
    "transformation_suggester": 1,
    "unexpected_neighbour": 1,
}


def _yaml(geist_id: str) -> Path:
    return GEISTS_DIR / f"{geist_id}.yaml"


def _populated_vault(root: Path) -> VaultBuilder:
    """A vault in which every bundled Tracery geist has data to draw on.

    - "Hub Note" has eight backlinks and "Garden Hub" three: the only hubs.
    - "Orphan Note" is the most recently modified note with no links in or out.
    - "Questions", "Past Reflection" and "Future Plans" give the reflective
      lens functions a questioning, a past-focused and a future-focused note.
    """
    builder = VaultBuilder(root)
    builder.note("Hub Note", "Gardens soil compost.", created=datetime(2023, 6, 1))
    builder.note("Garden Hub", "Seeds roots sprouts.", created=datetime(2023, 6, 2))
    for i in range(8):
        links = "[[Hub Note]]" + (" [[Garden Hub]]" if i < 3 else "")
        builder.note(
            f"Note {i:02d}",
            f"Test note {i} about gardens. {links}",
            created=datetime(2023, 7, 1 + i),
        )
    builder.note(
        "Questions",
        "What is this? How does it work? Why does it matter? When will it end?",
        created=datetime(2023, 8, 1),
    )
    builder.note(
        "Past Reflection",
        "I walked to the store. I bought groceries. I returned home.",
        created=datetime(2023, 8, 2),
    )
    builder.note(
        "Future Plans",
        "I will build this. I shall succeed. It will work.",
        created=datetime(2023, 8, 3),
    )
    builder.note("Orphan Note", "No links here.", created=datetime(2024, 3, 10))
    return builder


@pytest.fixture
def populated(tmp_path: Path) -> VaultContext:
    return _populated_vault(tmp_path).build()


# ============================================================================
# Contracts shared by every bundled Tracery geist
# ============================================================================


@pytest.mark.parametrize("geist_id", DEFAULT_TRACERY_GEISTS)
def test_bundled_geist_passes_the_validator(geist_id: str) -> None:
    """`geistfabrik validate` accepts every bundled grammar, save actions included."""
    result = GeistValidator().validate_tracery_geist(_yaml(geist_id))

    assert result.passed, [i.message for i in result.issues if i.severity == "error"]


def test_all_geists_produce_count_valid_suggestions(populated: VaultContext) -> None:
    """On a vault with data for every geist, each returns exactly `count` suggestions.

    A dropped suggestion means an empty placeholder or an empty vault-function
    result; an unregistered $vault function raises.
    """
    for geist_id in DEFAULT_TRACERY_GEISTS:
        geist = TraceryGeist.from_yaml(_yaml(geist_id), seed=42)
        suggestions = geist.suggest(populated)

        assert_valid_suggestions(suggestions, geist_id, min_count=geist.count)
        assert len(suggestions) == geist.count, geist_id


def test_all_geists_are_deterministic(tmp_path: Path) -> None:
    """Same seed + same vault + same session date => identical texts.

    Each run gets its own VaultContext built from the same files: sharing
    one context would let the first run advance the vault RNG. (Loading
    every bundled YAML with id == filename is owned by
    test_default_geists.test_default_geist_directories_load_exactly_the_default_lists.)
    """
    builder = _populated_vault(tmp_path)
    assert DEFAULT_TRACERY_GEISTS, "no bundled Tracery geists discovered"

    for geist_id in DEFAULT_TRACERY_GEISTS:
        runs = [
            [s.text for s in TraceryGeist.from_yaml(_yaml(geist_id), seed=999).suggest(ctx)]
            for ctx in (builder.build(), builder.build())
        ]
        assert runs[0], f"{geist_id} produced nothing on a populated vault"
        assert runs[0] == runs[1], f"{geist_id} is not deterministic"


def test_note_references_are_bracketed_links_to_real_notes(populated: VaultContext) -> None:
    """Every [[link]] names a real note, and Suggestion.notes lists exactly those links.

    Vault functions return bracketed links, so a template that adds its own
    brackets yields [[[[Note]]]] (target "[[Note", not a note) and a template
    that drops them yields fewer links than MIN_WIKILINKS.
    """
    link_texts = {note.link_text for note in populated.notes()}
    for geist_id in DEFAULT_TRACERY_GEISTS:
        suggestions = TraceryGeist.from_yaml(_yaml(geist_id), seed=42).suggest(populated)
        assert_valid_suggestions(suggestions, geist_id)

        for suggestion in suggestions:
            text = suggestion.text
            links = _WIKILINK.findall(text)
            assert len(links) >= MIN_WIKILINKS.get(geist_id, 0), f"{geist_id}: {text}"
            assert text.count("[[") == text.count("]]") == len(links), f"{geist_id}: {text}"
            assert set(links) <= link_texts, f"{geist_id} links to a non-note: {text}"
            assert suggestion.notes == links, f"{geist_id}: {suggestion.notes} vs {text}"


def test_vault_functions_request_at_least_count_items() -> None:
    """A data symbol must offer at least `count` items, or duplicates are guaranteed.

    With count: 2 and $vault.hubs(1), both suggestions would name the same hub.
    """
    vault_call = re.compile(r"^\$vault\.([a-z_]+)\((\d+)")
    checked = 0
    for geist_id in DEFAULT_TRACERY_GEISTS:
        data = yaml.safe_load(_yaml(geist_id).read_text())
        count = data.get("count", 1)
        for symbol, rules in data["tracery"].items():
            for rule in rules if isinstance(rules, list) else [rules]:
                match = vault_call.match(rule.strip())
                if match and count > 1:
                    checked += 1
                    assert int(match.group(2)) >= count, (
                        f"{geist_id}.{symbol} requests {match.group(2)} items via "
                        f"$vault.{match.group(1)}() but count={count}"
                    )
    assert checked, "no count > 1 geist draws from a vault function"


# ============================================================================
# Per-geist known answers
# ============================================================================


def test_hub_explorer_names_only_the_hubs(populated: VaultContext) -> None:
    """hub_explorer draws from the notes with at least three backlinks and nothing else."""
    seen: set[str] = set()
    for seed in range(20):
        suggestions = TraceryGeist.from_yaml(_yaml("hub_explorer"), seed=seed).suggest(populated)
        assert_valid_suggestions(suggestions, "hub_explorer", min_count=2)
        for suggestion in suggestions:
            assert len(suggestion.notes) == 1, suggestion.text
            seen.update(suggestion.notes)

    assert seen == {"Hub Note", "Garden Hub"}


def _hub_vault(root: Path) -> VaultBuilder:
    """Notes with 5, 4, 3, 2 and 1 backlinks ("Five" ... "One"), plus the linkers."""
    builder = VaultBuilder(root)
    backlinks = {"Five": 5, "Four": 4, "Three": 3, "Two": 2, "One": 1}
    for i, title in enumerate(backlinks):
        builder.note(title, f"Topic {title.lower()}.", created=datetime(2024, 1, 1 + i))
    for i in range(5):
        links = " ".join(f"[[{t}]]" for t, n in backlinks.items() if i < n)
        builder.note(f"Linker {i}", f"Links {links}", created=datetime(2024, 2, 1 + i))
    return builder


def test_hubs_function_honours_min_backlinks(tmp_path: Path) -> None:
    """Contract: $vault.hubs(count, min_backlinks) keeps only notes with that many backlinks.

    Ranked most-linked first and capped at count; the default min_backlinks=1
    keeps every linked-to note (backward compatible).
    Regression: hubs() had no minimum, so a note with one backlink was a "hub".
    """
    ctx = _hub_vault(tmp_path).build()

    assert ctx.call_function("hubs", 5) == [
        "[[Five]]",
        "[[Four]]",
        "[[Three]]",
        "[[Two]]",
        "[[One]]",
    ]
    assert ctx.call_function("hubs", 5, 3) == ["[[Five]]", "[[Four]]", "[[Three]]"]
    assert ctx.call_function("hubs", 2, 3) == ["[[Five]]", "[[Four]]"]
    assert ctx.call_function("hubs", 5, 6) == []


def test_hub_explorer_calls_only_well_linked_notes_central(tmp_path: Path) -> None:
    """Contract: every note hub_explorer names has at least three backlinks.

    Each suggestion picks among those hubs (all three appear across seeds),
    and no template claims the hub "has grown" (growth is never checked).
    Regression: the pool was the top five by backlinks with no minimum, so a
    note with one or two backlinks was called "central to your vault"; the
    real-run journal named a note whose only backlink was itself.
    """
    ctx = _hub_vault(tmp_path).build()
    named: set[str] = set()
    texts: list[str] = []
    for seed in range(30):
        suggestions = TraceryGeist.from_yaml(_yaml("hub_explorer"), seed=seed).suggest(ctx)
        assert_valid_suggestions(suggestions, "hub_explorer", min_count=2)
        for suggestion in suggestions:
            named.update(suggestion.notes)
            texts.append(suggestion.text)

    assert named == {"Five", "Four", "Three"}
    assert not [t for t in texts if "has grown" in t]


def test_hub_explorer_abstains_without_a_well_linked_note(tmp_path: Path) -> None:
    """Contract: with no note reaching three backlinks, hub_explorer says nothing.

    Regression: any linked-to note qualified, so a two-backlink note was "central".
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Target", "Topic.", created=datetime(2024, 1, 1))
    for i in range(2):
        builder.note(f"Linker {i}", "See [[Target]]", created=datetime(2024, 1, 2 + i))

    for seed in range(5):
        geist = TraceryGeist.from_yaml(_yaml("hub_explorer"), seed=seed)
        assert geist.suggest(builder.build()) == []


def test_orphan_connector_rotates_among_orphans(populated: VaultContext) -> None:
    """Contract: orphan_connector names an unlinked note, never a linked one, and rotates.

    The fixture has four orphans (Orphan Note, Questions, Past Reflection,
    Future Plans); across seeds each is named.
    Regression: $vault.orphans(1) named the single most recently modified
    orphan in every session (one note across 60 simulated sessions).
    """
    orphans = {"Orphan Note", "Questions", "Past Reflection", "Future Plans"}
    named: set[str] = set()
    for seed in range(20):
        suggestions = TraceryGeist.from_yaml(_yaml("orphan_connector"), seed=seed).suggest(
            populated
        )
        assert_valid_suggestions(suggestions, "orphan_connector", min_count=1)
        assert len(suggestions) == 1
        assert len(suggestions[0].notes) == 1, suggestions[0].text
        named.update(suggestions[0].notes)

    assert named == orphans


def test_perspective_shifter_writes_whole_sentences(populated: VaultContext) -> None:
    """Contract: every perspective_shifter suggestion starts with a capital and ends in . or ?.

    Regression: one template began "try viewing [[X]] ..." and three of the
    four had no terminal punctuation.
    """
    texts = [
        s.text
        for seed in range(30)
        for s in TraceryGeist.from_yaml(_yaml("perspective_shifter"), seed=seed).suggest(populated)
    ]

    assert len(texts) == 60
    assert [t for t in texts if not t[0].isupper() or t[-1] not in ".?"] == []
    # Every template was exercised.
    assert {t.split()[0] for t in texts} >= {"Try", "What"}


@pytest.mark.parametrize("note_count", [2, 3, 6])
def test_note_combinations_always_pairs_two_different_notes(
    tmp_path: Path, note_count: int
) -> None:
    """Regression: note1 and note2 came from two independent draws.

    With ``note1: $vault.sample_notes(2)`` and ``note2: $vault.sample_notes(2)``
    each symbol drew on its own, so a suggestion could read "What if you
    combined [[A]] with [[A]]?". The pair now comes from one note_pairs()
    expansion, split by .split_seed/.split_neighbours.

    Small vaults make a self-pairing likely on every draw; the loops vary the
    session date (the vault seed in production) and the geist seed.
    """
    builder = VaultBuilder(tmp_path)
    titles = [f"Topic {chr(ord('A') + i)}" for i in range(note_count)]
    for i, title in enumerate(titles):
        builder.note(title, f"Distinct words {title.lower()}.", created=datetime(2024, 1, 1 + i))

    pairs = set()
    for day in (1, 9, 20):
        session = datetime(2024, 3, day)
        ctx = builder.build(session_date=session, seed=session_seed(session))
        for seed in range(25):
            suggestions = TraceryGeist.from_yaml(_yaml("note_combinations"), seed=seed).suggest(ctx)
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


def test_note_combinations_abstains_with_a_single_note(tmp_path: Path) -> None:
    """With one note there is nothing to combine; it used to pair the note with itself."""
    builder = VaultBuilder(tmp_path)
    builder.note("Lonely Note", "Nothing else here.", created=datetime(2024, 1, 1))

    assert TraceryGeist.from_yaml(_yaml("note_combinations"), seed=1).suggest(builder.build()) == []


def test_random_prompts_never_connects_a_concept_with_itself(populated: VaultContext) -> None:
    """Regression: "the connection between #concept# and #concept#" drew twice.

    Two independent draws from six concepts paired a concept with itself
    about one time in six ("between emergence and emergence").
    """
    between = re.compile(r"connection between (\w+) and (\w+)\?")
    pairs = []
    for seed in range(200):
        for suggestion in TraceryGeist.from_yaml(_yaml("random_prompts"), seed=seed).suggest(
            populated
        ):
            match = between.search(suggestion.text)
            if match:
                pairs.append(match.groups())

    assert len(pairs) >= 50, "fixture rarely reaches the connection template"
    assert all(first != second for first, second in pairs), [p for p in pairs if p[0] == p[1]]


def test_seed_and_neighbours_come_from_the_same_cluster(tmp_path: Path) -> None:
    """Each semantic_neighbours suggestion names ONE cluster: a seed and its own neighbours.

    Contract: ``$vault.semantic_clusters`` bundles "[[Seed]]|||[[N1]], ..." so
    that one cluster can be split into its two halves. The grammar must split
    a single saved expansion of ``#cluster#``, not re-draw a cluster for the
    seed and another for the neighbours.

    Regression: with ``seed: #cluster.split_seed#`` and
    ``neighbours: #cluster.split_neighbours#`` each reference re-expands
    ``#cluster#`` independently, pairing seed A with seed B's neighbours
    (observed: "around [[Note 1]]: [[Note 0]], [[Note 1]]", the seed listed
    among its own neighbours).

    Fixture: three groups of four notes with disjoint vocabulary, so each
    note's three nearest neighbours are exactly the rest of its group. The
    loop varies the session date (which seeds semantic_clusters samples) and
    the geist seed (which cluster each template draws).
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

    geist_path = _yaml("semantic_neighbours")
    for day in (1, 9, 20):
        context = builder.build(session_date=datetime(2024, 3, day))
        # Fixture sanity: the lexical stub puts each note's neighbours in its group.
        for note in context.notes():
            found = {n.title for n in context.neighbours(note, 3)}
            assert found == group_of[note.title] - {note.title}, note.title

        for seed in range(30):
            geist = TraceryGeist.from_yaml(geist_path, seed=seed)
            suggestions = geist.suggest(context)
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


def test_semantic_clusters_link_virtual_notes_by_deeplink(tmp_path: Path) -> None:
    """semantic_clusters names journal entries as [[File#date]], seed and neighbours alike.

    Every note in this vault is a dated section of one journal, so every link
    the function returns must be one of the entries' deeplinks.
    """
    dates = ["2025-01-15", "2025-01-16", "2025-01-17", "2025-01-18"]
    (tmp_path / "Journal.md").write_text(
        "\n".join(f"## {d}\n\nThoughts on gardens and soil, day {d}.\n" for d in dates)
    )
    context = VaultBuilder(tmp_path).build(session_date=datetime(2025, 1, 20))
    deeplinks = {f"Journal#{d}" for d in dates}
    assert {n.link_text for n in context.notes()} == deeplinks

    results = context.call_function("semantic_clusters", 2, 2)

    assert len(results) == 2
    for result in results:
        seed, neighbours = result.split("|||")
        assert _WIKILINK.fullmatch(seed) and seed[2:-2] in deeplinks, result
        neighbour_links = _WIKILINK.findall(neighbours)
        assert len(neighbour_links) == 2, result
        assert set(neighbour_links) <= deeplinks - {seed[2:-2]}, result
