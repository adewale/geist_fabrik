"""Templates and privacy boundaries share physical-source identity checks."""

from datetime import datetime
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.models import NoteLinkIndex
from geistfabrik.source_eligibility import SourceEligibility
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("Templates/Daily.md", False),
        ("Templates\\Daily.md", False),
        ("./Templates/Daily.md", False),
        ("Archive/../Templates/Daily.md", False),
        ("Templates ideas.md", True),
        ("Archive/Templates/Daily.md", True),
        ("templates/Daily.md", True),
        ("Ideas.md", True),
    ],
)
def test_template_folder_has_explicit_case_sensitive_semantics(path: str, allowed: bool) -> None:
    assert SourceEligibility().allows(path) is allowed


@given(
    folder=st.sampled_from(["Templates", "Private", "Work"]),
    filename=st.text(alphabet="abcdef012345", min_size=1, max_size=20),
    separator=st.sampled_from(["/", "\\"]),
)
def test_boundary_decision_ignores_separator_and_redundant_path_segments(
    folder: str, filename: str, separator: str
) -> None:
    eligibility = SourceEligibility(("Private/",))
    path = f"{folder}/{filename}.md"
    decorated = f"./Scratch/../{folder}//{filename}.md".replace("/", separator)
    assert eligibility.allows(path) is (folder == "Work")
    assert eligibility.allows(decorated) == eligibility.allows(path)


def test_virtual_sources_and_ambiguous_aliases_fail_closed() -> None:
    index = NoteLinkIndex(
        [
            ("Work/Shared.md", "Shared", False, None, None),
            ("Templates/Shared.md", "Shared", False, None, None),
            (
                "virtual-daily-entry",
                "2024-03-01",
                True,
                "Templates/Daily.md",
                "2024-03-01",
            ),
            ("Work/Idea.md", "Idea", False, None, None),
        ]
    )
    eligibility = SourceEligibility()
    assert not eligibility.references_allowed(index, ["Shared"])
    assert not eligibility.references_allowed(index, ["Templates/Shared|Shown"])
    assert not eligibility.references_allowed(index, ["./Templates/Shared.md"])
    assert not eligibility.references_allowed(index, ["Daily#2024-03-01"])
    assert not eligibility.references_allowed(index, ["virtual-daily-entry"])
    assert not eligibility.references_allowed(index, ["Missing"])
    assert eligibility.references_allowed(index, ["Work/Shared", "Idea"])


def test_configured_prefixes_keep_existing_case_and_empty_prefix_semantics() -> None:
    eligibility = SourceEligibility(("./Private/", "Prefix"))
    assert not eligibility.allows("Private/Secret.md")
    assert eligibility.allows("private/Secret.md")
    assert not eligibility.allows("Prefix ideas.md")
    assert not eligibility.allows("Prefixless/Idea.md")
    assert not SourceEligibility(("",)).allows("Public/Idea.md")


