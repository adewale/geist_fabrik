"""Visible-topic projection uses parser spans and keeps evidence coordinates."""

import re

import pytest

from geistfabrik.topic_text import explicit_labels, topic_boundaries, topic_prose


@pytest.mark.parametrize("prefix", ["", "> ", "- "])
def test_property_paragraphs_do_not_seed_topics(prefix: str) -> None:
    source = (
        f"{prefix}up:: [[Hidden parent]]\n"
        f"{prefix}custom label:: Hidden property\n\n"
        "# Urban gardens\n\nUrban gardens support wildlife.\n"
    )
    prose = topic_prose(source)
    assert "Hidden" not in prose and "custom label" not in prose
    assert "Urban gardens" in prose and "wildlife" in prose
    assert len(prose) == len(source)
    assert [i for i, c in enumerate(prose) if c == "\n"] == [
        i for i, c in enumerate(source) if c == "\n"
    ]
    assert [label for label, _, _, _ in explicit_labels(source, prose)] == ["Urban gardens"]


@pytest.mark.parametrize(
    "source",
    [
        "Use std::vector for these values.",
        "# Topic:: Research\n\nPublic gardens.",
        "[property:: Visible subject](https://example.test)",
        "Public prose.\nproperty:: A mixed paragraph remains visible.",
    ],
)
def test_property_detection_preserves_other_document_roles(source: str) -> None:
    prose = topic_prose(source)
    assert any(word in prose for word in ("std::vector", "Research", "Visible", "Public"))


@pytest.mark.parametrize(
    "metadata",
    [
        "up:: %% hidden\n",
        "up:: <script>hidden\n",
        "up:: `<script> %% hidden`\n",
        "custom-key:: [[Hidden parent]]\ncréation:: hidden\n",
    ],
)
def test_property_values_cannot_own_later_public_prose(metadata: str) -> None:
    source = metadata + "\n# Urban gardens\n\nPublic wildlife.\n"
    prose = topic_prose(source)
    assert "Urban gardens" in prose and "Public wildlife" in prose
    assert "hidden" not in prose and "Hidden" not in prose


@pytest.mark.parametrize(
    "opening",
    [
        "%% hidden\n\nproperty:: ignored %%\n",
        "Visible <span hidden>secret\n\nproperty:: ignored </span>\n",
        "Visible <span hidden>secret\n\n%% ignored\n\n</span>\n",
        "Visible <span hidden>secret\n\nproperty:: ignored </span><script>\n",
        "Visible <span hidden>secret\n\nproperty:: ignored </span>hidden suffix\n",
    ],
)
def test_earlier_owners_retain_closing_syntax_across_property_blocks(opening: str) -> None:
    source = opening + "\n# Urban gardens\n"
    prose = topic_prose(source)
    assert "Urban gardens" in prose
    assert "secret" not in prose and "ignored" not in prose and "hidden" not in prose


def test_property_raw_text_cannot_disable_later_hidden_html() -> None:
    source = "property:: <script>\n\nPublic <span hidden>secret</span> gardens.\n"
    prose = topic_prose(source)
    assert "Public" in prose and "gardens" in prose
    assert "secret" not in prose


def test_property_inside_hidden_html_preserves_nested_closing_order() -> None:
    source = (
        "Visible <div hidden>secret\n\nproperty:: <div>nested</div>\n\n"
        "hidden suffix</div>\n\nPublic gardens.\n"
    )
    prose = topic_prose(source)
    assert "Public gardens" in prose
    assert "secret" not in prose and "nested" not in prose and "hidden" not in prose


@pytest.mark.parametrize("new_tag", ["script", "div"])
def test_unclosed_property_nesting_cannot_escape_earlier_hidden_html(new_tag: str) -> None:
    source = (
        f"Visible <div hidden>secret\n\nproperty:: <{new_tag}>\n\n"
        "</div>\n\nPublic gardens.\n"
    )
    prose = topic_prose(source)
    assert "Public gardens" in prose and "secret" not in prose


@pytest.mark.parametrize("tag", ["script", "style", "textarea", "title"])
def test_property_local_raw_text_cannot_close_an_earlier_html_owner(tag: str) -> None:
    source = (
        f"Visible <div hidden>secret\n\nproperty:: <{tag}> </div> ignored </{tag}>\n\n"
        "hidden suffix</div>\n\nPublic gardens.\n"
    )
    prose = topic_prose(source)
    assert "Public gardens" in prose
    assert "secret" not in prose and "hidden" not in prose and "ignored" not in prose


@pytest.mark.parametrize("tag", ["textarea", "title"])
def test_selfclosing_property_raw_text_has_paragraph_local_lifetime(tag: str) -> None:
    source = (
        f"Visible <div hidden>secret\n\nproperty:: <{tag}/> </div> ignored </{tag}>\n\n"
        "hidden suffix</div>\n\nPublic gardens.\n"
    )
    prose = topic_prose(source)
    assert "Public gardens" in prose and "hidden suffix" not in prose


