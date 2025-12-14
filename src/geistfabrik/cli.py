"""GeistFabrik command-line interface.

This module provides the main CLI entry point for GeistFabrik. It uses the
Command pattern to dispatch to individual command classes in the commands/
package.
"""

import argparse
import sys
from typing import Type

from .commands import (
    BaseCommand,
    InitCommand,
    InvokeCommand,
    StatsCommand,
    TestAllCommand,
    TestCommand,
    ValidateCommand,
    find_vault_root,
)
from .default_geists import TOTAL_GEIST_COUNT

# Re-export for backward compatibility
__all__ = ["find_vault_root", "main"]


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the CLI.

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="geistfabrik",
        description="A divergence engine for Obsidian vaults",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Lifecycle: Setup -> Preview -> Write
  geistfabrik init ~/my-vault          # [1] Initialise ({TOTAL_GEIST_COUNT} geists bundled)
  geistfabrik invoke ~/my-vault        # [2] Preview suggestions
  geistfabrik invoke ~/my-vault --write  # [3] Write to journal

  # Advanced usage
  geistfabrik invoke ~/my-vault --geist drift   # Run specific geist
  geistfabrik invoke ~/my-vault --full          # All filtered suggestions
  geistfabrik invoke ~/my-vault --date 2025-01-15  # Replay session
  geistfabrik test my_geist ~/my-vault          # Test geist during development
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Init command
    _add_init_parser(subparsers)

    # Invoke command
    _add_invoke_parser(subparsers)

    # Test command
    _add_test_parser(subparsers)

    # Test-all command
    _add_test_all_parser(subparsers)

    # Stats command
    _add_stats_parser(subparsers)

    # Validate command
    _add_validate_parser(subparsers)

    return parser


def _add_init_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the init subparser."""
    init_parser = subparsers.add_parser(
        "init",
        help="[Step 1] Initialise GeistFabrik in a vault (creates _geistfabrik/ directory)",
    )
    init_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Reinitialize even if _geistfabrik directory exists",
    )


def _add_invoke_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the invoke subparser."""
    invoke_parser = subparsers.add_parser(
        "invoke",
        help=(
            "[Step 2] Run geists and generate suggestions "
            "(preview mode by default, use --write to save)"
        ),
    )
    invoke_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    invoke_parser.add_argument(
        "--geist",
        type=str,
        help="Run specific geist by ID (e.g., temporal_drift)",
    )
    invoke_parser.add_argument(
        "--geists",
        type=str,
        help="Run multiple specific geists by ID, comma-separated (e.g., drift,columbo,skeptic)",
    )
    invoke_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    invoke_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Geist execution timeout in seconds (default: 30)",
    )
    invoke_parser.add_argument(
        "--full",
        action="store_true",
        help="Show all filtered suggestions (no sampling, filtering still applies)",
    )
    invoke_parser.add_argument(
        "--no-filter",
        action="store_true",
        dest="no_filter",
        help="Skip filtering pipeline (raw output from all geists)",
    )
    invoke_parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of suggestions to select in default mode (default: 5)",
    )
    invoke_parser.add_argument(
        "--write",
        action="store_true",
        help=(
            "Write suggestions to journal note at <vault>/geist journal/YYYY-MM-DD.md "
            "(default: preview only)"
        ),
    )
    invoke_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing session note (use with --write)",
    )
    invoke_parser.add_argument(
        "--diff",
        action="store_true",
        help="Show what changed since last session",
    )
    invoke_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution information",
    )
    invoke_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable performance profiling and diagnostic output for geist execution",
    )
    invoke_parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress non-essential output (only show suggestions)",
    )


def _add_test_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the test subparser."""
    test_parser = subparsers.add_parser(
        "test",
        help="[Debug] Test a single geist in isolation",
    )
    test_parser.add_argument(
        "geist_id",
        type=str,
        help="ID of the geist to test",
    )
    test_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    test_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    test_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Geist execution timeout in seconds (default: 30)",
    )
    test_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution information",
    )
    test_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable performance profiling and diagnostic output",
    )


def _add_test_all_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the test-all subparser."""
    test_all_parser = subparsers.add_parser(
        "test-all",
        help="[Debug] Test all geists and report results",
    )
    test_all_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    test_all_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    test_all_parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Geist execution timeout in seconds (default: 30)",
    )
    test_all_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed execution information",
    )
    test_all_parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable performance profiling and diagnostic output",
    )


def _add_stats_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the stats subparser."""
    stats_parser = subparsers.add_parser(
        "stats",
        help="Show vault statistics and health metrics",
    )
    stats_parser.add_argument(
        "vault",
        type=str,
        nargs="?",
        help="Path to Obsidian vault (optional, auto-detects from current directory)",
    )
    stats_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed statistics and breakdowns",
    )
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON for scripting",
    )
    stats_parser.add_argument(
        "--history",
        type=int,
        default=30,
        help="Days of session history to analyze (default: 30)",
    )


def _add_validate_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Add the validate subparser."""
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate geist files for errors without executing them",
    )
    validate_parser.add_argument(
        "vault",
        type=str,
        nargs="?",
        help="Path to Obsidian vault (optional, auto-detects from current directory)",
    )
    validate_parser.add_argument(
        "--geist",
        type=str,
        help="Validate specific geist by ID",
    )
    validate_parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    validate_parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    validate_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed validation information",
    )


# Command registry mapping command names to their classes
# Using a concrete type for each command to avoid abstract instantiation issues
COMMANDS: dict[str, Type[BaseCommand]] = {
    "init": InitCommand,
    "invoke": InvokeCommand,
    "test": TestCommand,
    "test-all": TestAllCommand,
    "stats": StatsCommand,
    "validate": ValidateCommand,
}


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    parser = create_parser()
    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 1

    # Get command class from registry
    command_class = COMMANDS.get(args.command)
    if command_class is None:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        return 1

    # Create and run the command
    command = command_class(args)
    return command.run()


if __name__ == "__main__":
    sys.exit(main())
