"""Markdown parser for Obsidian files."""

import re
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .bounded_yaml import BoundedYAMLError, load_bounded_yaml_text
from .config import MAX_NOTE_LINKS, MAX_NOTE_TAGS
from .models import Link

# Pre-compiled regex patterns for performance
# Pattern for wiki links: !?[[target|display?]]
# Handles: [[link]], [[link|text]], ![[embed]], [[note#heading]], [[note^block]]
WIKILINK_PATTERN = re.compile(r"(!?)\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")

# Trailing empty heading markers and whitespace before a block reference.
BLOCK_REF_TARGET_TAIL = re.compile(r"[#\s]+\Z")

# Pattern for inline tags: #tag, including nested tags like #parent/child.
# As in Obsidian, the # must start the text or follow whitespace, so URL
# fragments (page#section), markdown anchors ([toc](#section)) and "C#" are
# not tags. A tag also needs a non-numeric character (see _is_tag): "PR #30"
# and "#2023" are not tags.
TAG_PATTERN = re.compile(r"(?<!\S)#([a-zA-Z0-9_/-]+)")

# Code regions are stripped before link and tag extraction: Obsidian does
# not treat [[...]] or #words inside fenced or inline code as links or tags
# (#define, #!/bin/bash, hex colours like #fff, template examples such as
# "[[#note#]]" or f"[[{title}]]" in code samples, ...).
FENCED_CODE_PATTERN = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_PATTERN = re.compile(r"`[^`\n]+`")


def _prose_without_code(content: str) -> str:
    """Content with fenced, indented and inline code removed."""
    prose = "\n".join(line for _, line in markdown_prose_lines(content))
    return INLINE_CODE_PATTERN.sub("", prose)


def iter_wikilinks(text: str) -> Iterator[re.Match[str]]:
    """Yield the same matches as ``WIKILINK_PATTERN.finditer(text)``, in linear time.

    finditer retries a failed match from every following offset, and each
    attempt scans the target up to the next "]" or "|", so a long run of
    "[" (or of "[[" without a closing "]]") took quadratic time. After a
    failed attempt at "[[", every start before the next "]" fails for the
    same reason (they share the same closing "]"), so the scan resumes there.
    """
    pos = 0
    while True:
        i = text.find("[[", pos)
        if i < 0:
            return
        start = i - 1 if i > pos and text[i - 1] == "!" else i
        match = WIKILINK_PATTERN.match(text, start)
        if match is not None:
            yield match
            pos = match.end()
            continue
        if i + 2 < len(text) and text[i + 2] in "]|":
            # Empty target: the only cheap failure; the next "[[" may succeed.
            pos = i + 1
            continue
        close = text.find("]", i + 2)
        if close < 0:
            return
        pos = close + 1


def _is_tag(candidate: str) -> bool:
    """Obsidian tags need at least one non-numeric character."""
    return re.search(r"[A-Za-z_]", candidate) is not None


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

    # Links inside code are examples, not links (see FENCED_CODE_PATTERN).
    for match in iter_wikilinks(_prose_without_code(content)):
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
        # For a block reference, drop an empty heading marker ("Note#^id") and
        # any whitespace around it ("Note #^id"), so the target is canonical
        # and re-parsing a rendered link yields the same link.
        if block_ref is not None:
            target = BLOCK_REF_TARGET_TAIL.sub("", target)

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
    for match in TAG_PATTERN.finditer(_prose_without_code(content)):
        tag = match.group(1)
        if not _is_tag(tag):
            continue
        tags.add(tag)
        if len(tags) > MAX_NOTE_TAGS:
            raise MarkdownLimitError(f"note exceeds {MAX_NOTE_TAGS} unique tags")

    return sorted(tags)


# A note file named "2023-09-12.md" or "2023-09-12 Meeting with Steph.md".
_FILENAME_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?!\d)")


def _as_naive_datetime(value: object) -> datetime | None:
    """A frontmatter value as a naive local datetime, or None if it isn't a date."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    # Reject placeholders and typos such as 0001-01-01 or 20230-01-01.
    if not 1900 <= parsed.year <= 2200:
        return None
    return parsed


def _frontmatter_date(content: str, keys: tuple[str, ...]) -> datetime | None:
    """The first frontmatter property among ``keys`` that holds a valid date.

    Keys are matched case-insensitively and tried in the order given.
    """
    frontmatter, _ = parse_frontmatter(content)
    if not frontmatter:
        return None
    by_key = {str(key).strip().lower(): value for key, value in frontmatter.items()}
    for key in keys:
        if key in by_key:
            declared = _as_naive_datetime(by_key[key])
            if declared is not None:
                return declared
    return None


def declared_modification_date(content: str) -> datetime | None:
    """When the note says it was last changed, if it says so.

    A frontmatter ``modified:`` property, else ``updated:`` (both common in
    Obsidian templates and "update time on edit" plugins). Returns None when
    the note declares neither; callers then fall back to the file's mtime,
    which copying, syncing or a git clone resets.
    """
    return _frontmatter_date(content, ("modified", "updated"))


def declared_creation_date(path: str, content: str) -> datetime | None:
    """When the note says it was created, if it says so.

    Precedence: a frontmatter ``created:`` property (Obsidian's convention,
    used by its templates and kepano's vault), then a date at the start of the
    file name (daily notes such as ``2023-09-12.md``). Returns None when the
    note declares neither; callers then fall back to file timestamps, which
    copying, syncing or a git clone can reset.
    """
    declared = _frontmatter_date(content, ("created",))
    if declared is not None:
        return declared
    match = _FILENAME_DATE.match(Path(path).name)
    if match:
        try:
            return datetime(int(match[1]), int(match[2]), int(match[3]))
        except ValueError:
            return None
    return None


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
