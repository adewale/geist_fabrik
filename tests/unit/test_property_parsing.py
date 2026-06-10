"""Property-based tests for markdown parsing invariants."""

from hypothesis import given, settings
from hypothesis import strategies as st

from geistfabrik.markdown_parser import (
    extract_links,
    extract_tags,
    extract_title,
    parse_frontmatter,
)

# --- Strategies ---

# Valid YAML-safe text (no special chars that break YAML)
yaml_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "Zs"), whitelist_characters="_-"),
    min_size=1,
    max_size=30,
)

# Markdown body with optional wikilinks and tags
wikilink_target = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" _-"),
    min_size=1,
    max_size=30,
).filter(lambda t: t.strip())

tag_name = st.from_regex(r"[a-zA-Z][a-zA-Z0-9_/-]{0,19}", fullmatch=True)


# --- parse_frontmatter ---


@given(st.text())
@settings(max_examples=100)
def test_frontmatter_idempotent(content: str) -> None:
    """Parsing the body a second time should yield no frontmatter."""
    _, body = parse_frontmatter(content)
    fm2, body2 = parse_frontmatter(body)
    # If the original had valid frontmatter, the body shouldn't
    # Only assert body stability — re-parsing body gives same body
    assert body2 == body or fm2 is None


@given(yaml_safe_text)
def test_frontmatter_with_title_extracted(title: str) -> None:
    """Valid frontmatter with quoted title should round-trip as string."""
    # Quote the value to prevent YAML auto-typing (e.g. "0" → int, "true" → bool)
    content = f'---\ntitle: "{title}"\n---\nBody text here.'
    fm, body = parse_frontmatter(content)
    assert fm is not None
    assert fm["title"] == title
    assert "Body text here." in body


def test_no_frontmatter_returns_full_content() -> None:
    """Content without --- prefix returns None frontmatter and full content."""
    content = "Just regular markdown\nWith multiple lines"
    fm, body = parse_frontmatter(content)
    assert fm is None
    assert body == content


def test_malformed_frontmatter_returns_none() -> None:
    """Unclosed frontmatter returns None."""
    content = "---\ntitle: test\nNo closing delimiter"
    fm, body = parse_frontmatter(content)
    assert fm is None
    assert body == content


# --- extract_title ---


@given(yaml_safe_text)
def test_title_from_frontmatter(title: str) -> None:
    """Frontmatter title takes priority over heading or filename."""
    result = extract_title("note.md", {"title": title}, "# Heading\nBody")
    assert result == title


@given(yaml_safe_text.filter(lambda s: s.strip()))
def test_title_from_h1(heading: str) -> None:
    """First H1 heading is used when no frontmatter title."""
    result = extract_title("note.md", None, f"# {heading}\nBody")
    assert result == heading.strip()


@given(st.text(min_size=1, max_size=30).filter(lambda s: "/" not in s and "." not in s))
def test_title_falls_back_to_filename(stem: str) -> None:
    """Filename stem is used when no frontmatter or heading."""
    result = extract_title(f"{stem}.md", None, "No heading here")
    assert result == stem


@given(st.text(min_size=1, max_size=50))
def test_title_always_returns_string(content: str) -> None:
    """extract_title never returns empty string."""
    result = extract_title("fallback.md", None, content)
    assert isinstance(result, str)
    assert len(result) > 0


# --- extract_links ---


@given(st.lists(wikilink_target, min_size=1, max_size=10))
def test_extract_links_finds_all_wikilinks(targets: list[str]) -> None:
    """All [[target]] links in content should be extracted."""
    content = " ".join(f"[[{t}]]" for t in targets)
    links = extract_links(content)
    extracted_targets = [link.target for link in links]
    for target in targets:
        stripped = target.strip()
        if stripped:
            assert stripped in extracted_targets


@given(st.text(min_size=0, max_size=200))
def test_extract_links_idempotent(content: str) -> None:
    """Same content always produces same links."""
    links1 = extract_links(content)
    links2 = extract_links(content)
    assert links1 == links2


def test_extract_links_with_display_text() -> None:
    """[[target|display]] should parse target and display separately."""
    links = extract_links("See [[Note Title|my note]]")
    assert len(links) == 1
    assert links[0].target == "Note Title"
    assert links[0].display_text == "my note"


def test_extract_links_embed() -> None:
    """![[embed]] should be marked as embed."""
    links = extract_links("Here is ![[Image.png]]")
    assert len(links) == 1
    assert links[0].is_embed is True
    assert links[0].target == "Image.png"


def test_extract_links_heading_anchor() -> None:
    """[[Note#heading]] should strip the heading anchor."""
    links = extract_links("[[Note#Section One]]")
    assert len(links) == 1
    assert links[0].target == "Note"


def test_extract_links_block_ref() -> None:
    """[[Note^block123]] should capture block reference."""
    links = extract_links("[[Note^block123]]")
    assert len(links) == 1
    assert links[0].target == "Note"
    assert links[0].block_ref == "block123"


def test_extract_links_empty_content() -> None:
    """Empty content should yield no links."""
    assert extract_links("") == []


# --- extract_tags ---


@given(st.lists(tag_name, min_size=1, max_size=5, unique=True))
def test_extract_tags_finds_inline_tags(tags: list[str]) -> None:
    """All #tag occurrences should be extracted."""
    content = " ".join(f"#{t}" for t in tags)
    extracted = extract_tags(content)
    for tag in tags:
        assert tag in extracted


@given(st.lists(yaml_safe_text.filter(lambda t: t.strip()), min_size=1, max_size=5, unique=True))
def test_extract_tags_from_frontmatter(tags: list[str]) -> None:
    """Tags in frontmatter should be included."""
    extracted = extract_tags("No inline tags", frontmatter={"tags": tags})
    for tag in tags:
        assert tag.strip() in extracted


def test_extract_tags_returns_sorted() -> None:
    """Tags should be returned in sorted order."""
    content = "#zebra #alpha #middle"
    tags = extract_tags(content)
    assert tags == sorted(tags)


@given(st.text(min_size=0, max_size=200))
def test_extract_tags_idempotent(content: str) -> None:
    """Same content always produces same tags."""
    tags1 = extract_tags(content)
    tags2 = extract_tags(content)
    assert tags1 == tags2


def test_extract_tags_deduplicates() -> None:
    """Duplicate tags should appear only once."""
    content = "#python #python #python"
    tags = extract_tags(content)
    assert tags.count("python") == 1
