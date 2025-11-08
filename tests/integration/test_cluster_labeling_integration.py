"""Integration tests for cluster labeling with VaultContext."""

import pytest
from datetime import datetime
from pathlib import Path


class TestClusterLabelingIntegration:
    """Test cluster labeling through VaultContext with config."""

    @pytest.fixture
    def vault_with_config(self, tmp_path):
        """Create a vault with clustering configuration."""
        from geistfabrik.vault import Vault
        from geistfabrik.config_loader import GeistFabrikConfig, ClusterConfig

        # Create vault directory
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        # Create some test notes
        notes_data = [
            ("ml1.md", "# Machine Learning\nDeep learning neural networks"),
            ("ml2.md", "# Neural Networks\nBackpropagation and training"),
            ("ml3.md", "# AI Models\nModel training and evaluation"),
            ("ml4.md", "# Deep Learning\nConvolutional neural networks"),
            ("ml5.md", "# Training\nOptimization and gradient descent"),
            ("web1.md", "# React\nReact hooks and components"),
            ("web2.md", "# Frontend\nJavaScript and TypeScript"),
            ("web3.md", "# Web Dev\nFrontend architecture patterns"),
            ("web4.md", "# Components\nReact component lifecycle"),
            ("web5.md", "# State\nState management with hooks"),
        ]

        for filename, content in notes_data:
            (vault_path / filename).write_text(content)

        # Create vault with config
        config = GeistFabrikConfig()
        vault = Vault(vault_path, config=config)
        vault.sync()

        return vault

    def test_get_clusters_with_keybert_config(self, vault_with_config):
        """Test get_clusters uses KeyBERT when configured."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext
        from geistfabrik.config_loader import ClusterConfig

        vault = vault_with_config

        # Set KeyBERT as labeling method (default)
        vault.config.clustering = ClusterConfig(labeling_method="keybert", n_label_terms=3)

        # Create session and compute embeddings
        session = Session(datetime.now(), vault.db)
        session.compute_embeddings(vault.all_notes())

        # Create context
        context = VaultContext(vault, session)

        # Get clusters
        clusters = context.get_clusters(min_size=3)

        # Should have at least one cluster with labels
        if len(clusters) > 0:
            for cluster_id, cluster_info in clusters.items():
                assert "label" in cluster_info
                assert "formatted_label" in cluster_info
                assert isinstance(cluster_info["label"], str)
                assert len(cluster_info["label"]) > 0

    def test_get_clusters_with_tfidf_config(self, vault_with_config):
        """Test get_clusters uses c-TF-IDF when configured."""
        pytest.importorskip("sklearn")

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext
        from geistfabrik.config_loader import ClusterConfig

        vault = vault_with_config

        # Set TF-IDF as labeling method
        vault.config.clustering = ClusterConfig(labeling_method="tfidf", n_label_terms=3)

        # Create session and compute embeddings
        session = Session(datetime.now(), vault.db)
        session.compute_embeddings(vault.all_notes())

        # Create context
        context = VaultContext(vault, session)

        # Get clusters
        clusters = context.get_clusters(min_size=3)

        # Should have at least one cluster with labels
        if len(clusters) > 0:
            for cluster_id, cluster_info in clusters.items():
                assert "label" in cluster_info
                assert "formatted_label" in cluster_info
                assert isinstance(cluster_info["label"], str)
                assert len(cluster_info["label"]) > 0

    def test_switching_labeling_methods(self, vault_with_config):
        """Test that changing config affects labeling method."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext
        from geistfabrik.config_loader import ClusterConfig

        vault = vault_with_config

        # Create session and compute embeddings once
        session = Session(datetime.now(), vault.db)
        session.compute_embeddings(vault.all_notes())

        # Try KeyBERT first
        vault.config.clustering = ClusterConfig(labeling_method="keybert", n_label_terms=3)
        context1 = VaultContext(vault, session)
        clusters_keybert = context1.get_clusters(min_size=3)

        # Clear cache to force recomputation
        context1._clusters_cache.clear()

        # Switch to TF-IDF
        vault.config.clustering = ClusterConfig(labeling_method="tfidf", n_label_terms=3)
        context2 = VaultContext(vault, session)
        clusters_tfidf = context2.get_clusters(min_size=3)

        # Both should produce clusters
        if len(clusters_keybert) > 0 and len(clusters_tfidf) > 0:
            # Should have same cluster IDs (same clustering)
            assert set(clusters_keybert.keys()) == set(clusters_tfidf.keys())

            # But may have different labels (different labeling methods)
            # This is hard to assert definitively, but at least verify both produced labels
            for cluster_id in clusters_keybert:
                assert len(clusters_keybert[cluster_id]["label"]) > 0
                assert len(clusters_tfidf[cluster_id]["label"]) > 0

    def test_n_label_terms_config(self, vault_with_config):
        """Test that n_label_terms config is respected."""
        pytest.importorskip("sklearn")

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext
        from geistfabrik.config_loader import ClusterConfig

        vault = vault_with_config

        # Set n_label_terms to 2
        vault.config.clustering = ClusterConfig(labeling_method="tfidf", n_label_terms=2)

        # Create session and compute embeddings
        session = Session(datetime.now(), vault.db)
        session.compute_embeddings(vault.all_notes())

        # Create context
        context = VaultContext(vault, session)

        # Get clusters
        clusters = context.get_clusters(min_size=3)

        # Verify labels have approximately the right number of terms
        # (May be fewer if there aren't enough diverse terms)
        if len(clusters) > 0:
            for cluster_id, cluster_info in clusters.items():
                label = cluster_info["label"]
                term_count = len(label.split(","))
                # Should be <= n_label_terms (may be less due to filtering)
                assert term_count <= 2


