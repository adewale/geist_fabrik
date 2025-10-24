"""Tracery grammar support for GeistFabrik.

Implements a Tracery-like grammar system for declarative geist definitions.
Supports symbol expansion, modifiers, and vault function calls.
"""

import logging
import random
import re
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml

from .models import Suggestion
from .vault_context import VaultContext

logger = logging.getLogger(__name__)


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
        self.modifiers: Dict[str, Callable[[str], str]] = self._default_modifiers()
        self._preprocessed = False  # Track if pre-population done
        self._prepopulation_failed = False  # Track if pre-population failed

    def _default_modifiers(self) -> Dict[str, Callable[[str], str]]:
        """Get default English language modifiers.

        Returns:
            Dictionary mapping modifier names to transformation functions
        """
        return {
            "capitalize": self._capitalize,
            "capitalizeAll": self._capitalize_all,
            "s": self._pluralize,
            "ed": self._past_tense,
            "a": self._article,
        }

    def _capitalize(self, text: str) -> str:
        """Capitalize first letter of text.

        Args:
            text: Input text

        Returns:
            Text with first letter capitalized
        """
        if not text:
            return text
        return text[0].upper() + text[1:]

    def _capitalize_all(self, text: str) -> str:
        """Capitalize first letter of each word.

        Args:
            text: Input text

        Returns:
            Text with each word capitalized
        """
        return " ".join(word.capitalize() for word in text.split())

    def _pluralize(self, text: str) -> str:
        """Convert word to plural form.

        Simple English pluralization rules:
        - Words ending in 'y' (preceded by consonant) -> 'ies'
        - Words ending in 's', 'x', 'z', 'ch', 'sh' -> add 'es'
        - Default -> add 's'

        Args:
            text: Singular word

        Returns:
            Plural form of word
        """
        if not text:
            return text

        # Handle common irregular plurals
        irregulars = {
            "person": "people",
            "child": "children",
            "man": "men",
            "woman": "women",
            "tooth": "teeth",
            "foot": "feet",
            "mouse": "mice",
            "goose": "geese",
        }

        lower_text = text.lower()
        if lower_text in irregulars:
            # Preserve original capitalization
            result = irregulars[lower_text]
            if text[0].isupper():
                result = result.capitalize()
            return result

        # Words ending in consonant + y -> ies
        if len(text) >= 2 and text[-1] == "y" and text[-2] not in "aeiou":
            return text[:-1] + "ies"

        # Words ending in s, x, z, ch, sh -> es
        if text.endswith(("s", "x", "z")) or text.endswith(("ch", "sh")):
            return text + "es"

        # Words ending in consonant + o -> es (with exceptions)
        if len(text) >= 2 and text[-1] == "o" and text[-2] not in "aeiou":
            # Common exceptions that just add 's'
            if lower_text not in ["photo", "piano", "halo"]:
                return text + "es"

        # Default: add s
        return text + "s"

    def _past_tense(self, text: str) -> str:
        """Convert verb to past tense.

        Simple English past tense rules:
        - Words ending in 'e' -> add 'd'
        - Words ending in consonant + 'y' -> 'ied'
        - Words ending in single consonant (preceded by single vowel) -> double + 'ed'
        - Default -> add 'ed'

        Args:
            text: Present tense verb

        Returns:
            Past tense form
        """
        if not text:
            return text

        # Handle common irregular verbs
        irregulars = {
            "be": "was",
            "have": "had",
            "do": "did",
            "say": "said",
            "go": "went",
            "get": "got",
            "make": "made",
            "know": "knew",
            "think": "thought",
            "take": "took",
            "see": "saw",
            "come": "came",
            "want": "wanted",
            "use": "used",
            "find": "found",
            "give": "gave",
            "tell": "told",
            "work": "worked",
            "call": "called",
            "try": "tried",
            "ask": "asked",
            "need": "needed",
            "feel": "felt",
            "become": "became",
            "leave": "left",
            "put": "put",
            "write": "wrote",
            "build": "built",
            "grow": "grew",
            "split": "split",
        }

        lower_text = text.lower()
        if lower_text in irregulars:
            # Preserve original capitalization
            result = irregulars[lower_text]
            if text[0].isupper():
                result = result.capitalize()
            return result

        # Words ending in 'e' -> add 'd'
        if text.endswith("e"):
            return text + "d"

        # Words ending in consonant + 'y' -> 'ied'
        if len(text) >= 2 and text[-1] == "y" and text[-2] not in "aeiou":
            return text[:-1] + "ied"

        # Words ending in single consonant preceded by single vowel (CVC pattern)
        # and stressed on last syllable -> double consonant + 'ed'
        # Simplified: just check if last 3 chars match CVC pattern for short words
        if len(text) >= 3:
            if (
                text[-1] not in "aeiouwxy"  # consonant
                and text[-2] in "aeiou"  # vowel
                and text[-3] not in "aeiou"
            ):  # consonant
                # Double last consonant for short words
                if len(text) <= 5:
                    return text + text[-1] + "ed"

        # Default: add 'ed'
        return text + "ed"

    def _article(self, text: str) -> str:
        """Add appropriate article (a/an) before word.

        Args:
            text: Word to add article to

        Returns:
            Word with appropriate article
        """
        if not text:
            return text

        # Use 'an' before vowel sounds
        # Simplified: check first letter (doesn't handle silent 'h', 'u' as 'you', etc.)
        first_char = text[0].lower()

        # Special cases
        if text.lower().startswith(("honest", "hour", "honor", "heir")):
            article = "an"
        elif text.lower().startswith("uni"):
            article = "a"  # 'university', 'unique' etc. have 'yoo' sound
        elif first_char in "aeiou":
            article = "an"
        else:
            article = "a"

        return f"{article} {text}"

    def add_modifier(self, name: str, func: Callable[[str], str]) -> None:
        """Add a custom modifier.

        Args:
            name: Modifier name (used as .name in templates)
            func: Function that transforms text
        """
        self.modifiers[name] = func

    def set_vault_context(self, ctx: VaultContext) -> None:
        """Set vault context and pre-populate vault functions.

        Args:
            ctx: Vault context to use for $vault.* function calls
        """
        self.vault_context = ctx
        self._preprocess_vault_functions()

    def _preprocess_vault_functions(self) -> None:
        """Execute all $vault.* calls and expand symbol arrays.

        This pre-populates symbol arrays with vault function results before
        Tracery expansion begins, ensuring idiomatic Tracery behavior where
        each expansion independently samples from pre-populated arrays.
        """
        if self._preprocessed or not self.vault_context:
            return

        try:
            # Pattern to match $vault.function_name(args)
            pattern = r"\$vault\.([a-z_]+)\(([^)]*)\)"

            for symbol, rules in list(self.grammar.items()):
                expanded_rules: List[str] = []

                for rule in rules:
                    # Check if this rule is a vault function call
                    match = re.fullmatch(pattern, rule.strip())

                    if match:
                        # Execute vault function
                        func_name = match.group(1)
                        args_str = match.group(2).strip()

                        # Parse arguments
                        args = []
                        if args_str:
                            raw_args = [arg.strip().strip("\"'") for arg in args_str.split(",")]
                            args = [self._convert_arg(arg) for arg in raw_args]

                        # Call function and get results
                        result = self.vault_context.call_function(func_name, *args)

                        # If result is a list, expand into multiple rules
                        if isinstance(result, list):
                            expanded_rules.extend([str(item) for item in result])
                        else:
                            expanded_rules.append(str(result))
                    else:
                        # Static rule, keep as-is
                        expanded_rules.append(rule)

                # Replace symbol's rules with expanded version
                self.grammar[symbol] = expanded_rules

            self._preprocessed = True

        except Exception as e:
            logger.error(f"Vault function pre-population failed: {e}")
            self._prepopulation_failed = True

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

        return expanded

    def _expand_symbol(self, symbol: str, depth: int) -> str:
        """Expand a single symbol with optional modifiers.

        Supports syntax: symbol.modifier1.modifier2
        For example: animal.s.capitalize -> pluralize then capitalize

        Args:
            symbol: Symbol name with optional .modifiers
            depth: Current recursion depth

        Returns:
            Expanded and modified text
        """
        # Split symbol and modifiers
        parts = symbol.split(".")
        symbol_name = parts[0]
        modifier_names = parts[1:] if len(parts) > 1 else []

        # Check if symbol exists in grammar
        if symbol_name not in self.grammar:
            return f"#{symbol}#"  # Return unchanged if not in grammar

        rules = self.grammar[symbol_name]
        if not rules:
            return ""

        # Select random rule
        selected = self.rng.choice(rules)

        # Recursively expand the selected rule
        expanded = self.expand(selected, depth)

        # Apply modifiers in order
        result = expanded
        for modifier_name in modifier_names:
            if modifier_name in self.modifiers:
                result = self.modifiers[modifier_name](result)
            else:
                # Unknown modifier - leave as-is or could warn
                pass

        return result

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
            assert self.vault_context is not None  # Type narrowing for mypy
            result = self.vault_context.call_function(func_name, *args)

            # Format result for text
            if isinstance(result, list):
                # Join list items
                return self._format_list(result)
            else:
                return str(result)

        return re.sub(pattern, replace_function, text)

    def _format_list(self, items: List[Any]) -> str:
        """Format a list of primitive types for text output.

        TraceryEngine is a template layer that only knows about strings and
        numbers. Vault functions (adapter layer) convert domain objects to
        strings before returning them.

        Args:
            items: List of strings or numbers

        Returns:
            Formatted string representation
        """
        if not items:
            return ""

        # Convert all items to strings
        strings = [str(item) for item in items]

        # Format nicely for natural language
        if len(strings) == 1:
            return strings[0]
        elif len(strings) == 2:
            return f"{strings[0]} and {strings[1]}"
        else:
            return ", ".join(strings[:-1]) + f", and {strings[-1]}"


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

        # If preprocessing failed, return empty suggestions
        if self.engine._prepopulation_failed:
            logger.error(f"Geist {self.geist_id}: returning empty suggestions due to preprocessing failure")
            return []

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
                logger.warning(f"Tracery expansion failed for {self.geist_id}: {e}")
                continue

        return suggestions