def test_property_raw_text_closer_inside_literal_comment_retains_its_role() -> None:
    source = (
        "Visible <div hidden>secret\n\nproperty:: <script><!-- </script> --> </div>\n\n"
        "Public gardens.\n"
    )
    prose = topic_prose(source)
    assert "Public gardens" in prose and "secret" not in prose


def test_many_property_values_have_bounded_comment_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import geistfabrik.topic_text as topic_text

    source = "".join(f"field{number}:: hidden %%\n" for number in range(500))
    source += "\n# Urban gardens\n"
    original = topic_text._parse
    calls = 0

    def counted(content: str):
        nonlocal calls
        calls += 1
        return original(content)

    topic_text._projection.cache_clear()
    monkeypatch.setattr(topic_text, "_parse", counted)
    assert "Urban gardens" in topic_text.topic_prose(source)
    assert calls <= 3


def test_visible_link_syntax_does_not_insert_sentence_boundaries() -> None:
    source = "Using [[evergreen]] notes and [spaced repetition](https://example.test) cards."
    prose = topic_prose(source)
    assert re.search(r"evergreen\s+notes", prose)
    assert re.search(r"spaced repetition\s+cards", prose)


@pytest.mark.parametrize("opening", ["<script/>", "<div hidden/>"])
def test_nonvoid_selfclosing_html_remains_hidden(opening: str) -> None:
    closing = "</script>" if opening.startswith("<script") else "</div>"
    source = f"{opening}\n# Hidden subject\n{closing}\n\nPublic gardens.\n"
    prose = topic_prose(source)
    assert "Hidden subject" not in prose
    assert "Public gardens" in prose


def test_hidden_inline_html_owns_percent_markers() -> None:
    source = "Visible <script>%% hidden</script> gardening.\n"
    prose = topic_prose(source)
    assert "Visible" in prose and "gardening" in prose
    assert "hidden" not in prose


@pytest.mark.parametrize("literal", ["`<script>`", r"\<script>"])
def test_literal_html_cannot_own_visible_percent_comments(literal: str) -> None:
    source = f"{literal} %% hidden subject %% public gardens.\n"
    prose = topic_prose(source)
    assert "hidden subject" not in prose
    assert "public gardens" in prose


def test_unclosed_html_comment_never_becomes_prose() -> None:
    source = "# Public gardens\n\n<!-- hidden subject\n# Secret heading\n"
    prose = topic_prose(source)
    assert "Public gardens" in prose
    assert "hidden subject" not in prose and "Secret heading" not in prose


def test_empty_heading_cannot_turn_a_later_paragraph_into_heading_evidence() -> None:
    source = "#\n\nUnheaded prose.\n"
    labels = list(explicit_labels(source, topic_prose(source)))
    assert not any(kind == "heading" for _, _, _, kind in labels)


def test_many_simple_comments_use_bounded_parser_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import geistfabrik.topic_text as topic_text

    source = "%%x%%\n" * 500 + "# Public gardens\n"
    original = topic_text._parse
    calls = 0

    def counted(content: str):
        nonlocal calls
        calls += 1
        return original(content)

    topic_text._projection.cache_clear()
    monkeypatch.setattr(topic_text, "_parse", counted)
    assert "Public gardens" in topic_text.topic_prose(source)
    assert calls <= 3


def test_structural_comment_work_limit_is_explicit() -> None:
    source = "%%`x`%%\n" * 100 + "# Public gardens\n"
    with pytest.raises(ValueError, match="work limit"):
        topic_prose(source)


@pytest.mark.parametrize(
    "content",
    [
        '[docs](https://example.test/a_(b) "Hidden subject")\n',
        '[docs](<https://example.test/a_(b)> "Hidden subject")\n',
        '[docs][tracking]\n\n[tracking]: https://example.test/a_(b) "Hidden subject"\n',
    ],
)
def test_balanced_link_metadata_is_never_visible(content: str) -> None:
    prose = topic_prose(content)
    assert "docs" in prose
    assert "Hidden subject" not in prose
    assert "example.test" not in prose
    assert "tracking" not in prose


@pytest.mark.parametrize(
    "hidden",
    [
        "<!--\n```\n-->\n",
        "<!-- hidden ` marker -->\n",
        "%%\n```\nhidden text\n%%\n",
        "%% hidden ` marker %%\n",
        "`hidden <!-- marker`\n",
        "`hidden %% marker`\n",
        '[ref]: https://example.test "` Hidden subject"\n\n',
    ],
)
def test_first_owner_cannot_erase_later_visible_prose(hidden: str) -> None:
    content = hidden + "# Urban gardens\n\nUrban gardens support wildlife.\n"
    prose = topic_prose(content)
    assert "Urban gardens" in prose
    assert "hidden" not in prose
    assert "Hidden subject" not in prose
    assert next(explicit_labels(content, prose))[:2] == (
        "Urban gardens",
        content.index("Urban gardens"),
    )