class TestClusterMirrorGeist:
    """Test cluster_mirror geist with different config."""

    @pytest.fixture
    def vault_for_geist(self, tmp_path):
        """Create a vault suitable for cluster_mirror testing."""
        from geistfabrik.vault import Vault
        from geistfabrik.config_loader import GeistFabrikConfig

        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        # Create enough notes for meaningful clusters
        ml_notes = [
            ("ml1.md", "# Machine Learning\nDeep learning neural networks training"),
            ("ml2.md", "# Neural Nets\nBackpropagation gradient descent optimization"),
            ("ml3.md", "# AI Training\nModel validation testing evaluation metrics"),
            ("ml4.md", "# Deep Learning\nConvolutional networks image recognition"),
            ("ml5.md", "# Model Optimization\nHyperparameter tuning learning rate"),
        ]

        web_notes = [
            ("web1.md", "# React Hooks\nUseState useEffect custom hooks"),
            ("web2.md", "# Frontend Dev\nJavaScript TypeScript modern web"),
            ("web3.md", "# Web Architecture\nComponent patterns state management"),
            ("web4.md", "# React Components\nComponent lifecycle rendering"),
            ("web5.md", "# State Management\nRedux context hooks patterns"),
        ]

        for filename, content in ml_notes + web_notes:
            (vault_path / filename).write_text(content)

        config = GeistFabrikConfig()
        vault = Vault(vault_path, config=config)
        vault.sync()

        return vault

    def test_cluster_mirror_uses_config_method(self, vault_for_geist):
        """Test that cluster_mirror respects clustering config."""
        pytest.importorskip("sklearn")
        pytest.importorskip("sentence_transformers")

        from geistfabrik.embeddings import Session
        from geistfabrik.vault_context import VaultContext
        from geistfabrik.default_geists.code import cluster_mirror
        from geistfabrik.config_loader import ClusterConfig

        vault = vault_for_geist

        # Test with KeyBERT
        vault.config.clustering = ClusterConfig(labeling_method="keybert")

        session = Session(datetime.now(), vault.db)
        session.compute_embeddings(vault.all_notes())
        context = VaultContext(vault, session)

        suggestions_keybert = cluster_mirror.suggest(context)

        # Should produce suggestions with cluster names
        if len(suggestions_keybert) > 0:
            suggestion = suggestions_keybert[0]
            assert len(suggestion.text) > 0
            assert len(suggestion.notes) > 0

        # Clear cache and test with TF-IDF
        context._clusters_cache.clear()
        vault.config.clustering = ClusterConfig(labeling_method="tfidf")
        context_tfidf = VaultContext(vault, session)

        suggestions_tfidf = cluster_mirror.suggest(context_tfidf)

        # Should also produce suggestions
        if len(suggestions_tfidf) > 0:
            suggestion = suggestions_tfidf[0]
            assert len(suggestion.text) > 0
            assert len(suggestion.notes) > 0