class TraceryGeistLoader:
    """Loads Tracery geists from a directory."""

    def __init__(
        self,
        geists_dir: Path,
        seed: int | None = None,
        default_geists_dir: Path | None = None,
        enabled_defaults: Dict[str, bool] | None = None,
    ):
        """Initialize loader.

        Args:
            geists_dir: Directory containing custom .yaml geist files
            seed: Random seed for deterministic expansion
            default_geists_dir: Directory containing default geists (optional)
            enabled_defaults: Dictionary of default geist enabled states (optional)
        """
        self.geists_dir = geists_dir
        self.seed = seed
        self.default_geists_dir = default_geists_dir
        self.enabled_defaults = enabled_defaults or {}

    def load_all(self) -> List[TraceryGeist]:
        """Load all Tracery geists from directories.

        Loads default geists first (if configured), then custom geists.

        Returns:
            List of loaded TraceryGeist instances
        """
        geists = []

        # Load default geists first
        if self.default_geists_dir and self.default_geists_dir.exists():
            geists.extend(self._load_from_directory(self.default_geists_dir, is_default=True))

        # Load custom geists
        if self.geists_dir.exists():
            geists.extend(self._load_from_directory(self.geists_dir, is_default=False))

        return geists

    def _load_from_directory(self, directory: Path, is_default: bool = False) -> List[TraceryGeist]:
        """Load Tracery geists from a specific directory.

        Args:
            directory: Directory containing .yaml geist files
            is_default: Whether these are default geists

        Returns:
            List of loaded TraceryGeist instances
        """
        geists = []
        for yaml_file in directory.glob("*.yaml"):
            geist_id = yaml_file.stem

            # For default geists, check if they're enabled in config
            if is_default and not self.enabled_defaults.get(geist_id, True):
                continue  # Skip disabled default geists

            try:
                geist = TraceryGeist.from_yaml(yaml_file, self.seed)
                geists.append(geist)
            except Exception as e:
                logger.warning(f"Failed to load Tracery geist {yaml_file}: {e}")
                continue

        return geists
