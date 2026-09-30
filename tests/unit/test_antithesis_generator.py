"""Unit tests for the antithesis_generator geist.

antithesis_generator needs >= 10 notes. A note "makes strong claims" when at
least 3 claim indicators (is, are, must, should, always, never, ...) occur in
it as substrings. For each such note it looks among its 20 nearest
neighbours for an existing antithesis (>= 2 negation substrings such as not,
no, never, against; "anti"/"contra" in the title counts double):
  - found: suggest developing the thesis/antithesis pair;
  - none: suggest writing one, with a suggested title "Anti-<title>" (or
    "Against <title>" when the title contains "the").
A second pass suggests a synthesis for similar (> 0.5) opposed pairs. At most
2 suggestions are returned.

Fixtures use the bag-of-words test stub. Every fixture word is checked to
contain none of the indicator substrings, so claim and negation counts are
exactly the planted marker words.
"""

from datetime import datetime
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import antithesis_generator
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

CAP = 2
MIN_NOTES = 10
CREATED = datetime(2024, 1, 1)
CLAIMS = "must should always"  # 3 claim indicators
INDICATORS = (
    "is are must should always never will cannot impossible necessary essential fundamental "
    "critical key important proves not no contra anti against opposite reverse yes"
).split()
TOPICS = {
    "Tern": "tern plover curlew dunlin godwit sanderling",
    "Kiln": "kiln glaze porcelain celadon slip raku",
    "Fjord": "fjord skerry sound strait headland cove",
}
FILLER_WORDS = "quokka wombat platypus echidna dugong"
TITLE_WORDS = ["claims", "counter", "filler", "session", "weather"]


def _add_fillers(builder: VaultBuilder, count: int) -> None:
    for i in range(count):
        builder.note(f"Filler {chr(65 + i)}", FILLER_WORDS, created=CREATED)


def test_fixture_words_contain_no_indicator_substrings() -> None:
    """Guard for the fixture itself: counts must come only from planted marker words."""
    vocabulary = [*" ".join(TOPICS.values()).split(), *FILLER_WORDS.split(), *TITLE_WORDS]
    assert not [(v, w) for v in vocabulary for w in INDICATORS if w in v]


@pytest.mark.parametrize(
    ("title", "suggested_title"),
    [("Tern Claims", "Anti-Tern Claims"), ("Weather Claims", "Against Weather Claims")],
)
def test_antithesis_generator_proposes_antithesis_for_strong_claim(
    tmp_path: Path, title: str, suggested_title: str
) -> None:
    """Contract: a strong-claim note with no counterpart gets an antithesis proposal.

    Trigger: 10 notes; the claim note has 3 indicators; fillers have none and
    no negations, so no existing antithesis is found.
    """
    builder = VaultBuilder(tmp_path)
    builder.note(title, f"{TOPICS['Tern']} {CLAIMS}", created=CREATED)
    _add_fillers(builder, MIN_NOTES - 1)
    ctx = builder.build()

    suggestions = antithesis_generator.suggest(ctx)

    assert_valid_suggestions(suggestions, "antithesis_generator", must_reference=[title])
    assert len(suggestions) == 1
    assert suggestions[0].notes == [title]
    assert suggestions[0].title == suggested_title
    assert "What if you wrote its antithesis" in suggestions[0].text


def test_antithesis_generator_recognises_existing_antithesis(tmp_path: Path) -> None:
    """Contract: a similar note with >= 2 negations is offered as the antithesis."""
    builder = VaultBuilder(tmp_path)
    builder.note("Tern Claims", f"{TOPICS['Tern']} {CLAIMS}", created=CREATED)
    builder.note("Tern Counter", f"{TOPICS['Tern']} never against", created=CREATED)
    _add_fillers(builder, MIN_NOTES - 2)
    ctx = builder.build()

    suggestions = antithesis_generator.suggest(ctx)

    assert_valid_suggestions(
        suggestions, "antithesis_generator", must_reference=["Tern Claims", "Tern Counter"]
    )
    assert suggestions[0].notes == ["Tern Claims", "Tern Counter"]
    assert "seems to challenge it" in suggestions[0].text


