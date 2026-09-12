"""Core data structures for GeistFabrik."""

import posixpath
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime


def _normalise_vault_path(path: str) -> str:
    """Use one separator for persisted paths and user-supplied link targets."""
    return path.replace("\\", "/")


def link_target_forms(
    path: str,
    title: str,
    source_file: str | None = None,
    entry_date: str | None = None,
) -> frozenset[str]:
    """Return canonical aliases for one note, including journal deeplinks.

    Aliases alone cannot settle duplicate titles or source-local references;
    use NoteLinkIndex to resolve them against the complete note collection.

    Args:
        path: Note path relative to the vault root
        title: Note title

    Returns:
        Frozenset of target strings that resolve to the note
    """
    path = _normalise_vault_path(path)
    forms = {
        path,
        title,
        title.strip(),
        _normalise_vault_path(title),
        _normalise_vault_path(title.strip()),
    }
    if source_file:
        source_file = _normalise_vault_path(source_file)
        # A virtual path is not a filename: stripping at its last dot would
        # turn "archive.md/Journal.md/2025-01-15" into "archive.md/Journal".
        for source in {source_file, posixpath.basename(source_file)}:
            for filename in {source, source.removesuffix(".md")}:
                for heading in {title, entry_date or title}:
                    forms.add(f"{filename}#{heading}")
    else:
        forms.add(path.removesuffix(".md"))
        forms.add(posixpath.basename(path))
        forms.add(posixpath.basename(path).removesuffix(".md"))
    return frozenset(forms)


class NoteLinkIndex:
    """Resolve link identities consistently without a SQL query per edge.

    Exact paths win over aliases. Within a journal, bare dates first select
    entries in that same source file. Other short names prefer the source
    directory, then an unambiguous vault-wide title/basename. Ambiguous aliases
    stay unresolved instead of attaching an edge to an arbitrary note.
    """

    def __init__(self, rows: Iterable[tuple[str, str, bool, str | None, str | None]]):
        self.sources: dict[str, str] = {}
        self.path_identities: dict[str, set[str]] = {}
        self.forms: dict[str, set[str]] = {}
        self.journal_dates: dict[tuple[str, str], str] = {}
        for path, title, is_virtual, source_file, entry_date in rows:
            normalised_path = _normalise_vault_path(path)
            source = (
                _normalise_vault_path(source_file)
                if is_virtual and source_file
                else normalised_path
            )
            self.sources[path] = source
            self.path_identities.setdefault(normalised_path, set()).add(path)
            forms = link_target_forms(path, title, source_file if is_virtual else None, entry_date)
            for form in forms:
                self.forms.setdefault(form, set()).add(path)
            if is_virtual and source_file and entry_date:
                self.journal_dates[_normalise_vault_path(source_file), entry_date] = path

    @classmethod
    def from_notes(cls, notes: Iterable["Note"]) -> "NoteLinkIndex":
        """Build an index from a session's already loaded notes."""
        return cls(
            (
                note.path,
                note.title,
                note.is_virtual,
                note.source_file,
                note.entry_date.isoformat() if note.entry_date else None,
            )
            for note in notes
        )

    def candidates(self, target: str, source_path: str | None = None) -> frozenset[str]:
        """Return the best matching identities (possibly ambiguous)."""
        target = _normalise_vault_path(target.strip()).split("^", 1)[0].rstrip("#").strip()
        source_identity = source_path if source_path in self.sources else None
        if source_identity is None and source_path:
            source_candidates = self.path_identities.get(_normalise_vault_path(source_path), set())
            if len(source_candidates) == 1:
                source_identity = next(iter(source_candidates))
        source_file = self.sources.get(source_identity or "")
        if source_file and self.sources.get(source_identity or "") != _normalise_vault_path(
            source_identity or ""
        ) and "#" not in target:
            # Import here because date_collection also constructs Note objects.
            from .date_collection import parse_date_heading

            parsed = parse_date_heading(f"## {target}")
            if parsed is not None:
                local = self.journal_dates.get((source_file, parsed.isoformat()))
                if local is not None:
                    return frozenset((local,))

        if target.startswith("#"):
            if source_file is None:
                return frozenset()
            target = source_file + target

        if path_matches := self.path_identities.get(target):
            return frozenset(path_matches)
        if path_matches := self.path_identities.get(f"{target}.md"):
            return frozenset(path_matches)

        if source_file:
            local_target = posixpath.normpath(
                posixpath.join(posixpath.dirname(source_file), target)
            )
            local_matches = self.forms.get(local_target, set())
            if local_matches:
                return frozenset(local_matches)

        matches = self.forms.get(target, set())
        if matches:
            if source_file and "/" not in target:
                same_directory = {
                    path
                    for path in matches
                    if posixpath.dirname(self.sources[path]) == posixpath.dirname(source_file)
                }
                if same_directory:
                    return frozenset(same_directory)
            return frozenset(matches)

        if "#" in target:
            filename, heading = target.split("#", 1)
            from .date_collection import parse_date_heading

            parsed = parse_date_heading(f"## {heading}")
            if parsed is not None and heading != parsed.isoformat():
                date_matches = self.candidates(f"{filename}#{parsed.isoformat()}", source_path)
                if date_matches:
                    return date_matches
            # An ordinary note remains the target of a section/block link.
            # A split journal has no source Note, so nonexistent entries cannot
            # silently resolve to some other entry with a similar title.
            return self.candidates(filename, source_path) if filename else frozenset()
        return frozenset()

    def resolve(self, target: str, source_path: str | None = None) -> str | None:
        """Return one unambiguous note path, or None."""
        matches = self.candidates(target, source_path)
        return next(iter(matches)) if len(matches) == 1 else None

    def matching_paths(self, target: str) -> frozenset[str]:
        """Return every note that can emit or receive an unscoped reference.

        Graph resolution deliberately gives explicit paths precedence. Security
        boundaries need the broader set: a public path alias must not conceal an
        excluded note that emits the same title.
        """
        raw_target = target
        normalised_target = _normalise_vault_path(raw_target)
        matches = set(self.forms.get(raw_target, set()))
        matches.update(self.forms.get(normalised_target, set()))
        matches.update(self.forms.get(normalised_target.strip(), set()))

        # A boundary must consider both literal titles (which may contain ^ or
        # #) and their interpretation as block/section references. Otherwise a
        # public alias can conceal an excluded note with that exact title.
        target = normalised_target.strip().split("^", 1)[0].rstrip("#").strip()
        matches.update(self.forms.get(target, set()))
        if "#" in target:
            filename, heading = target.split("#", 1)
            from .date_collection import parse_date_heading

            parsed = parse_date_heading(f"## {heading}")
            if parsed is not None and heading != parsed.isoformat():
                normalized = self.forms.get(f"{filename}#{parsed.isoformat()}", set())
                matches.update(normalized)
            if filename:
                matches.update(self.matching_paths(filename))
        return frozenset(matches)


