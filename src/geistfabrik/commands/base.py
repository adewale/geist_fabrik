"""Base command class providing shared infrastructure for CLI commands."""

import sys
from abc import ABC, abstractmethod
from argparse import Namespace
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..config_loader import GeistFabrikConfig, load_config
from ..embeddings import Session
from ..function_registry import FunctionRegistry
from ..metadata_system import MetadataLoader
from ..vault import Vault
from ..vault_context import VaultContext


def find_vault_root(start_path: Path | None = None) -> Path | None:
    """Find vault root by looking for .obsidian directory.

    This is the canonical implementation used by both CLI and BaseCommand.

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


@dataclass
class CommandContext:
    """Shared context for command execution.

    This bundles together the commonly-needed objects that most commands require,
    reducing parameter passing and setup duplication.
    """

    vault_path: Path
    vault: Vault
    config: GeistFabrikConfig | None
    config_path: Path
    geistfabrik_dir: Path
    db_path: Path


@dataclass
class ExecutionContext(CommandContext):
    """Extended context including session and VaultContext for geist execution.

    Used by commands that need to execute geists (invoke, test, test-all).
    """

    session: Session
    vault_context: VaultContext
    metadata_loader: MetadataLoader | None
    function_registry: FunctionRegistry


class BaseCommand(ABC):
    """Base class for CLI commands with shared infrastructure.

    Provides common functionality:
    - Vault path validation
    - Config loading
    - Database setup
    - Session/context creation
    - Error handling
    - Output formatting

    Subclasses implement the `execute()` method with command-specific logic.
    """

    def __init__(self, args: Namespace) -> None:
        """Initialise the command with parsed arguments.

        Args:
            args: Parsed command-line arguments from argparse
        """
        self.args = args
        self._vault: Vault | None = None

    @property
    def verbose(self) -> bool:
        """Whether verbose output is enabled."""
        return getattr(self.args, "verbose", False)

    @property
    def quiet(self) -> bool:
        """Whether quiet mode is enabled."""
        return getattr(self.args, "quiet", False)

    def print(self, message: str) -> None:
        """Print a message unless quiet mode is enabled.

        Args:
            message: The message to print
        """
        if not self.quiet:
            print(message)

    def print_verbose(self, message: str) -> None:
        """Print a message only in verbose mode.

        Args:
            message: The message to print
        """
        if self.verbose:
            print(message)

    def print_error(self, message: str) -> None:
        """Print an error message to stderr.

        Args:
            message: The error message to print
        """
        print(f"Error: {message}", file=sys.stderr)

    def run(self) -> int:
        """Execute the command with error handling.

        This is the main entry point called by the CLI dispatcher.
        It wraps execute() with error handling.

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        try:
            return self.execute()
        except KeyboardInterrupt:
            print("\nInterrupted by user")
            return 130
        except Exception as e:
            self.print_error(str(e))
            if self.verbose:
                import traceback

                traceback.print_exc()
            return 1
        finally:
            self._cleanup()

    @abstractmethod
    def execute(self) -> int:
        """Execute the command-specific logic.

        Subclasses must implement this method.

        Returns:
            Exit code (0 for success, non-zero for error)
        """
        ...

    def _cleanup(self) -> None:
        """Clean up resources after command execution."""
        if self._vault is not None:
            self._vault.close()

    # -------------------------------------------------------------------------
    # Vault and Path Validation
    # -------------------------------------------------------------------------

    def validate_vault_path(self, vault_path: Path) -> bool:
        """Validate that a vault path exists and is a directory.

        Args:
            vault_path: Path to validate

        Returns:
            True if valid, False otherwise (with error printed)
        """
        if not vault_path.exists():
            self.print_error(f"Vault path does not exist: {vault_path}")
            return False

        if not vault_path.is_dir():
            self.print_error(f"Vault path is not a directory: {vault_path}")
            return False

        return True

    def validate_geistfabrik_initialised(self, vault_path: Path) -> bool:
        """Check if GeistFabrik is initialised in the vault.

        Args:
            vault_path: Path to the vault

        Returns:
            True if initialised, False otherwise (with error printed)
        """
        geistfabrik_dir = vault_path / "_geistfabrik"
        if not geistfabrik_dir.exists():
            self.print_error(f"GeistFabrik not initialised in {vault_path}")
            print(f"Run: geistfabrik init {vault_path}", file=sys.stderr)
            return False
        return True

    def get_vault_path(self, auto_detect: bool = False) -> Path | None:
        """Get and validate the vault path from arguments.

        Args:
            auto_detect: If True and no vault arg provided, try to auto-detect
                        from current directory by walking up to find .obsidian

        Returns:
            Resolved vault path, or None if invalid/not found
        """
        # Check if vault argument was provided
        if hasattr(self.args, "vault") and self.args.vault:
            vault_path = Path(self.args.vault).resolve()
            if not self.validate_vault_path(vault_path):
                return None
            return vault_path

        # If no vault arg and auto_detect enabled, try to find vault root
        if auto_detect:
            detected_path = find_vault_root()
            if detected_path is None:
                self.print_error("No vault specified and could not auto-detect vault.")
                print("Either run from within a vault or specify vault path.")
                return None
            return detected_path

        # No vault arg and no auto-detect - this shouldn't happen for required args
        # but handle gracefully
        self.print_error("No vault path specified.")
        return None

    def find_vault_root(self, start_path: Path | None = None) -> Path | None:
        """Find vault root by looking for .obsidian directory.

        Args:
            start_path: Directory to start search from (defaults to current dir)

        Returns:
            Path to vault root, or None if not found
        """
        return find_vault_root(start_path)

    # -------------------------------------------------------------------------
    # Config and Context Setup
    # -------------------------------------------------------------------------

    def setup_command_context(self, vault_path: Path) -> CommandContext | None:
        """Set up the basic command context with vault and config.

        Args:
            vault_path: Path to the vault

        Returns:
            CommandContext if successful, None on error
        """
        geistfabrik_dir = vault_path / "_geistfabrik"
        db_path = geistfabrik_dir / "vault.db"
        config_path = geistfabrik_dir / "config.yaml"

        # Load configuration
        config = None
        if config_path.exists():
            config = load_config(config_path)
            self.print_verbose(
                f"Loaded configuration from {config_path.relative_to(vault_path)}"
            )

        # Open vault
        self._vault = Vault(vault_path, db_path)

        return CommandContext(
            vault_path=vault_path,
            vault=self._vault,
            config=config,
            config_path=config_path,
            geistfabrik_dir=geistfabrik_dir,
            db_path=db_path,
        )

    def setup_execution_context(
        self,
        cmd_ctx: CommandContext,
        session_date: datetime,
    ) -> ExecutionContext:
        """Set up the full execution context including session and VaultContext.

        This is used by commands that need to execute geists.

        Args:
            cmd_ctx: Basic command context
            session_date: Date for the session

        Returns:
            ExecutionContext with session and VaultContext ready
        """
        vault = cmd_ctx.vault
        config = cmd_ctx.config
        geistfabrik_dir = cmd_ctx.geistfabrik_dir

        # Load metadata inference modules
        metadata_dir = geistfabrik_dir / "metadata_inference"
        metadata_loader = None
        if metadata_dir.exists():
            metadata_loader = MetadataLoader(metadata_dir)
            metadata_loader.load_modules()
            self.print_verbose(
                f"Loaded {len(metadata_loader.modules)} metadata inference modules"
            )

        # Load vault function modules
        functions_dir = geistfabrik_dir / "vault_functions"
        if functions_dir.exists():
            function_registry = FunctionRegistry(functions_dir)
            function_registry.load_modules()
            self.print_verbose(
                f"Loaded {len(function_registry.functions)} vault functions"
            )
        else:
            function_registry = FunctionRegistry()
            self.print_verbose(
                f"Using {len(function_registry.functions)} built-in vault functions"
            )

        # Create session
        backend_type = config.vector_search.backend if config else "in-memory"
        session = Session(session_date, vault.db, backend=backend_type)

        self.print_verbose(f"Computing embeddings for {len(vault.all_notes())} notes...")
        session.compute_embeddings(vault.all_notes())

        # Create VaultContext
        vault_context = VaultContext(
            vault,
            session,
            metadata_loader=metadata_loader,
            function_registry=function_registry,
        )

        return ExecutionContext(
            vault_path=cmd_ctx.vault_path,
            vault=cmd_ctx.vault,
            config=cmd_ctx.config,
            config_path=cmd_ctx.config_path,
            geistfabrik_dir=cmd_ctx.geistfabrik_dir,
            db_path=cmd_ctx.db_path,
            session=session,
            vault_context=vault_context,
            metadata_loader=metadata_loader,
            function_registry=function_registry,
        )

    # -------------------------------------------------------------------------
    # Date Parsing
    # -------------------------------------------------------------------------

    def parse_session_date(self, date_str: str | None = None) -> datetime | None:
        """Parse a session date from string or return current datetime.

        Args:
            date_str: Date string in YYYY-MM-DD format, or None for today

        Returns:
            Parsed datetime, or None if invalid format (with error printed)
        """
        if date_str is None:
            return datetime.now()

        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self.print_error(f"Invalid date format '{date_str}'. Use YYYY-MM-DD.")
            return None

    # -------------------------------------------------------------------------
    # Output Formatting
    # -------------------------------------------------------------------------

    def print_header(self, title: str, width: int = 60) -> None:
        """Print a formatted header.

        Args:
            title: Header title
            width: Width of the header line
        """
        print(f"\n{'=' * width}")
        print(title)
        print(f"{'=' * width}\n")

    def print_separator(self, width: int = 60, char: str = "-") -> None:
        """Print a separator line.

        Args:
            width: Width of the separator
            char: Character to use for the separator
        """
        print(char * width)