def test_templates_cannot_reenter_through_semantic_or_graph_queries(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    seed_path = builder.note("Seed", "orchard apple pruning [[Target]] [[Scaffold]]")
    target_path = builder.note("Target", "orchard apple pruning trees")
    builder.note("Lonely", "isolated boat sea waves [[Scaffold]]")
    template_path = builder.note(
        "Scaffold", "orchard apple pruning [[Target]] [[Seed]]", folder="Templates"
    )
    context = builder.build(history=[datetime(2023, 12, 1)])
    seed, target = context.get_note(seed_path), context.get_note(target_path)
    raw_template = context.vault.get_note(template_path)
    assert seed is not None and target is not None and raw_template is not None

    assert {note.path for note in context.notes()} == {seed_path, target_path, "Lonely.md"}
    assert context.get_note(template_path) is None
    assert context.get_embedding(template_path) is None
    assert context.resolve_link_target("Scaffold") is None
    assert context.neighbours(raw_template) == []
    assert {note.path for note in context.neighbours(seed, 20)} == {target_path, "Lonely.md"}
    assert context.backlinks(target) == [seed]
    assert context.outgoing_links(seed) == [target]
    assert context.hubs() == [target]
    assert {note.path for note in context.orphans()} == {"Lonely.md"}
    assert template_path not in context.get_all_embeddings()
    assert template_path not in context.surprisal_scores(k_neighbours=1)
    assert template_path not in context.neighbour_churn(since_days=30, k=1)
    assert all(
        note.path != template_path
        for group in context.notes_grouped_by_creation_date().values()
        for note in group
    )
    assert all(len(vectors) == 3 for _, _, vectors in context.session_embeddings_by_session())
    # Exclusion changes the idea view, never the synchronized source or history.
    assert len(context.vault.all_notes()) == 4
    assert (
        context.vault.db.execute(
            "SELECT COUNT(*) FROM session_embeddings WHERE note_path = ?", (template_path,)
        ).fetchone()[0]
        == 2
    )
    assert (
        context.vault.db.execute(
            "SELECT COUNT(*) FROM lexical_notes WHERE path = ?", (template_path,)
        ).fetchone()[0]
        == 1
    )


def test_only_boundary_exclusions_apply_to_shared_idea_view(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    public = builder.note("Idea", "a usable orchard idea")
    private = builder.note("Secret", "private orchard plans", folder="Private")
    lexical_only = builder.note("Clipping", "visible to nonlexical geists", folder="Clippings")
    template = builder.note("Daily", "template placeholders", folder="Templates")
    initial = builder.build()
    initial.vault.config.filtering.exclude_paths = ["Private/"]
    initial.vault.config.lexical_analysis.exclude_paths = ["Clippings/"]
    context = VaultContext(initial.vault, initial.session)

    assert {note.path for note in context.notes()} == {public, lexical_only}
    assert context.get_note(private) is None
    assert context.references_allowed([public, lexical_only])
    assert not context.references_allowed([private])

    initial.vault.config.filtering.boundary_enabled = False
    unfiltered = VaultContext(initial.vault, initial.session)
    assert {note.path for note in unfiltered.notes()} == {public, private, lexical_only}
    assert unfiltered.references_allowed([private])
    assert not unfiltered.references_allowed([template])
    assert len(initial.vault.all_notes()) == 4


def test_creation_group_minimum_counts_only_eligible_notes(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("One", "one idea", created=datetime(2024, 2, 1))
    builder.note("Daily", "not another idea", folder="Templates", created=datetime(2024, 2, 1))
    context = builder.build()
    assert context.notes_grouped_by_creation_date(min_per_day=2) == {}


def test_excluded_notes_do_not_consume_temporal_result_limit(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    idea = builder.note("Idea", "usable prose", modified=datetime(2024, 2, 1))
    builder.note("Older", "scaffolding", folder="Templates", modified=datetime(2023, 1, 1))
    builder.note("Newer", "scaffolding", folder="Templates", modified=datetime(2024, 3, 1))
    context = builder.build()
    assert [note.path for note in context.old_notes(count=1)] == [idea]
    assert [note.path for note in context.recent_notes(count=1)] == [idea]


def test_clusters_use_eligible_prose_while_raw_embedding_rows_remain(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    for index in range(4):
        builder.note(f"Orchard {index}", "orchard apple pruning grafting trees fruit")
        builder.note(f"Music {index}", "violin bow rosin strings orchestra quartet")
    for index in range(4):
        builder.note(
            f"Scaffold {index}", "orchard apple pruning grafting trees fruit", folder="Templates"
        )
    context = builder.build()
    clusters = context.get_clusters(min_size=3)
    assert clusters
    assert all(
        not note.path.startswith("Templates/")
        for cluster in clusters.values()
        for note in cluster.notes
    )
    assert context.vault.db.execute("SELECT COUNT(*) FROM session_embeddings").fetchone()[0] == 12


def test_cluster_history_requires_equivalent_source_population_policy(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    path = builder.note("Idea", "orchard soil pruning")
    initial = builder.build()
    initial.vault.config.filtering.exclude_paths = ["Private/", "Archive/"]
    context = VaultContext(initial.vault, initial.session)
    note = context.get_note(path)
    assert note is not None
    context.persist_cluster_labels({path: "orchard"})
    assert context.previous_cluster_label_for_note(note, initial.session.session_id) == "orchard"

    initial.vault.config.filtering.exclude_paths = ["./Archive/", "Private\\", "Private/"]
    equivalent = VaultContext(initial.vault, initial.session)
    assert equivalent.previous_cluster_label_for_note(note, initial.session.session_id) == "orchard"

    initial.vault.config.filtering.exclude_paths = ["Private/"]
    changed = VaultContext(initial.vault, initial.session)
    assert changed.previous_cluster_label_for_note(note, initial.session.session_id) is None
    assert (
        initial.vault.db.execute(
            "SELECT cluster_label FROM session_embeddings WHERE note_path = ?", (path,)
        ).fetchone()[0]
        is not None
    )


@pytest.mark.parametrize("excluded_folder", ["Private", "Templates"])
def test_pairwise_links_agree_with_graph_on_excluded_aliases(
    tmp_path: Path, excluded_folder: str
) -> None:
    builder = VaultBuilder(tmp_path)
    seed_path = builder.note("Seed", "orchard [[Shared]] [[Clear]]")
    shared_path = builder.note("Shared", "public orchard note", folder="Public")
    hidden_path = builder.note("Shared", "hidden alias [[Clear]]", folder=excluded_folder)
    clear_path = builder.note("Clear", "unambiguous public orchard note")
    ambiguous_path = builder.note("Ambiguous", "only an excluded alias [[Shared]]")
    unresolved_path = builder.note("Unresolved", "a deliberately unwritten link [[Future idea]]")
    initial = builder.build()
    initial.vault.config.filtering.exclude_paths = ["Private/"]
    context = VaultContext(initial.vault, initial.session)
    seed = context.get_note(seed_path)
    shared = context.get_note(shared_path)
    clear = context.get_note(clear_path)
    hidden = context.vault.get_note(hidden_path)
    assert seed is not None and shared is not None and clear is not None and hidden is not None

    assert context.outgoing_links(seed) == [clear]
    assert context.backlinks(shared) == []
    assert context.graph_neighbours(seed) == [clear]
    assert context.links_between(seed, shared) == context.links_between(shared, seed) == []
    assert not context.has_link(seed, shared)
    assert not context.has_link(shared, seed)
    assert context.links_between(seed, hidden) == []
    assert context.links_between(hidden, clear) == []
    assert context.links_between(seed, clear) == context.links_between(clear, seed)
    assert context.has_link(seed, clear) and context.has_link(clear, seed)
    orphan_paths = {note.path for note in context.orphans()}
    assert ambiguous_path in orphan_paths
    assert unresolved_path not in orphan_paths
