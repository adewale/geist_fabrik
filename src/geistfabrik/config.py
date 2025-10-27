"""Configuration constants for GeistFabrik.

This module centralizes all magic numbers and configuration constants
used throughout the application. These serve as default values that can
be overridden by user configuration files or CLI arguments.
"""

from typing import Any, Dict

# Embedding Configuration
# -----------------------
# These constants define the dimensionality and behavior of the embedding system.

MODEL_NAME = "all-MiniLM-L6-v2"
"""str: Name of the sentence-transformers model used for semantic embeddings.

This model produces 384-dimensional semantic vectors. The model is bundled
with GeistFabrik to enable offline operation.
"""

SEMANTIC_DIM = 384
"""int: Dimension of semantic embeddings from sentence-transformers.

This value is determined by the model architecture (all-MiniLM-L6-v2)
and should match the model's output dimension.
"""

TEMPORAL_DIM = 3
"""int: Dimension of temporal feature vectors.

Temporal features include:
1. Note age (days since creation, normalized)
2. Creation season (sin/cos encoding of time of year)
3. Session season (sin/cos encoding of current session time)

Currently using 3 dimensions for simplicity. Could be expanded to
include more temporal features in the future.
"""

TOTAL_DIM = SEMANTIC_DIM + TEMPORAL_DIM  # 387 total
"""int: Total dimension of combined semantic + temporal embeddings.

GeistFabrik combines semantic embeddings (384-dim) with temporal features (3-dim)
to create 387-dimensional vectors that capture both meaning and time.
"""

DEFAULT_SEMANTIC_WEIGHT = 0.9
"""float: Weight given to semantic similarity vs. temporal similarity.

When computing similarity, we use:
    semantic_weight * semantic_sim + (1-semantic_weight) * temporal_sim
A value of 0.9 means semantic similarity is emphasized over temporal similarity.
Range: [0.0, 1.0]
"""

DEFAULT_BATCH_SIZE = 8
"""int: Number of notes to process in parallel during embedding computation.

Smaller batch sizes reduce memory usage and prevent overwhelming the CPU.
Larger batch sizes may be faster but require more memory.
Range: [1, 32] typically
"""


# Filtering Configuration
# ------------------------
# These constants control the suggestion filtering pipeline.

DEFAULT_SIMILARITY_THRESHOLD = 0.85
"""float: Cosine similarity threshold for detecting duplicate/similar suggestions.

Used in both novelty and diversity filters to determine if two suggestions
are too similar. Higher values = more strict (only very similar items filtered).
Lower values = more lenient (more items filtered as similar).
Range: [0.0, 1.0], typically [0.7, 0.95]
Recommended: 0.85
"""

DEFAULT_NOVELTY_WINDOW_DAYS = 60
"""int: Number of days of history to check for similar suggestions.

The novelty filter looks back this many days to ensure new suggestions
aren't too similar to recent ones. Longer windows provide more novelty
but may reduce suggestion diversity over time.
Range: [7, 365] days
Recommended: 60 days (2 months)
"""

DEFAULT_MIN_SUGGESTION_LENGTH = 10
"""int: Minimum character length for a valid suggestion.

Suggestions shorter than this are rejected by the quality filter.
This prevents trivial or incomplete suggestions.
Range: [5, 50] characters
Recommended: 10 characters
"""

DEFAULT_MAX_SUGGESTION_LENGTH = 2000
"""int: Maximum character length for a valid suggestion.

Suggestions longer than this are rejected by the quality filter.
This ensures suggestions remain concise and focused.
Range: [500, 5000] characters
Recommended: 2000 characters
"""


# Geist Execution Configuration
# ------------------------------
# These constants control how geists are executed and managed.

DEFAULT_GEIST_TIMEOUT = 5
"""int: Maximum execution time for a single geist in seconds.

Geists that exceed this timeout are terminated to prevent hangs.
Applies to both code geists and Tracery geists.
Range: [1, 60] seconds
Recommended: 5 seconds
"""

DEFAULT_MAX_GEIST_FAILURES = 3
"""int: Number of consecutive failures before a geist is auto-disabled.

After this many failures, a geist will be automatically disabled for
the current session to prevent repeated errors from degrading UX.
Range: [1, 10] failures
Recommended: 3 failures
"""


def get_default_filter_config() -> Dict[str, Any]:
    """Get default filtering configuration dictionary.

    Returns:
        Default configuration for the SuggestionFilter with all constants.
    """
    return {
        "strategies": ["boundary", "novelty", "diversity", "quality"],
        "boundary": {"enabled": True},
        "novelty": {
            "enabled": True,
            "method": "embedding_similarity",
            "threshold": DEFAULT_SIMILARITY_THRESHOLD,
            "window_days": DEFAULT_NOVELTY_WINDOW_DAYS,
        },
        "diversity": {
            "enabled": True,
            "method": "embedding_similarity",
            "threshold": DEFAULT_SIMILARITY_THRESHOLD,
        },
        "quality": {
            "enabled": True,
            "min_length": DEFAULT_MIN_SUGGESTION_LENGTH,
            "max_length": DEFAULT_MAX_SUGGESTION_LENGTH,
            "check_repetition": True,
        },
    }
