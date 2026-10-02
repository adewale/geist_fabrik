"""Known-answer tests for VaultContext.hubs() (OP-8: canonical link graph + batch loading).

hubs(count) ranks notes by the number of distinct notes linking to them,
resolving every link form the graph accepts, and omits notes nobody links to.
"""

from pathlib import Path

import pytest

from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder


def _context(root: Path, files: dict[str, str]) -> VaultContext:
    root.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / name).write_text(text)
    return VaultBuilder(root).build()


def _hub_files() -> dict[str, str]:
    """Ten notes link to Hub through four link forms.

    Secondary Hub has three backlinks and note_0 one (from Isolated).
    """
    forms = ["[[hub]]"] * 4 + ["[[hub.md]]"] * 2 + ["[[Hub]]"] * 2 + ["[[hub|the hub]]"] * 2
    files = {
        "hub.md": "# Hub\n\nThis is a central hub note.",
        "secondary_hub.md": "# Secondary Hub\n\nLinked by fewer notes.",
        "isolated.md": "# Isolated\n\n[[note_0]]",
    }
    for i, form in enumerate(forms):
        extra = "\n[[secondary_hub]]" if i < 3 else ""
        files[f"note_{i}.md"] = f"# Note {i}\n\nThis note links to {form}.{extra}"
    return files


@pytest.fixture
def context_with_hubs(tmp_path: Path) -> VaultContext:
    return _context(tmp_path / "vault", _hub_files())


def test_hubs_rank_by_distinct_linking_notes_across_link_forms(
    context_with_hubs: VaultContext,
) -> None:
    hubs = context_with_hubs.hubs(count=3)

    assert [h.path for h in hubs] == ["hub.md", "secondary_hub.md", "note_0.md"]
    assert [len(context_with_hubs.backlinks(h)) for h in hubs] == [10, 3, 1]


def test_hubs_count_takes_a_prefix_and_omits_unlinked_notes(
    context_with_hubs: VaultContext,
) -> None:
    assert [h.path for h in context_with_hubs.hubs(count=1)] == ["hub.md"]
    # Only three notes have any backlinks, so a larger count cannot pad the list.
    assert [h.path for h in context_with_hubs.hubs(count=100)] == [
        "hub.md",
        "secondary_hub.md",
        "note_0.md",
    ]


def test_hubs_handles_vault_without_links(tmp_path: Path) -> None:
    context = _context(
        tmp_path, {"note1.md": "# Note 1\n\nNo links here.", "note2.md": "# Note 2\n\nNone."}
    )
    assert context.hubs(count=5) == []


def test_a_self_link_is_not_a_backlink(tmp_path: Path) -> None:
    """Contract: a link from a note to itself is not a connection.

    Regression: self-links ("[[#Section]]" anchors, or a note naming its own
    title) made a note its own backlink, so notes with one self-link and no
    real backlinks filled hubs() and were called "central to your vault".
    """
    files = {
        "self_linker.md": "# Self Linker\n\nI link to [[self_linker]] and [[#Intro]].",
        "loner.md": "# Loner\n\nSee [[loner]] and [[#Notes]].",
    }
    files.update({f"note_{i}.md": f"# Note {i}\n\n[[self_linker]]" for i in range(3)})
    context = _context(tmp_path, files)

    [hub] = context.hubs(count=5)
    assert hub.title == "Self Linker"
    assert sorted(n.title for n in context.backlinks(hub)) == ["Note 0", "Note 1", "Note 2"]
    assert context.outgoing_links(hub) == []
    loner = next(n for n in context.notes() if n.title == "Loner")
    assert context.backlinks(loner) == []
    assert loner in context.orphans()


def test_hubs_counts_a_repeated_link_once(tmp_path: Path) -> None:
    context = _context(
        tmp_path,
        {
            "target.md": "# Target\n\nTarget note.",
            "source.md": "# Source\n\n[[target]] and [[target]] and [[target]]",
        },
    )

    hubs = context.hubs(count=5)

    assert [h.title for h in hubs] == ["Target"]
    assert len(context.backlinks(hubs[0])) == 1


@pytest.mark.benchmark
def test_hubs_performance(context_with_hubs: VaultContext) -> None:
    """Benchmark hubs() (run with: pytest -m benchmark -v -s)."""
    import time

    trials = 50
    times = []
    for _ in range(trials):
        start = time.perf_counter()
        _ = context_with_hubs.hubs(count=5)
        times.append(time.perf_counter() - start)

    avg_time = sum(times) / trials
    print(f"\nhubs(5) over {len(context_with_hubs.notes())} notes: {avg_time * 1000:.3f}ms avg")
    assert avg_time < 0.010, f"Hubs should be fast (got {avg_time * 1000:.1f}ms)"
