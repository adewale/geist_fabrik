"""Document structure metadata inference module.

Infers structural properties like headings, lists, code blocks, etc.
"""

import re
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext


def infer(note: "Note", vault: "VaultContext") -> Dict[str, Any]:
    """Infer structural metadata for a note.

    Args:
        note: Note to analyse
        vault: VaultContext for accessing vault data

    Returns:
        Dictionary with structure metrics:
        - heading_count: Number of headings
        - has_tasks: True if note contains task checkboxes
        - task_count: Number of tasks
        - completed_task_count: Number of completed tasks
        - code_block_count: Number of code blocks
        - has_frontmatter: True if note has YAML frontmatter
        - list_item_count: Number of list items
    """
    content = note.content

    # Count headings
    heading_count = len(re.findall(r"^#{1,6}\s+", content, re.MULTILINE))

    # Count tasks
    task_pattern = r"- \[[ xX]\]"
    task_matches = re.findall(task_pattern, content)
    task_count = len(task_matches)
    completed_task_count = sum(1 for m in task_matches if m in ["- [x]", "- [X]"])
    has_tasks = task_count > 0

    # Count code blocks
    code_block_count = content.count("```") // 2

    # Check for frontmatter
    has_frontmatter = content.startswith("---\n")

    # Count list items (both ordered and unordered)
    list_item_count = len(re.findall(r"^[\s]*[-*+]\s+", content, re.MULTILINE))
    list_item_count += len(re.findall(r"^[\s]*\d+\.\s+", content, re.MULTILINE))

    return {
        "heading_count": heading_count,
        "has_tasks": has_tasks,
        "task_count": task_count,
        "completed_task_count": completed_task_count,
        "code_block_count": code_block_count,
        "has_frontmatter": has_frontmatter,
        "list_item_count": list_item_count,
    }
