"""Tests for built-in metadata keys and the geists they revive.

Several default geists gate on metadata keys (days_since_modified, staleness,
has_tasks, lexical_diversity, ...) that only an optional examples/ module used
to provide - in a default install those keys were absent, the gates never
opened, and the geists silently produced nothing. The keys are now computed
in VaultContext.metadata() itself, using the SESSION date as "now" so --date
replays stay deterministic. These tests pin the key semantics and assert the
revived geists actually fire on fixtures designed to trigger them.
"""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from geistfabrik import Session, Vault
from geistfabrik.function_registry import _GLOBAL_REGISTRY, FunctionRegistry
from geistfabrik.vault_context import VaultContext

SESSION_DATE = datetime(2024, 3, 15, 10, 0)


@pytest.fixture(autouse=True)
def clear_global_registry():
    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def _build_context(notes: dict[str, str], backdate_days: int) -> VaultContext:
    """Vault whose notes were all created/modified backdate_days before the session."""
    # Builtins register into the module-level _GLOBAL_REGISTRY; clear it so a
    # test can build more than one context.
    _GLOBAL_REGISTRY.clear()
    tmpdir = TemporaryDirectory()
    vault_path = Path(tmpdir.name)
    for name, content in notes.items():
        (vault_path / name).write_text(content)

    vault = Vault(str(vault_path), ":memory:")
    vault.sync()

    old = SESSION_DATE - timedelta(days=backdate_days)
    vault.db.execute(
        "UPDATE notes SET created = ?, modified = ?", (old.isoformat(), old.isoformat())
    )
    vault.db.commit()

    session = Session(SESSION_DATE, vault.db)
    session.compute_embeddings(vault.all_notes())
    ctx = VaultContext(vault, session, seed=20240315, function_registry=FunctionRegistry())
    ctx._tmpdir = tmpdir  # type: ignore[attr-defined]  # keep tempdir alive
    return ctx


class TestBuiltinMetadataKeys:
    def test_temporal_keys_use_session_date_not_wall_clock(self):
        ctx = _build_context({"a.md": "# A\nSome words here."}, backdate_days=100)
        md = ctx.metadata(ctx.notes()[0])
        # 100 days before the SESSION date - wall-clock today is irrelevant.
        assert md["days_since_modified"] == 100
        assert md["age_days"] == 100

    def test_staleness_curve_known_values(self):
        # Asymptotic curve: 30d = 0.5, 90d = 0.75 (same as the examples module).
        ctx30 = _build_context({"a.md": "# A\nText."}, backdate_days=30)
        assert ctx30.metadata(ctx30.notes()[0])["staleness"] == pytest.approx(0.5, abs=0.01)
        ctx90 = _build_context({"a.md": "# A\nText."}, backdate_days=90)
        assert ctx90.metadata(ctx90.notes()[0])["staleness"] == pytest.approx(0.75, abs=0.01)

    def test_future_modified_clamps_to_zero(self):
        # Replaying an old session date must not produce negative ages.
        ctx = _build_context({"a.md": "# A\nText."}, backdate_days=-50)
        md = ctx.metadata(ctx.notes()[0])
        assert md["days_since_modified"] == 0
        assert md["age_days"] == 0
        assert md["staleness"] == 0.0

    def test_task_counting(self):
        content = (
            "# Tasks\n"
            "- [ ] open one\n"
            "- [x] done one\n"
            "* [ ] open two\n"
            "+ [X] done two\n"
            "- not a task\n"
        )
        ctx = _build_context({"t.md": content}, backdate_days=10)
        md = ctx.metadata(ctx.notes()[0])
        assert md["has_tasks"] is True
        assert md["task_count"] == 4
        assert md["completed_task_count"] == 2

    def test_no_tasks(self):
        ctx = _build_context({"t.md": "# T\nJust prose, no checkboxes."}, backdate_days=10)
        md = ctx.metadata(ctx.notes()[0])
        assert md["has_tasks"] is False
        assert md["task_count"] == 0

    def test_lexical_diversity_bounds(self):
        repetitive = " ".join(["word"] * 50)
        diverse = " ".join(f"unique{i}" for i in range(50))
        ctx = _build_context(
            {"rep.md": f"# Rep\n{repetitive}", "div.md": f"# Div\n{diverse}"},
            backdate_days=10,
        )
        by_path = {n.path: ctx.metadata(n) for n in ctx.notes()}
        assert by_path["rep.md"]["lexical_diversity"] < by_path["div.md"]["lexical_diversity"]
        for md in by_path.values():
            assert 0.0 < md["lexical_diversity"] <= 1.0

    def test_user_modules_can_still_override(self):
        """Inference modules run after the builtins, so their keys win."""

        class FakeLoader:
            def infer_all(self, note, vault):
                return {"staleness": 0.123}, []

        ctx = _build_context({"a.md": "# A\nText."}, backdate_days=300)
        ctx._metadata_loader = FakeLoader()  # type: ignore[assignment]
        assert ctx.metadata(ctx.notes()[0])["staleness"] == 0.123


class TestRevivedGeists:
    """Fixtures designed to trigger; non-empty output is the assertion."""

    def test_temporal_drift_fires_on_stale_linked_notes(self):
        from geistfabrik.default_geists.code import temporal_drift

        notes = {
            "stale.md": "# Stale\nLinks: [[n1]], [[n2]], [[n3]]\nOld thinking lives here.",
            "n1.md": "# N1\nContent one.",
            "n2.md": "# N2\nContent two.",
            "n3.md": "# N3\nContent three.",
        }
        ctx = _build_context(notes, backdate_days=300)  # staleness ~0.91 > 0.7
        suggestions = temporal_drift.suggest(ctx)
        assert suggestions, "designed-to-trigger fixture must produce suggestions"
        assert any("Stale" in s.text for s in suggestions)

    def test_task_archaeology_fires_on_old_incomplete_tasks(self):
        from geistfabrik.default_geists.code import task_archaeology

        notes = {
            "todo.md": "# Plans\n- [ ] write the report\n- [x] gather data\n",
            "other.md": "# Other\nNo tasks here.",
        }
        ctx = _build_context(notes, backdate_days=90)  # > 30 days
        suggestions = task_archaeology.suggest(ctx)
        assert suggestions, "old incomplete task must produce a suggestion"
        assert "incomplete task" in suggestions[0].text

    def test_blind_spot_detector_fires(self):
        """Regression: contrarian links resolve to notes again (the geist fed
        bracketed '[[Title]]' strings into an exact-path lookup and was
        permanently inert)."""
        from geistfabrik.default_geists.code import blind_spot_detector

        notes = {
            f"topic{i}.md": f"# Topic {i}\nWriting about subject number {i}." for i in range(8)
        }
        # All notes old and unlinked: whichever contrarian is picked has zero
        # backlinks, so the blind-spot gate opens.
        ctx = _build_context(notes, backdate_days=400)
        suggestions = blind_spot_detector.suggest(ctx)
        assert suggestions, "unlinked old contrarians must register as blind spots"
        for s in suggestions:
            assert "opposite perspective" in s.text
