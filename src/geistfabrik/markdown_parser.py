"""Markdown parser for Obsidian files."""

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .bounded_yaml import BoundedYAMLError, load_bounded_yaml_text
from .config import MAX_NOTE_LINKS, MAX_NOTE_TAGS
from .models import Link

# Pre-compiled regex patterns for performance
# Pattern for wiki links: !?[[target|display?]]
# Handles: [[link]], [[link|text]], ![[embed]], [[note#heading]], [[note^block]]
WIKILINK_PATTERN = re.compile(r"(!?)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

# Pattern for inline tags: #tag, including nested tags like #parent/child
TAG_PATTERN = re.compile(r"#([a-zA-Z0-9_/-]+)")

# Code regions are stripped before tag extraction: Obsidian does not treat
# #words inside fenced or inline code as tags (#define, #!/bin/bash, hex
# colours like #fff in CSS, URL fragments in code samples, ...).
FENCED_CODE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")


def markdown_prose_lines(content: str) -> Iterator[tuple[int, str]]:
    """Yield original line numbers outside fenced and indented code blocks.

    Fences may use backticks or tildes, with up to three leading spaces; a
    closing fence must use the opening character and at least its length.
    Keeping line numbers lets journal splitting preserve code verbatim while
    excluding its example headings from detection and section boundaries.
    """
    fence_character = ""
    fence_length = 0
    for line_number, line in enumerate(content.split("\n"), start=1):
        expanded = line.expandtabs(4)
        fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", expanded)
        if fence_character:
            if (
                fence
                and fence[1][0] == fence_character
                and len(fence[1]) >= fence_length
                and not fence[2].strip()
            ):
                fence_character = ""
            continue
        if expanded.startswith("    "):
            continue
        if fence and (fence[1][0] != "`" or "`" not in fence[2]):
            fence_character, fence_length = fence[1][0], len(fence[1])
            continue
        yield line_number, line


class MarkdownLimitError(ValueError):
    """Raised when a structurally dense note exceeds a fixed parser quota."""


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Extract YAML frontmatter and remaining content.

    Args:
        content: Full markdown content

    Returns:
        Tuple of (frontmatter dict or None, content without frontmatter)
    """
    # Check for frontmatter (must start with ---)
    if not content.startswith("---"):
        return None, content

    # Find closing ---
    lines = content.split("\n")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break

    if end_idx is None:
        # Malformed frontmatter, treat as regular content
        return None, content

    # Parse YAML
    frontmatter_text = "\n".join(lines[1:end_idx])
    remaining_content = "\n".join(lines[end_idx + 1 :])

    try:
        frontmatter = load_bounded_yaml_text(frontmatter_text, "Markdown frontmatter")
        if frontmatter is None:
            return {}, remaining_content
        if not isinstance(frontmatter, dict) or any(
            not isinstance(key, str) for key in frontmatter
        ):
            return None, content
        return frontmatter, remaining_content
    except BoundedYAMLError:
        # Malformed or resource-heavy YAML is ordinary Markdown, not metadata.
        return None, content


def extract_title(path: str, frontmatter: dict[str, Any] | None, content: str) -> str:
    """Extract note title from frontmatter, first heading, or filename.

    Args:
        path: Note file path
        frontmatter: Parsed frontmatter (may be None)
        content: Markdown content (without frontmatter)

    Returns:
        Note title
    """
    # Priority 1: Frontmatter title
    if frontmatter and "title" in frontmatter:
        return str(frontmatter["title"])

    # Priority 2: First H1 heading (skip empty headings like "# ")
    for _, line in markdown_prose_lines(content):
        if line.startswith("# "):
            heading = line[2:].strip()
            if heading:
                return heading

    # Priority 3: Filename without extension
    return Path(path).stem


def extract_links(content: str) -> list[Link]:
    """Extract wiki-style links from markdown content.

    Supports:
    - [[target]]
    - [[target|display text]]
    - ![[embed]]
    - [[target#heading]]
    - [[target^blockref]]

    Args:
        content: Markdown content

    Returns:
        List of Link objects
    """
    links: list[Link] = []

    # Use pre-compiled pattern for better performance
    for match in WIKILINK_PATTERN.finditer(content):
        is_embed = match.group(1) == "!"
        target_raw = match.group(2).strip()
        display_text = match.group(3).strip() if match.group(3) else None

        # Check for block reference (^blockid)
        block_ref = None
        if "^" in target_raw:
            target, block_ref = target_raw.split("^", 1)
            target = target.strip()
            block_ref = block_ref.strip()
        else:
            target = target_raw

        # Preserve heading anchors: a journal heading identifies a distinct
        # virtual note. Resolution (with the source context) owns stripping a
        # regular note's section anchor, not this lossless parsing step.
        if block_ref is not None:
            target = target.rstrip("#")

        # Skip empty targets
        if not target:
            continue

        if len(links) >= MAX_NOTE_LINKS:
            raise MarkdownLimitError(f"note exceeds {MAX_NOTE_LINKS} links")
        links.append(
            Link(
                target=target,
                display_text=display_text,
                is_embed=is_embed,
                block_ref=block_ref,
            )
        )

    return links


def extract_tags(content: str, frontmatter: dict[str, Any] | None = None) -> list[str]:
    """Extract tags from markdown content and frontmatter.

    Supports:
    - Inline tags: #tag
    - Nested tags: #parent/child
    - Frontmatter tags field

    Args:
        content: Markdown content
        frontmatter: Parsed frontmatter (may be None)

    Returns:
        List of unique tags (without # prefix)
    """
    tags = set()

    # Extract from frontmatter
    if frontmatter:
        fm_tags = frontmatter.get("tags", [])
        if isinstance(fm_tags, str):
            # Single tag as string
            tags.add(fm_tags.strip())
        elif isinstance(fm_tags, list):
            # List of tags
            for tag in fm_tags:
                tags.add(str(tag).strip())
                if len(tags) > MAX_NOTE_TAGS:
                    raise MarkdownLimitError(f"note exceeds {MAX_NOTE_TAGS} unique tags")

    # Strip code regions first so #words inside fenced/inline code are not
    # misread as tags (matches Obsidian's behaviour).
    content_no_code = "\n".join(line for _, line in markdown_prose_lines(content))
    content_no_code = INLINE_CODE_PATTERN.sub("", content_no_code)

    # Extract inline tags from content using pre-compiled pattern
    for match in TAG_PATTERN.finditer(content_no_code):
        tag = match.group(1)
        tags.add(tag)
        if len(tags) > MAX_NOTE_TAGS:
            raise MarkdownLimitError(f"note exceeds {MAX_NOTE_TAGS} unique tags")

    return sorted(tags)


def parse_markdown(path: str, content: str) -> tuple[str, str, list[Link], list[str]]:
    """Parse markdown file and extract structured data.

    Args:
        path: Note file path
        content: Raw markdown content

    Returns:
        Tuple of (title, clean_content, links, tags)
    """
    # Extract frontmatter
    frontmatter, clean_content = parse_frontmatter(content)

    # Extract title
    title = extract_title(path, frontmatter, clean_content)

    # Extract links and tags
    links = extract_links(content)
    tags = extract_tags(content, frontmatter)

    return title, clean_content, links, tags
