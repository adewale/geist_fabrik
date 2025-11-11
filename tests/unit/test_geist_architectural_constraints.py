"""Test architectural constraints for geist implementations.

This test suite enforces key architectural principles that all geists must follow,
preventing regressions and ensuring consistency across the codebase.
"""

import re
from pathlib import Path


def test_geists_use_obsidian_link_not_title() -> None:
    """Enforce that all code geists use note.obsidian_link instead of note.title in wikilinks.

    Architectural Principle:
    All geists must use note.obsidian_link when generating Obsidian wikilinks.
    This ensures virtual notes (journal entries) work correctly.

    Why:
    - Regular notes: obsidian_link returns title (no change)
    - Virtual notes: obsidian_link returns deeplink format "Journal#2025-01-15"
    - Using .title directly breaks virtual notes by generating [[2025-01-15]]
      instead of [[Journal#2025-01-15]]

    This test prevents regressions by scanning all code geists for violations.
    """
    geist_dir = Path("src/geistfabrik/default_geists/code")
    violations = []

    # Pattern 1: f-string with .title inside [[ ]]
    # Matches: f"[[{note.title}]]" or f"[[{n.title}]]"
    pattern1 = re.compile(r'f"[^"]*\[\[{[^}]*\.title}[^\]]*\]\]')

    # Pattern 2: .title inside list comprehension creating wikilinks
    # Matches: [f"[[{n.title}]]" for n in ...]
    pattern2 = re.compile(r'\[f"\[\[{[^}]*\.title}\]\]"\s+for\s+')

    # Pattern 3: String concatenation with .title in wikilinks
    # Matches: "[[" + note.title + "]]"
    pattern3 = re.compile(r'"\[\["\s*\+\s*[^+]*\.title\s*\+\s*"\]\]"')

    for geist_file in sorted(geist_dir.glob("*.py")):
        if geist_file.name == "__init__.py":
            continue

        content = geist_file.read_text()
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            if line.strip().startswith("#"):
                continue

            # Check all patterns
            if pattern1.search(line) or pattern2.search(line) or pattern3.search(line):
                # Check if this line actually has .obsidian_link (might be a false positive)
                if ".obsidian_link" in line:
                    continue

                violations.append(
                    {
                        "file": geist_file.name,
                        "line": line_num,
                        "code": line.strip(),
                    }
                )

    if violations:
        error_msg = [
            "",
            "=" * 80,
            "ARCHITECTURAL CONSTRAINT VIOLATION",
            "=" * 80,
            "",
            "Found geists using .title instead of .obsidian_link in wikilinks.",
            "",
            "Why this matters:",
            "  - Regular notes: obsidian_link returns title (works correctly)",
            "  - Virtual notes: obsidian_link returns 'Journal#2025-01-15' (correct)",
            "  - Using .title for virtual notes generates [[2025-01-15]] (broken)",
            "",
            "Violations found:",
            "",
        ]

        for v in violations:
            error_msg.append(f"  {v['file']}:{v['line']}")
            error_msg.append(f"    {v['code']}")
            error_msg.append("")

        error_msg.extend(
            [
                "How to fix:",
                "  Replace all occurrences of .title in wikilinks with .obsidian_link",
                "",
                "  ❌ WRONG:",
                '    f"[[{note.title}]]"',
                '    notes=[note.title]',
                "",
                "  ✅ CORRECT:",
                '    f"[[{note.obsidian_link}]]"',
                '    notes=[note.obsidian_link]',
                "",
                "See specs/DATE_COLLECTION_NOTES_SPEC.md for architectural details.",
                "=" * 80,
            ]
        )

        raise AssertionError("\n".join(error_msg))


