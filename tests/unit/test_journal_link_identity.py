"""Journal parsing and all link consumers agree on persisted note identities."""

import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest
import yaml
from hypothesis import given
from hypothesis import strategies as st

from geistfabrik.config_loader import DateCollectionConfig, GeistFabrikConfig
from geistfabrik.date_collection import (
    extract_h2_headings,
    is_date_collection_note,
    split_date_collection_note,
)
from geistfabrik.embeddings import EmbeddingComputer, Session
from geistfabrik.filtering import SuggestionFilter
from geistfabrik.graph_analysis import GraphPatternFinder, _are_linked
from geistfabrik.models import Note, NoteLinkIndex, Suggestion
from geistfabrik.stats import StatsCollector
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext


@pytest.mark.parametrize(
    "changed",
    [
        DateCollectionConfig(enabled=False),
        DateCollectionConfig(exclude_files=["nested/*.md"]),
        DateCollectionConfig(min_sections=4),
        DateCollectionConfig(date_threshold=1.0),
    ],
)
def test_config_only_changes_reclassify_persisted_journal(
    tmp_path: Path,
    changed: DateCollectionConfig,
) -> None:
    """An unchanged file must be reconsidered after any parsing setting changes."""
    journal = tmp_path / "nested" / "Journal.md"
    journal.parent.mkdir()
    journal.write_text("## 2025-01-15\nFirst\n## Aside\nMore\n## 2025-01-16\nSecond")
    initial_stat = journal.stat()
    db_path = tmp_path / "vault.db"
    vault = Vault(tmp_path, db_path)
    assert vault.sync() == 2
    assert vault.sync() == 0
    vault.close()

    vault = Vault(tmp_path, db_path, GeistFabrikConfig(date_collection=changed))
    assert vault.sync() == 1
    assert [(n.path, n.is_virtual) for n in vault.all_notes()] == [("nested/Journal.md", False)]
    assert vault.sync() == 0
    vault.close()

    vault = Vault(tmp_path, db_path, GeistFabrikConfig())
    assert vault.sync() == 2
    assert all(n.is_virtual for n in vault.all_notes())
    assert vault.sync() == 0
    assert journal.stat().st_mtime_ns == initial_stat.st_mtime_ns
    assert journal.stat().st_ctime_ns == initial_stat.st_ctime_ns
    vault.close()


@pytest.mark.parametrize("opening,closing", [("```md", "```"), ("~~~~", "~~~~"), ("````", "````")])
def test_code_dates_are_not_journal_sections(opening: str, closing: str) -> None:
    code = f"{opening}\n## 2025-01-03\nFake A\n## 2025-01-04\nFake B\n{closing}"
    assert not is_date_collection_note(code)
    content = f"## 2025-01-01\nReal A\n{code}\n## 2025-01-02\nReal B"
    notes = split_date_collection_note(
        "Journal.md", content, datetime(2025, 1, 1), datetime(2025, 1, 2)
    )
    assert [n.entry_date for n in notes] == [date(2025, 1, 1), date(2025, 1, 2)]
    assert code in notes[0].content
    assert len(extract_h2_headings(content)) == 2


def test_shorter_fence_and_indented_headings_remain_code() -> None:
    content = (
        "## 2025-01-01\nFirst\n````\n```\n## 2025-02-01\nFake\n````\n"
        "    ## 2025-03-01\n\t## 2025-04-01\n## 2025-01-02\nLast"
    )
    assert [h for h, _ in extract_h2_headings(content)] == ["## 2025-01-01", "## 2025-01-02"]


@given(
    st.lists(
        st.one_of(
            st.none(),
            st.booleans(),
            st.integers(),
            st.dates(),
            st.text(alphabet="abcXYZ -_", max_size=15),
        ),
        max_size=10,
    )
)
def test_virtual_yaml_tags_are_normalized_strings(tags: list[object]) -> None:
    metadata = yaml.safe_dump({"tags": tags})
    content = f"---\n{metadata}---\n## 2025-01-01\nFirst #inline\n## 2025-01-02\nSecond"
    notes = split_date_collection_note(
        "Journal.md", content, datetime(2025, 1, 1), datetime(2025, 1, 2)
    )
    expected = {str(tag).strip() for tag in tags}
    assert notes[0].tags == sorted(expected | {"inline"})
    assert notes[1].tags == sorted(expected)


