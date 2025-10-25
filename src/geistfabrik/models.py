"""Core data structures for GeistFabrik."""

from dataclasses import dataclass
from datetime import datetime
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
    """Immutable representation of a vault note."""

    path: str  # Relative path in vault
    title: str  # Note title
    content: str  # Full markdown content
    links: List[Link]  # Outgoing [[links]]
    tags: List[str]  # #tags found in note
    created: datetime  # File creation time
    modified: datetime  # Last modification time

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
