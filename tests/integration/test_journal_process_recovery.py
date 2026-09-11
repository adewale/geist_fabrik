"""Process-boundary recovery tests for journal/database reconciliation."""

import sqlite3
import subprocess
import sys
import textwrap
from datetime import datetime
from pathlib import Path

from geistfabrik import Vault
from geistfabrik.journal_writer import JournalWriter
from geistfabrik.models import Suggestion


def _suggestion(text: str) -> Suggestion:
    return Suggestion(text=text, notes=[], geist_id="process-test")


def test_journal_recovers_after_process_exits_between_file_replace_and_commit(
    tmp_path: Path,
) -> None:
    """A fresh process reconciles a replaced file with the rolled-back database."""
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    db_path = tmp_path / "vault.db"
    date = datetime(2025, 1, 2)

    setup = Vault(vault_path, db_path)
    session_path = JournalWriter(vault_path, setup.db).write_session(
        date, [_suggestion("old")]
    )
    old_bytes = session_path.read_bytes()
    setup.close()

    child_code = textwrap.dedent(
        """
        import os
        import sys
        from datetime import datetime
        from pathlib import Path

        from geistfabrik import Vault
        from geistfabrik.journal_writer import JournalWriter
        from geistfabrik.models import Suggestion

        vault_path = Path(sys.argv[1])
        db_path = Path(sys.argv[2])
        vault = Vault(vault_path, db_path)
        real_install = JournalWriter._install_staged_file

        def install_then_exit(self, temporary_path, session_path, **kwargs):
            real_install(self, temporary_path, session_path, **kwargs)
            os._exit(73)

        JournalWriter._install_staged_file = install_then_exit
        JournalWriter(vault_path, vault.db).write_session(
            datetime(2025, 1, 2),
            [Suggestion(text="new", notes=[], geist_id="process-test")],
            overwrite=True,
        )
        """
    )
    child = subprocess.run(
        [sys.executable, "-c", child_code, str(vault_path), str(db_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert child.returncode == 73, child.stderr
    assert b"new" in session_path.read_bytes()
    assert list((vault_path / "geist journal").glob(".*.pending"))

    observer = sqlite3.connect(f"{db_path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        assert observer.execute(
            "SELECT suggestion_text FROM session_suggestions"
        ).fetchall() == [("old",)]
    finally:
        observer.close()

    recovered = Vault(vault_path, db_path)
    try:
        JournalWriter(vault_path, recovered.db)
        assert session_path.read_bytes() == old_bytes
        assert recovered.db.execute(
            "SELECT suggestion_text FROM session_suggestions"
        ).fetchall() == [("old",)]
        assert not list((vault_path / "geist journal").glob(".*.pending"))
    finally:
        recovered.close()