def test_yaml_collections_do_not_break_sqlite_sync(tmp_path: Path) -> None:
    (tmp_path / "Journal.md").write_text(
        "---\ntags: [null, true, 42, 2025-01-01, {nested: value}, [a, b]]\n---\n"
        "## 2025-01-01\nFirst\n## 2025-01-02\nSecond"
    )
    vault = Vault(tmp_path)
    try:
        assert vault.sync() == 2
        assert all(isinstance(tag, str) for note in vault.all_notes() for tag in note.tags)
        assert "{'nested': 'value'}" in vault.all_notes()[0].tags
    finally:
        vault.close()


@given(
    parent=st.lists(
        st.sampled_from(["notes", "archive.md", "日記", "a.b"]), min_size=1, max_size=4
    ),
    day=st.dates(min_value=date(2000, 1, 1), max_value=date(2040, 12, 31)),
)
def test_nested_virtual_links_round_trip_without_removing_directory_suffixes(
    parent: list[str],
    day: date,
) -> None:
    source = "/".join([*parent, "My.md Journal.md"])
    note = Note(
        path=f"{source}/{day.isoformat()}",
        title=day.isoformat(),
        content="Entry",
        links=[],
        tags=[],
        created=datetime(2025, 1, 1),
        modified=datetime(2025, 1, 2),
        is_virtual=True,
        source_file=source,
        entry_date=day,
    )
    assert note.link_text == f"{'/'.join(parent)}/My.md Journal#{day}"
    index = NoteLinkIndex.from_notes([note])
    assert index.resolve(note.link_text) == note.path
    assert index.resolve(note.path) == note.path
    assert source.removesuffix(".md") not in note.link_target_forms()


def test_persisted_links_resolve_consistently_across_consumers(tmp_path: Path) -> None:
    files = {
        "archive.md/work/Journal.md": (
            "## January 15, 2025\n[[2025-01-16]] [[#2025-01-16]]\n## 2025-01-16\n[[Reader#Details]]"
        ),
        "other/Journal.md": "## 2025-01-15\nOther A\n## 2025-01-16\nOther B",
        "2025-01-16.md": "# Independent date note\nNot the local date target",
        "Reader.md": "# Reader\n[[archive.md/work/Journal#January 15, 2025]]",
        "alone.md": "# Alone\nNo links",
    }
    for path, content in files.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
    db_path = tmp_path / "vault.db"
    vault = Vault(tmp_path, db_path)
    vault.sync()
    vault.close()
    vault = Vault(tmp_path, db_path)
    try:
        session = Session(datetime(2025, 1, 20), vault.db)
        session.compute_embeddings(vault.all_notes())
        ctx = VaultContext(vault, session)
        first = ctx.get_note("archive.md/work/Journal.md/2025-01-15")
        second = ctx.get_note("archive.md/work/Journal.md/2025-01-16")
        reader = ctx.get_note("Reader.md")
        assert first is not None and second is not None and reader is not None
        assert reader.links[0].target == "archive.md/work/Journal#January 15, 2025"
        assert vault.resolve_link_target("2025-01-16", first.path) == second
        assert vault.resolve_link_target("01/16/2025", first.path) == second
        assert vault.resolve_link_target("JANUARY 16, 2025", first.path) == second
        assert ctx.resolve_link_target("#2025-01-16", first.path) == second
        assert ctx.resolve_link_target("Journal#2025-01-16", first.path) == second
        assert vault.resolve_link_target("Journal#2025-01-15") is None
        assert ctx.outgoing_links(reader) == [first]
        assert ctx.outgoing_links(first) == [second, second]
        assert ctx.backlinks(first) == [reader]
        assert ctx.backlinks(second) == [first]
        assert len(ctx.links_between(first, second)) == 2
        assert _are_linked(first, second, ctx.link_index())
        assert GraphPatternFinder(ctx).shortest_path(reader, second) == [reader, first, second]

        stats = StatsCollector(vault, vault.config)
        top = {item["path"]: item for item in stats.get_top_linked_notes(100)}
        assert top[first.path]["incoming"] == 1
        assert top[second.path]["incoming"] == 2
        assert stats.stats["graph"]["largest_component_size"] == 3
        assert {n.path for n in ctx.orphans()} == {n["path"] for n in stats.get_orphan_notes()}
        assert {n.path for n in ctx.hubs(100)} == {first.path, second.path, reader.path}

        suggestions = [Suggestion(text="Revisit entry", notes=[first.link_text], geist_id="test")]
        filtering = SuggestionFilter(vault.db, EmbeddingComputer())
        assert filtering.filter_boundary(suggestions) == suggestions
        filtering.config["boundary"]["exclude_paths"] = ["archive.md/"]
        assert filtering.filter_boundary(suggestions) == []
        session.close()
    finally:
        vault.close()