@dataclass(frozen=True)
class Link:
    """A link from one note to another."""

    target: str  # Target note path or title
    display_text: str | None = None  # Optional display text
    is_embed: bool = False  # True if transclusion (![[note]])
    block_ref: str | None = None  # Block reference ID if present


@dataclass(frozen=True)
class Note:
    """Immutable representation of a vault note.

    For date-collection notes (journal files with date headings), virtual entries
    are created with is_virtual=True and paths like "filename.md/YYYY-MM-DD".
    """

    path: str  # Relative path in vault (or virtual path for entries)
    title: str  # Note title
    content: str  # Full markdown content
    links: list[Link]  # Outgoing [[links]]
    tags: list[str]  # #tags found in note
    created: datetime  # File creation time (or entry date for virtuals)
    modified: datetime  # Last modification time

    # Virtual entry fields (for date-collection notes)
    is_virtual: bool = False  # True for entries split from journal files
    source_file: str | None = None  # Original file path (e.g., "Daily Journal.md")
    entry_date: date | None = None  # Date extracted from heading

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

    def link_target_forms(self) -> frozenset[str]:
        """Canonical [[link]] target strings that resolve to this note.

        See the module-level link_target_forms() for the definition.
        """
        return link_target_forms(
            self.path,
            self.title,
            self.source_file if self.is_virtual else None,
            self.entry_date.isoformat() if self.entry_date else None,
        )

    @property
    def link_text(self) -> str:
        """Return the link text for this note (WITHOUT [[...]] brackets).

        Returns the text that should be placed inside Obsidian wikilink brackets.
        For regular notes, this is the title. For virtual notes (journal entries),
        this is a deeplink in the format "filename#heading".

        This allows geists to use note.link_text without needing to know
        whether the note is virtual or not.

        Examples:
            Regular note: "Project Ideas" (use as [[Project Ideas]])
            Virtual note: "Journal#2025-01-15" (use as [[Journal#2025-01-15]])

        Note:
            This is link TEXT, not a complete link - templates/code must add
            the [[...]] brackets. (Formerly named "obsidian_link", which wrongly
            implied it already included brackets.)
        """
        if self.is_virtual and self.source_file:
            # For virtual notes, create deeplink: "filename#heading"
            # Remove .md extension from source file
            filename = _normalise_vault_path(self.source_file).removesuffix(".md")
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
    notes: list[str]  # Referenced note titles
    geist_id: str  # Identifier of creating geist
    title: str | None = None  # Optional suggested note title
