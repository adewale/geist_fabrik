"""Core data structures for GeistFabrik."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import List, Optional


@dataclass(frozen=True)
class Link:
    """A link from one note to another."""

    target: str  # Target note path or title
    display_text: Optional[str] = None  # Optional display text
    is_embed: bool = False  # True if transclusion (![[note]])
    block_ref: Optional[str] = None  # Block reference ID if present


@dataclass(frozen=True)
class Note:
    """Immutable representation of a vault note.

    For date-collection notes (journal files with date headings), virtual entries
    are created with is_virtual=True and paths like "filename.md/YYYY-MM-DD".
    """

    path: str  # Relative path in vault (or virtual path for entries)
    title: str  # Note title
    content: str  # Full markdown content
    links: List[Link]  # Outgoing [[links]]
    tags: List[str]  # #tags found in note
    created: datetime  # File creation time (or entry date for virtuals)
    modified: datetime  # Last modification time

    # Virtual entry fields (for date-collection notes)
    is_virtual: bool = False  # True for entries split from journal files
    source_file: Optional[str] = None  # Original file path (e.g., "Daily Journal.md")
    entry_date: Optional[date] = None  # Date extracted from heading

    def __hash__(self) -> int:
        """Hash based on path (the unique identifier).

        Path is the primary key in the database, so it uniquely identifies
        a note. This allows Note objects to be used in sets and as dict keys.
        """
        return hash(self.path)

    def __eq__(self, other: object) -> bool:
        """Two notes are equal if they have the same path.

        This enables proper deduplication in sets - two Note objects
        referring to the same file are considered equal even if their
        content, links, or other fields differ.
        """
        if not isinstance(other, Note):
            return NotImplemented
        return self.path == other.path

    @property
    def obsidian_link(self) -> str:
        """Return the Obsidian wiki-link string for this note.

        For regular notes, this is just the title.
        For virtual notes (journal entries), this is a deeplink: "filename#heading"

        This allows geists to use note.obsidian_link without needing to know
        whether the note is virtual or not.

        Examples:
            Regular note: "Project Ideas"
            Virtual note: "Journal#2025-01-15"
        """
        if self.is_virtual and self.source_file:
            # For virtual notes, create deeplink: "filename#heading"
            # Remove .md extension from source file
            filename = self.source_file.replace(".md", "")
            return f"{filename}#{self.title}"
        else:
            # For regular notes, just use the title
            return self.title


@dataclass(frozen=True)
class Suggestion:
    """A geist-generated provocation.

    Immutable to ensure suggestions cannot be modified after creation,
    maintaining data integrity throughout the filtering pipeline.
    """

    text: str  # 1-2 sentence suggestion
    notes: List[str]  # Referenced note titles
    geist_id: str  # Identifier of creating geist
    title: Optional[str] = None  # Optional suggested note title
