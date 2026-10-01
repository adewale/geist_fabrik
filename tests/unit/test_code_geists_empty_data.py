"""Generic data-starvation contracts for every bundled code geist.

These are the shared owners that per-geist files no longer duplicate:
- an empty vault yields exactly [] from every code geist;
- a minimal vault (2 notes, no links) never crashes a code geist;
- whatever a geist returns on a small unlinked vault is well formed, carries
  its own geist_id and only references notes that exist.

Each test iterates DEFAULT_CODE_GEISTS and first asserts the list is not
empty, so a discovery regression cannot turn these into loops over nothing.
"""

import importlib
from datetime import datetime
from pathlib import Path
from types import ModuleType

import pytest

from geistfabrik.default_geists import DEFAULT_CODE_GEISTS
from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.models import Suggestion
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import assert_valid_suggestions

SESSION_DATE = datetime(2025, 1, 20)


def _context(tmp_path: Path, notes: dict[str, str]) -> VaultContext:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / ".obsidian").mkdir()
    for filename, content in notes.items():
        (vault_path / filename).write_text(content)
    vault = Vault(vault_path, ":memory:")
    vault.sync()
    session = Session(SESSION_DATE, vault.db)
    session.compute_embeddings(vault.all_notes())
    return VaultContext(vault, session, seed=42, function_registry=FunctionRegistry())


def _code_geists() -> list[tuple[str, ModuleType]]:
    assert DEFAULT_CODE_GEISTS, "no bundled code geists discovered"
    return [
        (name, importlib.import_module(f"geistfabrik.default_geists.code.{name}"))
        for name in DEFAULT_CODE_GEISTS
    ]


def _run_all(ctx: VaultContext) -> dict[str, list[Suggestion]]:
    return {name: module.suggest(ctx) for name, module in _code_geists()}


def test_all_code_geists_return_nothing_for_an_empty_vault(tmp_path: Path) -> None:
    """With no notes there is nothing to reference, so every geist returns []."""
    ctx = _context(tmp_path, {})
    assert ctx.notes() == []

    outputs = _run_all(ctx)

    assert len(outputs) == len(DEFAULT_CODE_GEISTS)
    non_empty = {name: out for name, out in outputs.items() if out != []}
    assert non_empty == {}, f"geists returned output for an empty vault: {non_empty}"


MINIMAL_VAULT = {
    "Note A.md": "# Note A\nSome content here",
    "Note B.md": "# Note B\nDifferent content",
}
SMALL_UNLINKED_VAULT = {
    f"Note {i}.md": f"# Note {i}\nContent without links or connections" for i in range(5)
}


def _assert_well_formed(outputs: dict[str, list[Suggestion]], ctx: VaultContext) -> None:
    """Every suggestion carries its geist's id and placeholder-free text, and
    references only notes that exist. At least one geist must have fired, so
    the check cannot pass vacuously."""
    real_notes = {note.link_text for note in ctx.notes()}
    fired = {name: out for name, out in outputs.items() if out}
    assert fired, "fixture should make at least one code geist fire"
    dangling: dict[str, set[str]] = {}
    for name, suggestions in fired.items():
        assert_valid_suggestions(suggestions, name)
        for s in suggestions:
            assert "  " not in s.text, f"{name}: empty placeholder in {s.text!r}"
            assert s.title is None or (isinstance(s.title, str) and s.title), name
            if not set(s.notes) <= real_notes:
                dangling.setdefault(name, set()).update(set(s.notes) - real_notes)
    assert not dangling, f"dangling note refs: {dangling}"


def test_all_code_geists_handle_minimal_vault(tmp_path: Path) -> None:
    """Two unlinked notes sit below most thresholds: no geist may crash, and
    the few that still fire must produce well-formed output."""
    ctx = _context(tmp_path, MINIMAL_VAULT)

    outputs = _run_all(ctx)

    assert len(outputs) == len(DEFAULT_CODE_GEISTS)
    _assert_well_formed(outputs, ctx)


def test_suggestions_have_required_fields(tmp_path: Path) -> None:
    """Output on a small unlinked vault, where several geists fire, is well formed."""
    ctx = _context(tmp_path, SMALL_UNLINKED_VAULT)

    outputs = _run_all(ctx)

    _assert_well_formed(outputs, ctx)


def test_code_geist_output_does_not_depend_on_hash_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same date + vault = same output, whatever PYTHONHASHSEED a process has.

    Salting Note.__hash__ reorders every set of Notes, as a different hash
    seed would in another process. Per-geist determinism tests run in one
    process and cannot see this; this sweep covers every geist that fires on
    a small linked vault (geist-specific fixtures cover the rest).
    """
    from geistfabrik.models import Note

    notes = {
        f"Note {i}.md": (
            f"# Note {i}\nOrchard idea {i} [[Note {(i + 1) % 8}]] [[Note {(i + 3) % 8}]]"
        )
        for i in range(8)
    }
    def run(label: str) -> dict[str, list[str]]:
        root = tmp_path / label
        root.mkdir()
        return {n: [s.text for s in out] for n, out in _run_all(_context(root, notes)).items()}

    baseline = run("v0")
    assert sum(1 for out in baseline.values() if out) >= 5

    for salt in ("a", "b", "c"):
        monkeypatch.setattr(Note, "__hash__", lambda self, salt=salt: hash(salt + self.path))
        assert run(f"v{salt}") == baseline, salt
