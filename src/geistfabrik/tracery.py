"""Tracery grammar support for GeistFabrik.

Implements a Tracery-like grammar system for declarative geist definitions.
Supports symbol expansion, modifiers, and vault function calls.
"""

import logging
import random
import re
import time
from collections.abc import Callable
from pathlib import Path

from .bounded_yaml import load_bounded_yaml
from .config import (
    DEFAULT_GEIST_TIMEOUT,
    MAX_TRACERY_COUNT,
    MAX_TRACERY_EXPANSIONS,
    MAX_TRACERY_OUTPUT_BYTES,
    MAX_TRACERY_PREPROCESSED_BYTES,
    MAX_TRACERY_RULE_BYTES,
    MAX_TRACERY_RULES,
    MAX_TRACERY_RULES_PER_SYMBOL,
    MAX_TRACERY_SYMBOLS,
    MAX_TRACERY_VAULT_CALLS,
    MAX_TRACERY_VAULT_ITEMS,
)
from .models import Suggestion
from .path_safety import ensure_contained
from .vault_context import VaultContext

logger = logging.getLogger(__name__)


class TraceryExecutionError(RuntimeError):
    """Raised when a Tracery invocation fails."""


class TraceryLimitError(TraceryExecutionError):
    """Raised when a grammar exceeds an invocation resource limit."""


