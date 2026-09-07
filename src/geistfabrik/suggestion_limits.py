"""Fixed resource and runtime-shape limits for geist suggestions."""

from .config import (
    MAX_GEIST_SUGGESTIONS,
    MAX_SESSION_SUGGESTIONS,
    MAX_SUGGESTION_GEIST_ID_CHARS,
    MAX_SUGGESTION_NOTE_CHARS,
    MAX_SUGGESTION_NOTES,
    MAX_SUGGESTION_TEXT_BYTES,
    MAX_SUGGESTION_TITLE_CHARS,
)
from .models import Suggestion


def validate_suggestion(suggestion: Suggestion, *, index: int | None = None) -> None:
    """Reject malformed or oversized runtime fields on one suggestion."""
    label = f"suggestion {index}" if index is not None else "suggestion"
    if not isinstance(suggestion.text, str):
        raise TypeError(f"{label}.text must be a string")
    if len(suggestion.text.encode("utf-8")) > MAX_SUGGESTION_TEXT_BYTES:
        raise ValueError(f"{label}.text exceeds {MAX_SUGGESTION_TEXT_BYTES} UTF-8 bytes")
    if not isinstance(suggestion.geist_id, str) or not suggestion.geist_id:
        raise TypeError(f"{label}.geist_id must be a non-empty string")
    if len(suggestion.geist_id) > MAX_SUGGESTION_GEIST_ID_CHARS:
        raise ValueError(f"{label}.geist_id exceeds {MAX_SUGGESTION_GEIST_ID_CHARS} characters")
    if not isinstance(suggestion.notes, list) or any(
        not isinstance(note, str) for note in suggestion.notes
    ):
        raise TypeError(f"{label}.notes must be a list of strings")
    if len(suggestion.notes) > MAX_SUGGESTION_NOTES:
        raise ValueError(f"{label}.notes exceeds {MAX_SUGGESTION_NOTES} entries")
    if any(len(note) > MAX_SUGGESTION_NOTE_CHARS for note in suggestion.notes):
        raise ValueError(
            f"{label}.notes contains an entry over {MAX_SUGGESTION_NOTE_CHARS} characters"
        )
    if suggestion.title is not None and not isinstance(suggestion.title, str):
        raise TypeError(f"{label}.title must be a string or None")
    if suggestion.title is not None and len(suggestion.title) > MAX_SUGGESTION_TITLE_CHARS:
        raise ValueError(f"{label}.title exceeds {MAX_SUGGESTION_TITLE_CHARS} characters")


def validate_geist_suggestions(suggestions: list[Suggestion]) -> None:
    """Validate one geist result before it enters aggregate processing."""
    if len(suggestions) > MAX_GEIST_SUGGESTIONS:
        raise ValueError(f"geist returned more than {MAX_GEIST_SUGGESTIONS} suggestions")
    for index, suggestion in enumerate(suggestions):
        if not isinstance(suggestion, Suggestion):
            raise TypeError(
                f"suggestion {index} is {type(suggestion).__name__}, expected Suggestion"
            )
        validate_suggestion(suggestion, index=index)


def validate_session_suggestions(suggestions: list[Suggestion]) -> None:
    """Validate the direct journal/session persistence boundary."""
    if len(suggestions) > MAX_SESSION_SUGGESTIONS:
        raise ValueError(f"session has more than {MAX_SESSION_SUGGESTIONS} suggestions")
    for index, suggestion in enumerate(suggestions):
        if not isinstance(suggestion, Suggestion):
            raise TypeError(
                f"suggestion {index} is {type(suggestion).__name__}, expected Suggestion"
            )
        validate_suggestion(suggestion, index=index)
