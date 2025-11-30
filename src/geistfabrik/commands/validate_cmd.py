"""Validate command for checking geist files for errors."""

import json
from pathlib import Path

from ..validator import GeistValidator, ValidationResult
from .base import BaseCommand


class ValidateCommand(BaseCommand):
    """Command to validate geist files for errors without executing them.

    Checks both code and Tracery geists for syntax errors, missing fields,
    and other issues.
    """

    def execute(self) -> int:
        """Execute the validate command.

        Returns:
            Exit code (0 for success, 1 for errors found)
        """
        # Find vault path (supports auto-detection)
        vault_path = self._get_vault_path()
        if vault_path is None:
            return 1

        # Check if vault is initialised
        geistfabrik_dir = vault_path / "_geistfabrik"
        if not geistfabrik_dir.exists():
            self.print_error(f"GeistFabrik not initialised in {vault_path}")
            print(f"Run: geistfabrik init {vault_path}")
            return 1

        # Set up directories
        code_dir = geistfabrik_dir / "geists" / "code"
        tracery_dir = geistfabrik_dir / "geists" / "tracery"

        # Get default geists directories
        package_dir = Path(__file__).parent.parent
        default_code_dir = package_dir / "default_geists" / "code"
        default_tracery_dir = package_dir / "default_geists" / "tracery"

        # Initialise validator
        strict = getattr(self.args, "strict", False)
        validator = GeistValidator(strict=strict)

        # Validate geists
        results = self._validate_geists(
            validator,
            code_dir,
            tracery_dir,
            default_code_dir,
            default_tracery_dir,
        )

        # Format and display output
        output_format = getattr(self.args, "format", "text")
        if output_format == "json":
            self._output_json(results)
        else:
            self._output_text(results, vault_path)

        # Return exit code based on results
        if any(not r.passed for r in results):
            return 1
        return 0

    def _get_vault_path(self) -> Path | None:
        """Get vault path from args or auto-detect.

        Returns:
            Vault path, or None if not found
        """
        if hasattr(self.args, "vault") and self.args.vault:
            vault_path = Path(self.args.vault).resolve()
            if not self.validate_vault_path(vault_path):
                return None
            return vault_path

        # Auto-detect vault
        detected_path = self.find_vault_root()
        if detected_path is None:
            self.print_error("No vault specified and could not auto-detect vault.")
            print("Either run from within a vault or specify vault path.")
            return None
        return detected_path

    def _validate_geists(
        self,
        validator: GeistValidator,
        code_dir: Path,
        tracery_dir: Path,
        default_code_dir: Path,
        default_tracery_dir: Path,
    ) -> list[ValidationResult]:
        """Validate geists based on arguments.

        Args:
            validator: The geist validator
            code_dir: Custom code geists directory
            tracery_dir: Custom Tracery geists directory
            default_code_dir: Default code geists directory
            default_tracery_dir: Default Tracery geists directory

        Returns:
            List of validation results
        """
        # Check if validating specific geist
        if hasattr(self.args, "geist") and self.args.geist:
            return self._validate_specific_geist(
                validator,
                self.args.geist,
                code_dir,
                tracery_dir,
                default_code_dir,
                default_tracery_dir,
            )

        # Validate all geists
        results: list[ValidationResult] = []
        # Custom geists
        results.extend(validator.validate_all(code_dir, tracery_dir))
        # Default geists
        results.extend(validator.validate_all(default_code_dir, default_tracery_dir))
        return results

    def _validate_specific_geist(
        self,
        validator: GeistValidator,
        geist_id: str,
        code_dir: Path,
        tracery_dir: Path,
        default_code_dir: Path,
        default_tracery_dir: Path,
    ) -> list[ValidationResult]:
        """Validate a specific geist.

        Args:
            validator: The geist validator
            geist_id: ID of the geist to validate
            code_dir: Custom code geists directory
            tracery_dir: Custom Tracery geists directory
            default_code_dir: Default code geists directory
            default_tracery_dir: Default Tracery geists directory

        Returns:
            List containing the validation result
        """
        # Check all possible locations
        code_file = code_dir / f"{geist_id}.py"
        default_code_file = default_code_dir / f"{geist_id}.py"
        tracery_file = tracery_dir / f"{geist_id}.yaml"
        default_tracery_file = default_tracery_dir / f"{geist_id}.yaml"

        if code_file.exists():
            return [validator.validate_code_geist(code_file)]
        elif default_code_file.exists():
            return [validator.validate_code_geist(default_code_file)]
        elif tracery_file.exists():
            return [validator.validate_tracery_geist(tracery_file)]
        elif default_tracery_file.exists():
            return [validator.validate_tracery_geist(default_tracery_file)]
        else:
            self.print_error(f"Geist '{geist_id}' not found")
            return []

    def _output_json(self, results: list[ValidationResult]) -> None:
        """Output results as JSON.

        Args:
            results: Validation results
        """
        output = {
            "total": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "geists": [
                {
                    "id": r.geist_id,
                    "type": r.geist_type,
                    "path": str(r.file_path),
                    "passed": r.passed,
                    "issues": [
                        {
                            "severity": i.severity,
                            "message": i.message,
                            "line": i.line_number,
                            "suggestion": i.suggestion,
                        }
                        for i in r.issues
                    ],
                }
                for r in results
            ],
        }
        print(json.dumps(output, indent=2))

    def _output_text(self, results: list[ValidationResult], vault_path: Path) -> None:
        """Output results as human-readable text.

        Args:
            results: Validation results
            vault_path: Path to the vault
        """
        print(f"Validating geists in {vault_path}/_geistfabrik/geists/...\n")

        for result in results:
            if result.passed:
                print(f"v {result.geist_type}/{result.geist_id}")
                if result.has_warnings or self.verbose:
                    for issue in result.issues:
                        if issue.severity == "info":
                            print(f"   i  {issue.message}")
                        elif issue.severity == "warning":
                            print(f"   !  {issue.message}")
            else:
                print(f"x {result.geist_type}/{result.geist_id}")
                for issue in result.issues:
                    if issue.severity == "error":
                        if issue.line_number:
                            print(f"   Line {issue.line_number}: {issue.message}")
                        else:
                            print(f"   {issue.message}")
                        if issue.suggestion and (
                            self.verbose or len(result.issues) <= 3
                        ):
                            print(f"      -> {issue.suggestion}")
                    elif issue.severity == "warning":
                        print(f"   !  {issue.message}")

            print()

        # Summary
        passed = sum(1 for r in results if r.passed)
        errors = sum(1 for r in results if r.has_errors)
        warnings = sum(1 for r in results if r.has_warnings and not r.has_errors)

        print("-" * 60)
        print(f"Summary: {passed} passed, {errors} errors, {warnings} warnings")
        print("-" * 60)