class TraceryEngine:
    """Simple Tracery grammar engine with vault function support."""

    def __init__(self, grammar: dict[str, list[str]], seed: int | None = None):
        """Initialise Tracery engine.

        Args:
            grammar: Dictionary mapping symbols to expansion rules
            seed: Random seed for deterministic expansion
        """
        self.grammar = grammar
        self.rng = random.Random(seed)
        self.vault_context: VaultContext | None = None
        self.max_depth = 50
        self.modifiers: dict[str, Callable[[str], str]] = self._default_modifiers()
        self._preprocessed = False  # Track if pre-population done
        self._prepopulation_failed = False  # Track if pre-population failed
        self._has_empty_symbols = False  # Track if any symbols have empty arrays
        self.deadline = 0.0
        self.expansions_remaining = MAX_TRACERY_EXPANSIONS
        self.vault_calls_remaining = MAX_TRACERY_VAULT_CALLS
        self.vault_items_remaining = MAX_TRACERY_VAULT_ITEMS

    def begin_invocation(self, timeout: int) -> None:
        """Reset cooperative per-invocation budgets."""
        self.deadline = time.monotonic() + timeout
        self.expansions_remaining = MAX_TRACERY_EXPANSIONS
        self.vault_calls_remaining = MAX_TRACERY_VAULT_CALLS
        self.vault_items_remaining = MAX_TRACERY_VAULT_ITEMS

    def _consume(self, kind: str, amount: int = 1) -> None:
        if self.deadline and time.monotonic() > self.deadline:
            raise TraceryLimitError("Tracery cooperative deadline exceeded")
        if kind == "expansion":
            self.expansions_remaining -= amount
            remaining = self.expansions_remaining
        elif kind == "vault_call":
            self.vault_calls_remaining -= amount
            remaining = self.vault_calls_remaining
        else:
            self.vault_items_remaining -= amount
            remaining = self.vault_items_remaining
        if remaining < 0:
            raise TraceryLimitError(f"Tracery {kind} budget exceeded")

    def _default_modifiers(self) -> dict[str, Callable[[str], str]]:
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
            "split_seed": self._split_seed,
            "split_neighbours": self._split_neighbours,
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
        if text.lower().startswith(("honest", "hour", "honour", "heir")):
            article = "an"
        elif text.lower().startswith("uni"):
            article = "a"  # 'university', 'unique' etc. have 'yoo' sound
        elif first_char in "aeiou":
            article = "an"
        else:
            article = "a"

        return f"{article} {text}"

    def _split_seed(self, text: str) -> str:
        """Extract seed part from delimited semantic cluster string.

        Args:
            text: Formatted cluster string "SEED|||NEIGHBOURS"

        Returns:
            The seed part (before delimiter)
        """
        if "|||" in text:
            return text.split("|||")[0]
        return text

    def _split_neighbours(self, text: str) -> str:
        """Extract neighbours part from delimited semantic cluster string.

        Args:
            text: Formatted cluster string "SEED|||NEIGHBOURS"

        Returns:
            The neighbours part (after delimiter)
        """
        if "|||" in text:
            parts = text.split("|||")
            return parts[1] if len(parts) > 1 else ""
        return ""

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
        """Transactionally pre-populate grammar rules from vault functions."""
        if self._preprocessed or not self.vault_context:
            return
        pattern = r"\$vault\.([a-z_]+)\(([^)]*)\)"
        new_grammar: dict[str, list[str]] = {}
        has_empty = False
        preprocessed_bytes = 0

        def append_rule(rules: list[str], value: object) -> None:
            nonlocal preprocessed_bytes
            text = str(value)
            size = len(text.encode("utf-8"))
            if size > MAX_TRACERY_RULE_BYTES:
                raise TraceryLimitError(
                    f"Preprocessed Tracery rule exceeds {MAX_TRACERY_RULE_BYTES} bytes"
                )
            preprocessed_bytes += size
            if preprocessed_bytes > MAX_TRACERY_PREPROCESSED_BYTES:
                raise TraceryLimitError(
                    f"Preprocessed Tracery grammar exceeds {MAX_TRACERY_PREPROCESSED_BYTES} bytes"
                )
            rules.append(text)

        try:
            for symbol, rules in self.grammar.items():
                expanded_rules: list[str] = []
                for rule in rules:
                    match = re.fullmatch(pattern, rule.strip())
                    if not match:
                        append_rule(expanded_rules, rule)
                        continue
                    self._consume("vault_call")
                    func_name = match.group(1)
                    args_str = match.group(2).strip()
                    args: list[int | str] = []
                    if args_str:
                        raw_args = [arg.strip().strip("\"'") for arg in args_str.split(",")]
                        args = [self._convert_arg(arg) for arg in raw_args]
                    result = self.vault_context.call_function(func_name, *args)
                    if isinstance(result, list):
                        self._consume("vault_item", len(result))
                        if not result:
                            has_empty = True
                        for item in result:
                            append_rule(expanded_rules, item)
                    else:
                        self._consume("vault_item")
                        append_rule(expanded_rules, result)
                new_grammar[symbol] = expanded_rules
        except TraceryLimitError:
            raise
        except Exception as exc:
            raise TraceryExecutionError(
                f"Vault function preprocessing failed: {type(exc).__name__}: {exc}"
            ) from exc
        self.grammar = new_grammar
        self._has_empty_symbols = has_empty
        self._preprocessed = True

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
        self._consume("expansion")
        if depth > self.max_depth:
            raise TraceryLimitError(f"Tracery expansion exceeded max depth ({self.max_depth})")

        # Expand incrementally so amplification is rejected before a large
        # intermediate string is allocated.
        pattern = r"#([^#]+)#"
        pieces: list[str] = []
        output_bytes = 0
        cursor = 0

        def append_piece(piece: str) -> None:
            nonlocal output_bytes
            output_bytes += len(piece.encode("utf-8"))
            if output_bytes > MAX_TRACERY_OUTPUT_BYTES:
                raise TraceryLimitError(f"Tracery output exceeds {MAX_TRACERY_OUTPUT_BYTES} bytes")
            pieces.append(piece)

        for match in re.finditer(pattern, text):
            append_piece(text[cursor : match.start()])
            append_piece(self._expand_symbol(match.group(1), depth + 1))
            cursor = match.end()
        append_piece(text[cursor:])
        return "".join(pieces)

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
                if len(result.encode("utf-8")) > MAX_TRACERY_OUTPUT_BYTES:
                    raise TraceryLimitError(
                        f"Tracery output exceeds {MAX_TRACERY_OUTPUT_BYTES} bytes"
                    )
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


