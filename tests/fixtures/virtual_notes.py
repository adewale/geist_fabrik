"""Helper for writing journal files that split into virtual notes.

A file is a date collection when it has at least two H2 headings (##) and at
least half of its H2 headings parse as dates; each dated section then becomes
a virtual note with a path like ``Journal.md/2024-03-15``.
"""

from pathlib import Path


def create_journal_file(
    path: Path,
    dates: list[str],
    content_template: str = "{date} entry content.",
) -> None:
    """Create a journal file with one H2 section per date.

    Args:
        path: Path where journal file should be created
        dates: List of date strings (e.g., ["2024-03-15", "2024-03-16"])
        content_template: Template for entry content, {date} will be replaced
    """
    entries = [f"## {date}\n\n{content_template.format(date=date)}\n" for date in dates]
    path.write_text("\n".join(entries))
