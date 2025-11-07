"""Metadata-Driven Discovery - Find unexpected patterns in note properties.

This geist creates surprising combinations by finding notes that share
uncommon metadata characteristics. It reveals hidden patterns in how
you think and organize information.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext

from geistfabrik import Suggestion


def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Find unexpected note groupings based on metadata patterns.

    Args:
        vault: VaultContext with access to vault data

    Returns:
        List of suggestions about metadata-driven discoveries
    """
    suggestions = []

    # Pattern 1: High complexity but low connectivity (understood but not connected)
    high_complexity_isolated = _find_complex_but_isolated(vault)
    if len(high_complexity_isolated) >= 3:
        note_titles = [n.obsidian_link for n in high_complexity_isolated[:3]]
        text = (
            "What do these have in common?\n"
            + "\n".join(f"- [[{title}]]" for title in note_titles)
            + "\n\nThey're all complex topics with few connections. "
            + "You understand them but haven't linked them to your other thinking. "
            + "What pattern does this reveal?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=note_titles,
                geist_id="metadata_driven_discovery",
            )
        )

    # Pattern 2: Old notes with high lexical diversity (buried gems)
    buried_gems = _find_buried_gems(vault)
    if len(buried_gems) >= 2:
        note_titles = [n.obsidian_link for n in buried_gems[:2]]
        text = (
            "These notes have high lexical diversity but haven't been touched in months:\n"
            + "\n".join(f"- [[{title}]]" for title in note_titles)
            + "\n\nThey might contain rich language and ideas that are gathering dust. "
            + "Worth revisiting?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=note_titles,
                geist_id="metadata_driven_discovery",
            )
        )

    # Pattern 3: Task-heavy but no recent updates (abandoned projects)
    abandoned_projects = _find_abandoned_task_notes(vault)
    if len(abandoned_projects) >= 2:
        note_titles = [n.obsidian_link for n in abandoned_projects[:2]]
        incomplete_counts = [_get_incomplete_task_count(vault, n) for n in abandoned_projects[:2]]

        text = (
            "These notes have incomplete tasks but haven't been updated recently:\n"
            + "\n".join(
                f"- [[{title}]] ({count} incomplete tasks)"
                for title, count in zip(note_titles, incomplete_counts)
            )
            + "\n\nTime to revive them or archive them?"
        )

        suggestions.append(
            Suggestion(
                text=text,
                notes=note_titles,
                geist_id="metadata_driven_discovery",
            )
        )

    # Sample suggestions to avoid overwhelming
    return vault.sample(suggestions, min(2, len(suggestions)))


def _find_complex_but_isolated(vault: "VaultContext") -> list["Note"]:
    """Find notes with high complexity but low connectivity."""
    complex_isolated = []

    all_notes = vault.notes()
    for note in all_notes:
        metadata = vault.metadata(note)

        # High complexity (high lexical diversity or long reading time)
        lexical_diversity = metadata.get("lexical_diversity", 0)
        reading_time = metadata.get("reading_time", 0)

        # Low connectivity
        backlink_count = len(vault.backlinks(note))
        link_count = len(note.links)

        if (lexical_diversity > 0.5 or reading_time > 3) and (backlink_count + link_count < 2):
            complex_isolated.append(note)

    return complex_isolated


def _find_buried_gems(vault: "VaultContext") -> list["Note"]:
    """Find old notes with high lexical diversity."""
    gems = []

    all_notes = vault.notes()
    for note in all_notes:
        metadata = vault.metadata(note)

        lexical_diversity = metadata.get("lexical_diversity", 0)
        days_since_modified = metadata.get("days_since_modified", 0)

        # High diversity + old = buried gem
        if lexical_diversity > 0.6 and days_since_modified > 90:
            gems.append(note)

    return gems


def _find_abandoned_task_notes(vault: "VaultContext") -> list["Note"]:
    """Find notes with incomplete tasks that are stale."""
    abandoned = []

    all_notes = vault.notes()
    for note in all_notes:
        metadata = vault.metadata(note)

        has_tasks = metadata.get("has_tasks", False)
        task_count = metadata.get("task_count", 0)
        completed = metadata.get("completed_task_count", 0)
        days_since_modified = metadata.get("days_since_modified", 0)

        # Has tasks, some incomplete, and old
        if has_tasks and task_count > completed and days_since_modified > 60:
            abandoned.append(note)

    return abandoned


def _get_incomplete_task_count(vault: "VaultContext", note: "Note") -> int:
    """Get count of incomplete tasks in a note."""
    metadata = vault.metadata(note)
    total = int(metadata.get("task_count", 0))
    completed = int(metadata.get("completed_task_count", 0))
    return total - completed
