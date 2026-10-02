"""Unit tests for markdown parser."""

import pytest

from geistfabrik.markdown_parser import (
    extract_links,
    extract_tags,
    extract_title,
    parse_frontmatter,
    parse_markdown,
)


def test_parse_frontmatter_valid() -> None:
    """Test parsing valid YAML frontmatter."""
    content = """---
title: My Note
tags: [test, example]
---

Content here"""
    frontmatter, remaining = parse_frontmatter(content)
    assert frontmatter is not None
    assert frontmatter["title"] == "My Note"
    assert frontmatter["tags"] == ["test", "example"]
    assert remaining.strip() == "Content here"


def test_parse_frontmatter_none() -> None:
    """Test parsing content without frontmatter."""
    content = "# My Note\n\nContent here"
    frontmatter, remaining = parse_frontmatter(content)
    assert frontmatter is None
    assert remaining == content


def test_parse_malformed_frontmatter() -> None:
    """Test handling malformed YAML frontmatter."""
    content = """---
title: My Note
invalid yaml: [unclosed
---

Content"""
    frontmatter, remaining = parse_frontmatter(content)
    assert frontmatter is None
    assert remaining == content


def test_parse_unclosed_code_blocks() -> None:
    """Test parsing markdown with unclosed code blocks."""
    content = """# My Note

Some content about [[Before Fence]] and #prose

```python
def foo():
    return 42

And more content without closing the code block."""

    # Should not crash, just parse what we can
    title = extract_title("test.md", None, content)
    assert title == "My Note"

    # Links and tags in the prose before the unclosed fence still extract
    links = extract_links(content)
    assert [link.target for link in links] == ["Before Fence"]

    tags = extract_tags(content, None)
    assert tags == ["prose"]


def test_extract_title_from_frontmatter() -> None:
    """Test extracting title from frontmatter."""
    frontmatter = {"title": "Frontmatter Title"}
    content = "# Heading Title"
    title = extract_title("test.md", frontmatter, content)
    assert title == "Frontmatter Title"


def test_extract_title_from_heading() -> None:
    """Test extracting title from H1 heading."""
    content = "# Heading Title\n\nContent"
    title = extract_title("test.md", None, content)
    assert title == "Heading Title"


def test_extract_title_from_filename() -> None:
    """Test extracting title from filename as fallback."""
    content = "No headings here"
    title = extract_title("test-note.md", None, content)
    assert title == "test-note"


def test_extract_links_simple() -> None:
    """Test extracting simple wiki links."""
    content = "Link to [[Note 1]] and [[Note 2]]"
    links = extract_links(content)
    assert len(links) == 2
    assert links[0].target == "Note 1"
    assert links[0].display_text is None
    assert not links[0].is_embed
    assert links[1].target == "Note 2"


def test_extract_links_with_display_text() -> None:
    """Test extracting links with display text."""
    content = "Link to [[Note 1|Display Text]]"
    links = extract_links(content)
    assert len(links) == 1
    assert links[0].target == "Note 1"
    assert links[0].display_text == "Display Text"


def test_extract_links_embeds() -> None:
    """Test extracting embeds (transclusions)."""
    content = "Embed: ![[Embedded Note]]"
    links = extract_links(content)
    assert len(links) == 1
    assert links[0].target == "Embedded Note"
    assert links[0].is_embed


def test_extract_links_with_heading() -> None:
    """Test extracting links with heading anchors."""
    content = "Link to [[Note#Section]]"
    links = extract_links(content)
    assert len(links) == 1
    assert links[0].target == "Note#Section"
    assert links[0].block_ref is None


def test_extract_links_with_block_ref() -> None:
    """Test extracting links with block references."""
    content = "Link to [[Note^block123]]"
    links = extract_links(content)
    assert len(links) == 1
    assert links[0].target == "Note"
    assert links[0].block_ref == "block123"


def test_extract_links_invalid() -> None:
    """Test handling invalid or empty links."""
    content = "Empty link: [[]] or [[#just-anchor]]"
    links = extract_links(content)
    # Anchor-only links must survive until source-aware resolution.
    assert [link.target for link in links] == ["#just-anchor"]


def test_extract_tags_inline() -> None:
    """Test extracting inline tags."""
    content = "Some content #tag1 and #tag2"
    tags = extract_tags(content)
    assert len(tags) == 2
    assert "tag1" in tags
    assert "tag2" in tags


def test_extract_tags_nested() -> None:
    """Test extracting nested tags."""
    content = "Content with #parent/child tag"
    tags = extract_tags(content)
    assert len(tags) == 1
    assert "parent/child" in tags


def test_extract_tags_from_frontmatter() -> None:
    """Test extracting tags from frontmatter."""
    frontmatter = {"tags": ["tag1", "tag2"]}
    content = "No inline tags"
    tags = extract_tags(content, frontmatter)
    assert len(tags) == 2
    assert "tag1" in tags
    assert "tag2" in tags


