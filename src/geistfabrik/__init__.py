"""GeistFabrik: A Python-based divergence engine for Obsidian vaults."""

from .embeddings import EmbeddingComputer, Session, cosine_similarity, find_similar_notes
from .filtering import SuggestionFilter, select_suggestions
from .function_registry import (
    DuplicateFunctionError,
    FunctionRegistry,
    FunctionRegistryError,
    vault_function,
)
from .geist_executor import GeistExecutor, GeistMetadata
from .journal_writer import JournalWriter
from .metadata_system import (
    MetadataConflictError,
    MetadataInferenceError,
    MetadataLoader,
)
from .models import Link, Note, Suggestion
from .vault import Vault
from .vault_context import VaultContext

__version__ = "0.9.0"

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
    "SuggestionFilter",
    "select_suggestions",
    "JournalWriter",
    "MetadataLoader",
    "MetadataInferenceError",
    "MetadataConflictError",
    "FunctionRegistry",
    "FunctionRegistryError",
    "DuplicateFunctionError",
    "vault_function",
]
