"""Init command for setting up GeistFabrik in a vault."""

from pathlib import Path

from ..default_geists import CODE_GEIST_COUNT, TOTAL_GEIST_COUNT, TRACERY_GEIST_COUNT
from ..vault import Vault
from .base import BaseCommand


class InitCommand(BaseCommand):
    """Command to initialise GeistFabrik in an Obsidian vault.

    Creates the _geistfabrik directory structure, default config,
    and syncs the vault to the database.
    """

    def execute(self) -> int:
        """Execute the init command.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        # Get and validate vault path
        vault_path = self.get_vault_path()
        if vault_path is None:
            return 1

        # Check if it's an Obsidian vault
        obsidian_dir = vault_path / ".obsidian"
        if not obsidian_dir.exists():
            print(f"Warning: No .obsidian directory found in {vault_path}")
            print(
                "This doesn't appear to be an Obsidian vault, but continuing anyway..."
            )
            print()

        print(f"Initialising GeistFabrik in: {vault_path}\n")

        # Display first-run warnings
        self._print_safety_info()

        # Create _geistfabrik directory structure
        geistfabrik_dir = vault_path / "_geistfabrik"

        if geistfabrik_dir.exists() and not self.args.force:
            self.print_error(
                f"_geistfabrik directory already exists at {geistfabrik_dir}"
            )
            print("Use --force to reinitialize (this will overwrite existing configuration)")
            return 1

        # Create directory structure
        self._create_directories(vault_path, geistfabrik_dir)

        # Create default config file
        self._create_config(vault_path, geistfabrik_dir)

        # Initialise database
        if not self._init_database(vault_path, geistfabrik_dir):
            return 1

        # Success message
        self._print_success(vault_path, geistfabrik_dir)

        return 0

    def _print_safety_info(self) -> None:
        """Print safety information about what GeistFabrik will do."""
        print("GeistFabrik will:")
        print("   - Read all markdown files in your vault")
        print("   - Create a database at _geistfabrik/vault.db")
        print("   - Compute embeddings for all notes (stored locally)")
        print("   - Create session notes in 'geist journal/' when you invoke with --write")
        print()
        print("GeistFabrik will NEVER:")
        print("   - Modify your existing notes (read-only access)")
        print("   - Send data to the internet (100% local)")
        print("   - Delete any files")
        print()

    def _create_directories(self, vault_path: Path, geistfabrik_dir: Path) -> None:
        """Create the _geistfabrik directory structure.

        Args:
            vault_path: Path to the vault
            geistfabrik_dir: Path to _geistfabrik directory
        """
        directories = [
            geistfabrik_dir / "geists" / "code",
            geistfabrik_dir / "geists" / "tracery",
            geistfabrik_dir / "metadata_inference",
            geistfabrik_dir / "vault_functions",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"Created {directory.relative_to(vault_path)}")

    def _create_config(self, vault_path: Path, geistfabrik_dir: Path) -> None:
        """Create the default config file.

        Args:
            vault_path: Path to the vault
            geistfabrik_dir: Path to _geistfabrik directory
        """
        config_path = geistfabrik_dir / "config.yaml"
        if not config_path.exists() or self.args.force:
            from geistfabrik import generate_default_config

            config_content = generate_default_config()
            with open(config_path, "w") as f:
                f.write(config_content)
            print(f"Created {config_path.relative_to(vault_path)}")

    def _init_database(self, vault_path: Path, geistfabrik_dir: Path) -> bool:
        """Initialise the vault database.

        Args:
            vault_path: Path to the vault
            geistfabrik_dir: Path to _geistfabrik directory

        Returns:
            True if successful, False on error
        """
        print("\nInitialising database...")
        db_path = geistfabrik_dir / "vault.db"
        try:
            vault = Vault(vault_path, db_path)
            note_count = vault.sync()
            vault.close()
            print(f"Synced {note_count} notes to database")

            # Display summary stats
            db_size_mb = db_path.stat().st_size / (1024 * 1024)

            print("\nVault Summary:")
            print(f"   Notes found: {note_count}")
            print(f"   Database size: {db_size_mb:.2f} MB")

            return True

        except Exception as e:
            self.print_error(f"Initialising database: {e}")
            return False

    def _print_success(self, vault_path: Path, geistfabrik_dir: Path) -> None:
        """Print success message with next steps.

        Args:
            vault_path: Path to the vault
            geistfabrik_dir: Path to _geistfabrik directory
        """
        config_path = geistfabrik_dir / "config.yaml"

        print("\n" + "=" * 60)
        print("GeistFabrik initialised successfully!")
        print("=" * 60)
        print(f"\nVault: {vault_path}")
        print(f"Configuration: {geistfabrik_dir.relative_to(vault_path)}")

        # Inform about bundled defaults
        print(f"\n{TOTAL_GEIST_COUNT} default geists are bundled and ready to use:")
        print(
            f"   - {CODE_GEIST_COUNT} code geists "
            "(blind_spot_detector, temporal_drift, columbo, creation_burst, etc.)"
        )
        print(
            f"   - {TRACERY_GEIST_COUNT} Tracery geists "
            "(contradictor, hub_explorer, transformation_suggester, etc.)"
        )
        print(f"\n   Configure in: {config_path.relative_to(vault_path)}")

        print("\nNext steps:")
        print(f"   geistfabrik invoke {vault_path}")
        print("   # or just: geistfabrik invoke (from within the vault)\n")
