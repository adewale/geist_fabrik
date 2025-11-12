"""Metadata inference system - extensible note property inference.

This module provides a system for loading and executing metadata inference modules.
Modules are discovered from `<vault>/_geistfabrik/metadata_inference/` and must
export an `infer(note, vault) -> Dict` function.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

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
        """Initialise metadata loader.

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

    def infer_all(self, note: Note, vault: "VaultContext") -> Tuple[Dict[str, Any], List[str]]:
        """Run all metadata inference modules on a note.

        Args:
            note: Note to infer metadata for
            vault: VaultContext for accessing vault data

        Returns:
            Tuple of (metadata dict, list of failed module names)

        Raises:
            MetadataConflictError: If multiple modules return the same key
        """
        metadata: Dict[str, Any] = {}
        failed_modules: List[str] = []

        for module_name, infer_func in self.modules.items():
            try:
                result = infer_func(note, vault)

                # Validate return type
                if not isinstance(result, dict):
                    logger.warning(
                        f"Metadata module {module_name} returned non-dict type: {type(result)}"
                    )
                    failed_modules.append(module_name)
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
                failed_modules.append(module_name)
                continue

        return metadata, failed_modules

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


class MetadataAnalyser:
    """Analyse metadata distributions and outliers.

    Provides statistical operations on metadata values across the vault:
    percentiles, outliers, comparisons, and profiles. Enables reasoning
    about metadata patterns without manual aggregation.

    Example:
        >>> analyser = MetadataAnalyser(vault)
        >>> dist = analyser.distribution("word_count")
        >>> # {'p10': 150, 'p25': 300, 'p50': 500, 'p75': 800, 'p90': 1200}
        >>> outliers = analyser.outliers("word_count", threshold=2.0)
    """

    def __init__(self, vault: "VaultContext"):
        """Initialize metadata analyser with vault context.

        Args:
            vault: VaultContext for accessing notes and metadata
        """
        self.vault = vault

    def distribution(self, metadata_key: str) -> Dict[str, float]:
        """Get percentiles (p10, p25, p50, p75, p90) for metadata.

        Args:
            metadata_key: Metadata key to analyze

        Returns:
            Dictionary with percentile values
        """
        import numpy as np

        notes = self.vault.notes()
        values = []

        for note in notes:
            metadata = self.vault.metadata(note)
            if metadata_key in metadata:
                value = metadata[metadata_key]
                # Only numeric values can be analyzed
                if isinstance(value, (int, float)):
                    values.append(float(value))

        if not values:
            return {
                "p10": 0.0,
                "p25": 0.0,
                "p50": 0.0,
                "p75": 0.0,
                "p90": 0.0,
            }

        values_array = np.array(values)
        return {
            "p10": float(np.percentile(values_array, 10)),
            "p25": float(np.percentile(values_array, 25)),
            "p50": float(np.percentile(values_array, 50)),
            "p75": float(np.percentile(values_array, 75)),
            "p90": float(np.percentile(values_array, 90)),
        }

    def outliers(
        self, metadata_key: str, threshold: float = 2.0
    ) -> List[Note]:
        """Find notes with metadata > threshold standard deviations from mean.

        Args:
            metadata_key: Metadata key to analyze
            threshold: Number of standard deviations (default: 2.0)

        Returns:
            List of notes with outlier values
        """
        import numpy as np

        notes = self.vault.notes()
        values = []
        note_value_map: Dict[str, float] = {}

        for note in notes:
            metadata = self.vault.metadata(note)
            if metadata_key in metadata:
                value = metadata[metadata_key]
                if isinstance(value, (int, float)):
                    values.append(float(value))
                    note_value_map[note.path] = float(value)

        if not values:
            return []

        values_array = np.array(values)
        mean = float(np.mean(values_array))
        std = float(np.std(values_array))

        if std < 1e-10:  # Avoid division by zero
            return []

        # Find outliers
        outlier_notes = []
        for note in notes:
            if note.path in note_value_map:
                value = note_value_map[note.path]
                z_score = abs((value - mean) / std)
                if z_score > threshold:
                    outlier_notes.append(note)

        return outlier_notes

    def compare_notes(
        self, note_a: Note, note_b: Note, keys: List[str]
    ) -> Dict[str, float]:
        """Compare metadata between two notes (ratios).

        Args:
            note_a: First note
            note_b: Second note
            keys: Metadata keys to compare

        Returns:
            Dictionary mapping keys to ratios (note_a / note_b)
        """
        metadata_a = self.vault.metadata(note_a)
        metadata_b = self.vault.metadata(note_b)

        ratios: Dict[str, float] = {}

        for key in keys:
            value_a = metadata_a.get(key)
            value_b = metadata_b.get(key)

            # Can only compute ratios for numeric values
            if isinstance(value_a, (int, float)) and isinstance(value_b, (int, float)):
                if value_b != 0:
                    ratios[key] = float(value_a) / float(value_b)
                else:
                    ratios[key] = float("inf")  # Infinite ratio

        return ratios

    def profile(self, note: Note) -> Dict[str, str]:
        """Get metadata profile: {key: 'high'|'moderate'|'low'} based on percentiles.

        Args:
            note: Note to profile

        Returns:
            Dictionary mapping metadata keys to qualitative levels
        """
        metadata = self.vault.metadata(note)
        profile: Dict[str, str] = {}

        for key, value in metadata.items():
            if not isinstance(value, (int, float)):
                continue  # Only profile numeric metadata

            dist = self.distribution(key)
            p25 = dist["p25"]
            p75 = dist["p75"]

            float_value = float(value)

            if float_value >= p75:
                profile[key] = "high"
            elif float_value <= p25:
                profile[key] = "low"
            else:
                profile[key] = "moderate"

        return profile
