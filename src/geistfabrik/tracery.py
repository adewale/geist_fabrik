"""Tracery grammar support for GeistFabrik.

Implements a Tracery-like grammar system for declarative geist definitions.
Supports symbol expansion, modifiers, and vault function calls.
"""

import random
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml

from .models import Suggestion
from .vault_context import VaultContext


class TraceryEngine:
    """Simple Tracery grammar engine with vault function support."""

    def __init__(self, grammar: Dict[str, List[str]], seed: int | None = None):
        """Initialize Tracery engine.

        Args:
            grammar: Dictionary mapping symbols to expansion rules
            seed: Random seed for deterministic expansion
        """
        self.grammar = grammar
        self.rng = random.Random(seed)
        self.vault_context: VaultContext | None = None
        self.max_depth = 50

    def set_vault_context(self, ctx: VaultContext) -> None:
        """Set vault context for function calls.

        Args:
            ctx: Vault context to use for $vault.* function calls
        """
        self.vault_context = ctx

    def expand(self, text: str, depth: int = 0) -> str:
        """Expand a text template using grammar rules.

        Args:
            text: Template text with #symbols# to expand
            depth: Current recursion depth (for infinite loop prevention)

        Returns:
            Expanded text

        Raises:
            RecursionError: If expansion exceeds max depth
        """
        if depth > self.max_depth:
            raise RecursionError(f"Tracery expansion exceeded max depth ({self.max_depth})")

        # Find and expand #symbols#
        pattern = r"#([^#]+)#"

        def replace_symbol(match: re.Match[str]) -> str:
            symbol = match.group(1)
            expanded = self._expand_symbol(symbol, depth + 1)
            return expanded

        expanded = re.sub(pattern, replace_symbol, text)

        # Expand vault function calls
        expanded = self._expand_vault_functions(expanded)

        return expanded

    def _expand_symbol(self, symbol: str, depth: int) -> str:
        """Expand a single symbol.

        Args:
            symbol: Symbol name to expand
            depth: Current recursion depth

        Returns:
            Randomly selected expansion from grammar rules
        """
        if symbol not in self.grammar:
            return f"#{symbol}#"  # Return unchanged if not in grammar

        rules = self.grammar[symbol]
        if not rules:
            return ""

        # Select random rule
        selected = self.rng.choice(rules)

        # Recursively expand the selected rule
        return self.expand(selected, depth)

    def _convert_arg(self, arg: str) -> int | str:
        """Convert string argument to appropriate type.

        Args:
            arg: String argument from Tracery

        Returns:
            Converted argument (int if numeric, str otherwise)
        """
        # Try to convert to int
        try:
            return int(arg)
        except ValueError:
            pass

        # Return as string
        return arg

    def _expand_vault_functions(self, text: str) -> str:
        """Expand $vault.* function calls.

        Args:
            text: Text potentially containing $vault.function() calls

        Returns:
            Text with function calls replaced by results
        """
        if not self.vault_context:
            return text

        # Pattern: $vault.function_name(arg1, arg2)
        pattern = r"\$vault\.([a-z_]+)\(([^)]*)\)"

        def replace_function(match: re.Match[str]) -> str:
            func_name = match.group(1)
            args_str = match.group(2).strip()

            # Parse arguments (simple comma-separated for now)
            args = []
            if args_str:
                raw_args = [arg.strip().strip("\"'") for arg in args_str.split(",")]
                # Convert arguments to appropriate types
                args = [self._convert_arg(arg) for arg in raw_args]

            # Call the function
            try:
                assert self.vault_context is not None  # Type narrowing for mypy
                result = self.vault_context.call_function(func_name, *args)

                # Format result for text
                if isinstance(result, list):
                    # Join list items
                    return self._format_list(result)
                else:
                    return str(result)

            except Exception as e:
                return f"[Error calling {func_name}: {e}]"

        return re.sub(pattern, replace_function, text)

    def _format_list(self, items: List[Any]) -> str:
        """Format a list for text output.

        Args:
            items: List to format

        Returns:
            Formatted string representation
        """
        if not items:
            return ""

        # If items are Note objects, use their titles
        if hasattr(items[0], "title"):
            titles = [f"[[{item.title}]]" for item in items]
            if len(titles) == 1:
                return titles[0]
            elif len(titles) == 2:
                return f"{titles[0]} and {titles[1]}"
            else:
                return ", ".join(titles[:-1]) + f", and {titles[-1]}"
        else:
            return ", ".join(str(item) for item in items)


class TraceryGeist:
    """A geist defined via Tracery grammar."""

    def __init__(
        self,
        geist_id: str,
        grammar: Dict[str, List[str]],
        count: int = 1,
        seed: int | None = None,
    ):
        """Initialize Tracery geist.

        Args:
            geist_id: Unique identifier for this geist
            grammar: Tracery grammar dictionary
            count: Number of suggestions to generate per invocation
            seed: Random seed for deterministic expansion
        """
        self.geist_id = geist_id
        self.engine = TraceryEngine(grammar, seed)
        self.count = count

    @classmethod
    def from_yaml(cls, yaml_path: Path, seed: int | None = None) -> "TraceryGeist":
        """Load Tracery geist from YAML file.

        Expected YAML format:
        ```yaml
        type: geist-tracery
        id: geist_id
        count: 3  # optional, default 1
        tracery:
          origin: "#template#"
          template: ["rule1", "rule2"]
        ```

        Args:
            yaml_path: Path to YAML file
            seed: Random seed for deterministic expansion

        Returns:
            Loaded TraceryGeist instance
        """
        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        if data.get("type") != "geist-tracery":
            raise ValueError(f"Invalid geist type: {data.get('type')}")

        geist_id = data["id"]
        grammar = data["tracery"]
        count = data.get("count", 1)

        return cls(geist_id, grammar, count, seed)

    def suggest(self, vault: VaultContext) -> List[Suggestion]:
        """Generate suggestions using Tracery grammar.

        Args:
            vault: Vault context for function calls

        Returns:
            List of generated suggestions
        """
        self.engine.set_vault_context(vault)

        suggestions = []
        for _ in range(self.count):
            try:
                # Expand the origin symbol
                text = self.engine.expand("#origin#")

                # Extract note references from text
                note_pattern = r"\[\[([^\]]+)\]\]"
                note_refs = re.findall(note_pattern, text)

                suggestion = Suggestion(
                    text=text,
                    notes=note_refs,
                    geist_id=self.geist_id,
                )
                suggestions.append(suggestion)

            except Exception as e:
                # Skip failed expansions
                print(f"Warning: Tracery expansion failed for {self.geist_id}: {e}")
                continue

        return suggestions


class TraceryGeistLoader:
    """Loads Tracery geists from a directory."""

    def __init__(self, geists_dir: Path, seed: int | None = None):
        """Initialize loader.

        Args:
            geists_dir: Directory containing .yaml geist files
            seed: Random seed for deterministic expansion
        """
        self.geists_dir = geists_dir
        self.seed = seed

    def load_all(self) -> List[TraceryGeist]:
        """Load all Tracery geists from directory.

        Returns:
            List of loaded TraceryGeist instances
        """
        if not self.geists_dir.exists():
            return []

        geists = []
        for yaml_file in self.geists_dir.glob("*.yaml"):
            try:
                geist = TraceryGeist.from_yaml(yaml_file, self.seed)
                geists.append(geist)
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")
                continue

        return geists
