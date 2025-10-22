"""GeistFabrik command-line interface."""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from .embeddings import EmbeddingComputer, Session
from .filtering import SuggestionFilter, select_suggestions
from .geist_executor import GeistExecutor
from .journal_writer import JournalWriter
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


def init_command(args: argparse.Namespace) -> int:
    """Execute the init command to set up a vault for GeistFabrik.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code (0 for success, 1 for error)
    """
    vault_path = Path(args.vault).resolve()

    # Check if vault exists
    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}", file=sys.stderr)
        return 1

    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}", file=sys.stderr)
        return 1

    # Check if it's an Obsidian vault
    obsidian_dir = vault_path / ".obsidian"
    if not obsidian_dir.exists():
        print(f"Warning: No .obsidian directory found in {vault_path}")
        print("This doesn't appear to be an Obsidian vault, but continuing anyway...")
        print()

    print(f"Initializing GeistFabrik in: {vault_path}\n")

    # Display first-run warnings
    print("⚠️  GeistFabrik will:")
    print("   • Read all markdown files in your vault")
    print("   • Create a database at _geistfabrik/vault.db")
    print("   • Compute embeddings for all notes (stored locally)")
    print("   • Create session notes in 'geist journal/' when you invoke with --write")
    print()
    print("✅ GeistFabrik will NEVER:")
    print("   • Modify your existing notes (read-only access)")
    print("   • Send data to the internet (100% local)")
    print("   • Delete any files")
    print()

    # Create _geistfabrik directory structure
    geistfabrik_dir = vault_path / "_geistfabrik"

    if geistfabrik_dir.exists() and not args.force:
        print(f"Error: _geistfabrik directory already exists at {geistfabrik_dir}")
        print("Use --force to reinitialize (this will overwrite existing configuration)")
        return 1

    # Create directory structure
    directories = [
        geistfabrik_dir / "geists" / "code",
        geistfabrik_dir / "geists" / "tracery",
        geistfabrik_dir / "metadata_inference",
        geistfabrik_dir / "vault_functions",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {directory.relative_to(vault_path)}")

    # Copy examples if requested
    if args.examples:
        # Find the examples directory (relative to this file)
        package_dir = Path(__file__).parent.parent.parent
        examples_dir = package_dir / "examples"

        if not examples_dir.exists():
            print(f"\nWarning: Examples directory not found at {examples_dir}")
            print("Skipping example installation.")
        else:
            print("\n📦 Installing examples...")

            # Copy geists
            for geist_type in ["code", "tracery"]:
                src = examples_dir / "geists" / geist_type
                dst = geistfabrik_dir / "geists" / geist_type
                if src.exists():
                    for file in src.iterdir():
                        if file.is_file():
                            shutil.copy2(file, dst / file.name)
                            print(f"  ✓ {geist_type}/{file.name}")

            # Copy metadata inference modules
            src = examples_dir / "metadata_inference"
            dst = geistfabrik_dir / "metadata_inference"
            if src.exists():
                for file in src.iterdir():
                    if file.is_file() and file.suffix == ".py":
                        shutil.copy2(file, dst / file.name)
                        print(f"  ✓ metadata_inference/{file.name}")

            # Copy vault functions
            src = examples_dir / "vault_functions"
            dst = geistfabrik_dir / "vault_functions"
            if src.exists():
                for file in src.iterdir():
                    if file.is_file() and file.suffix == ".py":
                        shutil.copy2(file, dst / file.name)
                        print(f"  ✓ vault_functions/{file.name}")

    # Initialize database
    print("\n🗄️  Initializing database...")
    db_path = geistfabrik_dir / "vault.db"
    try:
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        vault.close()
        print(f"✓ Synced {note_count} notes to database")

        # Display summary stats
        db_size_mb = db_path.stat().st_size / (1024 * 1024)
        geist_count = 0
        if args.examples:
            code_geists = geistfabrik_dir / "geists" / "code"
            tracery_geists = geistfabrik_dir / "geists" / "tracery"
            geist_count = sum(1 for f in code_geists.iterdir() if f.suffix == ".py")
            geist_count += sum(1 for f in tracery_geists.iterdir() if f.suffix in [".yaml", ".yml"])

        print("\n📊 Vault Summary:")
        print(f"   Notes found: {note_count}")
        print(f"   Database size: {db_size_mb:.2f} MB")
        if args.examples:
            print(f"   Example geists installed: {geist_count}")

    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        return 1

    # Success message
    print("\n" + "=" * 60)
    print("✨ GeistFabrik initialized successfully!")
    print("=" * 60)
    print(f"\nVault: {vault_path}")
    print(f"Configuration: {geistfabrik_dir.relative_to(vault_path)}")
    if args.examples:
        print("\n📚 Example geists have been installed.")
        print("   You can modify or remove them as needed.")
    else:
        print("\n💡 Tip: Use --examples to install example geists:")
        print(f"   geistfabrik init {vault_path} --examples")

    print("\n🚀 Next steps:")
    print(f"   geistfabrik invoke --vault {vault_path}")
    print("   # or just: geistfabrik invoke (from within the vault)\n")

    return 0


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

        # Load metadata inference modules
        metadata_dir = geistfabrik_dir / "metadata_inference"
        metadata_loader = None
        if metadata_dir.exists():
            from geistfabrik import MetadataLoader

            metadata_loader = MetadataLoader(metadata_dir)
            metadata_loader.load_modules()
            print(f"Loaded {len(metadata_loader.modules)} metadata inference modules")

        # Load vault function modules
        functions_dir = geistfabrik_dir / "vault_functions"
        function_registry = None
        if functions_dir.exists():
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry(functions_dir)
            function_registry.load_modules()
            print(f"Loaded {len(function_registry.functions)} vault functions")
        else:
            # Always create function registry with built-in functions
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry()
            print(f"Using {len(function_registry.functions)} built-in vault functions")

        # Create session and context
        session = Session(session_date, vault.db)
        print(f"Computing embeddings for {len(vault.all_notes())} notes...")
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(
            vault, session, metadata_loader=metadata_loader, function_registry=function_registry
        )

        # Load code geists
        code_geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        code_executor = None
        code_geists_count = 0
        if code_geists_dir.exists():
            code_executor = GeistExecutor(code_geists_dir, timeout=args.timeout, max_failures=3)
            code_executor.load_geists()
            code_geists_count = len(code_executor.geists)

        # Load Tracery geists
        tracery_geists_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
        tracery_geists = []
        if tracery_geists_dir.exists():
            from geistfabrik.tracery import TraceryGeistLoader

            seed = int(session_date.timestamp())
            tracery_loader = TraceryGeistLoader(tracery_geists_dir, seed=seed)
            tracery_geists = tracery_loader.load_all()

        total_geists = code_geists_count + len(tracery_geists)
        if total_geists == 0:
            print(f"\nNo geists found in {vault_path / '_geistfabrik' / 'geists'}")
            print("Run 'geistfabrik init --examples' to install example geists.")
            vault.close()
            return 0

        # Get enabled code geists
        enabled_code_geists = []
        disabled_code_geists = []
        if code_executor:
            enabled_code_geists = code_executor.get_enabled_geists()
            all_code_ids = list(code_executor.geists.keys())
            disabled_code_geists = [gid for gid in all_code_ids if gid not in enabled_code_geists]

        # Show configuration summary
        enabled_geists_count = len(enabled_code_geists) + len(tracery_geists)
        disabled_geists = disabled_code_geists

        print(f"\n{'=' * 60}")
        print("GeistFabrik Configuration Audit")
        print(f"{'=' * 60}")
        print(f"Vault: {vault_path}")
        print(f"Geists directory: {vault_path / '_geistfabrik' / 'geists'}")
        print(f"Total geists found: {total_geists}")
        print(f"  - Code geists: {code_geists_count} ({len(enabled_code_geists)} enabled)")
        print(f"  - Tracery geists: {len(tracery_geists)}")
        if disabled_geists:
            print(f"  - Disabled: {len(disabled_geists)} ({', '.join(disabled_geists)})")
        filtering_status = (
            "DISABLED (--nofilter)" if args.nofilter else "ENABLED (4-stage pipeline)"
        )
        print(f"Filtering: {filtering_status}")
        sampling_status = (
            "DISABLED (--full or --nofilter)"
            if (args.full or args.nofilter)
            else f"ENABLED (count={args.count})"
        )
        print(f"Sampling: {sampling_status}")
        mode = "Raw output" if args.nofilter else "Filtered output" if args.full else "Default"
        print(f"Mode: {mode}")
        print(f"{'=' * 60}\n")

        print(f"Executing {enabled_geists_count} geists...")

        # Execute specific geist or all geists
        all_suggestions = []
        code_results = {}
        tracery_results = {}

        if args.geist:
            # Check if it's a code geist
            if code_executor and args.geist in code_executor.geists:
                code_results = {args.geist: code_executor.execute_geist(args.geist, context)}
            # Check if it's a Tracery geist
            elif any(g.geist_id == args.geist for g in tracery_geists):
                tracery_geist = next(g for g in tracery_geists if g.geist_id == args.geist)
                try:
                    suggestions = tracery_geist.suggest(context)
                    tracery_results = {args.geist: suggestions}
                except Exception as e:
                    print(f"Error executing Tracery geist {args.geist}: {e}", file=sys.stderr)
                    tracery_results = {args.geist: []}
            else:
                print(f"Error: Geist '{args.geist}' not found", file=sys.stderr)
                vault.close()
                return 1
        else:
            # Execute all code geists
            if code_executor:
                code_results = code_executor.execute_all(context)

            # Execute all Tracery geists
            for tracery_geist in tracery_geists:
                try:
                    suggestions = tracery_geist.suggest(context)
                    tracery_results[tracery_geist.geist_id] = suggestions
                except Exception as e:
                    print(
                        f"Error executing Tracery geist {tracery_geist.geist_id}: {e}",
                        file=sys.stderr,
                    )
                    tracery_results[tracery_geist.geist_id] = []

        # Collect all suggestions from both code and Tracery geists
        for suggestions in code_results.values():
            all_suggestions.extend(suggestions)
        for suggestions in tracery_results.values():
            all_suggestions.extend(suggestions)

        # Show execution summary
        code_success = sum(1 for s in code_results.values() if s)
        code_empty = sum(1 for s in code_results.values() if not s)
        tracery_success = sum(1 for s in tracery_results.values() if s)
        tracery_empty = sum(1 for s in tracery_results.values() if not s)

        if code_results or tracery_results:
            print("Execution summary:")
            if code_results:
                print(
                    f"  - Code geists: {code_success} generated suggestions, "
                    f"{code_empty} returned empty"
                )
            if tracery_results:
                print(
                    f"  - Tracery geists: {tracery_success} generated suggestions, "
                    f"{tracery_empty} returned empty"
                )

        print(f"Generated {len(all_suggestions)} raw suggestions")

        # Filter suggestions (unless --nofilter is specified)
        if args.nofilter:
            filtered = all_suggestions
            print("Skipping filtering pipeline (--nofilter)")
        else:
            embedding_computer = EmbeddingComputer()
            filter = SuggestionFilter(vault.db, embedding_computer)
            filtered = filter.filter_all(all_suggestions, session_date)
            print(f"Filtered to {len(filtered)} suggestions")

        # Select final suggestions based on mode
        # Both --full and --nofilter should show all suggestions (no sampling)
        mode = "full" if (args.full or args.nofilter) else "default"
        count = args.count if hasattr(args, "count") else 5
        seed = int(session_date.timestamp())
        final = select_suggestions(filtered, mode, count, seed)
        print(f"Selected {len(final)} final suggestions\n")

        # Handle --diff mode
        if args.diff:
            journal_writer = JournalWriter(vault_path, vault.db)
            recent_suggestions = journal_writer.get_recent_suggestions(days=60)
            if recent_suggestions:
                from difflib import SequenceMatcher

                print("🔍 Diff Mode: Comparing to recent sessions...\n")
                for suggestion in final:
                    # Check similarity to recent suggestions
                    max_similarity = 0.0
                    for recent in recent_suggestions:
                        similarity = SequenceMatcher(None, suggestion.text, recent).ratio()
                        max_similarity = max(max_similarity, similarity)

                    if max_similarity > 0.8:
                        print(f"  ⚠️  Similar to recent: {suggestion.text[:60]}...")
                    elif max_similarity > 0.5:
                        print(f"  ⚡ Somewhat similar: {suggestion.text[:60]}...")
                    else:
                        print(f"  ✨ New: {suggestion.text[:60]}...")
                print()

        # Write to journal if requested
        if args.write:
            journal_writer = JournalWriter(vault_path, vault.db)

            # Check if session already exists
            if journal_writer.session_exists(session_date):
                if not args.force:
                    print(
                        f"\n⚠️  Session note already exists for {session_date.strftime('%Y-%m-%d')}"
                    )
                    print("Use --force to overwrite, or delete the existing note first.")
                    vault.close()
                    return 1
                else:
                    # Delete existing session note
                    existing_path = (
                        vault_path / "geist journal" / f"{session_date.strftime('%Y-%m-%d')}.md"
                    )
                    existing_path.unlink()

            try:
                journal_path = journal_writer.write_session(session_date, final, mode)
                print(f"✓ Wrote session note: {journal_path.relative_to(vault_path)}\n")
            except Exception as e:
                print(f"Error writing session note: {e}", file=sys.stderr)
                vault.close()
                return 1

        # Display results
        print(f"{'=' * 80}")
        print(f"GeistFabrik Session - {session_date.strftime('%Y-%m-%d')}")
        print(f"{'=' * 80}\n")

        if not final:
            print("No suggestions to display.")
        else:
            for i, suggestion in enumerate(final, 1):
                print(f"## {suggestion.geist_id}")
                print(f"{suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"_Notes: {note_refs}_")
                print()

            print(f"{'=' * 80}")
            print(f"Total: {len(final)} suggestions")
            print(f"{'=' * 80}\n")

        # Display execution log summary (for code geists only - they have detailed logs)
        if code_executor:
            log = code_executor.get_execution_log()
            errors = [entry for entry in log if entry["status"] == "error"]
            timeouts = [entry for entry in log if "timeout" in str(entry.get("error", "")).lower()]
            successful = [entry for entry in log if entry["status"] == "success"]

            if errors or timeouts:
                print(f"\n{'=' * 60}")
                print("Detailed Execution Log")
                print(f"{'=' * 60}")
                print(f"Successful: {len(successful)} geists")
                if errors:
                    print(f"Errors: {len(errors)} geists")
                    for entry in errors:
                        print(f"  ✗ {entry['geist_id']}: {entry['error']}")
                if timeouts:
                    print(f"Timeouts: {len(timeouts)} geists (consider increasing --timeout)")
                print(f"{'=' * 60}\n")

        vault.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def test_command(args: argparse.Namespace) -> int:
    """Execute the test command to test a single geist.

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

    geist_id = args.geist_id

    print(f"Testing geist '{geist_id}' in vault: {vault_path}\n")

    # Set up database path
    geistfabrik_dir = vault_path / "_geistfabrik"
    if not geistfabrik_dir.exists():
        print(f"Error: GeistFabrik not initialized in {vault_path}", file=sys.stderr)
        print(f"Run: geistfabrik init {vault_path}")
        return 1

    db_path = geistfabrik_dir / "vault.db"

    try:
        # Load vault
        vault = Vault(vault_path, db_path)
        note_count = vault.sync()
        print(f"Loaded {note_count} notes")

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

        print(f"Session date: {session_date.strftime('%Y-%m-%d')}")

        # Load metadata inference modules
        metadata_dir = geistfabrik_dir / "metadata_inference"
        metadata_loader = None
        if metadata_dir.exists():
            from geistfabrik import MetadataLoader

            metadata_loader = MetadataLoader(metadata_dir)
            metadata_loader.load_modules()
            print(f"Loaded {len(metadata_loader.modules)} metadata inference modules")

        # Load vault function modules
        functions_dir = geistfabrik_dir / "vault_functions"
        function_registry = None
        if functions_dir.exists():
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry(functions_dir)
            function_registry.load_modules()
            print(f"Loaded {len(function_registry.functions)} vault functions")
        else:
            from geistfabrik import FunctionRegistry

            function_registry = FunctionRegistry()
            print(f"Using {len(function_registry.functions)} built-in vault functions")

        # Create session and context
        session = Session(session_date, vault.db)
        print("Computing embeddings...")
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(
            vault, session, metadata_loader=metadata_loader, function_registry=function_registry
        )

        # Load and execute the specific geist
        geists_dir = vault_path / "_geistfabrik" / "geists" / "code"
        if not geists_dir.exists():
            print(f"\nError: No geists directory found at {geists_dir}", file=sys.stderr)
            vault.close()
            return 1

        executor = GeistExecutor(geists_dir, timeout=args.timeout, max_failures=3)
        executor.load_geists()

        if geist_id not in executor.geists:
            print(f"\nError: Geist '{geist_id}' not found in {geists_dir}", file=sys.stderr)
            print("\nAvailable geists:")
            for gid in sorted(executor.geists.keys()):
                print(f"  - {gid}")
            vault.close()
            return 1

        print(f"\n{'=' * 60}")
        print(f"Executing geist: {geist_id}")
        print(f"{'=' * 60}\n")

        # Execute the geist
        suggestions = executor.execute_geist(geist_id, context)

        # Display results
        if not suggestions:
            print("⚠️  No suggestions generated")
        else:
            print(f"✓ Generated {len(suggestions)} suggestion(s):\n")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion.text}")
                if suggestion.notes:
                    note_refs = ", ".join(f"[[{note}]]" for note in suggestion.notes)
                    print(f"   Notes: {note_refs}")
                if suggestion.title:
                    print(f"   Suggested title: {suggestion.title}")
                print()

        # Display execution log
        log = executor.get_execution_log()
        for entry in log:
            if entry["geist_id"] == geist_id:
                if entry["status"] == "success":
                    print("✓ Status: Success")
                    print(f"  Execution time: {entry['execution_time']:.3f}s")
                elif entry["status"] == "error":
                    print("✗ Status: Error")
                    print(f"  Error: {entry['error']}")

        print(f"\n{'=' * 60}\n")

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

    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize GeistFabrik in a vault")
    init_parser.add_argument(
        "vault",
        type=str,
        help="Path to Obsidian vault",
    )
    init_parser.add_argument(
        "--examples",
        action="store_true",
        help="Install example geists, metadata modules, and vault functions",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Reinitialize even if _geistfabrik directory exists",
    )

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
        help="Show all filtered suggestions (no sampling, filtering still applies)",
    )
    invoke_parser.add_argument(
        "--nofilter",
        action="store_true",
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
        help="Write suggestions to geist journal note",
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

    # Test command
    test_parser = subparsers.add_parser("test", help="Test a single geist")
    test_parser.add_argument(
        "geist_id",
        type=str,
        help="ID of the geist to test",
    )
    test_parser.add_argument(
        "--vault",
        type=str,
        help="Path to Obsidian vault (auto-detects if not specified)",
    )
    test_parser.add_argument(
        "--date",
        type=str,
        help="Session date in YYYY-MM-DD format (defaults to today)",
    )
    test_parser.add_argument(
        "--timeout",
        type=int,
        default=5,
        help="Geist execution timeout in seconds (default: 5)",
    )

    args = parser.parse_args()

    # Show help if no command specified
    if not args.command:
        parser.print_help()
        return 1

    # Route to command handler
    if args.command == "init":
        return init_command(args)
    elif args.command == "invoke":
        return invoke_command(args)
    elif args.command == "test":
        return test_command(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
