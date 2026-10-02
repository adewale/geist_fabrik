"""Behavioural tests for the bundled Tracery geists.

Every test runs real YAML through TraceryGeist.suggest() on a VaultBuilder
vault (pinned dates, lexical embedding stub), so outputs are deterministic and
the assertions name the notes a designed fixture must produce. Engine
mechanics (modifiers, save actions, preprocessing) are owned by
tests/unit/test_tracery.py; the extension examples in examples/geists/tracery/
(note_combinations, semantic_neighbours, transformation_suggester) are tested
in tests/integration/test_example_geists.py.
"""

import re
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from geistfabrik.default_geists import DEFAULT_TRACERY_GEISTS
from geistfabrik.tracery import TraceryGeist
from geistfabrik.validator import GeistValidator
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

GEISTS_DIR = (
    Path(__file__).parent.parent.parent / "src" / "geistfabrik" / "default_geists" / "tracery"
)

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")

# Minimum wikilinks every suggestion of a note-referencing geist must carry.
# Geists absent from this table may or may not name notes.
MIN_WIKILINKS = {
    "contradictor": 1,
    "hub_explorer": 1,
    "what_if": 1,
}


def _yaml(geist_id: str) -> Path:
    return GEISTS_DIR / f"{geist_id}.yaml"


def _populated_vault(root: Path) -> VaultBuilder:
    """A vault in which every bundled Tracery geist has data to draw on.

    - "Hub Note" has eight backlinks and "Garden Hub" three: the only hubs.
      Each repeats its three-word body (same bag-of-words direction) to
      clear hub_explorer's 100-word floor.
    - "Orphan Note" is the most recently modified note with no links in or out.
    - "Questions", "Past Reflection" and "Future Plans" give the reflective
      lens functions a questioning, a past-focused and a future-focused note.
    """
    builder = VaultBuilder(root)
    builder.note("Hub Note", " ".join(["Gardens soil compost."] * 40), created=datetime(2023, 6, 1))
    builder.note(
        "Garden Hub", " ".join(["Seeds roots sprouts."] * 40), created=datetime(2023, 6, 2)
    )
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
    """Notes with 5, 4, 3, 2 and 1 backlinks ("Five" ... "One"), plus the linkers.

    Each target repeats a two-word body to 120 words, over hub_explorer's
    100-word floor.
    """
    builder = VaultBuilder(root)
    backlinks = {"Five": 5, "Four": 4, "Three": 3, "Two": 2, "One": 1}
    for i, title in enumerate(backlinks):
        body = " ".join([f"Topic {title.lower()}."] * 60)
        builder.note(title, body, created=datetime(2024, 1, 1 + i))
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


def test_hub_explorer_never_names_a_stub_that_stub_expander_names(tmp_path: Path) -> None:
    """Contract: hub_explorer only names hubs of at least 100 words, so a
    well-linked stub is stub_expander's ("expand it") and never also
    hub_explorer's ("split into subtopics?").

    Regression: in the real 12-session run hub_explorer and stub_expander
    both named the 19-word "Obsidian" (6 backlinks) every session.
    """
    from geistfabrik.default_geists.code import stub_expander

    builder = _hub_vault(tmp_path)
    builder.note("Obsidian", "A note-taking app.", created=datetime(2024, 1, 9))
    for i in range(6):
        builder.note(f"Mention {i}", "Uses [[Obsidian]]", created=datetime(2024, 3, 1 + i))
    ctx = builder.build()

    stubs = {ref for s in stub_expander.suggest(ctx) for ref in s.notes}
    named: set[str] = set()
    for seed in range(30):
        suggestions = TraceryGeist.from_yaml(_yaml("hub_explorer"), seed=seed).suggest(ctx)
        assert_valid_suggestions(suggestions, "hub_explorer", min_count=2)
        named.update(ref for s in suggestions for ref in s.notes)

    assert "Obsidian" in stubs
    assert named == {"Five", "Four", "Three"}


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


