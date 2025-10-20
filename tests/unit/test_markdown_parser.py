"""Unit tests for markdown parser."""

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

Some content

```python
def foo():
    return 42

And more content without closing the code block."""

    # Should not crash, just parse what we can
    title = extract_title("test.md", None, content)
    assert title == "My Note"

    # Links should still be extracted from non-code parts
    links = extract_links(content)
    assert links == []  # No links in this content

    # Tags should still work
    tags = extract_tags(content, None)
    assert tags == []


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
    assert links[0].target == "Note"
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
    # Both should be filtered out (empty target after processing)
    assert len(links) == 0


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
