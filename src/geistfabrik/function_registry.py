"""Function registry system - extensible vault functions for geists and Tracery.

This module provides:
1. @vault_function decorator for registering functions
2. FunctionRegistry for loading and managing functions
3. Built-in vault functions for common operations
"""

import importlib.util
import inspect
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

if TYPE_CHECKING:
    from .vault_context import VaultContext

logger = logging.getLogger(__name__)


class FunctionRegistryError(Exception):
    """Raised when function registry operations fail."""

    pass


class DuplicateFunctionError(Exception):
    """Raised when duplicate function names are registered."""

    pass


# Global registry for decorated functions
_GLOBAL_REGISTRY: Dict[str, Callable[..., Any]] = {}


def vault_function(name: str) -> Callable[..., Any]:
    """Decorator to register a function for use in geists and Tracery.

    Args:
        name: Name to register the function under

    Returns:
        Decorator function

    Example:
        @vault_function("find_questions")
        def find_question_notes(vault: VaultContext, k: int = 5):
            questions = [n for n in vault.notes() if "?" in n.title]
            return vault.sample(questions, k)
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        if name in _GLOBAL_REGISTRY:
            raise DuplicateFunctionError(
                f"Function '{name}' is already registered: {_GLOBAL_REGISTRY[name]}"
            )

        # Validate function signature
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        if not params or params[0].name != "vault":
            raise FunctionRegistryError(f"Function '{name}' must have 'vault' as first parameter")

        _GLOBAL_REGISTRY[name] = func
        logger.debug(f"Registered vault function: {name}")
        return func

    return decorator


class FunctionRegistry:
    """Manages vault functions from modules and built-ins.

    Functions can be:
    1. Loaded from a directory of Python modules
    2. Registered programmatically via @vault_function decorator
    3. Built-in functions provided by the system
    """

    def __init__(self, function_dir: Optional[Path] = None):
        """Initialize function registry.

        Args:
            function_dir: Directory containing vault function modules.
                         If None, only built-in and decorated functions are available.
        """
        self.function_dir = function_dir
        self.functions: Dict[str, Callable[..., Any]] = {}

        # Load built-in functions
        self._register_builtin_functions()

    def _register_builtin_functions(self) -> None:
        """Register built-in vault functions.

        These functions act as the adapter layer between Tracery (string-based)
        and VaultContext (Note-based). They:
        - Accept strings from Tracery
        - Work with Note objects internally
        - Return strings (note titles) back to Tracery
        """

        @vault_function("sample_notes")
        def sample_notes(vault: "VaultContext", k: int = 5) -> List[str]:
            """Sample k random notes from vault.

            Returns:
                List of note titles (strings for Tracery)
            """
            notes = vault.notes()
            sampled = vault.sample(notes, k)
            return [note.title for note in sampled]

        @vault_function("old_notes")
        def old_notes(vault: "VaultContext", k: int = 5) -> List[str]:
            """Get k least recently modified notes.

            Returns:
                List of note titles (strings for Tracery)
            """
            notes = vault.old_notes(k)
            return [note.title for note in notes]

        @vault_function("recent_notes")
        def recent_notes(vault: "VaultContext", k: int = 5) -> List[str]:
            """Get k most recently modified notes.

            Returns:
                List of note titles (strings for Tracery)
            """
            notes = vault.recent_notes(k)
            return [note.title for note in notes]

        @vault_function("sample_old_notes")
        def sample_old_notes(vault: "VaultContext", k: int = 1, pool_size: int = 10) -> List[str]:
            """Sample k notes from the pool_size oldest notes.

            Follows 'Sample, don't rank' principle by randomly selecting from old notes
            rather than deterministically returning THE oldest.

            Returns:
                List of note titles (strings for Tracery)
            """
            old_pool = vault.old_notes(pool_size)
            sampled_notes = vault.sample(old_pool, k)
            return [note.title for note in sampled_notes]

        @vault_function("sample_recent_notes")
        def sample_recent_notes(
            vault: "VaultContext", k: int = 1, pool_size: int = 10
        ) -> List[str]:
            """Sample k notes from the pool_size most recently modified notes.

            Follows 'Sample, don't rank' principle by randomly selecting from recent notes
            rather than deterministically returning THE newest.

            Returns:
                List of note titles (strings for Tracery)
            """
            recent_pool = vault.recent_notes(pool_size)
            sampled_notes = vault.sample(recent_pool, k)
            return [note.title for note in sampled_notes]

        @vault_function("orphans")
        def orphans(vault: "VaultContext", k: int = 5) -> List[str]:
            """Get k orphan notes (no incoming or outgoing links).

            Returns:
                List of note titles (strings for Tracery)
            """
            notes = vault.orphans(k)
            return [note.title for note in notes]

        @vault_function("hubs")
        def hubs(vault: "VaultContext", k: int = 5) -> List[str]:
            """Get k notes with most incoming links.

            Returns:
                List of note titles (strings for Tracery)
            """
            notes = vault.hubs(k)
            return [note.title for note in notes]

        @vault_function("neighbours")
        def neighbours(vault: "VaultContext", note_title: str, k: int = 5) -> List[str]:
            """Get k semantically similar notes to given note.

            Args:
                note_title: Note title (string from Tracery)
                k: Number of neighbors to return

            Returns:
                List of note titles (strings for Tracery)
            """
            # Resolve string → Note (adapter layer responsibility)
            note = vault.resolve_link_target(note_title)
            if note is None:
                return []

            # Work with Note objects internally
            neighbor_notes = vault.neighbours(note, k)

            # Convert Note → string for Tracery
            return [n.title for n in neighbor_notes]

        # Transfer built-in functions from global registry to instance
        self.functions.update(_GLOBAL_REGISTRY)

    def load_modules(self, enabled_modules: Optional[List[str]] = None) -> None:
        """Load vault function modules from directory.

        Args:
            enabled_modules: Optional list of module names to load. If None, load all.

        Raises:
            FunctionRegistryError: If module loading fails
            DuplicateFunctionError: If duplicate function names are found
        """
        # First, register any globally decorated functions
        self.functions.update(_GLOBAL_REGISTRY)

        if self.function_dir is None or not self.function_dir.exists():
            logger.debug("Function module directory does not exist, skipping")
            return

        # Discover Python files
        module_files = sorted(self.function_dir.glob("*.py"))
        if not module_files:
            logger.debug("No function modules found")
            return

        for module_file in module_files:
            module_name = module_file.stem
            if module_name.startswith("_"):
                continue  # Skip private modules

            if enabled_modules is not None and module_name not in enabled_modules:
                continue  # Skip disabled modules

            try:
                self._load_module(module_name, module_file)
            except Exception as e:
                logger.error(f"Failed to load function module {module_name}: {e}")
                continue

        # Transfer any functions added to global registry during module loading
        self.functions.update(_GLOBAL_REGISTRY)

        logger.info(f"Loaded {len(self.functions)} vault functions")

    def _load_module(self, module_name: str, module_file: Path) -> None:
        """Load a single function module.

        Args:
            module_name: Name of the module
            module_file: Path to the module file

        Raises:
            FunctionRegistryError: If module is invalid
            DuplicateFunctionError: If function names conflict
        """
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            raise FunctionRegistryError(f"Could not load module spec for {module_name}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"_vaultfunc_{module_name}"] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise FunctionRegistryError(f"Error executing module {module_name}: {e}")

        # After module execution, check if any new functions were registered globally
        # (This happens automatically via @vault_function decorator)

        logger.debug(f"Loaded function module: {module_name}")

    def register(self, name: str, func: Callable[..., Any]) -> None:
        """Manually register a function.

        Args:
            name: Name to register function under
            func: Function to register

        Raises:
            DuplicateFunctionError: If name already exists
        """
        if name in self.functions:
            raise DuplicateFunctionError(f"Function '{name}' already registered")

        self.functions[name] = func
        logger.debug(f"Manually registered function: {name}")

    def call(self, name: str, vault: "VaultContext", *args: Any, **kwargs: Any) -> Any:
        """Call a registered function.

        Args:
            name: Name of function to call
            vault: VaultContext to pass to function
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of function call

        Raises:
            FunctionRegistryError: If function not found or execution fails
        """
        if name not in self.functions:
            raise FunctionRegistryError(f"Function '{name}' not registered")

        func = self.functions[name]

        try:
            return func(vault, *args, **kwargs)
        except Exception as e:
            raise FunctionRegistryError(f"Error calling function '{name}': {e}") from e

    def get_function_names(self) -> List[str]:
        """Get list of all registered function names.

        Returns:
            Sorted list of function names
        """
        return sorted(self.functions.keys())

    def has_function(self, name: str) -> bool:
        """Check if a function is registered.

        Args:
            name: Function name

        Returns:
            True if function exists, False otherwise
        """
        return name in self.functions
