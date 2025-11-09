"""Test that documentation geist counts match reality.

This test ensures that geist counts in documentation files stay synchronized
with the actual number of default geists bundled with GeistFabrik.

Single source of truth: src/geistfabrik/default_geists/__init__.py
"""

import re
from pathlib import Path

from geistfabrik.default_geists import (
    CODE_GEIST_COUNT,
    TOTAL_GEIST_COUNT,
    TRACERY_GEIST_COUNT,
)


def test_geist_counts_are_correct():
    """Verify constants match actual file counts."""
    # Verify programmatic counts are internally consistent
    assert CODE_GEIST_COUNT + TRACERY_GEIST_COUNT == TOTAL_GEIST_COUNT, (
        "Code + Tracery should equal Total"
    )
    # Verify counts are positive
    assert CODE_GEIST_COUNT > 0, "Should have at least one code geist"
    assert TRACERY_GEIST_COUNT > 0, "Should have at least one Tracery geist"
    assert TOTAL_GEIST_COUNT > 0, "Should have at least one total geist"


def test_readme_geist_counts():
    """Verify README.md mentions correct geist counts."""
    readme_path = Path(__file__).parent.parent.parent / "README.md"
    content = readme_path.read_text()

    # Check for "49 (40 code + 9 Tracery)" pattern
    pattern = (
        rf"\b{TOTAL_GEIST_COUNT}\s*\(\s*{CODE_GEIST_COUNT}\s+code"
        rf"\s*\+\s*{TRACERY_GEIST_COUNT}\s+Tracery\s*\)"
    )

    matches = re.findall(pattern, content, re.IGNORECASE)

    error_msg = (
        f"README.md should mention '{TOTAL_GEIST_COUNT} "
        f"({CODE_GEIST_COUNT} code + {TRACERY_GEIST_COUNT} Tracery)' "
        f"at least once. Current counts: {CODE_GEIST_COUNT} code, "
        f"{TRACERY_GEIST_COUNT} Tracery, {TOTAL_GEIST_COUNT} total"
    )
    assert len(matches) > 0, error_msg


def test_claude_md_geist_counts():
    """Verify CLAUDE.md mentions correct geist counts."""
    claude_md_path = Path(__file__).parent.parent.parent / "CLAUDE.md"
    content = claude_md_path.read_text()

    # Check for "49 bundled geists (40 code, 9 Tracery)" pattern
    pattern = (
        rf"\b{TOTAL_GEIST_COUNT}\s+bundled\s+geists\s*\(\s*{CODE_GEIST_COUNT}"
        rf"\s+code,\s*{TRACERY_GEIST_COUNT}\s+Tracery\s*\)"
    )

    matches = re.findall(pattern, content, re.IGNORECASE)

    error_msg = (
        f"CLAUDE.md should mention '{TOTAL_GEIST_COUNT} bundled geists "
        f"({CODE_GEIST_COUNT} code, {TRACERY_GEIST_COUNT} Tracery)' "
        f"at least once. Current counts: {CODE_GEIST_COUNT} code, "
        f"{TRACERY_GEIST_COUNT} Tracery, {TOTAL_GEIST_COUNT} total"
    )
    assert len(matches) > 0, error_msg


def test_no_outdated_geist_counts_in_main_docs():
    """Ensure README.md and CLAUDE.md don't mention outdated counts."""
    readme_path = Path(__file__).parent.parent.parent / "README.md"
    claude_md_path = Path(__file__).parent.parent.parent / "CLAUDE.md"

    # Common outdated counts (when we had 38 code geists)
    outdated_patterns = [
        r"\b47\s+geists?\s*\(.*38.*code",
        r"\b38\s+code.*geists",
        r"\(38\s+code\s*\+\s*9\s+Tracery\)",
    ]

    for doc_path in [readme_path, claude_md_path]:
        content = doc_path.read_text()

        for pattern in outdated_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            error_msg = (
                f"{doc_path.name} contains outdated geist count pattern "
                f"'{pattern}'. Update to use current counts: "
                f"{CODE_GEIST_COUNT} code, {TRACERY_GEIST_COUNT} Tracery, "
                f"{TOTAL_GEIST_COUNT} total"
            )
            assert len(matches) == 0, error_msg
