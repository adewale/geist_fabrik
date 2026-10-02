"""Unit tests for metadata_driven_discovery geist.

Trigger arithmetic (see the geist source; metadata is VaultContext's
built-in set, with "now" = the session date):
- vocabulary richness is the built-in root_ttr (unique / sqrt(total) over
  whitespace tokens, case-insensitive). It cannot exceed sqrt(word_count), so
  a stub can never look rich, which raw lexical_diversity (TTR ~1.0 for any
  short note) got wrong;
- buried gems: root_ttr > BURIED_GEM_ROOT_TTR and days_since_modified > 90;
  the geist needs >= 2 and yields one suggestion naming two of them, sampled
  from all of its matches.

Its former patterns moved: complex-but-isolated notes to link_density_analyser
(tests/unit/test_link_density_analyser.py) and abandoned task notes to
task_archaeology (tests/unit/test_task_archaeology.py).

word_count counts every whitespace token of the file, including the
"# Title" heading that VaultBuilder writes. Background notes use a
repeated-word body and 2 links so they can never be gems.
"""

from datetime import timedelta
from pathlib import Path

import pytest

from geistfabrik.default_geists.code import metadata_driven_discovery
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions

GEIST = "metadata_driven_discovery"
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
    """A note of distinct words, long enough to clear the root-TTR threshold."""
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


@pytest.mark.parametrize(("age_days", "fires"), [(90, False), (91, True)])
def test_buried_gems_need_more_than_ninety_days(tmp_path: Path, age_days: int, fires: bool) -> None:
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


def test_old_stubs_and_repetitive_notes_are_not_gems(tmp_path: Path) -> None:
    """Contract: rich vocabulary means a high root TTR, not a handful of
    distinct words (raw TTR 1.0) or sheer length.

    Regression: raw lexical_diversity is 1.0 for any few-word stub, so old
    stubs read as "rich language"; length alone is not richness either.
    """
    builder = VaultBuilder(tmp_path)
    for i in range(2):
        _note(builder, f"Stub {i}", STUB, age_days=200)
        _note(builder, f"Loop {i}", " ".join(["echo"] * (GEM_WORDS + 20)), age_days=200)
    _background(builder)
    ctx = builder.build()
    assert {ctx.metadata(n)["lexical_diversity"] for n in ctx.notes() if "Stub" in n.title} == {1.0}

    assert metadata_driven_discovery.suggest(ctx) == []


def test_geist_journal_notes_are_never_gems(tmp_path: Path) -> None:
    """Contract: old, diverse geist journal notes are never named."""
    builder = VaultBuilder(tmp_path)
    gems = ["Gem 0", "Gem 1"]
    for title in gems:
        _complex(builder, title, suffix=LINKS, age_days=120)
    stamp = SESSION_DATE - timedelta(days=120)
    for i in range(3):
        title = f"Session Log {i}"
        body = _diverse_body(title, GEM_WORDS + 20)
        builder.journal(title, body, created=stamp, modified=stamp)
    _background(builder)

    suggestions = metadata_driven_discovery.suggest(builder.build())

    assert_valid_suggestions(suggestions, GEIST, must_not_reference=["Session Log"])
    assert [sorted(s.notes) for s in suggestions] == [gems]


def test_same_seed_and_date_give_identical_output(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for i in range(4):
        _complex(builder, f"Gem {i}", suffix=LINKS, age_days=120)
    _background(builder)

    first = [s.text for s in metadata_driven_discovery.suggest(builder.build())]
    second = [s.text for s in metadata_driven_discovery.suggest(builder.build())]

    assert first
    assert first == second


def test_moved_patterns_are_no_longer_reported_here(tmp_path: Path) -> None:
    """Contract: this geist reports buried gems only. Three long unlinked
    notes and two stale task notes, which its old patterns 1 and 3 named,
    produce nothing here: link_density_analyser and task_archaeology own them.

    Regression: the same notes were named by two geists in one session
    (pattern 1 duplicated link_density_analyser's sparse notes, pattern 3
    duplicated task_archaeology).
    """
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        _complex(builder, f"Complex {i}")
    for i in range(2):
        _note(builder, f"Project {i}", OPEN_TASKS, age_days=70)
    _background(builder)

    assert metadata_driven_discovery.suggest(builder.build()) == []
