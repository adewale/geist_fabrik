"""Stats command for showing vault statistics and health metrics."""

from pathlib import Path

from ..config_loader import GeistFabrikConfig, load_config
from ..stats import (
    EmbeddingMetricsComputer,
    StatsCollector,
    StatsFormatter,
    generate_recommendations,
)
from ..vault import Vault
from .base import BaseCommand


class StatsCommand(BaseCommand):
    """Command to show vault statistics and health metrics.

    Displays information about the vault, embedding quality, temporal drift,
    and provides recommendations for improvement.
    """

    def execute(self) -> int:
        """Execute the stats command.

        Returns:
            Exit code (0 for success, 1 for error)
        """
        # Find vault path (supports auto-detection)
        vault_path = self._get_vault_path()
        if vault_path is None:
            return 1

        # Check if vault is initialised
        db_path = vault_path / "_geistfabrik" / "vault.db"
        if not db_path.exists():
            self.print_error("GeistFabrik not initialised in this vault.")
            print(f"Run: geistfabrik init {vault_path}")
            return 1

        # Load vault and config
        self._vault = Vault(vault_path, db_path)
        config_path = vault_path / "_geistfabrik" / "config.yaml"
        config = load_config(config_path) if config_path.exists() else GeistFabrikConfig()

        # Collect statistics
        history_days = getattr(self.args, "history", 30)
        collector = StatsCollector(self._vault, config, history_days=history_days)

        # Compute embedding metrics if embeddings exist
        self._compute_embedding_metrics(collector, history_days)

        # Add verbose details if requested
        if self.verbose:
            collector.add_verbose_details()

        # Generate recommendations
        recommendations = generate_recommendations(collector.stats)

        # Format and display output
        formatter = StatsFormatter(collector.stats, recommendations, verbose=self.verbose)

        if getattr(self.args, "json", False):
            output = formatter.format_json()
        else:
            output = formatter.format_text()

        print(output)

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

    def _compute_embedding_metrics(
        self,
        collector: StatsCollector,
        history_days: int,
    ) -> None:
        """Compute embedding metrics if embeddings exist.

        Args:
            collector: Stats collector
            history_days: Number of days of history to analyze
        """
        if not collector.has_embeddings():
            return

        latest = collector.get_latest_embeddings()
        if not latest:
            return

        session_date, embeddings, paths = latest
        assert self._vault is not None  # Set in execute()
        metrics_computer = EmbeddingMetricsComputer(self._vault.db, self._vault.config)
        force_recompute = getattr(self.args, "force_recompute", False)
        metrics = metrics_computer.compute_metrics(
            session_date, embeddings, paths, force_recompute=force_recompute
        )
        collector.add_embedding_metrics(metrics)

        # Compute temporal drift analysis if multiple sessions exist
        temporal = collector.get_temporal_drift(session_date, days_back=history_days)
        if temporal:
            collector.add_temporal_analysis(temporal)
