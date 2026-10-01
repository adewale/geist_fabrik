"""Regression tests for virtual note references across all code geists.

Virtual notes (dated sections split from journal files) share bare titles:
``Work Journal.md/2024-05-10`` and ``Garden Journal.md/2024-05-10`` are both
titled ``2024-05-10``. A geist that renders ``note.title`` instead of
``note.link_text`` emits an ambiguous reference (``[[2024-05-10]]``, or
``"2024-05-10"`` in ``Suggestion.notes``) that matches every journal's entry
for that date, so the boundary filter can no longer tell a public entry from
an excluded one.

The fixture is built so that most of the vault is virtual, every journal date
collides across journals, and a named set of geists demonstrably produce
suggestions that reference virtual notes. The contract is then checked over
real output; an empty run cannot pass.
"""

import importlib
import os
import pkgutil
import re
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

from geistfabrik.default_geists import code as code_geists_package
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.models import Suggestion
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SEED, VaultBuilder

SESSION = datetime(2024, 7, 15)
HISTORY = [
    datetime(2023, 9, 15),
    datetime(2023, 12, 15),
    datetime(2024, 3, 15),
    datetime(2024, 6, 15),
]

# Every journal has an entry on each of these dates, so each date is the bare
# title of several virtual notes. 2023-07-12 is "this time last year".
SHARED_DATES = [
    "2023-03-15",
    "2023-05-10",
    "2023-06-21",
    "2023-08-02",
    "2023-09-18",
    "2023-11-05",
    "2023-12-20",
    "2024-05-22",
    "2023-10-14",
    "2023-07-12",
]

CABIN = "Solstice frost snow hearth candle blanket quiet darkness hibernation."

JOURNALS = {
    "Work Journal": [
        "Planning the roadmap. What if the roadmap is wrong? I believe deadlines drive "
        "quality. - [ ] TODO draft the migration plan",
        "We shipped the search feature. Perhaps search should rank by recency, maybe not. "
        "> Simplicity is prerequisite for reliability.",
        "Refactoring is defined as changing structure without changing behaviour. "
        "Hypothesis: smaller pull requests reduce review time. See [[Garden Journal#2023-06-21]].",
        "I will write the design document tomorrow. We will review the architecture next week.",
        "Why do meetings expand to fill time? How could we protect focus? "
        "- [ ] TODO cancel the recurring sync",
        "Search ranking again: recency, relevance, embeddings, semantic similarity, vectors.",
        "I wrote the retrospective. I felt the project drifted. I remember the early prototypes.",
        f"{CABIN} Office heating broke.",
        "Deadlines, roadmap, quality, review, architecture, design document, migration plan.",
        "What is the real goal? Maybe the goal is learning. Perhaps it might be shipping.",
    ],
    "Garden Journal": [
        "Planted tomatoes and basil. Soil was cold. What if I start seeds indoors?",
        "Compost is defined as decomposed organic matter. I believe compost improves soil. "
        "> The best fertiliser is the gardener's shadow.",
        "Tomatoes flowering. Bees everywhere. Perhaps the basil attracts pollinators, maybe.",
        "Harvested tomatoes, basil, zucchini. We will save seeds for next spring.",
        "Autumn cleanup. Leaves for compost. - [ ] TODO mulch the beds before frost",
        "Soil, compost, mulch, worms, roots, decomposition, organic matter, fertiliser.",
        "I remember the drought last summer. I watered every morning. I learned patience.",
        f"{CABIN} Seed catalogues arrived.",
        "Why do seedlings get leggy? How much light do tomatoes need? What about basil?",
        "Embeddings of the garden: semantic similarity between soil and compost and vectors.",
    ],
    "Reading Journal": [
        "Reading about clustering algorithms and semantic search. What if books cluster?",
        "Finished a novel about memory. > We are what we repeatedly do. I believe habits matter.",
        "Notes on habits and attention. Perhaps attention is the scarce resource, maybe.",
        "We will start a reading group. I will choose the first book next month.",
        "Why do some books stick? How does memory consolidate? - [ ] TODO reread chapter three",
        "Attention is defined as selective concentration. Hypothesis: boredom fuels creativity.",
        "I read Thinking in Systems. I remember the bathtub metaphor. I learned about stocks.",
        f"{CABIN} Reading by the fire.",
        "Memory, habits, attention, boredom, creativity, consolidation, repetition, learning.",
        "Semantic search over my reading notes: embeddings, vectors, similarity, clustering.",
    ],
}

# A spring run of near-identical entries (one shares 2024-05-22 with the
# journals above), so seasonal geists find a same-season cluster.
CABIN_DAYS = {
    "2024-04-05": "Icicles.",
    "2024-04-22": "Soup simmering.",
    "2024-05-01": "Woodstove crackling.",
    "2024-05-22": "Owls calling.",
    "2024-06-10": "Thaw beginning.",
}

