"""GeistFabrik command-line interface."""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .embeddings import Session
from .geist_executor import GeistExecutor
from .vault import Vault
from .vault_context import VaultContext


def find_vault_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find vault root by looking for .obsidian directory.

    Args:
        start_path: Directory to start search from (defaults to current dir)

    Returns:
        Path to vault root, or None if not found
    """
    if start_path is None:
        start_path = Path.cwd()

    current = start_path.resolve()

    # Walk up the directory tree
    for parent in [current] + list(current.parents):
        obsidian_dir = parent / ".obsidian"
        if obsidian_dir.exists() and obsidian_dir.is_dir():
            return parent

    return None


def invoke_command(args: argparse.Namespace) -> int:
    """Execute the invoke command.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Determine vault path
    if args.vault:
        vault_path: Path = Path(args.vault)
    else:
        # Auto-detect vault
        found_vault = find_vault_root()
        if found_vault is None:
            print(
                "Error: Could not find Obsidian vault. Use --vault to specify path.",
                file=sys.stderr,
            )
            return 1
        vault_path = found_vault

    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    print(f"Loading vault: {vault_path}")

    # Set up database path
    geistfabrik_dir = vault_path / "_geistfabrik"
    geistfabrik_dir.mkdir(exist_ok=True)
    db_path = geistfabrik_dir / "vault.db"

    try:
        # Load vault
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        print(f"Synced {note_count} notes")

        # Determine session date
        if args.date:
            try:
                session_date = datetime.strptime(args.date, "%Y-%m-%d")
            except ValueError:
                print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.", file=sys.stderr)
                vault.close()
                return 1
        else:
            session_date = datetime.now()

        # Create session and context
        session = Session(session_date, vault.db)
        print(f"Computing embeddings for {len(vault.all_notes())} notes...")
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        # Load and execute geists
        geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        if not geists_dir.exists():
            print(f"\nNo geists directory found at {geists_dir}")
            print("Create geists in this directory to generate suggestions.")
            vault.close()
            return 0

        executor = GeistExecutor(geists_dir, timeout=args.timeout, max_failures=3)
        executor.load_geists()

        enabled_geists = executor.get_enabled_geists()
        if not enabled_geists:
            print(f"\nNo geists found in {geists_dir}")
            print("Create Python geists with a suggest(vault) function.")
            vault.close()
            return 0

        print(f"\nExecuting {len(enabled_geists)} geists...")

        # Execute specific geist or all geists
        if args.geist:
            if args.geist not in executor.geists:
                print(f"Error: Geist '{args.geist}' not found", file=sys.stderr)
                vault.close()
                return 1
            results = {args.geist: executor.execute_geist(args.geist, context)}
        else:
            results = executor.execute_all(context)

        # Display results
        print(f"\n{'=' * 80}")
        print(f"GeistFabrik Session - {session_date.strftime('%Y-%m-%d')}")
        print(f"{'=' * 80}\n")

        total_suggestions = 0
        for geist_id, suggestions in results.items():
            if not suggestions:
                continue

            print(f"\n## {geist_id} ({len(suggestions)} suggestions)\n")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"   Notes: {note_refs}")
                print()
                total_suggestions += 1

        if total_suggestions == 0:
            print("No suggestions generated.")
        else:
            print(f"\n{'=' * 80}")
            print(f"Total: {total_suggestions} suggestions from {len(results)} geists")
            print(f"{'=' * 80}\n")

        # Display execution log if there were errors
        log = executor.get_execution_log()
        errors = [entry for entry in log if entry["status"] == "error"]
        if errors:
            print(f"\n⚠️  {len(errors)} geist(s) encountered errors:\n")
            for entry in errors:
                print(f"  - {entry['geist_id']}: {entry['error']}")
            print()

        vault.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="geistfabrik",
        description="A divergence engine for Obsidian vaults",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  geistfabrik invoke                    # Run in current vault with default settings
  geistfabrik invoke --vault ~/notes    # Specify vault path
  geistfabrik invoke --geist drift      # Run specific geist
  geistfabrik invoke --date 2025-01-15  # Replay session from specific date
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Invoke command
    invoke_parser = subparsers.add_parser("invoke", help="Execute geists and generate suggestions")
    invoke_parser.add_argument(
        "--vault",
        type=str,
        help="Path to Obsidian vault (auto-detects if not specified)",
    )
    invoke_parser.add_argument(
        "--geist",
        type=str,
        help="Run specific geist by ID",
    )
    invoke_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    invoke_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Geist execution timeout in seconds (default: 5)",
    )
    invoke_parser.add_argument(
        "--full",
        action="store_true",
        help="Show all suggestions (firehose mode - not yet implemented)",
    )

    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 1

    # Route to command handler
    if args.command == "invoke":
        return invoke_command(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
