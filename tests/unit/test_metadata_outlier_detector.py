"""The metadata_outlier_detector extension example (examples/geists/code/).

It is not a bundled geist; this test keeps its MetadataAnalyser demo working
(distribution() for the median, z-score outliers on log word count), loading
it from examples/ the way a user would copy it into a vault.

One 203-word note among eleven 13-word notes has |z| = sqrt(11) = 3.3 > 2.
"""

import importlib.util
from pathlib import Path
from types import ModuleType

from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions

EXAMPLE = (
    Path(__file__).parents[2] / "examples" / "geists" / "code" / "metadata_outlier_detector.py"
)
SHORT = "plain words about ordinary things here and there again today"  # 10 words
LONG = " ".join(f"word{i}" for i in range(200))


def _load_example() -> ModuleType:
    spec = importlib.util.spec_from_file_location("metadata_outlier_detector_example", EXAMPLE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_example_names_an_unusually_long_note_against_the_median(tmp_path: Path) -> None:
    """Contract: the example, loaded from examples/, reports a word-count
    outlier with the median from MetadataAnalyser.distribution().

    Regression: moving the geist out of the bundle must not leave a broken
    example (a stale import or a MetadataAnalyser API drift).
    """
    builder = VaultBuilder(tmp_path)
    for i in range(11):
        builder.note(f"Note {chr(65 + i)}", SHORT)
    builder.note("Long Treatise", LONG)

    suggestions = _load_example().suggest(builder.build())

    assert_valid_suggestions(
        suggestions, "metadata_outlier_detector", must_reference=["Long Treatise"]
    )
    assert [(s.text, s.notes) for s in suggestions] == [
        (
            "[[Long Treatise]] is unusually detailed (203 words vs median 13). "
            "Does this depth signal importance?",
            ["Long Treatise"],
        )
    ]