def test_regular_basename_and_ambiguous_titles_have_one_resolution(tmp_path: Path) -> None:
    for folder in ("one", "two"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Note.md").write_text("# Shared\nContent")
    (tmp_path / "one" / "Source.md").write_text("[[Note]] [[Shared]]")
    vault = Vault(tmp_path)
    try:
        vault.sync()
        assert vault.resolve_link_target("Note") is None
        assert vault.resolve_link_target("Shared") is None
        target = vault.resolve_link_target("Note", "one/Source.md")
        assert target is not None and target.path == "one/Note.md"
        assert vault.resolve_link_target("Shared", "one/Source.md") == target
        assert vault.resolve_link_target("one/Note#Section") == target
    finally:
        vault.close()


def test_legacy_fingerprint_refreshes_previously_stripped_anchors(tmp_path: Path) -> None:
    reader = tmp_path / "Reader.md"
    reader.write_text("[[Journal#2025-01-15]]")
    (tmp_path / "Journal.md").write_text("## 2025-01-15\nFirst\n## 2025-01-16\nSecond")
    vault = Vault(tmp_path)
    try:
        vault.sync()
        stat = reader.stat()
        old_fingerprint = ":".join(
            str(value)
            for value in (
                stat.st_dev,
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
                stat.st_ctime_ns,
            )
        )
        vault.db.execute("UPDATE links SET target = 'Journal' WHERE source_path = 'Reader.md'")
        vault.db.execute(
            "UPDATE notes SET source_fingerprint = ? WHERE path = 'Reader.md'", (old_fingerprint,)
        )
        vault.db.commit()
        assert vault.sync() == 1
        restored = vault.get_note("Reader.md")
        assert restored is not None
        assert [link.target for link in restored.links] == ["Journal#2025-01-15"]
        assert vault.sync() == 0
    finally:
        vault.close()


def test_link_index_built_in_rolled_back_transaction_is_not_published(tmp_path: Path) -> None:
    """Uncommitted aliases must disappear when their transaction rolls back."""
    (tmp_path / "Note.md").write_text("# Original\nContent")
    vault = Vault(tmp_path)
    try:
        vault.sync()
        assert vault.resolve_link_target("Original") is not None
        vault.db.execute("BEGIN")
        vault.db.execute("UPDATE notes SET title = 'Temporary' WHERE path = 'Note.md'")
        assert vault.resolve_link_target("Temporary") is not None
        vault.db.rollback()
        assert vault.resolve_link_target("Temporary") is None
        assert vault.resolve_link_target("Original") is not None
    finally:
        vault.close()


def test_ambiguous_private_alias_is_rejected_but_explicit_public_path_is_kept(
    tmp_path: Path,
) -> None:
    for folder in ("Private", "Public"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "Note.md").write_text("# Shared\nDetails")
    vault = Vault(tmp_path)
    try:
        vault.sync()
        filtering = SuggestionFilter(vault.db, EmbeddingComputer())
        filtering.config["boundary"]["exclude_paths"] = ["Private/"]
        ambiguous, public, private = [
            Suggestion(text="Revisit this note", notes=[ref], geist_id="test")
            for ref in ("Shared", "Public/Note#Details", "Private/Note#Details")
        ]
        assert filtering.filter_boundary([ambiguous, public, private]) == [public]

        (tmp_path / "Public.md").write_text("# Public\nPublic details")
        (tmp_path / "Private" / "secret.md").write_text("# Public^2\nPrivate details")
        vault.sync()
        shadowed_private = Suggestion(
            text="Private title shadowed by a public filename",
            notes=["Public^2"],
            geist_id="test",
        )
        padded_shadow = Suggestion(
            text="Padding cannot hide a literal title containing a block marker",
            notes=[" Public^2 "],
            geist_id="test",
        )
        explicit_public = Suggestion(
            text="Explicit public path remains usable",
            notes=["Public.md"],
            geist_id="test",
        )
        assert filtering.filter_boundary([shadowed_private, padded_shadow, explicit_public]) == [
            explicit_public
        ]

        (tmp_path / "Private" / "secret.md").write_text(
            "---\ntitle: ' Public '\n---\nPrivate details"
        )
        vault.sync()
        spaced_literal = Suggestion(
            text="Literal whitespace cannot conceal a private title",
            notes=[" Public "],
            geist_id="test",
        )
        trimmed_alias = Suggestion(
            text="Parser trimming cannot conceal a private title",
            notes=["Public"],
            geist_id="test",
        )
        assert filtering.filter_boundary([spaced_literal, trimmed_alias, explicit_public]) == [
            explicit_public
        ]
    finally:
        vault.close()


def test_windows_paths_resolve_locally_and_honour_forward_slash_references() -> None:
    index = NoteLinkIndex(
        [
            (r"one\Note.md", "Shared", False, None, None),
            (r"two\Note.md", "Shared", False, None, None),
            (r"one\Source.md", "Source", False, None, None),
        ]
    )

    assert index.resolve("Note", "one/Source.md") == r"one\Note.md"
    assert index.resolve("Shared", r"one\Source.md") == r"one\Note.md"
    assert index.resolve("one/Note") == r"one\Note.md"
    assert index.resolve(r"two\Note.md") == r"two\Note.md"


def test_windows_paths_cannot_bypass_boundary_folder_exclusions() -> None:
    db = sqlite3.connect(":memory:")
    db.execute(
        """
        CREATE TABLE notes (
            path TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            is_virtual INTEGER NOT NULL,
            source_file TEXT,
            entry_date TEXT
        )
        """
    )
    db.executemany(
        "INSERT INTO notes VALUES (?, ?, 0, NULL, NULL)",
        [("Public.md", "Public"), (r"Private\secret.md", "Secret")],
    )
    filtering = SuggestionFilter(db, EmbeddingComputer())
    filtering.config["boundary"]["exclude_paths"] = ["Private/"]

    public = Suggestion(text="Public", notes=["Public"], geist_id="test")
    private = Suggestion(text="Private", notes=["Secret"], geist_id="test")
    assert filtering.filter_boundary([public, private]) == [public]
    db.close()


def test_stats_count_reciprocal_aliases_as_resolved_edges(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    (tmp_path / "A.md").write_text("# Renamed A\n[[sub/B#Details]]")
    (tmp_path / "sub" / "B.md").write_text("# Renamed B\n[[Renamed A]]")
    vault = Vault(tmp_path)
    try:
        vault.sync()
        stats = StatsCollector(vault, vault.config)
        assert stats.stats["links"]["bidirectional"] == 2
        assert stats.stats["graph"]["largest_component_size"] == 2
        assert stats.get_orphan_notes() == []
        assert [(n["incoming"], n["outgoing"]) for n in stats.get_top_linked_notes()] == [
            (1, 1),
            (1, 1),
        ]
    finally:
        vault.close()