class TraceryGeist:
    """A geist defined via Tracery grammar."""

    def __init__(
        self,
        geist_id: str,
        grammar: dict[str, list[str]],
        count: int = 1,
        seed: int | None = None,
        yaml_path: Path | None = None,
    ):
        """Initialise Tracery geist.

        Args:
            geist_id: Unique identifier for this geist
            grammar: Tracery grammar dictionary
            count: Number of suggestions to generate per invocation
            seed: Random seed for deterministic expansion
        """
        self.geist_id = geist_id
        self.engine = TraceryEngine(grammar, seed)
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= MAX_TRACERY_COUNT
        ):
            raise ValueError(f"Tracery count must be an integer in [1, {MAX_TRACERY_COUNT}]")
        self.count = count
        self.yaml_path = yaml_path or Path(f"{geist_id}.yaml")
        self.execution_timeout = DEFAULT_GEIST_TIMEOUT

    @staticmethod
    def _normalise_grammar(grammar: object, geist_id: str, yaml_path: Path) -> dict[str, list[str]]:
        if not isinstance(grammar, dict):
            raise ValueError(f"Tracery grammar must be a mapping in {yaml_path}")
        if len(grammar) > MAX_TRACERY_SYMBOLS:
            raise ValueError(f"Tracery grammar exceeds {MAX_TRACERY_SYMBOLS} symbols")
        normalised: dict[str, list[str]] = {}
        total_rules = 0
        for symbol, raw_rules in grammar.items():
            if not isinstance(symbol, str) or not symbol or len(symbol) > 256:
                raise ValueError(f"Invalid Tracery symbol in {yaml_path}: {symbol!r}")
            rules = [raw_rules] if isinstance(raw_rules, str) else raw_rules
            if not isinstance(rules, list) or any(not isinstance(rule, str) for rule in rules):
                raise ValueError(f"Rules for '{symbol}' must be a string or list of strings")
            if len(rules) > MAX_TRACERY_RULES_PER_SYMBOL:
                raise ValueError(f"Symbol '{symbol}' exceeds {MAX_TRACERY_RULES_PER_SYMBOL} rules")
            for rule in rules:
                if len(rule.encode("utf-8")) > MAX_TRACERY_RULE_BYTES:
                    raise ValueError(f"Rule for '{symbol}' exceeds {MAX_TRACERY_RULE_BYTES} bytes")
            total_rules += len(rules)
            if total_rules > MAX_TRACERY_RULES:
                raise ValueError(f"Tracery grammar exceeds {MAX_TRACERY_RULES} total rules")
            normalised[symbol] = list(rules)
        if "origin" not in normalised:
            raise ValueError(f"Missing origin symbol in {yaml_path} for geist {geist_id}")
        return normalised

    @staticmethod
    def _validate_grammar(grammar: dict[str, list[str]], geist_id: str, yaml_path: Path) -> None:
        """Validate Tracery grammar for common anti-patterns.

        Args:
            grammar: Tracery grammar dictionary
            geist_id: Geist identifier (for error messages)
            yaml_path: Path to YAML file (for error messages)

        Raises:
            ValueError: If anti-patterns are detected
        """
        # Pattern to detect vault function calls with Tracery symbol arguments
        # Matches: $vault.func(#symbol#, ...) or $vault.func(..., #symbol#)
        unsafe_pattern = r"\$vault\.\w+\([^)]*#\w+#[^)]*\)"

        for symbol, rules in grammar.items():
            for rule in rules:
                if not isinstance(rule, str):
                    continue

                # Check for unsafe vault function patterns
                if re.search(unsafe_pattern, rule):
                    # Extract the problematic function call
                    match = re.search(r"(\$vault\.\w+\([^)]+\))", rule)
                    func_call = match.group(1) if match else rule

                    raise ValueError(
                        f"Unsafe vault function pattern in {yaml_path}\n"
                        f"  → Geist: {geist_id}\n"
                        f"  → Symbol: {symbol}\n"
                        f"  → Pattern: {func_call}\n"
                        f"  → Problem: Cannot pass Tracery symbols (#symbol#) to vault functions\n"
                        f"  → Reason: Vault functions execute during preprocessing, "
                        f"before symbol expansion\n"
                        f"  → Solution: Use 'cluster' functions that bundle related data\n"
                        f"  → Example: $vault.semantic_clusters(2, 3) with "
                        f".split_seed/.split_neighbours modifiers\n"
                        f"  → See: specs/tracery_research.md "
                        f"(Designing Tracery-Safe Vault Functions)"
                    )

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
        ensure_contained(yaml_path, yaml_path.parent, must_exist=True, reject_symlinks=True)
        data = load_bounded_yaml(yaml_path)
        if not isinstance(data, dict):
            raise ValueError(f"Tracery YAML root must be a mapping: {yaml_path}")

        if data.get("type") != "geist-tracery":
            raise ValueError(
                f"Invalid geist type in {yaml_path}: '{data.get('type')}'\n"
                f"  → Expected: type: geist-tracery\n"
                f"  → Got: type: {data.get('type')}\n"
                f"  → Fix the YAML file to use the correct type"
            )

        geist_id = data.get("id")
        if not isinstance(geist_id, str) or not geist_id or len(geist_id) > 256:
            raise ValueError(f"Tracery geist id must be a non-empty string in {yaml_path}")
        count = data.get("count", 1)
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or not 1 <= count <= MAX_TRACERY_COUNT
        ):
            raise ValueError(f"Tracery count must be an integer in [1, {MAX_TRACERY_COUNT}]")
        grammar = cls._normalise_grammar(data.get("tracery"), geist_id, yaml_path)
        cls._validate_grammar(grammar, geist_id, yaml_path)

        return cls(geist_id, grammar, count, seed, yaml_path)

    def suggest(self, vault: VaultContext) -> list[Suggestion]:
        """Generate suggestions using Tracery grammar.

        Args:
            vault: Vault context for function calls

        Returns:
            List of generated suggestions
        """
        self.engine.begin_invocation(self.execution_timeout)
        self.engine.set_vault_context(vault)

        # If any symbols have empty arrays, don't generate suggestions
        if self.engine._has_empty_symbols:
            logger.debug(f"Geist {self.geist_id}: skipping suggestions due to empty symbol arrays")
            return []

        suggestions = []
        for _ in range(self.count):
            # Expand the origin symbol. Any broken expansion fails the whole
            # invocation so the shared executor can account for it.
            text = self.engine.expand("#origin#")
            if len(text.encode("utf-8")) > MAX_TRACERY_OUTPUT_BYTES:
                raise TraceryLimitError(f"Tracery output exceeds {MAX_TRACERY_OUTPUT_BYTES} bytes")

            if self._has_empty_placeholder(text):
                continue
            note_refs = re.findall(r"\[\[([^\]]+)\]\]", text)
            suggestions.append(Suggestion(text=text, notes=note_refs, geist_id=self.geist_id))

        return suggestions

    def _has_empty_placeholder(self, text: str) -> bool:
        """Check if text has empty placeholders from failed symbol expansion.

        Detects patterns like:
        - Double spaces: "word  word"
        - Space before punctuation: "word . "
        - Missing content: "through . Is"

        Args:
            text: Expanded text to check

        Returns:
            True if text has empty placeholders
        """
        # Check for double spaces (common sign of empty expansion)
        if "  " in text:
            return True

        # Check for space before common punctuation
        if " ." in text or " ," in text or " !" in text or " ?" in text:
            return True

        # Check for punctuation preceded by space (e.g., "word . word")
        # This catches patterns like "through . Is"
        patterns = [
            r"\s+\.\s+[A-Z]",  # Space, period, space, capital letter
            r"\s+,\s+[A-Z]",  # Space, comma, space, capital letter
        ]
        for pattern in patterns:
            if re.search(pattern, text):
                return True

        return False


