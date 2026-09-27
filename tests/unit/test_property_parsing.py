"""Property-based tests for markdown parsing invariants."""

import yaml
from hypothesis import example, given
from hypothesis import strategies as st

from geistfabrik.markdown_parser import (
    extract_links,
    extract_tags,
    extract_title,
    parse_frontmatter,
)
from geistfabrik.models import Link

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


@given(
    metadata=st.fixed_dictionaries(
        {
            "title": yaml_safe_text,
            "tags": st.lists(yaml_safe_text, max_size=5),
            "count": st.integers(min_value=-1000, max_value=1000),
            "published": st.booleans(),
        }
    ),
    body=st.text(max_size=500),
)
@example(
    metadata={"title": "first", "tags": [], "count": 0, "published": False},
    body="---\ntitle: second\n---\nBody",
)
def test_frontmatter_preserves_metadata_and_exact_body(metadata: dict, body: str) -> None:
    """Consume only the first metadata block, leaving even a second block intact."""
    content = "---\n" + yaml.safe_dump(metadata, allow_unicode=True) + "---\n" + body
    actual_metadata, actual_body = parse_frontmatter(content)
    assert actual_metadata == metadata
    assert actual_body == body


@given(yaml_safe_text)
def test_frontmatter_with_title_extracted(title: str) -> None:
    """Valid frontmatter with quoted title should round-trip as string."""
    # Quote the value to prevent YAML auto-typing (e.g. "0" → int, "true" → bool)
    content = f'---\ntitle: "{title}"\n---\nBody text here.'
    fm, body = parse_frontmatter(content)
    assert fm is not None
    assert fm["title"] == title
    assert "Body text here." in body


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
    """Plain wikilinks round-trip exactly, including order and duplicates."""
    content = " ".join(f"[[{t}]]" for t in targets)
    links = extract_links(content)
    assert [link.target for link in links] == [target.strip() for target in targets]
    assert all(link.display_text is None for link in links)
    assert all(not link.is_embed for link in links)
    assert all(link.block_ref is None for link in links)


@given(st.text(min_size=0, max_size=200))
def test_extract_links_is_deterministic(content: str) -> None:
    """Same content always produces same links (determinism, not idempotence)."""
    links1 = extract_links(content)
    links2 = extract_links(content)
    assert links1 == links2


def _render_link(link: Link) -> str:
    """Inverse of extract_links for one link, in wikilink syntax."""
    target = link.target if link.block_ref is None else f"{link.target}^{link.block_ref}"
    # extract_links strips display text, so "" can only come from whitespace.
    display = "" if link.display_text is None else f"|{link.display_text or ' '}"
    return f"{'!' if link.is_embed else ''}[[{target}{display}]]"


# Dense in the syntax characters, so malformed and nested links are common.
wikilink_soup = st.lists(
    st.sampled_from(["[[", "]]", "|", "^", "#", "!", " ", "\n", "a", "b"]), max_size=40
).map("".join)


@given(st.one_of(st.text(min_size=0, max_size=200), wikilink_soup))
@example("[[Note #^block1]]")  # was target "Note " -> re-parsed as "Note"
@example("[[Note # #^block1]]")
@example("[[a| ]]")
def test_reparsing_rendered_links_is_a_fixpoint(content: str) -> None:
    """Idempotence: extract -> render -> extract returns the same links."""
    links = extract_links(content)
    assert extract_links(" ".join(_render_link(link) for link in links)) == links


def test_extract_links_empty_content() -> None:
    """Empty content should yield no links."""
    assert extract_links("") == []


# --- extract_tags ---


@given(st.lists(tag_name, min_size=1, max_size=5, unique=True))
def test_extract_tags_finds_inline_tags(tags: list[str]) -> None:
    """Inline tags are returned as the exact sorted unique set."""
    content = " ".join(f"#{t}" for t in tags)
    assert extract_tags(content) == sorted(tags)


@given(st.lists(yaml_safe_text.filter(lambda t: t.strip()), min_size=1, max_size=5, unique=True))
def test_extract_tags_from_frontmatter(tags: list[str]) -> None:
    """Frontmatter tags are returned as the exact sorted unique set."""
    assert extract_tags("No inline tags", frontmatter={"tags": tags}) == sorted(
        {tag.strip() for tag in tags}
    )


@given(st.text(min_size=0, max_size=200))
def test_extract_tags_idempotent(content: str) -> None:
    """Same content always produces same tags."""
    tags1 = extract_tags(content)
    tags2 = extract_tags(content)
    assert tags1 == tags2


def test_extract_tags_deduplicates() -> None:
    """Duplicate tags should appear only once."""
    assert extract_tags("#python #python #python") == ["python"]