def test_extract_tags_mixed() -> None:
    """Test extracting tags from both frontmatter and inline."""
    frontmatter = {"tags": ["fm-tag"]}
    content = "Content with #inline-tag"
    tags = extract_tags(content, frontmatter)
    assert len(tags) == 2
    assert "fm-tag" in tags
    assert "inline-tag" in tags


def test_parse_markdown_complete() -> None:
    """Test complete markdown parsing."""
    content = """---
title: Test Note
tags: [test]
---

# Test Note

Link to [[Other Note]] and #inline-tag

![[Embedded]]
"""
    title, clean_content, links, tags = parse_markdown("test.md", content)

    assert title == "Test Note"
    assert len(links) == 2
    assert links[0].target == "Other Note"
    assert not links[0].is_embed
    assert links[1].target == "Embedded"
    assert links[1].is_embed
    assert len(tags) >= 2
    assert "test" in tags
    assert "inline-tag" in tags


def test_parse_invalid_utf8() -> None:
    """Test handling of invalid UTF-8 sequences (AC-1.11)."""
    # Create content with valid UTF-8 replacement character
    # (simulating how Python handles invalid UTF-8)
    content = "# Test\n\nSome text with � replacement character"

    title, clean_content, links, tags = parse_markdown("test.md", content)

    # Should handle gracefully without crashing
    assert title == "Test"
    assert "replacement character" in clean_content
    assert len(links) == 0
    assert len(tags) == 0


def test_extract_tags_ignores_fenced_code_blocks() -> None:
    """#words inside fenced code are not tags (e.g. #define, shebangs)."""
    content = "Real tag #genuine here.\n```c\n#define MAX 10\n#include <stdio.h>\n```\n"
    tags = extract_tags(content)
    assert tags == ["genuine"]


def test_extract_tags_ignores_inline_code() -> None:
    """#words inside inline code spans are not tags (e.g. CSS hex colours)."""
    content = "Use `color: #fff` for white. Also #styling matters."
    tags = extract_tags(content)
    assert tags == ["styling"]


def test_extract_links_ignores_links_inside_code() -> None:
    """Contract: [[...]] inside fenced, indented or inline code is not a link.

    Regression: links were read from raw content, so Tracery examples such as
    "[[#note#]]" and f-strings like f"[[{title}]]" in code samples became
    links (one note had 73 such "links" and no real connection).
    """
    content = (
        "See [[Real Target]].\n"
        "```python\n"
        'text = f"[[{note.title}]]"\n'
        "```\n"
        "Template: `origin: [[#note#]]`\n"
        "\n"
        "    indented = '[[Indented Code]]'\n"
    )
    assert [link.target for link in extract_links(content)] == ["Real Target"]


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("Fixed in PR #30 and #2023.", []),
        ("Read https://example.com/page#Section first.", []),
        ("Jump to [contents](#benchmark-types).", []),
        ("Written in C# and F#.", []),
        ("Tagged #y2023 and #1a and #area/sub-topic.", ["1a", "area/sub-topic", "y2023"]),
        ("#start-of-line tag", ["start-of-line"]),
    ],
    ids=["numeric", "url-fragment", "anchor", "suffix", "valid", "line-start"],
)
def test_extract_tags_follows_obsidian_tag_rules(content: str, expected: list[str]) -> None:
    """Contract: a tag starts the text or follows whitespace and has a non-digit.

    Regression: "#30" in "PR #30" and URL fragments were read as tags, so
    seasonal_patterns reported topics such as "#1" and "#30".
    """
    assert extract_tags(content) == expected


@pytest.mark.timeout(10)
@pytest.mark.parametrize(
    "content",
    [
        pytest.param("[" * 100_000, id="100k-open-brackets"),
        pytest.param("[[a|" * 45_000, id="45k-unclosed-piped-links"),
        pytest.param("[[" + "a" * 100_000 + "|" + "[[b" * 30_000, id="unclosed-display"),
    ],
)
def test_extract_links_is_linear_on_unclosed_brackets(content: str) -> None:
    """Regression: WIKILINK_PATTERN.finditer retried from every "[[" and each
    attempt scanned to the next "]", so these took over 30 s (sync hung)."""
    links = extract_links("[[Real Note]] " + content)
    assert [link.target for link in links] == ["Real Note"]


def test_iter_wikilinks_yields_exactly_what_finditer_yields() -> None:
    import random

    from geistfabrik.markdown_parser import WIKILINK_PATTERN, iter_wikilinks

    rng = random.Random(11)
    texts = ["[[a]] ![[b|c]] [[|x]] [[d|]] [[[e]] [[f[g]]", "![[x]]", "!![[y|z]]]"]
    texts += [
        "".join(rng.choice("[[[]]|!a ") for _ in range(rng.randint(0, 24))) for _ in range(5000)
    ]
    for text in texts:
        expected = [(m.span(), m.groups()) for m in WIKILINK_PATTERN.finditer(text)]
        assert [(m.span(), m.groups()) for m in iter_wikilinks(text)] == expected
