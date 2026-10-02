"""Shared test helpers for geist tests.

assert_valid_suggestions() is the standard oracle for geist output: it
asserts non-emptiness (vacuous-by-default loops over possibly-empty lists are
how dead geists kept green tests), structural validity, and the journal-
exclusion contract, in one call with clear failure messages.

VaultBuilder builds a real on-disk vault with an in-memory database, pinned
session dates and explicit creation/modification times, so fixtures can be
designed to trigger a geist without wall-clock time or hand-rolled setup.
"""

import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from geistfabrik.embeddings import Session
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.models import Suggestion
from geistfabrik.vault import Vault
from geistfabrik.vault_context import VaultContext

SESSION_DATE = datetime(2024, 3, 15)
DEFAULT_NOTE_DATE = datetime(2024, 3, 1)
SEED = 20240315


def assert_valid_suggestions(
    suggestions: Sequence[Suggestion],
    geist_id: str,
    *,
    min_count: int = 1,
    must_reference: Sequence[str] = (),
    must_not_reference: Sequence[str] = ("geist journal",),
) -> None:
    """Assert a geist's output is non-empty, well-formed, and on-contract.

    Args:
        suggestions: The geist's return value
        geist_id: Expected geist_id on every suggestion
        min_count: Minimum number of suggestions (default 1 - a happy-path
            test runs on a fixture DESIGNED to trigger, so empty output means
            the geist is dead; pass min_count=0 only for tests that are
            explicitly about emptiness)
        must_reference: Substrings at least one suggestion must reference
            (in text or notes) - ties the output to the fixture's content
        must_not_reference: Substrings no suggestion may reference (case-
            insensitive); defaults to the geist-journal exclusion contract
    """
    assert isinstance(suggestions, list), (
        f"geist must return a list, got {type(suggestions).__name__}"
    )
    assert len(suggestions) >= min_count, (
        f"expected >= {min_count} suggestion(s) from a designed-to-trigger "
        f"fixture, got {len(suggestions)} - is the geist dead?"
    )

    for i, s in enumerate(suggestions):
        assert isinstance(s, Suggestion), f"suggestion {i} is {type(s).__name__}"
        assert s.geist_id == geist_id, f"suggestion {i} has geist_id {s.geist_id!r}"
        assert s.text and s.text.strip(), f"suggestion {i} has empty text"
        assert isinstance(s.notes, list), f"suggestion {i} notes is not a list"

        haystacks = [s.text.lower(), *(ref.lower() for ref in s.notes)]
        for banned in must_not_reference:
            assert not any(banned.lower() in h for h in haystacks), (
                f"suggestion {i} references banned content {banned!r}: {s.text[:120]}"
            )

    for required in must_reference:
        assert any(
            required.lower() in s.text.lower()
            or any(required.lower() in ref.lower() for ref in s.notes)
            for s in suggestions
        ), f"no suggestion references expected content {required!r}"


class VaultBuilder:
    """Declarative vault fixture: write notes, then build a VaultContext.

    Example::

        builder = VaultBuilder(tmp_path)
        builder.note("Old Idea", "Gardens and soil.", created=datetime(2021, 3, 1))
        ctx = builder.build(history=[datetime(2024, 1, 1), datetime(2024, 2, 1)])
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._times: dict[str, tuple[datetime | None, datetime | None]] = {}

    def note(
        self,
        title: str,
        body: str,
        *,
        folder: str = "",
        created: datetime | None = None,
        modified: datetime | None = None,
    ) -> str:
        """Write ``<folder>/<title>.md`` and return its vault-relative path.

        ``created`` defaults to ``modified`` and vice versa; with neither, the
        note is dated ``DEFAULT_NOTE_DATE`` (never the wall clock).
        """
        rel_path = f"{folder}/{title}.md" if folder else f"{title}.md"
        path = self.root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {title}\n\n{body}")
        # Undated notes get a fixed date, never the wall clock: age and
        # staleness metadata are measured from the (fixed) session date.
        stamp = created or modified or DEFAULT_NOTE_DATE
        os.utime(path, (stamp.timestamp(), stamp.timestamp()))
        self._times[rel_path] = (created, modified)
        return rel_path

    def journal(self, title: str, body: str, **times: datetime) -> str:
        """Write a geist journal session note (must never be suggested)."""
        return self.note(title, body, folder="geist journal", **times)

    def build(
        self,
        *,
        session_date: datetime = SESSION_DATE,
        history: Sequence[datetime] = (),
        seed: int = SEED,
    ) -> VaultContext:
        """Sync into an in-memory DB, compute ``history`` sessions, then the current one."""
        vault = Vault(str(self.root), ":memory:")
        vault.sync()
        for rel_path, (created, modified) in self._times.items():
            if created is not None and modified is not None:
                vault.db.execute(
                    "UPDATE notes SET created = ?, modified = ? WHERE path = ?",
                    (created.isoformat(), modified.isoformat(), rel_path),
                )
        vault.db.commit()
        for past in sorted(history):
            Session(past, vault.db).compute_embeddings(vault.all_notes())
        session = Session(session_date, vault.db)
        session.compute_embeddings(vault.all_notes())
        return VaultContext(vault, session, seed=seed, function_registry=FunctionRegistry())
