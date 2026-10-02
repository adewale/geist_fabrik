"""Tests for the attention_shift geist (absorbs cluster_evolution_tracker's role).

Trigger: VaultContext.neighbour_churn(since_days=180) finds notes whose 10
nearest neighbours changed by churn = 1 - Jaccard > 0.6 against a session at
least 180 days old. One such note is sampled and named with up to 3 departed
and 3 arrived neighbours. More attention_shift tests live in
tests/unit/test_reflective_geists.py.
"""

from datetime import datetime
from pathlib import Path

from geistfabrik.default_geists.code import attention_shift
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import VaultBuilder, assert_valid_suggestions
from tests.fixtures.temporal import set_session_text

HISTORY = datetime(2023, 6, 1)  # 288 days before the 2024-03-15 session
GROUPS = {
    "Alpha": "quartz lichen harbour violin saffron glacier",
    "Beta": "meadow lantern cobalt thistle walnut falcon",
    "Gamma": "copper tundra mango sextant pewter heron",
}


def _shifted(root: Path) -> VaultContext:
    """Ten notes per vocabulary group; "Pivot Beta" and "Pivot Gamma" said the
    Alpha words in the historical session and say Beta / Gamma words now, so
    both churn far above 0.6 (their old neighbours were Alpha notes)."""
    builder = VaultBuilder(root)
    for group, words in GROUPS.items():
        for i in range(10):
            builder.note(f"{group} {i}", f"{words} {group.lower()}{i}x")
    builder.note("Pivot Beta", GROUPS["Beta"])
    builder.note("Pivot Gamma", GROUPS["Gamma"])
    ctx = builder.build(history=[HISTORY])
    for pivot in ("Pivot Beta", "Pivot Gamma"):
        set_session_text(ctx, f"{pivot}.md", HISTORY, f"# {pivot}\n\n{GROUPS['Alpha']}")
    return ctx


def test_attention_shift_samples_among_shifted_notes(tmp_path):
    """Contract: every note above the churn threshold can be named; the
    session seed picks one, and each is named with its own neighbours.

    Regression: the highest-churn note was taken with max(), so the same note
    was named every session while the vault's history stayed the same.
    """
    base = _shifted(tmp_path)

    named = {}
    for seed in range(20):
        ctx = VaultContext(
            base.vault, base.session, seed=seed, function_registry=FunctionRegistry()
        )
        suggestions = attention_shift.suggest(ctx)
        assert_valid_suggestions(suggestions, "attention_shift")
        [suggestion] = suggestions
        pivot, *moved = suggestion.notes
        named[pivot] = moved

    assert set(named) == {"Pivot Beta", "Pivot Gamma"}
    for pivot, moved in named.items():
        departed, arrived = moved[:3], moved[3:]
        assert all(t.startswith("Alpha") for t in departed), (pivot, departed)
        assert all(t.startswith(pivot.split()[1]) for t in arrived), (pivot, arrived)
