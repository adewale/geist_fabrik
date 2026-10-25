"""Generic heading-name exclusions are fallible source-role decisions."""

import pytest

from geistfabrik.topic_text import (
    explicit_labels,
    topic_boundaries,
    topic_prose,
    topic_role_exclusions,
)


@pytest.mark.parametrize("heading", ["Notes", "Methods"])
@pytest.mark.parametrize("prefix", ["# ", "## ", "> # "])
def test_visible_generic_heading_names_report_their_exact_role_spans(
    heading: str, prefix: str,
) -> None:
    source = f"{prefix}{heading}\n\nCyanotypes preserve useful images.\n"
    start = len(prefix)
    assert topic_role_exclusions(source) == ((start, start + len(heading)),)
    assert source[start : start + len(heading)] == heading
    assert heading not in topic_prose(source)
    assert "Cyanotypes preserve useful images." in topic_prose(source)


def test_only_the_heading_occurrence_of_notes_has_a_generic_section_role() -> None:
    source = "# Notes\n\nNotes support research.\n"
    assert topic_role_exclusions(source) == ((2, 7),)
    assert topic_prose(source) == "  .    \n\nNotes support research.\n"
    assert topic_boundaries(source) == (2, 7, 9, len(source) - 1)
    assert list(explicit_labels(source, topic_prose(source))) == []


def test_meaningful_body_occurrences_of_generic_words_have_no_heading_role() -> None:
    source = "Notes organize evidence. Methods describe reproducible experiments.\n"
    assert topic_role_exclusions(source) == ()
    assert topic_prose(source) == source


def test_frontmatter_and_code_stay_masked_without_heuristic_role_exclusions() -> None:
    source = (
        "---\ntitle: Notes\nsubject: Methods\n---\n\n"
        "```markdown\n# Notes\n## Methods\n```\n"
        "\n    # Notes\n"
    )
    assert topic_role_exclusions(source) == ()
    assert "Notes" not in topic_prose(source)
    assert "Methods" not in topic_prose(source)
    assert list(explicit_labels(source, topic_prose(source))) == []


def test_visible_role_spans_do_not_cover_identical_words_in_hard_exclusions() -> None:
    source = (
        "---\ntitle: Notes\n---\n\n"
        "```markdown\n# Methods\n```\n\n"
        "# Notes\n"
    )
    start = source.rindex("Notes")
    assert topic_role_exclusions(source) == ((start, start + 5),)
    assert "Notes" not in topic_prose(source)
    assert "Methods" not in topic_prose(source)
    assert source.index("Notes") < start
    assert source.index("Methods") < start


def test_numbered_generic_heading_reports_the_existing_masked_source_range() -> None:
    source = "## 2. Notes\n\nA substantive body.\n"
    assert topic_role_exclusions(source) == ((3, 11),)
    assert source[3:11] == "2. Notes"
    assert "Notes" not in topic_prose(source)


def test_reporting_roles_preserves_primary_subject_and_link_evidence() -> None:
    source = "# Notes\n\n# Cyanotypes\n\n[[Photograms]]\n"
    prose = topic_prose(source)
    boundaries = topic_boundaries(source)
    labels = list(explicit_labels(source, prose))
    assert topic_role_exclusions(source) == ((2, 7),)
    assert topic_prose(source) == prose
    assert topic_boundaries(source) == boundaries
    assert list(explicit_labels(source, prose)) == labels
    assert [(label, provenance) for label, _, _, provenance in labels] == [
        ("Cyanotypes", "heading"), ("Photograms", "wikilink"),
    ]
    assert all(source[start:end] == label for label, start, end, _ in labels)


@pytest.mark.parametrize("opening", ["<code>", "<span hidden>", '<span aria-hidden="true">'])
def test_earlier_html_ownership_wins_over_a_generic_heading_role(opening: str) -> None:
    closing = "</code>" if opening == "<code>" else "</span>"
    source = f"Visible {opening}\n\n# Notes\n\n{closing}\n\n## Methods\n"
    start = source.index("Methods")
    assert topic_role_exclusions(source) == ((start, start + 7),)
    assert "Notes" not in topic_prose(source)
    assert "Methods" not in topic_prose(source)
    assert "Visible" in topic_prose(source)