def test_geists_have_proper_type_hints() -> None:
    """Enforce that all code geists have proper type hints on suggest() function.

    Architectural Principle:
    All geist suggest() functions must have proper type hints for maintainability
    and must follow the project's type hint style guide.

    Required signature (per CLAUDE.md):
        def suggest(vault: "VaultContext") -> list["Suggestion"]:

    Style requirements:
        - Use lowercase 'list' (not 'List' from typing)
        - Use quotes for forward references (TYPE_CHECKING pattern)
    """
    geist_dir = Path("src/geistfabrik/default_geists/code")
    violations = []

    # Pattern: def suggest without proper type hints
    suggest_pattern = re.compile(r"^\s*def suggest\([^)]*\)\s*(?:->)?")

    for geist_file in sorted(geist_dir.glob("*.py")):
        if geist_file.name == "__init__.py":
            continue

        content = geist_file.read_text()
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            match = suggest_pattern.match(line)
            if match:
                # Check for proper type hints
                if 'vault: "VaultContext"' not in line:
                    violations.append(
                        {
                            "file": geist_file.name,
                            "line": line_num,
                            "issue": "Missing VaultContext type hint",
                            "code": line.strip(),
                        }
                    )
                # Enforce project standard: list["Suggestion"] (lowercase, quoted)
                elif '-> list["Suggestion"]' not in line:
                    # Detect specific violations for better error messages
                    if 'List[' in line:
                        issue = "Uses 'List' instead of 'list' (violates PEP 585 style)"
                    elif '-> list[Suggestion]' in line:
                        issue = (
                            'Missing quotes around \'Suggestion\' '
                            '(should be list["Suggestion"])'
                        )
                    else:
                        issue = "Missing or incorrect return type hint"

                    violations.append(
                        {
                            "file": geist_file.name,
                            "line": line_num,
                            "issue": issue,
                            "code": line.strip(),
                        }
                    )

    if violations:
        error_msg = [
            "",
            "=" * 80,
            "TYPE HINT VIOLATIONS IN GEISTS",
            "=" * 80,
            "",
            "All geist suggest() functions must follow the project type hint style.",
            "",
            "Required signature (per CLAUDE.md):",
            '    def suggest(vault: "VaultContext") -> list["Suggestion"]:',
            "",
            "Style requirements:",
            "  - Use lowercase 'list' (not 'List' from typing)",
            "  - Use quotes for forward references",
            "",
            "Violations found:",
            "",
        ]

        for v in violations:
            error_msg.append(f"  {v['file']}:{v['line']} - {v['issue']}")
            error_msg.append(f"    {v['code']}")
            error_msg.append("")

        error_msg.append("=" * 80)

        raise AssertionError("\n".join(error_msg))


def test_geists_use_vault_sample_not_random() -> None:
    """Enforce that geists use vault.sample() instead of random.sample().

    Architectural Principle:
    All randomness in geists must use vault.sample() for deterministic behavior.

    Why:
    - vault.sample() uses deterministic random based on session date
    - Same date + same vault = same suggestions (reproducibility)
    - random.sample() is non-deterministic and breaks reproducibility
    """
    geist_dir = Path("src/geistfabrik/default_geists/code")
    violations = []

    # Pattern: import random or from random import
    import_pattern = re.compile(r"^\s*(?:import random|from random import)")

    # Pattern: random.sample() usage
    usage_pattern = re.compile(r"\brandom\.sample\(")

    for geist_file in sorted(geist_dir.glob("*.py")):
        if geist_file.name == "__init__.py":
            continue

        content = geist_file.read_text()
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            if import_pattern.match(line):
                violations.append(
                    {
                        "file": geist_file.name,
                        "line": line_num,
                        "type": "import",
                        "code": line.strip(),
                    }
                )

            if usage_pattern.search(line):
                violations.append(
                    {
                        "file": geist_file.name,
                        "line": line_num,
                        "type": "usage",
                        "code": line.strip(),
                    }
                )

    if violations:
        error_msg = [
            "",
            "=" * 80,
            "DETERMINISTIC RANDOMNESS VIOLATION",
            "=" * 80,
            "",
            "Geists must use vault.sample() instead of random.sample().",
            "",
            "Why:",
            "  - vault.sample() is deterministic (same date = same suggestions)",
            "  - random.sample() is non-deterministic (breaks reproducibility)",
            "",
            "Violations found:",
            "",
        ]

        for v in violations:
            error_msg.append(f"  {v['file']}:{v['line']} - {v['type']}")
            error_msg.append(f"    {v['code']}")
            error_msg.append("")

        error_msg.extend(
            [
                "How to fix:",
                "  ❌ WRONG:",
                "    import random",
                "    sample = random.sample(notes, k=5)",
                "",
                "  ✅ CORRECT:",
                "    sample = vault.sample(notes, k=5)",
                "",
                "=" * 80,
            ]
        )

        raise AssertionError("\n".join(error_msg))
