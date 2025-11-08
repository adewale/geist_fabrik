#!/usr/bin/env python3
"""Compare cluster labeling approaches: c-TF-IDF vs KeyBERT.

This script runs both labeling methods on a test vault and generates
a side-by-side comparison showing:
- Cluster sizes
- c-TF-IDF labels (current method)
- KeyBERT labels (new method)
- Sample notes from each cluster
"""

import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from geistfabrik.embeddings import Session  # noqa: E402
from geistfabrik.stats import EmbeddingMetricsComputer  # noqa: E402
from geistfabrik.vault import Vault  # noqa: E402


def run_comparison(vault_path: str) -> None:
    """Run cluster labeling comparison on vault.

    Args:
        vault_path: Path to Obsidian vault
    """
    print("🔬 Cluster Naming Comparison: c-TF-IDF vs KeyBERT\n")
    print(f"Vault: {vault_path}\n")
    print("=" * 80 + "\n")

    # Load vault and config
    vault_path_obj = Path(vault_path).expanduser()
    config_path = vault_path_obj / "_geistfabrik" / "config.yaml"
    from geistfabrik.config_loader import load_config

    config = load_config(config_path)
    vault = Vault(vault_path_obj, config=config)

    # Sync vault to load notes into database
    num_synced = vault.sync()
    print(f"Synced {num_synced} notes\n")

    # Get or create today's session
    session_date = datetime.now()
    session = Session(session_date, vault.db, backend="in-memory")

    # Compute embeddings if needed
    notes = vault.all_notes()
    if len(notes) == 0:
        print("❌ No notes found in vault")
        return

    print(f"📊 Processing {len(notes)} notes...\n")

    # Check if embeddings exist for this session
    cursor = vault.db.execute(
        "SELECT COUNT(*) FROM session_embeddings WHERE session_id = ?",
        (session.session_id,),
    )
    embedding_count = cursor.fetchone()[0]

    if embedding_count == 0:
        print("Computing embeddings (this may take a moment)...")
        session.compute_embeddings(notes)
    else:
        print(f"Using existing embeddings for session {session.session_id}")

    # Get embeddings and paths
    cursor = vault.db.execute(
        """
        SELECT note_path, embedding FROM session_embeddings
        WHERE session_id = ?
        """,
        (session.session_id,),
    )
    embeddings_dict = {}
    for row in cursor.fetchall():
        note_path, embedding_bytes = row
        embeddings_dict[note_path] = np.frombuffer(embedding_bytes, dtype=np.float32)

    paths = list(embeddings_dict.keys())
    embeddings_array = np.array([embeddings_dict[p] for p in paths])

    # Run clustering
    print("\n🔍 Running HDBSCAN clustering...")
    try:
        from sklearn.cluster import HDBSCAN  # type: ignore[import-untyped]
    except ImportError:
        print("❌ sklearn not available - install with: uv pip install scikit-learn")
        return

    clusterer = HDBSCAN(min_cluster_size=5, min_samples=3)
    labels = clusterer.fit_predict(embeddings_array)

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = np.sum(labels == -1)

    print(f"Found {n_clusters} clusters ({n_noise} noise points)\n")

    if n_clusters == 0:
        print("❌ No clusters found (vault may be too small or too homogeneous)")
        return

    # Run both labeling methods
    print("🏷️  Generating labels with both methods...\n")

    metrics_computer = EmbeddingMetricsComputer(vault.db, config)

    # Method 1: c-TF-IDF (current)
    print("  Computing c-TF-IDF labels...")
    tfidf_labels = metrics_computer._label_clusters_tfidf(paths, labels, n_terms=4)

    # Method 2: KeyBERT (new)
    print("  Computing KeyBERT labels...")
    try:
        keybert_labels = metrics_computer._label_clusters_keybert(paths, labels, n_terms=4)
    except Exception as e:
        print(f"  ⚠️  KeyBERT failed: {e}")
        print("  Using simple labels as fallback")
        keybert_labels = {cid: f"Cluster {cid}" for cid in set(labels) if cid != -1}

    # Display comparison
    print("=" * 80)
    print("COMPARISON RESULTS")
    print("=" * 80)

    cluster_ids = sorted(set(labels))
    cluster_ids = [c for c in cluster_ids if c != -1]  # Remove noise cluster

    for cluster_id in cluster_ids:
        # Get notes in this cluster
        cluster_note_paths = [paths[i] for i, label in enumerate(labels) if label == cluster_id]
        cluster_size = len(cluster_note_paths)

        # Get sample note titles
        sample_notes = []
        for path in cluster_note_paths[:3]:  # First 3 notes
            cursor = vault.db.execute("SELECT title FROM notes WHERE path = ?", (path,))
            row = cursor.fetchone()
            if row:
                sample_notes.append(row[0])

        # Get labels
        tfidf_label = tfidf_labels.get(cluster_id, f"Cluster {cluster_id}")
        keybert_label = keybert_labels.get(cluster_id, f"Cluster {cluster_id}")

        # Display
        print(f"\n📁 Cluster {cluster_id} ({cluster_size} notes)")
        print("-" * 80)
        print(f"🔤 c-TF-IDF:  {tfidf_label}")
        print(f"🧠 KeyBERT:   {keybert_label}")
        print("\n   Sample notes:")
        for note_title in sample_notes:
            print(f"   • {note_title}")

    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print(f"""
📊 Summary:
   • Total clusters: {n_clusters}
   • Notes clustered: {len(labels) - n_noise}
   • Noise points: {n_noise}

🔍 Method Comparison:
   • c-TF-IDF: Frequency-based keyword extraction
     - Fast, deterministic
     - Focuses on term frequency within cluster
     - May select common but less meaningful terms

   • KeyBERT: Semantic similarity-based extraction
     - Leverages existing embeddings
     - Selects terms semantically similar to cluster centroid
     - May identify more coherent conceptual labels
     - Uses 1-3 word n-grams (vs 1-2 for c-TF-IDF)

💡 Next Steps:
   • Review labels above - which method produces more meaningful names?
   • Consider hybrid approach: TF-IDF for candidates, KeyBERT for ranking
   • Implement UMass coherence metric for quantitative comparison
    """)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python compare_cluster_labeling.py <vault_path>")
        print("\nExample:")
        print("  python scripts/compare_cluster_labeling.py testdata/kepano-obsidian-main")
        sys.exit(1)

    vault_path = sys.argv[1]
    run_comparison(vault_path)


if __name__ == "__main__":
    main()
