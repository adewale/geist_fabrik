"""Unit tests for metadata_driven_discovery geist.

Trigger arithmetic (see the geist source; metadata is VaultContext's
built-in set, with "now" = the session date):
- vocabulary richness is the built-in root_ttr (unique / sqrt(total) over
  whitespace tokens, case-insensitive). It cannot exceed sqrt(word_count), so
  a stub can never look rich, which raw lexical_diversity (TTR ~1.0 for any
  short note) got wrong;
- complex-but-isolated: (root_ttr > COMPLEX_ROOT_TTR or reading_time > 3) and
  links + backlinks < 2; the pattern needs >= 3 such notes;
- buried gems: root_ttr > BURIED_GEM_ROOT_TTR and days_since_modified > 90; >= 2;
- abandoned tasks: an open "- [ ]" task and days_since_modified > 60; >= 2;
- each pattern yields at most one suggestion and output is capped at 2.

word_count counts every whitespace token of the file, including the
"# Title" heading that VaultBuilder writes. Background notes use a
repeated-word body and 2 links so no pattern can pick them up.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import metadata_driven_discovery
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

GEIST = "metadata_driven_discovery"
CAP = 2
COMPLEX_TTR = metadata_driven_discovery.COMPLEX_ROOT_TTR
GEM_TTR = metadata_driven_discovery.BURIED_GEM_ROOT_TTR
# A stub: a handful of distinct words, so its raw TTR is 1.0.
STUB = "quartz lichen harbour violin saffron"
LINKS = "[[Anchor A]] [[Anchor B]]"
LINKED_BACKGROUND = f"echo echo echo echo echo echo echo echo echo echo {LINKS}"
OPEN_TASKS = f"- [ ] echo\n- [ ] echo\n- [x] echo\n{LINKS}"


def _words_to_clear(threshold: float, repeated: int = 0) -> int:
    """Smallest note length whose root TTR exceeds threshold.

    The note is all distinct words except `repeated` duplicate tokens (the
    LINKS suffix repeats "[[Anchor"), so root TTR = (n - repeated) / sqrt(n),
    rounded to 3 places as the built-in metadata stores it.
    """
    n = 1
    while round((n - repeated) / n**0.5, 3) <= threshold:
        n += 1
    return n


COMPLEX_WORDS = _words_to_clear(COMPLEX_TTR)
GEM_WORDS = _words_to_clear(GEM_TTR, repeated=1)


def _diverse_body(title: str, total_words: int, suffix: str = "") -> str:
    """Body of distinct words making the whole note exactly total_words tokens.

    The note's tokens are "#", the title words, the body words and the suffix
    words, so the body supplies whatever is left.
    """
    fixed = 1 + len(title.split()) + len(suffix.split())
    words = " ".join(f"{title.split()[0].lower()}idea{i}" for i in range(total_words - fixed))
    return f"{words} {suffix}".strip()


def _note(builder: VaultBuilder, title: str, body: str, *, age_days: int = 0) -> None:
    stamp = SESSION_DATE - timedelta(days=age_days)
    builder.note(title, body, created=stamp, modified=stamp)


def _complex(builder: VaultBuilder, title: str, *, suffix: str = "", age_days: int = 0) -> None:
    """A note of distinct words, long enough to clear both root-TTR thresholds."""
    _note(builder, title, _diverse_body(title, GEM_WORDS + 20, suffix), age_days=age_days)


def _background(builder: VaultBuilder, count: int = 4) -> None:
    _note(builder, "Anchor A", LINKED_BACKGROUND)
    _note(builder, "Anchor B", LINKED_BACKGROUND)
    for i in range(count):
        _note(builder, f"Background {i}", LINKED_BACKGROUND)


def _word_counts(ctx: VaultContext, prefix: str) -> set[int]:
    return {ctx.metadata(n)["word_count"] for n in ctx.notes() if n.title.startswith(prefix)}


def _root_ttrs(ctx: VaultContext, prefix: str) -> set[float]:
    return {ctx.metadata(n)["root_ttr"] for n in ctx.notes() if n.title.startswith(prefix)}


@pytest.mark.parametrize(("planted", "fires"), [(2, False), (3, True)])
def test_complex_isolated_pattern_needs_three_notes(
    tmp_path: Path, planted: int, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    titles = [f"Complex {i}" for i in range(planted)]
    for title in titles:
        _complex(builder, title)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST, must_reference=titles)
    assert [sorted(s.notes) for s in suggestions] == [titles]
    assert "complex topics with few connections" in suggestions[0].text


def test_short_unlinked_stubs_are_not_complex(tmp_path: Path) -> None:
    """Contract: a few-word stub is not a "complex topic".

    Regression: raw TTR is 1.0 for any handful of distinct words, so a geist
    reading lexical_diversity reported three 8-word unlinked stubs as complex,
    isolated ideas. Their root TTR is below sqrt(8) < 3.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _note(builder, f"Stub {i}", STUB)
    _background(builder)
    ctx = builder.build()
    stubs = [ctx.metadata(n) for n in ctx.notes() if "Stub" in n.title]
    assert all(md["lexical_diversity"] == 1.0 for md in stubs)
    assert all(md["root_ttr"] < 3 for md in stubs)

    assert metadata_driven_discovery.suggest(ctx) == []