class TraceryGeistLoader:
    """Loads Tracery geists from a directory."""

    def __init__(
        self,
        geists_dir: Path,
        seed: int | None = None,
        default_geists_dir: Path | None = None,
        enabled_defaults: dict[str, bool] | None = None,
    ):
        """Initialise loader.

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
        self.newly_discovered: list[str] = []
        self.load_errors: list[dict[str, str]] = []

    def load_all(self) -> tuple[list[TraceryGeist], list[str]]:
        """Load all Tracery geists from directories.

        Loads default geists first (if configured), then custom geists.
        Tracks any geists found on disk but not in config.

        Returns:
            Tuple of (loaded TraceryGeist instances, newly discovered geist IDs)
        """
        geists = []
        self.newly_discovered = []
        self.load_errors = []

        # Load default geists first
        if self.default_geists_dir and self.default_geists_dir.exists():
            geists.extend(self._load_from_directory(self.default_geists_dir, is_default=True))

        # Load custom geists
        if self.geists_dir.exists():
            geists.extend(self._load_from_directory(self.geists_dir, is_default=False))

        return geists, self.newly_discovered

    def _load_from_directory(self, directory: Path, is_default: bool = False) -> list[TraceryGeist]:
        """Load Tracery geists from a specific directory.

        Loads geists in config order if they're in config, alphabetically if not.
        Tracks newly discovered geists (not in config) for addition to config.

        Args:
            directory: Directory containing .yaml geist files
            is_default: Whether these are default geists

        Returns:
            List of loaded TraceryGeist instances in load order
        """
        geists = []

        # Find all .yaml files
        all_geist_files = {f.stem: f for f in directory.glob("*.yaml")}

        if self.enabled_defaults:
            # Load geists in config order (preserves user's ordering)
            # Python 3.7+ dicts maintain insertion order
            for geist_id in self.enabled_defaults.keys():
                if not self.enabled_defaults.get(geist_id, True):
                    continue  # Skip disabled geists

                yaml_file = all_geist_files.get(geist_id)
                if yaml_file is None:
                    continue  # Geist in config but not on disk

                try:
                    geist = TraceryGeist.from_yaml(yaml_file, self.seed)
                    geists.append(geist)
                except Exception as e:
                    self.load_errors.append(
                        {"geist_id": geist_id, "path": str(yaml_file), "error": str(e)}
                    )
                    logger.warning(
                        f"Failed to load Tracery geist from {yaml_file}\n"
                        f"  Error: {e}\n"
                        f"  → Check YAML syntax at {yaml_file}\n"
                        f"  → Validate: geistfabrik validate --geist {geist_id}"
                    )
                    continue

        # Load any geists found on disk but not in config (alphabetically)
        # These are "newly discovered" geists that should be added to config
        remaining_geists = sorted(
            geist_id for geist_id in all_geist_files.keys() if geist_id not in self.enabled_defaults
        )
        for geist_id in remaining_geists:
            self.newly_discovered.append(geist_id)
            try:
                geist = TraceryGeist.from_yaml(all_geist_files[geist_id], self.seed)
                geists.append(geist)
            except Exception as e:
                yaml_file = all_geist_files[geist_id]
                self.load_errors.append(
                    {"geist_id": geist_id, "path": str(yaml_file), "error": str(e)}
                )
                logger.warning(
                    f"Failed to load Tracery geist from {yaml_file}\n"
                    f"  Error: {e}\n"
                    f"  → Check YAML syntax at {yaml_file}\n"
                    f"  → Validate: geistfabrik validate --geist {geist_id}"
                )
                continue

        return geists