def test_what_if_constraints_name_the_note_they_mean(populated: VaultContext) -> None:
    """Contract: a constraint prompt says which note it is about.

    Regression: "What if you had to draw it?" and "What if you had to explain
    it to a child?" named no note, so "it" had nothing to refer to.
    """
    constraint_words = ("explain", "draw", "keep only one idea", " as a ")
    seen = 0
    for seed in range(40):
        for suggestion in TraceryGeist.from_yaml(_yaml("what_if"), seed=seed).suggest(populated):
            if any(word in suggestion.text for word in constraint_words):
                seen += 1
                assert suggestion.notes, suggestion.text
                assert " it to " not in suggestion.text and "draw it" not in suggestion.text
    assert seen >= 5


# The seven what_if templates, by a phrase only that template renders.
WHAT_IF_TEMPLATES = {
    "metaphor": re.compile(r"^What if you read \[\[[^\]]+\]\] as an? [a-z ]+\?$"),
    "direction": re.compile(r"^What if you approached \[\[[^\]]+\]\] from .+\?$"),
    "constraint": re.compile(r"^What if (you could|you had to|you rewrote) .+, what would .+\?$"),
    "descriptor": re.compile(r"^What if \[\[[^\]]+\]\] were an? \w+, not an? \w+\?$"),
    "split": re.compile(r"^What if \[\[[^\]]+\]\] split into (three|five) [a-z ]+s\? [A-Z].*\?$"),
    "recent": re.compile(r"^What if you rewrote \[\[[^\]]+\]\] for an? \w+\?$"),
    "old": re.compile(
        r"^\[\[[^\]]+\]\] is one of the notes you have left alone longest\. "
        r"What if you rewrote it as it would read now\?$"
    ),
}


def _what_if_texts(context: VaultContext, seeds: range) -> list[tuple[str, list[str]]]:
    return [
        (s.text, s.notes)
        for seed in seeds
        for s in TraceryGeist.from_yaml(_yaml("what_if"), seed=seed).suggest(context)
    ]


def test_what_if_every_prompt_names_one_note(populated: VaultContext) -> None:
    """Contract: every what_if suggestion names exactly one note, is a whole
    question, and matches one of the seven templates; all seven are used.

    Regression: about a third of what_if's output named no note ("What if your
    thinking reframed the gaps in your knowledge?"), and filtering drops every
    suggestion with no notes, so those prompts never reached a journal. The
    merge with perspective_shifter, transformation_suggester and random_prompts
    added the metaphor, descriptor, split and recency templates, and the
    "opposite of [[X]]" template (contradictor's job) was removed.
    """
    rendered = _what_if_texts(populated, range(40))

    assert len(rendered) == 120
    used = set()
    for text, notes in rendered:
        assert len(notes) == 1 and _WIKILINK.findall(text) == notes, text
        assert "opposite" not in text, text
        matches = [name for name, pattern in WHAT_IF_TEMPLATES.items() if pattern.match(text)]
        assert len(matches) == 1, text
        used.update(matches)
    assert used == set(WHAT_IF_TEMPLATES)


def test_what_if_rewrite_prompt_names_a_note_left_alone_longest(populated: VaultContext) -> None:
    """Contract: "left alone longest" is said only of a note among the five
    least recently modified (VaultContext.old_notes(5)).

    Regression: the prompt to rewrite an old note as it would read now came
    from temporal_contrast (retired), which picked notes by a past-tense
    heuristic that mostly matched status tables; what_if had no such prompt.
    """
    oldest = {n.link_text for n in populated.old_notes(5)}
    named = {
        notes[0]
        for text, notes in _what_if_texts(populated, range(60))
        if WHAT_IF_TEMPLATES["old"].match(text)
    }

    assert oldest == {"Hub Note", "Garden Hub", "Note 00", "Note 01", "Note 02"}
    assert named and named <= oldest
