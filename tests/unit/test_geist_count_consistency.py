"""Test that documentation geist counts match reality.

This test ensures that geist counts in documentation files stay synchronised
with the actual number of default geists bundled with GeistFabrik.

Single source of truth: src/geistfabrik/default_geists/__init__.py
"""

import re
from pathlib import Path

import geistfabrik
from geistfabrik.default_geists import (
    CODE_GEIST_COUNT,
    TOTAL_GEIST_COUNT,
    TRACERY_GEIST_COUNT,
)


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


def test_early_adopters_version_and_geist_counts():
    """Verify the early-adopter guide cannot drift from runtime constants."""
    guide_path = Path(__file__).parent.parent.parent / "README_EARLY_ADOPTERS.md"
    content = guide_path.read_text()
    count_pattern = (
        rf"\b{TOTAL_GEIST_COUNT}\s+default\s+geists\s+bundled\s*\(\s*"
        rf"{CODE_GEIST_COUNT}\s+code\s*\+\s*{TRACERY_GEIST_COUNT}\s+Tracery\s*\)"
    )

    assert f"v{geistfabrik.__version__} Beta" in content
    assert re.search(count_pattern, content, re.IGNORECASE)


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
