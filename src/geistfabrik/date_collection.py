"""Date-collection note detection and splitting.

Handles journal files with multiple date-based entries separated by date headings.
These files are split into virtual note entries during vault synchronization.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .markdown_parser import extract_links, extract_tags, parse_frontmatter
from .models import Note

logger = logging.getLogger(__name__)

# Date format patterns (H2 headings only)
DATE_PATTERNS: List[Tuple[str, Callable[[Tuple[str, ...]], date]]] = [
    # ISO date: 2025-01-15
    (r"^##\s+(\d{4})-(\d{2})-(\d{2})\s*$", lambda m: date(int(m[0]), int(m[1]), int(m[2]))),
    # US format: 01/15/2025
    (r"^##\s+(\d{2})/(\d{2})/(\d{4})\s*$", lambda m: date(int(m[2]), int(m[0]), int(m[1]))),
    # EU format: 15.01.2025
    (r"^##\s+(\d{2})\.(\d{2})\.(\d{4})\s*$", lambda m: date(int(m[2]), int(m[1]), int(m[0]))),
    # Long format: January 15, 2025
    (
        r"^##\s+(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),?\s+(\d{4})\s*$",
        lambda m: _parse_long_date(m[0], m[1], m[2]),
    ),
    # Long format without weekday: January 15, 2025
    (
        r"^##\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2}),?\s+(\d{4})\s*$",
        lambda m: _parse_long_date(m[0], m[1], m[2]),
    ),
    # Year Month Day format: 2022 August 8
    (
        r"^##\s+(\d{4})\s+"
        r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(\d{1,2})\s*$",
        lambda m: _parse_long_date(m[1], m[2], m[0]),
    ),
    # ISO datetime: 2025-01-15T09:00:00
    (
        r"^##\s+(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}:\d{2}\s*$",
        lambda m: date(int(m[0]), int(m[1]), int(m[2])),
    ),
]

# Pre-compiled patterns for performance (avoid recompiling on every heading)
_COMPILED_DATE_PATTERNS: List[Tuple[re.Pattern[str], Callable[[Tuple[str, ...]], date]]] = [
    (re.compile(pattern, re.IGNORECASE), parser) for pattern, parser in DATE_PATTERNS
]

MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def _parse_long_date(month_name: str, day_str: str, year_str: str) -> date:
    """Parse long date format like 'January 15, 2025'."""
    month_num = MONTHS[month_name]
    return date(int(year_str), month_num, int(day_str))


@dataclass
class DateSection:
    """A date-based section extracted from a journal file."""

    heading: str  # Original heading text
    entry_date: date  # Parsed date from heading
    content: str  # Content from this heading to next (or EOF)
    start_line: int  # Line number where section starts
    end_line: int  # Line number where section ends


def parse_date_heading(heading: str, file_path: str | None = None) -> Optional[date]:
    """Parse date from H2 heading.

    Args:
        heading: H2 heading line (including ##)
        file_path: Optional file path for error context

    Returns:
        Parsed date if heading matches a date pattern, None otherwise
    """
    heading = heading.strip()

    for pattern, parser_func in _COMPILED_DATE_PATTERNS:
        match = pattern.match(heading)
        if match:
            try:
                return parser_func(match.groups())
            except (ValueError, KeyError) as e:
                context = f" in {file_path}" if file_path else ""
                logger.warning(f"Invalid date in heading '{heading}'{context}: {e}")
                return None

    return None


def extract_h2_headings(content: str) -> List[Tuple[str, int]]:
    """Extract H2 headings and their line numbers.

    Args:
        content: Markdown content

    Returns:
        List of (heading_text, line_number) tuples
    """
    headings = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("## ") and not stripped.startswith("### "):
            headings.append((stripped, line_num))

    return headings


def is_date_collection_note(
    content: str, min_sections: int = 2, date_threshold: float = 0.5
) -> bool:
    """Detect if file contains date-based entries.

    Args:
        content: Full file content
        min_sections: Minimum number of date sections required
        date_threshold: Minimum fraction of H2 headings that must be dates

    Returns:
        True if file should be split into date entries
    """
    headings = extract_h2_headings(content)

    # Must have at least min_sections headings
    if len(headings) < min_sections:
        return False

    # Count how many headings parse as dates
    date_count = sum(1 for heading, _ in headings if parse_date_heading(heading) is not None)

    # Check if enough headings are dates
    return date_count >= len(headings) * date_threshold


def split_by_date_headings(content: str, file_path: str | None = None) -> List[DateSection]:
    """Split content into date-based sections.

    Args:
        content: Full file content
        file_path: Optional file path for error context

    Returns:
        List of DateSection objects, one per valid date heading
    """
    sections = []
    lines = content.split("\n")
    headings = extract_h2_headings(content)

    # Track which headings are date headings
    # Store both line_num (1-indexed) and array index (0-indexed)
    date_headings: List[Tuple[str, int, int, date]] = []
    for heading_text, line_num in headings:
        parsed_date = parse_date_heading(heading_text, file_path)
        if parsed_date is not None:
            # line_num is 1-indexed, array index is line_num - 1
            date_headings.append((heading_text, line_num, line_num - 1, parsed_date))

    if not date_headings:
        return []

    # Extract content for each date section
    for i, (heading, line_num, heading_idx, entry_date) in enumerate(date_headings):
        # Find end of section (next date heading or EOF)
        if i + 1 < len(date_headings):
            # End at the line before the next heading
            end_idx = date_headings[i + 1][2]
        else:
            end_idx = len(lines)

        # Extract section content (excluding the heading itself)
        # Content starts after the heading line
        section_lines = lines[heading_idx + 1 : end_idx]
        section_content = "\n".join(section_lines).strip()

        # Skip empty sections
        if not section_content:
            logger.debug(f"Skipping empty section for date {entry_date}")
            continue

        sections.append(
            DateSection(
                heading=heading,
                entry_date=entry_date,
                content=section_content,
                start_line=line_num,
                end_line=end_idx,
            )
        )

    return sections


def split_date_collection_note(
    file_path: str,
    content: str,
    file_created: datetime,
    file_modified: datetime,
) -> List[Note]:
    """Split journal file into virtual note entries.

    Args:
        file_path: Original file path (e.g., "Daily Journal.md")
        content: Full file content
        file_created: File creation timestamp
        file_modified: File modification timestamp

    Returns:
        List of virtual Note objects, one per date section
    """
    # Parse frontmatter (applies to all entries)
    frontmatter, clean_content = parse_frontmatter(content)
    frontmatter_tags = []
    if frontmatter and "tags" in frontmatter:
        tags_value = frontmatter["tags"]
        if isinstance(tags_value, list):
            frontmatter_tags = tags_value
        elif isinstance(tags_value, str):
            frontmatter_tags = [tags_value]

    # Split by date headings
    sections = split_by_date_headings(clean_content, file_path)

    if not sections:
        logger.debug(f"No valid date sections found in {file_path}")
        return []

    # Merge duplicate dates, keeping track of first heading text
    merged_sections: Dict[date, List[str]] = {}
    original_headings: Dict[date, str] = {}
    for section in sections:
        if section.entry_date not in merged_sections:
            merged_sections[section.entry_date] = []
            # Store original heading text (strip ## prefix and whitespace)
            original_headings[section.entry_date] = section.heading.lstrip('#').strip()
        merged_sections[section.entry_date].append(section.content)

    # Create virtual notes
    virtual_notes = []
    file_stem = Path(file_path).stem

    for entry_date in sorted(merged_sections.keys()):
        contents = merged_sections[entry_date]
        merged_content = "\n\n".join(contents)

        # Extract links and tags from this entry only
        links = extract_links(merged_content)
        inline_tags = extract_tags(merged_content, frontmatter)

        # Combine frontmatter tags with inline tags
        all_tags = frontmatter_tags + [tag for tag in inline_tags if tag not in frontmatter_tags]

        # Generate virtual path and title
        # Path uses ISO date for consistency and uniqueness
        # Title uses original heading text for Obsidian deeplink compatibility
        virtual_path = f"{file_path}/{entry_date.isoformat()}"
        original_heading_text = original_headings[entry_date]
        title = f"{file_stem}#{original_heading_text}"

        # Create note with entry_date as created time
        entry_datetime = datetime.combine(entry_date, datetime.min.time())

        virtual_notes.append(
            Note(
                path=virtual_path,
                title=title,
                content=merged_content,
                links=links,
                tags=all_tags,
                created=entry_datetime,
                modified=file_modified,
                is_virtual=True,
                source_file=file_path,
                entry_date=entry_date,
            )
        )

    return virtual_notes
