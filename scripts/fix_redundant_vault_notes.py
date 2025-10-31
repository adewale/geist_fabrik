#!/usr/bin/env python3
"""Fix redundant vault.notes() calls across all geists.

This script automatically refactors patterns like:
    vault.sample(vault.notes(), min(5, len(vault.notes())))
To:
    all_notes = vault.notes()
    vault.sample(all_notes, min(5, len(all_notes)))
"""

import re
from pathlib import Path
from typing import List, Tuple


def find_redundant_patterns(content: str) -> List[Tuple[str, str]]:
    """Find redundant vault.notes() patterns and generate fixes.

    Returns:
        List of (old_pattern, new_pattern) tuples
    """
    fixes = []

    # Pattern 1: vault.sample(vault.notes(), min(X, len(vault.notes())))
    pattern1 = re.compile(
        r"(\s+)(\w+\s*=\s*)?vault\.sample\(vault\.notes\(\),\s*min\(\d+,\s*len\(vault\.notes\(\)\)\)\)"
    )

    for match in pattern1.finditer(content):
        old_line = match.group(0)
        indent = match.group(1)
        var_assign = match.group(2) or ""

        # Extract the number from min(X, ...)
        num_match = re.search(r"min\((\d+),", old_line)
        if num_match:
            num = num_match.group(1)

            new_lines = (
                f"{indent}all_notes = vault.notes()\n"
                f"{indent}{var_assign}vault.sample(all_notes, min({num}, len(all_notes)))"
            )

            fixes.append((old_line, new_lines))

    # Pattern 2: for note in vault.sample(vault.notes(), X): where X appears later
    pattern2 = re.compile(
        r"(\s+)for\s+\w+\s+in\s+vault\.sample\(vault\.notes\(\),\s*min\(\d+,\s*len\(vault\.notes\(\)\)\)\):"
    )

    for match in pattern2.finditer(content):
        old_line = match.group(0)
        indent = match.group(1)

        # Extract variable name and number
        var_match = re.search(r"for\s+(\w+)\s+in", old_line)
        num_match = re.search(r"min\((\d+),", old_line)

        if var_match and num_match:
            var_name = var_match.group(1)
            num = num_match.group(1)

            new_lines = (
                f"{indent}all_notes = vault.notes()\n"
                f"{indent}for {var_name} in vault.sample(all_notes, min({num}, len(all_notes))):"
            )

            fixes.append((old_line, new_lines))

    return fixes


def fix_file(file_path: Path) -> bool:
    """Fix redundant vault.notes() calls in a file.

    Returns:
        True if file was modified, False otherwise
    """
    content = file_path.read_text()
    original_content = content

    fixes = find_redundant_patterns(content)

    if not fixes:
        return False

    # Apply fixes
    for old_pattern, new_pattern in fixes:
        content = content.replace(old_pattern, new_pattern, 1)

    if content != original_content:
        file_path.write_text(content)
        return True

    return False


def main():
    """Main entry point."""
    base_dir = Path(__file__).parent.parent
    geists_dir = base_dir / "src" / "geistfabrik" / "default_geists" / "code"

    print("=" * 70)
    print("FIXING REDUNDANT vault.notes() CALLS")
    print("=" * 70)
    print()

    if not geists_dir.exists():
        print(f"Error: {geists_dir} does not exist")
        return 1

    python_files = sorted(geists_dir.glob("*.py"))

    fixed_files = []
    skipped_files = []

    for file_path in python_files:
        if file_path.name.startswith("_"):
            continue

        print(f"Checking {file_path.name}...", end=" ")

        if fix_file(file_path):
            print("✅ FIXED")
            fixed_files.append(file_path.name)
        else:
            print("⏭️  No changes needed")
            skipped_files.append(file_path.name)

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Files checked: {len(python_files)}")
    print(f"Files fixed: {len(fixed_files)}")
    print(f"Files skipped: {len(skipped_files)}")

    if fixed_files:
        print()
        print("Fixed files:")
        for name in fixed_files:
            print(f"  - {name}")

    return 0


if __name__ == "__main__":
    exit(main())
