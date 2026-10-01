"""Tests for the metadata_outlier_detector geist.

Trigger: >= 10 user notes and a note whose ``word_count`` (built-in metadata)
or ``link_density`` (supplied by a user metadata module, as in the spec's
metadata-inference example) is more than 2.0 population standard deviations
from the vault mean. At most one suggestion per metric: 2 in total.

Z-score arithmetic: if k of n notes share one value and the rest share
another, each of the k notes has |z| = sqrt((n - k) / k). One long note among
12 gives sqrt(11) = 3.3 > 2; two among 12 give sqrt(5) = 2.24 > 2; three among
12 give sqrt(3) = 1.73 < 2, whatever the word counts are.

Every title has two words, so the "# <title>" heading adds the same three
words to each count: a SHORT note has 13 words, a LONG one 203.
"""

from pathlib import Path

import pytest

from geistfabrik.default_geists.code import metadata_outlier_detector
from geistfabrik.metadata_system import MetadataLoader
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SEED, VaultBuilder, assert_valid_suggestions

SHORT = "plain words about ordinary things here and there again today"  # 10 words
LONG = " ".join(f"word{i}" for i in range(200))
LINKS = " ".join(f"[[Target {i}]]" for i in range(5))  # 10 words, 5 links

LINK_DENSITY_MODULE = """
def infer(note, vault):
    return {"link_density": len(note.links) / max(1, len(note.content.split()))}
"""


def _vault(
    root: Path,
    bodies: dict[str, str],
    *,
    journal: dict[str, str] | None = None,
    link_density_module: bool = False,
) -> VaultContext:
    builder = VaultBuilder(root / "vault")
    for title, body in bodies.items():
        builder.note(title, body)
    for title, body in (journal or {}).items():
        builder.journal(title, body)
    ctx = builder.build()
    if not link_density_module:
        return ctx
    module_dir = root / "metadata_inference"
    module_dir.mkdir()
    (module_dir / "link_density.py").write_text(LINK_DENSITY_MODULE)
    loader = MetadataLoader(module_dir)
    loader.load_modules()
    return VaultContext(ctx.vault, ctx.session, seed=SEED, metadata_loader=loader)


def _plain(count: int, body: str = SHORT) -> dict[str, str]:
    return {f"Note {chr(65 + i)}": body for i in range(count)}


def test_metadata_outlier_detector_names_an_unusually_long_note(tmp_path):
    ctx = _vault(tmp_path, {**_plain(11), "Long Treatise": LONG})

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(
        suggestions, "metadata_outlier_detector", must_reference=["Long Treatise"]
    )
    assert [s.notes for s in suggestions] == [["Long Treatise"]]
    assert suggestions[0].text == (
        "[[Long Treatise]] is unusually detailed (203 words vs median 13). "
        "Does this depth signal importance?"
    )


def test_metadata_outlier_detector_names_an_unusually_short_note(tmp_path):
    """The other side of the median: one 4-word note among 203-word notes."""
    ctx = _vault(tmp_path, {**_plain(11, LONG), "Tiny Stub": "tiny"})

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(suggestions, "metadata_outlier_detector", must_reference=["Tiny Stub"])
    assert suggestions[0].text.startswith(
        "[[Tiny Stub]] is unusually brief (4 words vs median 203)."
    )


def test_metadata_outlier_detector_z_score_threshold(tmp_path):
    """Boundary pair on 2.0 standard deviations: in 12 notes, two long notes
    sit at z = 2.24 (reported); three sit at z = 1.73 (not)."""
    two = _vault(tmp_path / "two", {**_plain(10), "Long 1": LONG, "Long 2": LONG})
    three = _vault(tmp_path / "three", {**_plain(9), **{f"Long {i}": LONG for i in range(3)}})

    assert metadata_outlier_detector.suggest(three) == []
    assert_valid_suggestions(
        metadata_outlier_detector.suggest(two),
        "metadata_outlier_detector",
        must_reference=["Long"],
    )


def test_metadata_outlier_detector_needs_ten_notes(tmp_path):
    """Boundary pair: one long note among 9 notes is ignored (z = 2.83 would
    qualify), among 10 notes (z = 3.0) it is reported."""
    nine = _vault(tmp_path / "nine", {**_plain(8), "Long Treatise": LONG})
    ten = _vault(tmp_path / "ten", {**_plain(9), "Long Treatise": LONG})

    assert metadata_outlier_detector.suggest(nine) == []
    assert_valid_suggestions(
        metadata_outlier_detector.suggest(ten),
        "metadata_outlier_detector",
        must_reference=["Long Treatise"],
    )


@pytest.mark.parametrize(
    ("bodies", "outlier", "text"),
    [
        ({**_plain(11), "Busy Hub": LINKS}, "Busy Hub", "exceptionally high link density (0.38)"),
        (
            {**_plain(11, LINKS), "Lone Island": SHORT},
            "Lone Island",
            "exceptionally low link density (0.00)",
        ),
    ],
    ids=["high", "low"],
)
def test_metadata_outlier_detector_link_density_from_a_metadata_module(
    tmp_path, bodies, outlier, text
):
    """link_density is not built-in metadata; a user module supplies it
    (5 links / 13 words = 0.38). All word counts are equal (13), so only the
    link-density branch can fire."""
    ctx = _vault(tmp_path, bodies, link_density_module=True)

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(suggestions, "metadata_outlier_detector", must_reference=[outlier])
    assert [s.notes for s in suggestions] == [[outlier]]
    assert text in suggestions[0].text


def test_metadata_outlier_detector_caps_at_two(tmp_path):
    """Cap: two word-count outliers and one link-density outlier (three
    candidates) yield exactly two suggestions, one per metric."""
    ctx = _vault(
        tmp_path,
        {**_plain(10), "Long 1": LONG, "Long 2": LONG, "Busy Hub": LINKS},
        link_density_module=True,
    )

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert len(suggestions) == 2
    assert_valid_suggestions(suggestions, "metadata_outlier_detector", must_reference=["Busy Hub"])
    assert "unusually detailed" in suggestions[0].text
    assert suggestions[0].notes[0] in {"Long 1", "Long 2"}
    assert suggestions[1].notes == ["Busy Hub"]


def test_metadata_outlier_detector_excludes_geist_journal(tmp_path):
    """Both directions: a session note far longer than anything else is
    neither named nor counted in the statistics; the user's long note is."""
    ctx = _vault(
        tmp_path,
        {**_plain(11), "Long Treatise": LONG},
        journal={"2024-03-14": " ".join(["session"] * 5000)},
    )

    suggestions = metadata_outlier_detector.suggest(ctx)

    assert_valid_suggestions(
        suggestions,
        "metadata_outlier_detector",
        must_reference=["Long Treatise"],
        must_not_reference=["geist journal", "2024-03-14"],
    )
