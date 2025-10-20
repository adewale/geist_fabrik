"""Text complexity metadata inference module.

Infers reading time, lexical diversity, and other complexity metrics.
"""

from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from geistfabrik import Note, VaultContext


def infer(note: "Note", vault: "VaultContext") -> Dict[str, Any]:
    """Infer text complexity metrics for a note.

    Args:
        note: Note to analyze
        vault: VaultContext for accessing vault data

    Returns:
        Dictionary with complexity metrics:
        - reading_time: Estimated reading time in minutes
        - lexical_diversity: Ratio of unique words to total words
        - avg_word_length: Average character length of words
        - sentence_count: Number of sentences (estimated)
    """
    content = note.content
    words = content.split()
    word_count = len(words)

    # Reading time (200 words per minute)
    reading_time = word_count / 200

    # Lexical diversity
    unique_words = len(set(w.lower() for w in words if w.isalnum()))
    lexical_diversity = unique_words / max(1, word_count)

    # Average word length
    word_lengths = [len(w) for w in words if w.isalnum()]
    avg_word_length = sum(word_lengths) / max(1, len(word_lengths))

    # Sentence count (rough estimate by counting periods, exclamation, question marks)
    sentence_terminators = content.count(".") + content.count("!") + content.count("?")
    sentence_count = max(1, sentence_terminators)

    return {
        "reading_time": round(reading_time, 1),
        "lexical_diversity": round(lexical_diversity, 3),
        "avg_word_length": round(avg_word_length, 1),
        "sentence_count": sentence_count,
    }
