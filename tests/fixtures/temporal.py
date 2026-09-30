"""Session-history helpers for temporal geist tests.

VaultBuilder computes every history session from the notes' *current* file
content, so every session stores the same semantic vector for a note, and
trajectory geists (drift, convergence, divergence, instability) never see
movement. ``set_session_text`` rewrites what a note "said" in one recorded
session: it replaces the semantic part of that session's stored embedding
with the test stub's embedding of ``text`` and keeps the calendar tail, just
as if the note had had that content when the session ran.

Only history sessions should be rewritten. The current session's vectors are
loaded when the VaultContext is built, so the current text of a note is its
file content.
"""

from datetime import datetime

import numpy as np

from geistfabrik.config import DEFAULT_SEMANTIC_WEIGHT, SEMANTIC_DIM
from geistfabrik.vault_context import VaultContext
from tests.stubs import lexical_embedding

# Sixteen distinct content words. Under the lexical stub, a note whose text
# grows from BASE16 by k new words drifts by 1 - sqrt(n / (n + k)), where n
# counts BASE16 plus the title's words: small, controllable drifts for
# threshold boundary pairs.
BASE16 = (
    "alpha bravo charlie delta echo foxtrot golf hotel "
    "india juliet kilo lima mike november oscar papa"
)


def set_session_text(ctx: VaultContext, path: str, session_date: datetime, text: str) -> None:
    """Make ``path``'s stored vector in the ``session_date`` session embed ``text``."""
    if session_date.date() == ctx.session.date.date():
        raise ValueError("rewrite history sessions only; the current session is already loaded")
    row = ctx.db.execute(
        """
        SELECT se.session_id, se.embedding
        FROM session_embeddings se JOIN sessions s ON s.session_id = se.session_id
        WHERE s.date = ? AND se.note_path = ?
        """,
        (session_date.strftime("%Y-%m-%d"), path),
    ).fetchone()
    if row is None:
        raise KeyError(f"no stored embedding for {path!r} on {session_date:%Y-%m-%d}")
    session_id, raw = row
    vector = np.frombuffer(raw, dtype=np.float32).copy()
    vector[:SEMANTIC_DIM] = lexical_embedding(text) * DEFAULT_SEMANTIC_WEIGHT
    ctx.db.execute(
        "UPDATE session_embeddings SET embedding = ? WHERE session_id = ? AND note_path = ?",
        (vector.astype(np.float32).tobytes(), session_id, path),
    )
    ctx.db.commit()


def set_history(ctx: VaultContext, path: str, texts: dict[datetime, str]) -> None:
    """Apply ``set_session_text`` for each ``{session_date: text}`` entry."""
    for session_date, text in texts.items():
        set_session_text(ctx, path, session_date, text)


def drop_from_session(ctx: VaultContext, path: str, session_date: datetime) -> None:
    """Remove ``path`` from the ``session_date`` session, as if it did not exist yet.

    Geist journal notes are written after their session runs, so a session
    note first appears in the NEXT session's embeddings.
    """
    ctx.db.execute(
        """
        DELETE FROM session_embeddings
        WHERE note_path = ?
          AND session_id = (SELECT session_id FROM sessions WHERE date = ?)
        """,
        (path, session_date.strftime("%Y-%m-%d")),
    )
    ctx.db.commit()
