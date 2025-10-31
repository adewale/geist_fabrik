"""Geist validation system for pre-flight checks."""

import importlib.util
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


@dataclass
class ValidationIssue:
    """A validation issue found in a geist."""

    severity: str  # "error", "warning", "info"
    message: str
    line_number: int | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a single geist."""

    geist_id: str
    file_path: Path
    geist_type: str  # "code" or "tracery"
    passed: bool
    issues: List[ValidationIssue]

    @property
    def has_errors(self) -> bool:
        """Check if result has any errors."""
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if result has any warnings."""
        return any(issue.severity == "warning" for issue in self.issues)


class GeistValidator:
    """Validates geists without executing them."""

    def __init__(self, strict: bool = False):
        """Initialize validator.

        Args:
            strict: If True, treat warnings as errors
        """
        self.strict = strict

    def validate_code_geist(self, geist_file: Path) -> ValidationResult:
        """Validate a code geist file.

        Args:
            geist_file: Path to Python geist file

        Returns:
            Validation result with any issues found
        """
        geist_id = geist_file.stem
        issues: List[ValidationIssue] = []

        # Check file is readable
        if not geist_file.exists():
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"File does not exist: {geist_file}",
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="code",
                passed=False,
                issues=issues,
            )

        # Try to load module
        try:
            spec = importlib.util.spec_from_file_location(geist_id, geist_file)
            if spec is None or spec.loader is None:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message="Could not create module spec (invalid Python file?)",
                        suggestion="Check for syntax errors with: python -m py_compile "
                        + str(geist_file),
                    )
                )
                return ValidationResult(
                    geist_id=geist_id,
                    file_path=geist_file,
                    geist_type="code",
                    passed=False,
                    issues=issues,
                )

            module = importlib.util.module_from_spec(spec)
            sys.modules[geist_id] = module
            spec.loader.exec_module(module)

        except SyntaxError as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Syntax error: {e.msg}",
                    line_number=e.lineno,
                    suggestion="Fix the syntax error at the indicated line",
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="code",
                passed=False,
                issues=issues,
            )
        except ImportError as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Import error: {str(e)}",
                    suggestion="Check that all required packages are installed",
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="code",
                passed=False,
                issues=issues,
            )
        except Exception as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Error loading module: {str(e)}",
                    suggestion="Run the geist with: geistfabrik test " + geist_id,
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="code",
                passed=False,
                issues=issues,
            )

        # Check for suggest() function
        if not hasattr(module, "suggest"):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Missing suggest() function",
                    suggestion=(
                        "Add this function to your geist:\n\n"
                        "def suggest(vault: VaultContext) -> List[Suggestion]:\n"
                        '    """Generate suggestions."""\n'
                        "    return []"
                    ),
                )
            )

        # Check function signature (warning only)
        if hasattr(module, "suggest"):
            suggest_func = getattr(module, "suggest")
            if not hasattr(suggest_func, "__annotations__"):
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message="suggest() function missing type hints",
                        suggestion=(
                            "Add type hints: def suggest(vault: VaultContext) -> List[Suggestion]:"
                        ),
                    )
                )

        # Check for docstring (warning only)
        if not module.__doc__:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message="Missing module docstring",
                    suggestion=(
                        'Add a docstring at the top: """Description of what this geist does."""'
                    ),
                )
            )

        # Clean up imported module
        if geist_id in sys.modules:
            del sys.modules[geist_id]

        passed = not self.has_blocking_issues(issues)
        return ValidationResult(
            geist_id=geist_id, file_path=geist_file, geist_type="code", passed=passed, issues=issues
        )

    def validate_tracery_geist(self, geist_file: Path) -> ValidationResult:
        """Validate a Tracery geist file.

        Args:
            geist_file: Path to YAML geist file

        Returns:
            Validation result with any issues found
        """
        geist_id = geist_file.stem
        issues: List[ValidationIssue] = []

        # Check file is readable
        if not geist_file.exists():
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"File does not exist: {geist_file}",
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="tracery",
                passed=False,
                issues=issues,
            )

        # Try to parse YAML
        try:
            with open(geist_file, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"YAML parsing error: {str(e)}",
                    suggestion="Check YAML syntax at yamllint.com or use a YAML validator",
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="tracery",
                passed=False,
                issues=issues,
            )

        # Validate required fields
        if not isinstance(data, dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="YAML file must contain a dictionary",
                )
            )
            return ValidationResult(
                geist_id=geist_id,
                file_path=geist_file,
                geist_type="tracery",
                passed=False,
                issues=issues,
            )

        # Check type field
        if data.get("type") != "geist-tracery":
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Invalid type field: {data.get('type')} (expected 'geist-tracery')",
                    suggestion="Add: type: geist-tracery",
                )
            )

        # Check id field
        if "id" not in data:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Missing 'id' field",
                    suggestion=f"Add: id: {geist_id}",
                )
            )
        elif data["id"] != geist_id:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"ID mismatch: filename is '{geist_id}' but id field is '{data['id']}'",
                    suggestion=f"Change id to: {geist_id}",
                )
            )

        # Check tracery grammar
        if "tracery" not in data:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="Missing 'tracery' grammar field",
                    suggestion="Add a tracery grammar dictionary",
                )
            )
        elif not isinstance(data["tracery"], dict):
            issues.append(
                ValidationIssue(
                    severity="error",
                    message="'tracery' field must be a dictionary",
                )
            )
        else:
            grammar = data["tracery"]
            # Check for origin symbol
            if "origin" not in grammar:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message="Missing 'origin' symbol in tracery grammar",
                        suggestion="Add: origin: '#yourtemplate#'",
                    )
                )

            # Check for undefined symbols (warning only)
            self._check_undefined_symbols(grammar, issues)

            # Check for vault function calls
            self._check_vault_functions(grammar, issues)

        # Check count field (optional)
        if "count" in data:
            count = data["count"]
            if not isinstance(count, int) or count < 1:
                issues.append(
                    ValidationIssue(
                        severity="error",
                        message=f"Invalid count value: {count} (must be positive integer)",
                    )
                )
            elif count > 10:
                issues.append(
                    ValidationIssue(
                        severity="warning",
                        message=f"High count value: {count} (consider using count <= 5)",
                        suggestion="Large counts may generate too many similar suggestions",
                    )
                )

        # Check for description field (warning if missing)
        if "description" not in data:
            issues.append(
                ValidationIssue(
                    severity="info",
                    message="Missing 'description' field (recommended for documentation)",
                    suggestion="Add: description: 'What this geist does'",
                )
            )

        passed = not self.has_blocking_issues(issues)
        return ValidationResult(
            geist_id=geist_id,
            file_path=geist_file,
            geist_type="tracery",
            passed=passed,
            issues=issues,
        )

    def _check_undefined_symbols(
        self, grammar: Dict[str, Any], issues: List[ValidationIssue]
    ) -> None:
        """Check for undefined symbol references in grammar.

        Args:
            grammar: Tracery grammar dictionary
            issues: List to append issues to
        """
        # Find all symbol references in rules
        symbol_pattern = r"#([a-zA-Z_][a-zA-Z0-9_]*)#"
        referenced_symbols = set()
        defined_symbols = set(grammar.keys())

        for symbol, rules in grammar.items():
            if isinstance(rules, list):
                for rule in rules:
                    if isinstance(rule, str):
                        matches = re.findall(symbol_pattern, rule)
                        referenced_symbols.update(matches)
            elif isinstance(rules, str):
                matches = re.findall(symbol_pattern, rules)
                referenced_symbols.update(matches)

        # Check for undefined symbols
        undefined = referenced_symbols - defined_symbols
        if undefined:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    message=f"Undefined symbols referenced: {', '.join(sorted(undefined))}",
                    suggestion="Define these symbols or check for typos",
                )
            )

    def _check_vault_functions(
        self, grammar: Dict[str, Any], issues: List[ValidationIssue]
    ) -> None:
        """Check for vault function calls in grammar.

        Args:
            grammar: Tracery grammar dictionary
            issues: List to append issues to
        """
        vault_func_pattern = r"\$vault\.([a-z_]+)\("

        for symbol, rules in grammar.items():
            rules_list = rules if isinstance(rules, list) else [rules]
            for rule in rules_list:
                if isinstance(rule, str):
                    matches = re.findall(vault_func_pattern, rule)
                    if matches:
                        # Just note the usage (we can't validate function exists without context)
                        for func_name in matches:
                            issues.append(
                                ValidationIssue(
                                    severity="info",
                                    message=f"Uses vault function: $vault.{func_name}()",
                                    suggestion="Ensure this function exists in your vault",
                                )
                            )

    def has_blocking_issues(self, issues: List[ValidationIssue]) -> bool:
        """Check if issues list contains blocking problems.

        Args:
            issues: List of validation issues

        Returns:
            True if there are errors (or warnings in strict mode)
        """
        if self.strict:
            # In strict mode, warnings are also blocking
            return any(issue.severity in ["error", "warning"] for issue in issues)
        else:
            # Normally, only errors are blocking
            return any(issue.severity == "error" for issue in issues)

    def validate_all(
        self, code_dir: Path | None, tracery_dir: Path | None
    ) -> List[ValidationResult]:
        """Validate all geists in the specified directories.

        Args:
            code_dir: Directory containing code geists (optional)
            tracery_dir: Directory containing Tracery geists (optional)

        Returns:
            List of validation results for all geists found
        """
        results: List[ValidationResult] = []

        # Validate code geists
        if code_dir and code_dir.exists():
            for geist_file in sorted(code_dir.glob("*.py")):
                if geist_file.name == "__init__.py":
                    continue
                result = self.validate_code_geist(geist_file)
                results.append(result)

        # Validate Tracery geists
        if tracery_dir and tracery_dir.exists():
            for geist_file in sorted(tracery_dir.glob("*.yaml")):
                result = self.validate_tracery_geist(geist_file)
                results.append(result)

        return results
