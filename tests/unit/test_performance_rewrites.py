"""Behavioral regressions for source parsing and dense graph traversal."""

from dataclasses import replace
from itertools import combinations
from pathlib import Path

import pytest

from geistfabrik import bounded_yaml
from geistfabrik.lexical_index import LexicalIndex, extract_terms
from geistfabrik.markdown_parser import ParsedMarkdown, declared_creation_day
from tests.fixtures.helpers import VaultBuilder


@pytest.mark.parametrize(
    ("setting", "limit", "accepted", "rejected"),
    [
        ("MAX_YAML_NODES", 3, "a: b", "a: [b]"),
        ("MAX_YAML_DEPTH", 2, "a: [b]", "a: [[b]]"),
        ("MAX_YAML_BYTES", 4, "a: b", "a: bc"),
    ],
)
def test_yaml_bounds_apply_before_constructing_values(
    monkeypatch: pytest.MonkeyPatch, setting: str, limit: int, accepted: str, rejected: str
) -> None:
    monkeypatch.setattr(bounded_yaml, setting, limit)
    assert bounded_yaml.load_bounded_yaml_text(accepted) == {"a": ["b"] if "[" in accepted else "b"}
    with pytest.raises(bounded_yaml.BoundedYAMLError):
        bounded_yaml.load_bounded_yaml_text(rejected)


def test_replacing_note_content_rebuilds_its_source(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Original", "original prose")
    context = builder.build()
    note = context.notes()[0]
    original = replace(note, _parsed_source=ParsedMarkdown.parse(note.content))
    changed = replace(original, content="---\ncreated: 2024-02-01\n---\nreplacement prose")
    assert original.source is not None and original.source.body.endswith("original prose")
    assert changed.source is None
    assert changed.body == "replacement prose"
    day = declared_creation_day(changed.path, changed.content, parsed=changed.source)
    assert day is not None and day.isoformat() == "2024-02-01"


def test_dense_graph_agrees_with_link_records_and_phrase_isolation(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("A", "[[B]] [[B|repeat]] [[A#heading]] [[Missing]]")
    builder.note("B", "[[C]]")
    builder.note("C", "independent prose")
    builder.note("D", "[[Templates/Hidden]]")
    builder.note("Hidden", "[[A]]", folder="Templates")
    builder.journal("Output", "[[D]]")
    context = builder.build()
    notes = context.notes()
    assert {note.title for note in notes} == {"A", "B", "C", "D"}
    graph = context.resolved_graph()
    for a, b in combinations(notes, 2):
        assert graph.connected(graph.ids[a.path], graph.ids[b.path]) == bool(
            context.links_between(a, b)
        )
    by_title = {note.title: note for note in notes}
    outsider = replace(by_title["A"], path="unsynced.md")
    assert context.has_link(outsider, by_title["B"])
    edited = replace(by_title["A"], links=[])
    assert not context.has_link(edited, by_title["B"])
    marks = [0] * len(notes)
    for generation, group in enumerate(combinations(notes, 3), start=1):
        expected = [
            a.path for a in group if not any(a != b and context.links_between(a, b) for b in group)
        ]
        actual = graph.isolated_members([graph.ids[n.path] for n in group], marks, generation)
        assert [graph.notes[i].path for i in actual] == expected
    assert [n.title for n in context.outgoing_links(next(n for n in notes if n.title == "A"))] == [
        "B"
    ]


def test_reused_lexical_grammar_keeps_document_state_separate(tmp_path: Path) -> None:
    builder = VaultBuilder(tmp_path)
    builder.note("Seed", "initial")
    context = builder.build()
    index = LexicalIndex(
        context.vault.db, context.vault.config.lexical_analysis, context.session.date
    )
    contents = [
        "[label][id]\n\n[id]: https://hidden.invalid/secret\n",
        "[label][id]\n\n`invisible` [[Target|visible]]\n",
        "---\ncreated: 2024-01-01\n---\n> hidden quotation\n\nvisible prose",
        "<div>visible <code>hidden</code></div>\n",
    ]
    # Repeat in reverse order to expose grammar/environment leakage.
    for content in contents + contents[::-1]:
        expected = extract_terms(content, ngram_max=3)
        assert (
            extract_terms(
                content, ngram_max=3, parsed=ParsedMarkdown.parse(content), parser=index._parser
            )
            == expected
        )
