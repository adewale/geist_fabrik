"""Tests for core data models (Note, Link, Suggestion)."""

from datetime import datetime

from geistfabrik.models import Link, Note, Suggestion


class TestNote:
    """Tests for Note hashability and equality."""

    def test_note_is_hashable(self):
        """Test that Note objects can be hashed."""
        note = Note(
            path="test.md",
            title="Test",
            content="Content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        # Should not raise TypeError
        hash_value = hash(note)
        assert isinstance(hash_value, int)

    def test_notes_in_set(self):
        """Test that Notes can be added to sets (the bug that broke before).

        This was failing with 'unhashable type: list' before implementing
        __hash__ and __eq__, because frozen dataclasses with list fields
        are not automatically hashable.
        """
        note1 = Note(
            path="note1.md",
            title="Note 1",
            content="Content 1",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note2 = Note(
            path="note2.md",
            title="Note 2",
            content="Content 2",
            links=[],
            tags=[],
            created=datetime(2023, 1, 2),
            modified=datetime(2023, 1, 2),
        )

        # Should not raise TypeError: unhashable type: 'list'
        notes_set = {note1, note2}
        assert len(notes_set) == 2
        assert note1 in notes_set
        assert note2 in notes_set

    def test_notes_with_same_path_are_equal(self):
        """Test that two Notes with same path are equal even if content differs."""
        note1 = Note(
            path="same.md",
            title="Title 1",
            content="Content 1",
            links=[],
            tags=["tag1"],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note2 = Note(
            path="same.md",
            title="Title 2",  # Different title
            content="Content 2",  # Different content
            links=[Link(target="other.md")],  # Different links
            tags=["tag2"],  # Different tags
            created=datetime(2023, 1, 2),  # Different dates
            modified=datetime(2023, 1, 2),
        )

        # Should be equal because path is the same
        assert note1 == note2
        assert hash(note1) == hash(note2)

    def test_notes_with_different_paths_are_not_equal(self):
        """Test that Notes with different paths are not equal."""
        note1 = Note(
            path="note1.md",
            title="Same Title",
            content="Same Content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note2 = Note(
            path="note2.md",
            title="Same Title",
            content="Same Content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        # Should not be equal because paths differ
        assert note1 != note2

    def test_set_deduplication_works(self):
        """Test that sets properly deduplicate Notes by path.

        This is the actual use case that was breaking in method_scrambler
        and density_inversion geists.
        """
        # Create same note twice with different content
        note_v1 = Note(
            path="note.md",
            title="Version 1",
            content="Content v1",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note_v2 = Note(
            path="note.md",
            title="Version 2",
            content="Content v2",
            links=[],
            tags=["new-tag"],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 2),
        )

        other_note = Note(
            path="other.md",
            title="Other",
            content="Other content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        # Combine duplicates
        all_notes = [note_v1, other_note, note_v2]

        # Deduplicate using set
        unique_notes = list(set(all_notes))

        # Should have only 2 unique notes (note.md appears twice but deduped)
        assert len(unique_notes) == 2

        # Should contain both unique paths
        paths = {n.path for n in unique_notes}
        assert paths == {"note.md", "other.md"}

    def test_notes_as_dict_keys(self):
        """Test that Notes can be used as dictionary keys."""
        note1 = Note(
            path="note1.md",
            title="Note 1",
            content="Content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note2 = Note(
            path="note2.md",
            title="Note 2",
            content="Content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        # Should work as dict keys
        note_metadata = {note1: "metadata1", note2: "metadata2"}

        assert note_metadata[note1] == "metadata1"
        assert note_metadata[note2] == "metadata2"

    def test_note_equality_with_non_note(self):
        """Test that comparing Note with non-Note returns NotImplemented."""
        note = Note(
            path="note.md",
            title="Note",
            content="Content",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        assert note != "note.md"
        assert note != 123
        assert note != None  # noqa: E711

    def test_set_operations_on_notes(self):
        """Test set operations like union, intersection, difference."""
        note1 = Note(
            path="note1.md",
            title="Note 1",
            content="",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note2 = Note(
            path="note2.md",
            title="Note 2",
            content="",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        note3 = Note(
            path="note3.md",
            title="Note 3",
            content="",
            links=[],
            tags=[],
            created=datetime(2023, 1, 1),
            modified=datetime(2023, 1, 1),
        )

        set_a = {note1, note2}
        set_b = {note2, note3}

        # Union
        assert set_a | set_b == {note1, note2, note3}

        # Intersection
        assert set_a & set_b == {note2}

        # Difference
        assert set_a - set_b == {note1}
        assert set_b - set_a == {note3}


class TestLink:
    """Tests for Link model."""

    def test_link_is_hashable(self):
        """Test that Link objects can be hashed (frozen dataclass)."""
        link = Link(target="test.md")
        hash_value = hash(link)
        assert isinstance(hash_value, int)

    def test_links_in_set(self):
        """Test that Links can be added to sets."""
        link1 = Link(target="note1.md")
        link2 = Link(target="note2.md")

        links_set = {link1, link2}
        assert len(links_set) == 2


class TestSuggestion:
    """Tests for Suggestion model."""

    def test_suggestion_creation(self):
        """Test basic Suggestion creation."""
        suggestion = Suggestion(
            text="Test suggestion",
            notes=["Note 1", "Note 2"],
            geist_id="test_geist",
        )

        assert suggestion.text == "Test suggestion"
        assert suggestion.notes == ["Note 1", "Note 2"]
        assert suggestion.geist_id == "test_geist"
        assert suggestion.title is None

    def test_suggestion_with_title(self):
        """Test Suggestion with optional title."""
        suggestion = Suggestion(
            text="Test suggestion",
            notes=["Note 1"],
            geist_id="test_geist",
            title="Suggested Title",
        )

        assert suggestion.title == "Suggested Title"
