"""Stats command for showing vault statistics and health metrics."""

import sys

from ..config_loader import load_config
from ..embedding_metrics import EmbeddingMetricsComputer
from ..path_safety import ensure_contained
from ..stats import StatsCollector
from ..stats_formatter import StatsFormatter, generate_recommendations
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
        vault_path = self.get_vault_path(auto_detect=True)
        if vault_path is None:
            return 1

        # Check contained managed paths before reading config or opening SQLite.
        geistfabrik_dir = vault_path / "_geistfabrik"
        db_path = geistfabrik_dir / "vault.db"
        config_path = geistfabrik_dir / "config.yaml"
        for managed_path in (geistfabrik_dir, db_path, config_path):
            ensure_contained(managed_path, vault_path, reject_symlinks=True)

        # Check if vault is initialised (need database for stats)
        if not db_path.exists():
            self.print_error(f"GeistFabrik not initialised in {vault_path}")
            print(f"Run: geistfabrik init {vault_path}", file=sys.stderr)
            return 1

        # Validate configuration before opening the database and pass the same
        # authoritative object to every consumer.
        config = load_config(config_path)
        self._vault = Vault(vault_path, db_path, config=config)

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
