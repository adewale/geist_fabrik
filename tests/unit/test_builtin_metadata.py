"""Tests for the built-in metadata keys computed by VaultContext.metadata().

Several default geists gate on metadata keys (days_since_modified, staleness,
has_tasks, lexical_diversity, ...) that only an optional examples/ module used
to provide - in a default install those keys were absent, the gates never
opened, and the geists silently produced nothing. The keys are now computed
in VaultContext.metadata() itself, using the SESSION date as "now" so --date
replays stay deterministic. These tests pin the key semantics; the geists
they revived are owned by their own designed-to-trigger tests
(test_temporal_drift.py, test_task_archaeology.py, test_blind_spot_detector.py).
"""

from datetime import timedelta
from pathlib import Path

import pytest

from geistfabrik.metadata_system import MetadataLoader
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import SEED, SESSION_DATE, VaultBuilder


def _build_context(root: Path, notes: dict[str, str], backdate_days: int) -> VaultContext:
    """Vault whose notes were all created/modified backdate_days before the session."""
    builder = VaultBuilder(root)
    stamp = SESSION_DATE - timedelta(days=backdate_days)
    for title, body in notes.items():
        builder.note(title, body, created=stamp, modified=stamp)
    return builder.build()


def _only_metadata(ctx: VaultContext) -> dict[str, object]:
    return ctx.metadata(ctx.notes()[0])


def test_temporal_keys_use_session_date_not_wall_clock(tmp_path: Path) -> None:
    md = _only_metadata(_build_context(tmp_path, {"A": "Some words here."}, backdate_days=100))
    # 100 days before the SESSION date - wall-clock today is irrelevant.
    assert md["days_since_modified"] == 100
    assert md["age_days"] == 100


@pytest.mark.parametrize(("days", "staleness"), [(30, 0.5), (90, 0.75)])
def test_staleness_curve_known_values(tmp_path: Path, days: int, staleness: float) -> None:
    # Asymptotic curve 1 - 1 / (1 + days / 30), the same as the examples module.
    md = _only_metadata(_build_context(tmp_path, {"A": "Text."}, backdate_days=days))
    assert md["staleness"] == pytest.approx(staleness, abs=0.01)


def test_future_modified_clamps_to_zero(tmp_path: Path) -> None:
    # Replaying an old session date must not produce negative ages.
    md = _only_metadata(_build_context(tmp_path, {"A": "Text."}, backdate_days=-50))
    assert md["days_since_modified"] == 0
    assert md["age_days"] == 0
    assert md["staleness"] == 0.0


def test_task_counting(tmp_path: Path) -> None:
    content = "- [ ] open one\n- [x] done one\n* [ ] open two\n+ [X] done two\n- not a task\n"
    md = _only_metadata(_build_context(tmp_path, {"Tasks": content}, backdate_days=10))
    assert md["has_tasks"] is True
    assert md["task_count"] == 4
    assert md["completed_task_count"] == 2


def test_no_tasks(tmp_path: Path) -> None:
    md = _only_metadata(
        _build_context(tmp_path, {"T": "Just prose, no checkboxes."}, backdate_days=10)
    )
    assert md["has_tasks"] is False
    assert md["task_count"] == 0


def test_lexical_diversity_bounds(tmp_path: Path) -> None:
    repetitive = " ".join(["word"] * 50)
    diverse = " ".join(f"unique{i}" for i in range(50))
    ctx = _build_context(tmp_path, {"Rep": repetitive, "Div": diverse}, backdate_days=10)
    by_path = {n.path: ctx.metadata(n) for n in ctx.notes()}
    assert by_path["Rep.md"]["lexical_diversity"] < by_path["Div.md"]["lexical_diversity"]
    for md in by_path.values():
        assert 0.0 < md["lexical_diversity"] <= 1.0


def test_lexical_diversity_is_raw_case_insensitive_ttr(tmp_path: Path) -> None:
    """Public key contract: raw type-token ratio, a float in [0, 1], never None.

    It is not length-corrected: a short stub of distinct words scores 1.0.
    Consumers that read it as vocabulary richness must apply their own
    minimum length (metadata_driven_discovery.MIN_WORDS_FOR_DIVERSITY).
    User plugins compare it with `.get("lexical_diversity", 0) > x`, so
    turning it into None or an unbounded length-corrected score would
    break them silently.
    """
    ctx = _build_context(
        # Tokens: "#", "K", "alpha", "beta", "Alpha", "BETA" -> 4 types / 6.
        tmp_path,
        {"K": "alpha beta Alpha BETA", "S": "quartz lichen harbour"},
        backdate_days=10,
    )
    by_path = {n.path: ctx.metadata(n)["lexical_diversity"] for n in ctx.notes()}
    assert by_path["K.md"] == pytest.approx(4 / 6, abs=1e-3)
    assert by_path["S.md"] == 1.0
    assert all(isinstance(v, float) for v in by_path.values())


def test_root_ttr_known_values(tmp_path: Path) -> None:
    """root_ttr = unique / sqrt(total), case-insensitive, 0.0 for no words.

    Known answers: "# K alpha beta Alpha BETA" has 4 types in 6 tokens, so
    4 / sqrt(6) = 1.633. A stub cannot exceed sqrt(word_count), unlike raw
    TTR, which is 1.0 for any handful of distinct words.
    """
    ctx = _build_context(
        tmp_path,
        {"K": "alpha beta Alpha BETA", "S": "quartz lichen harbour"},
        backdate_days=10,
    )
    by_path = {n.path: ctx.metadata(n) for n in ctx.notes()}
    assert by_path["K.md"]["root_ttr"] == pytest.approx(4 / 6**0.5, abs=1e-3)
    # "# S quartz lichen harbour": 5 distinct tokens.
    assert by_path["S.md"]["lexical_diversity"] == 1.0
    assert by_path["S.md"]["root_ttr"] == pytest.approx(5**0.5, abs=1e-3)


def test_link_density_is_links_per_word(tmp_path: Path) -> None:
    """link_density = len(note.links) / max(1, word_count), as in the spec."""
    ctx = _build_context(
        tmp_path,
        # "# L see [[A]] and [[B]] here": 2 links in 7 tokens.
        {"L": "see [[A]] and [[B]] here", "N": "no links at all"},
        backdate_days=10,
    )
    by_path = {n.path: ctx.metadata(n) for n in ctx.notes()}
    assert by_path["L.md"]["link_density"] == pytest.approx(2 / 7, abs=1e-6)
    assert by_path["N.md"]["link_density"] == 0.0


def test_user_modules_can_still_override(tmp_path: Path) -> None:
    """A user inference module runs after the builtins, so its keys win."""
    modules = tmp_path / "metadata_inference"
    modules.mkdir()
    (modules / "pinned_staleness.py").write_text(
        "def infer(note, vault):\n    return {'staleness': 0.123}\n"
    )
    loader = MetadataLoader(modules)
    loader.load_modules()
    built = _build_context(tmp_path / "vault", {"A": "Text."}, backdate_days=300)
    ctx = VaultContext(built.vault, built.session, seed=SEED, metadata_loader=loader)

    md = _only_metadata(ctx)

    assert md["staleness"] == 0.123
    assert md["days_since_modified"] == 300  # builtins still present alongside
