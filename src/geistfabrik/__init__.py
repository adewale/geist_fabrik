"""GeistFabrik: A Python-based divergence engine for Obsidian vaults."""

from .embeddings import EmbeddingComputer, Session, cosine_similarity, find_similar_notes
from .geist_executor import GeistExecutor, GeistMetadata
from .models import Link, Note, Suggestion
from .vault import Vault
from .vault_context import VaultContext

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "Link",
    "Note",
    "Suggestion",
    "Vault",
    "VaultContext",
    "EmbeddingComputer",
    "Session",
    "cosine_similarity",
    "find_similar_notes",
    "GeistExecutor",
    "GeistMetadata",
]
