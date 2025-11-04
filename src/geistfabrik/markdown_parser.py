"""Markdown parser for Obsidian files."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .models import Link

# Pre-compiled regex patterns for performance
# Pattern for wiki links: !?[[target|display?]]
# Handles: [[link]], [[link|text]], ![[embed]], [[note#heading]], [[note^block]]
WIKILINK_PATTERN = re.compile(r"(!?)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

# Pattern for inline tags: #tag, including nested tags like #parent/child
TAG_PATTERN = re.compile(r"#([a-zA-Z0-9_/-]+)")


def parse_frontmatter(content: str) -> Tuple[Optional[Dict[str, Any]], str]:
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
        frontmatter = yaml.safe_load(frontmatter_text)
        return frontmatter, remaining_content
    except yaml.YAMLError:
        # Malformed YAML, treat as regular content
        return None, content


def extract_title(path: str, frontmatter: Optional[Dict[str, Any]], content: str) -> str:
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

    # Priority 2: First H1 heading
    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()

    # Priority 3: Filename without extension
    return Path(path).stem


def extract_links(content: str) -> List[Link]:
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
    links = []

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

        # Remove heading anchors (#heading) from target
        if "#" in target:
            target = target.split("#")[0].strip()

        # Skip empty targets
        if not target:
            continue

        links.append(
            Link(
                target=target,
                display_text=display_text,
                is_embed=is_embed,
                block_ref=block_ref,
            )
        )

    return links


def extract_tags(content: str, frontmatter: Optional[Dict[str, Any]] = None) -> List[str]:
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
            tags.update(str(tag).strip() for tag in fm_tags)

    # Extract inline tags from content using pre-compiled pattern
    # Match #tag but not inside code blocks
    # Simple approach: match #word boundaries (not perfect but good enough)
    for match in TAG_PATTERN.finditer(content):
        tag = match.group(1)
        tags.add(tag)

    return sorted(tags)


def parse_markdown(path: str, content: str) -> Tuple[str, str, List[Link], List[str]]:
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