def test_antithesis_generator_proposes_synthesis_for_opposed_pair(tmp_path: Path) -> None:
    """Contract: similar notes with opposed polarity get a titled synthesis proposal.

    The claim has 2 positive markers (must, always); its neighbour (cosine
    > 0.5) has 3 negative ones (never, not, and "no" inside "not").
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Tern Claims", f"{TOPICS['Tern']} {CLAIMS}", created=CREATED)
    builder.note("Tern Counter", f"{TOPICS['Tern']} never not", created=CREATED)
    _add_fillers(builder, MIN_NOTES - 2)
    ctx = builder.build()

    suggestions = antithesis_generator.suggest(ctx)

    assert_valid_suggestions(suggestions, "antithesis_generator")
    synthesis = [s for s in suggestions if s.title == "Synthesis: Tern Claims + Tern Counter"]
    assert len(synthesis) == 1
    assert synthesis[0].notes == ["Tern Claims", "Tern Counter"]
    assert "dialectically opposed" in synthesis[0].text


def test_antithesis_generator_caps_at_two_distinct_notes(tmp_path: Path) -> None:
    """Contract: 3 strong-claim notes -> exactly 2 suggestions about distinct notes."""
    builder = VaultBuilder(tmp_path)
    claims = [f"{topic} Claims" for topic in TOPICS]
    for topic, title in zip(TOPICS, claims):
        builder.note(title, f"{TOPICS[topic]} {CLAIMS}", created=CREATED)
    _add_fillers(builder, MIN_NOTES - len(claims))
    ctx = builder.build()

    suggestions = antithesis_generator.suggest(ctx)

    assert_valid_suggestions(suggestions, "antithesis_generator", min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.notes[0] for s in suggestions}) == CAP
    assert {s.notes[0] for s in suggestions} <= set(claims)


@pytest.mark.parametrize(("markers", "fires"), [("must should", False), (CLAIMS, True)])
def test_antithesis_generator_claim_threshold(tmp_path: Path, markers: str, fires: bool) -> None:
    """Contract: 2 claim indicators are not a strong claim; 3 are."""
    builder = VaultBuilder(tmp_path)
    builder.note("Tern Claims", f"{TOPICS['Tern']} {markers}", created=CREATED)
    _add_fillers(builder, MIN_NOTES - 1)
    ctx = builder.build()

    suggestions = antithesis_generator.suggest(ctx)

    if fires:
        assert_valid_suggestions(
            suggestions, "antithesis_generator", must_reference=["Tern Claims"]
        )
    else:
        assert suggestions == []


def test_antithesis_generator_excludes_geist_journal(tmp_path: Path) -> None:
    """Contract: journal notes are neither theses nor antitheses.

    Three journal notes make strong claims (they would be theses), and one is
    a close negating counterpart of the regular claim (it would be offered as
    its antithesis).
    """
    builder = VaultBuilder(tmp_path)
    builder.note("Tern Claims", f"{TOPICS['Tern']} {CLAIMS}", created=CREATED)
    _add_fillers(builder, MIN_NOTES - 1)
    journal = ["Session Kiln", "Session Fjord", "Session Weather"]
    builder.journal(journal[0], f"{TOPICS['Kiln']} {CLAIMS}", created=CREATED)
    builder.journal(journal[1], f"{TOPICS['Fjord']} {CLAIMS}", created=CREATED)
    builder.journal(journal[2], f"{TOPICS['Tern']} never against", created=CREATED)
    ctx = builder.build()

    suggestions = antithesis_generator.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "antithesis_generator",
        must_reference=["Tern Claims"],
        must_not_reference=["geist journal", *journal],
    )
