"""Prevention test: internal doc links must resolve.

Several specs/docs referenced files that were never written
(docs/CONFIGURATION.md, docs/TROUBLESHOOTING.md, ...). This test walks the
top-level docs and asserts every relative markdown link and `docs/...` /
`specs/...` reference points at a file that exists - so a dead link fails CI
instead of rotting silently.

Scope: every checked-in Markdown document under the repository root, docs/,
examples/, and specs/. Historical documents remain useful navigation records;
their relative links must resolve even when their claims are explicitly dated.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

DOC_FILES = sorted(
    [
        *REPO.glob("*.md"),
        *REPO.glob("docs/**/*.md"),
        *REPO.glob("examples/**/*.md"),
        *REPO.glob("specs/**/*.md"),
    ]
)
MAINTAINED_BARE_PATH_DOCS = {
    REPO / "README.md",
    REPO / "CLAUDE.md",
    REPO / "CONTRIBUTING.md",
    REPO / "TODO.md",
    REPO / "docs" / "ARCHITECTURE.md",
    REPO / "docs" / "GEIST_CATALOG.md",
    REPO / "docs" / "WRITING_GOOD_GEISTS.md",
}

# Markdown link target, e.g. [text](path) - capture the path.
MD_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
# Bare repo-path mentions in prose/backticks, e.g. docs/FOO.md or specs/BAR.md.
BARE_PATH = re.compile(r"`?((?:docs|specs)/[A-Za-z0-9_./-]+\.md)`?")


def _resolve(base: Path, target: str) -> Path | None:
    target = target.split("#", 1)[0].strip()  # drop anchors
    if not target or target.startswith(("http://", "https://", "mailto:")):
        return None
    if not target.lower().endswith(".md"):
        return None
    if target.startswith("/"):
        return REPO / target.lstrip("/")
    # Bare repo-rooted mentions (docs/..., specs/...) resolve from the repo root,
    # not the referring file's directory.
    if target.startswith(("docs/", "specs/")):
        return REPO / target
    return (base.parent / target).resolve()


def _broken_links() -> list[str]:
    broken = []
    for doc in DOC_FILES:
        if not doc.exists():
            continue
        text = doc.read_text()
        candidates = set(MD_LINK.findall(text))
        if doc in MAINTAINED_BARE_PATH_DOCS:
            candidates |= set(BARE_PATH.findall(text))
        for target in candidates:
            resolved = _resolve(doc, target)
            if resolved is None:
                continue
            if not resolved.exists():
                broken.append(f"{doc.relative_to(REPO)} -> {target}")
    return sorted(set(broken))


def test_no_dead_internal_doc_links():
    broken = _broken_links()
    assert not broken, (
        "Dead internal doc links (create the file or fix the reference):\n" + "\n".join(broken)
    )
