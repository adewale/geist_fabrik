"""Metadata inference system - extensible note property inference.

This module provides a system for loading and executing metadata inference modules.
Modules are discovered from `<vault>/_geistfabrik/metadata_inference/` and must
export an `infer(note, vault) -> Dict` function.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

from .models import Note

if TYPE_CHECKING:
    from .vault_context import VaultContext

logger = logging.getLogger(__name__)


class MetadataInferenceError(Exception):
    """Raised when metadata inference fails."""

    pass


class MetadataConflictError(Exception):
    """Raised when multiple modules try to infer the same key."""

    pass


class MetadataLoader:
    """Loads and manages metadata inference modules.

    Discovers Python modules from a directory, validates that they export
    an `infer(note, vault) -> Dict` function, and detects key conflicts.
    """

    def __init__(self, module_dir: Optional[Path] = None):
        """Initialize metadata loader.

        Args:
            module_dir: Directory containing metadata inference modules.
                       If None, no modules are loaded.
        """
        self.module_dir = module_dir
        self.modules: Dict[str, Callable[[Note, "VaultContext"], Dict[str, Any]]] = {}
        self._key_to_module: Dict[str, str] = {}  # Track which module provides which key

    def load_modules(self, enabled_modules: Optional[List[str]] = None) -> None:
        """Load metadata inference modules from directory.

        Args:
            enabled_modules: Optional list of module names to load. If None, load all.

        Raises:
            MetadataConflictError: If multiple modules try to infer the same key
        """
        if self.module_dir is None or not self.module_dir.exists():
            logger.debug("Metadata module directory does not exist, skipping")
            return

        # Discover Python files
        module_files = sorted(self.module_dir.glob("*.py"))
        if not module_files:
            logger.debug("No metadata modules found")
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
                logger.error(f"Failed to load metadata module {module_name}: {e}")
                continue

        logger.info(f"Loaded {len(self.modules)} metadata inference modules")

    def _load_module(self, module_name: str, module_file: Path) -> None:
        """Load a single metadata module.

        Args:
            module_name: Name of the module
            module_file: Path to the module file

        Raises:
            MetadataInferenceError: If module is invalid
            MetadataConflictError: If module keys conflict with existing modules
        """
        # Load module dynamically
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        if spec is None or spec.loader is None:
            raise MetadataInferenceError(f"Could not load module spec for {module_name}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[f"_metadata_{module_name}"] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise MetadataInferenceError(f"Error executing module {module_name}: {e}")

        # Validate that module exports infer function
        if not hasattr(module, "infer"):
            raise MetadataInferenceError(f"Module {module_name} does not export 'infer' function")

        infer_func = module.infer
        if not callable(infer_func):
            raise MetadataInferenceError(f"Module {module_name} 'infer' is not callable")

        # Detect key conflicts by doing a dry run with a dummy note
        # (This is optional but helps catch conflicts early)
        # For now, we'll detect conflicts during actual inference

        self.modules[module_name] = infer_func
        logger.debug(f"Loaded metadata module: {module_name}")

    def infer_all(self, note: Note, vault: "VaultContext") -> Dict[str, Any]:
        """Run all metadata inference modules on a note.

        Args:
            note: Note to infer metadata for
            vault: VaultContext for accessing vault data

        Returns:
            Dictionary of all inferred metadata

        Raises:
            MetadataConflictError: If multiple modules return the same key
        """
        metadata: Dict[str, Any] = {}

        for module_name, infer_func in self.modules.items():
            try:
                result = infer_func(note, vault)

                # Validate return type
                if not isinstance(result, dict):
                    logger.warning(
                        f"Metadata module {module_name} returned non-dict type: {type(result)}"
                    )
                    continue

                # Detect key conflicts
                for key, value in result.items():
                    if key in metadata:
                        existing_module = self._key_to_module[key]
                        raise MetadataConflictError(
                            f"Metadata key conflict: '{key}' provided by both "
                            f"'{existing_module}' and '{module_name}'"
                        )

                    # Validate value types (must be JSON-serializable)
                    if not self._is_valid_value(value):
                        logger.warning(
                            f"Metadata module {module_name} returned invalid value type "
                            f"for key '{key}': {type(value)}"
                        )
                        continue

                    metadata[key] = value
                    self._key_to_module[key] = module_name

            except MetadataConflictError:
                raise  # Re-raise conflict errors
            except Exception as e:
                logger.error(
                    f"Error running metadata module {module_name} on note {note.path}: {e}"
                )
                continue

        return metadata

    def _is_valid_value(self, value: Any) -> bool:
        """Check if a value is a valid metadata type.

        Valid types are: str, int, float, bool, None, list, dict (JSON-serializable)

        Args:
            value: Value to check

        Returns:
            True if valid, False otherwise
        """
        if value is None:
            return True
        if isinstance(value, (str, int, float, bool)):
            return True
        if isinstance(value, list):
            return all(self._is_valid_value(v) for v in value)
        if isinstance(value, dict):
            return all(isinstance(k, str) and self._is_valid_value(v) for k, v in value.items())
        return False

    def get_module_keys(self, module_name: str) -> List[str]:
        """Get list of keys provided by a specific module.

        Args:
            module_name: Name of the module

        Returns:
            List of keys provided by the module
        """
        return [k for k, m in self._key_to_module.items() if m == module_name]

    def clear_cache(self) -> None:
        """Clear the key-to-module mapping cache."""
        self._key_to_module.clear()