# Geists that must reference virtual notes on this fixture. Each one renders
# note references through a different code path, so together they guard the
# contract instead of letting silent geists pass it vacuously. A geist that
# stops producing here should either be re-triggered by the fixture or be
# removed from this set with a reason.
EXPECTED_VIRTUAL_REFERENCERS = frozenset(
    {
        "bridge_hunter",
        "burst_evolution",
        "cluster_evolution_tracker",
        "cluster_mirror",
        "concept_cluster",
        "creation_burst",
        "creative_collision",
        "dialectic_triad",
        "metadata_outlier_detector",
        "method_scrambler",
        "pattern_finder",
        "seasonal_revisit",
        "seasonal_topic_analysis",
        "self_and_other",
        "stub_expander",
        "surprisal",
        "temporal_mirror",
        "temporal_voice",
        "this_time_last_year",
        "uncertainty_mapper",
    }
)

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")


def _code_geists() -> list[tuple[str, ModuleType]]:
    package_path = Path(code_geists_package.__file__).parent
    geists = []
    for info in pkgutil.iter_modules([str(package_path)]):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"geistfabrik.default_geists.code.{info.name}")
        if hasattr(module, "suggest"):
            geists.append((info.name, module))
    return geists


@pytest.fixture(scope="module")
def journal_vault(tmp_path_factory: pytest.TempPathFactory) -> VaultContext:
    """A mostly-virtual vault with colliding journal dates and session history."""
    root = tmp_path_factory.mktemp("virtual_vault")
    builder = VaultBuilder(root)
    files = {
        f"{name}.md": "\n".join(f"## {d}\n\n{body}\n" for d, body in zip(SHARED_DATES, bodies))
        for name, bodies in JOURNALS.items()
    }
    files["Cabin Journal.md"] = "\n".join(f"## {d}\n\n{CABIN} {b}\n" for d, b in CABIN_DAYS.items())
    stamp = datetime(2024, 7, 12).timestamp()
    for name, text in files.items():
        (root / name).write_text(text)
        os.utime(root / name, (stamp, stamp))
    builder.note(
        "Systems Thinking",
        "Feedback loops, stocks and flows. "
        "[[Reading Journal#2023-12-20]] and [[Work Journal#2023-06-21]].",
        created=datetime(2023, 4, 1),
    )
    builder.note(
        "Search Design",
        "Embeddings, vectors, semantic search, similarity. [[Work Journal#2023-11-05]]",
        created=datetime(2023, 7, 1),
    )
    ctx = builder.build(session_date=SESSION, history=HISTORY)

    # Last month's run labelled every journal entry, as persist_cluster_labels
    # does at the end of a real session, so cluster migration is observable.
    previous = VaultContext(ctx.vault, Session(HISTORY[-1], ctx.db), seed=SEED)
    previous.persist_cluster_labels(
        {note.path: "last month" for note in previous.notes() if note.is_virtual}
    )
    return ctx


@pytest.fixture(scope="module")
def geist_output(journal_vault: VaultContext) -> dict[str, list[Suggestion]]:
    """Run every code geist on its own fresh context, so results do not depend on order."""
    return {
        name: module.suggest(
            VaultContext(
                journal_vault.vault,
                journal_vault.session,
                seed=SEED,
                function_registry=FunctionRegistry(),
            )
        )
        for name, module in _code_geists()
    }


def test_fixture_titles_collide_across_journals(journal_vault: VaultContext) -> None:
    """Each shared date is the bare title of several virtual notes."""
    virtual = [n for n in journal_vault.notes() if n.is_virtual]
    titles = [n.title for n in virtual]
    assert all(titles.count(date) >= len(JOURNALS) for date in SHARED_DATES)
    assert len({n.link_text for n in virtual}) == len(virtual)


def test_code_geists_reference_virtual_notes_by_link_text(
    journal_vault: VaultContext, geist_output: dict[str, list[Suggestion]]
) -> None:
    """Every note reference a geist emits names exactly one note.

    ``Suggestion.notes`` entries must be a note's ``link_text`` (the boundary
    filter resolves them), and no ``[[wikilink]]`` in the text may be a bare
    virtual title such as ``[[2024-05-22]]``.
    """
    notes = journal_vault.notes()
    link_texts = {n.link_text for n in notes}
    virtual_link_texts = {n.link_text for n in notes if n.is_virtual}
    bare_virtual_titles = {n.title for n in notes if n.is_virtual} - link_texts

    violations = []
    referencing = set()
    for name, suggestions in geist_output.items():
        for suggestion in suggestions:
            unresolved = [ref for ref in suggestion.notes if ref not in link_texts]
            bare_links = [
                target
                for target in _WIKILINK.findall(suggestion.text)
                if target in bare_virtual_titles
            ]
            if unresolved or bare_links:
                violations.append(f"{name}: notes={unresolved} text links={bare_links}")
            if virtual_link_texts.intersection(suggestion.notes):
                referencing.add(name)

    assert not violations, "ambiguous virtual-note references:\n" + "\n".join(violations)
    silent = EXPECTED_VIRTUAL_REFERENCERS - referencing
    assert not silent, (
        f"geists no longer reference virtual notes on this fixture: {sorted(silent)}; "
        f"referencing now: {sorted(referencing)}"
    )