@pytest.mark.parametrize(
    "content",
    [
        "`hidden %% subject`\n",
        '> ```python\n> hidden_subject = "%%"\n> ```\n',
        '~~~\nhidden_subject = "%%"\n~~~\n',
        '    hidden_subject = "%%"\n',
        "``hidden\nmultiline subject``\n",
        "![hidden](https://example.test/image.png)\n",
        "![[hidden subject]]\n",
        "<script>hidden subject</script>\n",
        "<div hidden>hidden subject</div>\n",
        "public <code>hidden subject</code> public\n",
    ],
)
def test_nonprose_does_not_seed_topics(content: str) -> None:
    prose = topic_prose(content)
    assert "hidden" not in prose
    assert "subject" not in prose


def test_inline_script_and_style_do_not_lose_their_opening_owner() -> None:
    source = (
        "Visible gardening <script>secrettrackingpixel</script> "
        "<style>secretstyleword</style> wildlife.\n"
    )
    prose = topic_prose(source)
    assert "Visible gardening" in prose and "wildlife" in prose
    assert "secret" not in prose
    assert "script" not in prose and "style" not in prose


@pytest.mark.parametrize("tag", ["script", "style"])
def test_self_closing_raw_text_cannot_close_parent_ownership(tag: str) -> None:
    source = (
        f"<div><{tag}/>ignored </div>Hidden subject</{tag}></div>\n\n"
        "# Urban gardens\n\nUrban gardens support wildlife.\n"
    )
    prose = topic_prose(source)
    assert "Hidden subject" not in prose and "ignored" not in prose
    assert "Urban gardens" in prose and "wildlife" in prose


def test_link_labels_still_obey_comment_and_code_rules() -> None:
    content = (
        '[seed %% hidden subject %% libraries](https://example.test/%%metadata "` title") '
        "`hidden code`\n"
    )
    prose = topic_prose(content)
    assert "seed" in prose and "libraries" in prose
    assert "hidden" not in prose and "subject" not in prose
    assert "metadata" not in prose and "title" not in prose


def test_first_visible_primary_heading_gets_the_heading_seed() -> None:
    content = "```\n# Hidden primary\n```\n# Zebra primary\n" + "".join(
        f"# A{number} heading\n" for number in range(6)
    )
    labels = list(explicit_labels(content, topic_prose(content)))
    assert [label for label, _, _, kind in labels if kind == "heading"] == ["Zebra primary"]
    start = content.index("Zebra primary")
    assert labels[0] == ("Zebra primary", start, start + len("Zebra primary"), "heading")


def test_wikilink_display_words_keep_their_original_spans() -> None:
    content = "# Gardening\n\n[[Private destination|seed libraries]] ![[hidden subject]]\n"
    prose = topic_prose(content)
    labels = list(explicit_labels(content, prose))
    assert "Private destination" not in prose
    assert "hidden subject" not in prose
    assert (
        "seed libraries",
        content.index("seed libraries"),
        content.index("seed libraries") + len("seed libraries"),
        "wikilink",
    ) in labels
    assert all(content[start:end] == label for label, start, end, _ in labels)


def test_projection_preserves_every_original_offset_and_newline() -> None:
    source = (
        "---\r\ntags: [hidden]\r\n---\r\n# Gardening\r\n\r\n"
        '[seed libraries](https://example.test "hidden")\r\n`hidden code`\r\n'
    )
    prose = topic_prose(source)
    assert len(prose) == len(source)
    assert [(i, c) for i, c in enumerate(prose) if c in "\r\n"] == [
        (i, c) for i, c in enumerate(source) if c in "\r\n"
    ]
    start = source.index("seed libraries")
    assert prose[start : start + len("seed libraries")] == "seed libraries"
    assert "hidden" not in prose


@pytest.mark.parametrize("content", ["red\n\nblue", "red\n- blue", "red\n## blue"])
def test_block_boundaries_cannot_be_joined_as_one_phrase(content: str) -> None:
    prose = topic_prose(content)
    start = prose.index("red")
    end = prose.index("blue") + len("blue")
    assert any(start < boundary < end for boundary in topic_boundaries(content))


def test_soft_paragraph_wrap_can_remain_one_phrase() -> None:
    content = "seed\nlibraries"
    assert not any(0 < boundary < len(content) for boundary in topic_boundaries(content))


def test_generic_secondary_headings_are_masked() -> None:
    content = "# Gardening\n## 1 Introduction\n## 2 Methods\nGardening supports wildlife.\n"
    prose = topic_prose(content)
    assert "Gardening" in prose
    assert "Introduction" not in prose and "Methods" not in prose