def test_long_repetitive_unlinked_notes_are_not_complex(tmp_path: Path) -> None:
    """Contract: length alone is not rich vocabulary.

    Regression: treating any note long enough to clear the threshold as rich.
    Reading time stays under 3 minutes, so only root TTR could qualify them.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _note(builder, f"Loop {i}", " ".join(["echo"] * (GEM_WORDS + 20)))
    _background(builder)

    assert metadata_driven_discovery.suggest(builder.build()) == []


def test_complex_isolated_notes_are_reported_and_stubs_are_not(tmp_path: Path) -> None:
    """Contract: with both present, the suggestion names the long notes only.

    Regression: pre-fix, six notes qualified and the first three in
    candidate order were reported. The stubs are titled "Aside" so they come
    first in that order, and the pre-fix geist names them instead.
    """
    builder = VaultBuilder(tmp_path)
    complex_titles = [f"Complex {i}" for i in range(3)]
    for title in complex_titles:
        _complex(builder, title)
    for i in range(3):
        _note(builder, f"Aside {i}", STUB)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    assert_valid_suggestions(
        suggestions, GEIST, must_reference=complex_titles, must_not_reference=["Aside"]
    )
    assert [sorted(s.notes) for s in suggestions] == [complex_titles]


@pytest.mark.parametrize(("offset", "fires"), [(-1, False), (0, True)])
def test_complex_isolated_root_ttr_boundary(tmp_path: Path, offset: int, fires: bool) -> None:
    """Contract: root TTR must exceed COMPLEX_ROOT_TTR (strictly).

    Regression: an off-by-one (>= instead of >), or reading raw TTR, which is
    1.0 for both notes and cannot tell them apart.
    """
    builder = VaultBuilder(tmp_path)
    titles = [f"Edge {i}" for i in range(3)]
    for title in titles:
        _note(builder, title, _diverse_body(title, COMPLEX_WORDS + offset))
    _background(builder)
    ctx = builder.build()
    assert _word_counts(ctx, "Edge") == {COMPLEX_WORDS + offset}
    (ttr,) = _root_ttrs(ctx, "Edge")
    assert (ttr > COMPLEX_TTR) is fires

    suggestions = metadata_driven_discovery.suggest(ctx)

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST, must_reference=titles)
    assert "complex topics with few connections" in suggestions[0].text


@pytest.mark.parametrize(("age_days", "fires"), [(90, False), (91, True)])
def test_buried_gems_need_more_than_ninety_days(tmp_path: Path, age_days: int, fires: bool) -> None:
    # Linked, so the diverse gems cannot be read as complex-and-isolated.
    builder = VaultBuilder(tmp_path)
    gems = ["Gem 1", "Gem 2"]
    for title in gems:
        _complex(builder, title, suffix=LINKS, age_days=age_days)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST)
    assert [sorted(s.notes) for s in suggestions] == [gems]
    assert "high lexical diversity" in suggestions[0].text


@pytest.mark.parametrize(("offset", "fires"), [(-1, False), (0, True)])
def test_buried_gems_root_ttr_boundary(tmp_path: Path, offset: int, fires: bool) -> None:
    """Contract: an old note is a "rich language" gem only above BURIED_GEM_ROOT_TTR.

    Regression: pre-fix any two old, linked notes of a few distinct words
    (raw TTR ~1.0) were reported.
    """
    builder = VaultBuilder(tmp_path)
    gems = ["Gem 1", "Gem 2"]
    for title in gems:
        _note(builder, title, _diverse_body(title, GEM_WORDS + offset, LINKS), age_days=200)
    _background(builder)
    ctx = builder.build()
    assert _word_counts(ctx, "Gem") == {GEM_WORDS + offset}
    (ttr,) = _root_ttrs(ctx, "Gem")
    assert (ttr > GEM_TTR) is fires

    suggestions = metadata_driven_discovery.suggest(ctx)

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST, must_reference=gems)
    assert "high lexical diversity" in suggestions[0].text


@pytest.mark.parametrize(("age_days", "fires"), [(60, False), (61, True)])
def test_abandoned_task_notes_need_more_than_sixty_days(
    tmp_path: Path, age_days: int, fires: bool
) -> None:
    builder = VaultBuilder(tmp_path)
    projects = ["Project 1", "Project 2"]
    for title in projects:
        _note(builder, title, OPEN_TASKS, age_days=age_days)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    if not fires:
        assert suggestions == []
        return
    assert_valid_suggestions(suggestions, GEIST)
    assert [sorted(s.notes) for s in suggestions] == [projects]
    assert "[[Project 1]] (2 incomplete tasks)" in suggestions[0].text


def test_completed_task_notes_are_not_abandoned(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for title in ["Project 1", "Project 2"]:
        _note(builder, title, OPEN_TASKS.replace("[ ]", "[x]"), age_days=200)
    _background(builder)

    assert metadata_driven_discovery.suggest(builder.build()) == []


def test_output_is_capped_when_all_three_patterns_fire(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _complex(builder, f"Complex {i}")
    for i in range(2):
        _complex(builder, f"Gem {i}", suffix=LINKS, age_days=120)
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, min_count=CAP)
    assert len(suggestions) == CAP
    assert len({s.text for s in suggestions}) == CAP


def test_geist_journal_notes_never_complete_a_pattern(tmp_path: Path) -> None:
    # Two regular complex notes are one short of the pattern; three long,
    # diverse, unlinked journal notes would complete it if the journal were
    # scanned. The abandoned-task pattern fires on regular notes as the
    # positive side.
    builder = VaultBuilder(tmp_path)
    for i in range(2):
        _complex(builder, f"Complex {i}")
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    for i in range(3):
        title = f"Session Log {i}"
        stamp = SESSION_DATE - timedelta(days=1)
        body = _diverse_body(title, GEM_WORDS + 20)
        builder.journal(title, body, created=stamp, modified=stamp)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    assert_valid_suggestions(
        suggestions,
        GEIST,
        must_reference=["Project 0", "Project 1"],
        must_not_reference=["Session Log"],
    )
    assert len(suggestions) == 1


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _complex(builder, f"Complex {i}")
    for i in range(2):
        _complex(builder, f"Gem {i}", suffix=LINKS, age_days=120)
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    _background(builder)

    first = [s.text for s in metadata_driven_discovery.suggest(builder.build())]
    second = [s.text for s in metadata_driven_discovery.suggest(builder.build())]

    assert first
    assert first == second
