# GeistFabrik Stats Command Specification

**Version**: 1.0
**Status**: ✅ Implemented
**Author**: Research synthesis from embedding corpus analysis
**Spec Date**: 2025-01-30
**Implementation Date**: 2025-01-30
**Implementation**: src/geistfabrik/stats.py (26 passing tests)

---

## Overview

The `stats` command provides a comprehensive, read-only overview of vault health, structure, and GeistFabrik state without executing geists or computing new embeddings. It serves as a "vault health check" and diagnostic tool for understanding knowledge base characteristics.

### Design Principles

1. **Fast** - Complete in < 1 second for typical vaults (100-2000 notes)
2. **Read-only** - Never modifies files or computes new embeddings
3. **Informative** - Provides actionable insights, not just numbers
4. **Tiered output** - Summary by default, detailed with `--verbose`
5. **Scriptable** - Optional JSON output for automation

---

## Command Syntax

```bash
geistfabrik stats [vault_path] [--verbose] [--json] [--history DAYS]
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `vault_path` | Path | Auto-detect | Path to Obsidian vault (optional, detects from cwd) |
| `--verbose`, `-v` | Flag | False | Show detailed statistics and breakdowns |
| `--json` | Flag | False | Output as JSON for scripting |
| `--history DAYS` | Int | 30 | Days of session history to analyze |

### Examples

```bash
# Basic stats (auto-detect vault)
geistfabrik stats

# Stats for specific vault
geistfabrik stats ~/Documents/MyVault

# Detailed output with breakdowns
geistfabrik stats --verbose

# JSON output for scripting
geistfabrik stats --json > vault_stats.json

# Analyze last 60 days of sessions
geistfabrik stats --history 60
```

---

## Output Sections

### Section 1: Vault Overview

**Always displayed**

```
================================================
GeistFabrik Vault Statistics
================================================
Vault: /Users/user/Documents/MyVault
Database: _geistfabrik/vault.db (12.34 MB)
Last sync: 2025-01-30 14:32:15
Configuration: _geistfabrik/config.yaml
```

**Data sources:**
- Vault path: From argument or auto-detection
- Database size: `os.stat(db_path).st_size`
- Last sync: Most recent note `file_mtime` from database
- Configuration: Existence check

---

### Section 2: Note Statistics

**Always displayed**

```
Notes:
  Total: 247 notes
  Regular notes: 235 (95.1%)
  Virtual notes: 12 (4.9%) from 3 date-collection files
  Average note age: 142 days
  Most recent: 2025-01-30
  Oldest: 2023-06-15

Tags:
  Unique tags: 45
  Total tag instances: 312
  Average tags per note: 1.26
  Most used: #project (23 notes), #todo (18 notes), #idea (15 notes)

Links:
  Total links: 1,234
  Average links per note: 5.0
  Bidirectional links: 234 (18.9%)
```

**Data sources:**
```sql
-- Total notes
SELECT COUNT(*) FROM notes;

-- Regular vs virtual
SELECT COUNT(*) FROM notes WHERE is_virtual = 0;
SELECT COUNT(*) FROM notes WHERE is_virtual = 1;

-- Virtual note sources
SELECT source_file, COUNT(*)
FROM notes
WHERE is_virtual = 1
GROUP BY source_file;

-- Note ages
SELECT
  AVG(julianday('now') - julianday(created)) as avg_age,
  MAX(modified) as most_recent,
  MIN(created) as oldest
FROM notes;

-- Tag stats
SELECT COUNT(DISTINCT tag) FROM tags;
SELECT COUNT(*) FROM tags;
SELECT tag, COUNT(*) as cnt
FROM tags
GROUP BY tag
ORDER BY cnt DESC
LIMIT 3;

-- Link stats
SELECT COUNT(*) FROM links;
SELECT COUNT(DISTINCT source_path) FROM links;
-- Bidirectional: links where reverse link exists
```

**Verbose additions:**
```
Top 10 Most Linked Notes:
  1. [[Index]] - 45 outgoing, 32 incoming (77 total)
  2. [[Projects]] - 32 outgoing, 28 incoming (60 total)
  3. [[People]] - 28 outgoing, 15 incoming (43 total)
  ...

Tag Distribution:
  #project: 23 notes (9.3%)
  #todo: 18 notes (7.3%)
  #idea: 15 notes (6.1%)
  #research: 12 notes (4.9%)
  #meeting: 8 notes (3.2%)
  [40 more tags...]

Virtual Notes by Source:
  journal/2025-Q1.md → 45 virtual entries
  journal/2025-Q2.md → 32 virtual entries
  meetings/All Hands.md → 12 virtual entries
```

---

### Section 3: Graph Structure

**Always displayed**

```
Graph Structure:
  Orphans: 23 notes (9.3%)
  Hubs (≥10 connections): 8 notes
  Average degree: 5.0 links/note
  Density: 0.021 (2.1% of possible links exist)
  Largest connected component: 224 notes (90.7%)
```

**Data sources:**
```python
# Orphans: notes with no incoming or outgoing links
orphans = vault.orphans()

# Hubs: notes with high link count
all_links = vault.db.execute("SELECT source_path, COUNT(*) FROM links GROUP BY source_path")
hubs = [note for note, count in all_links if count >= 10]

# Density: actual_links / possible_links
n = len(vault.all_notes())
possible_links = n * (n - 1)
actual_links = vault.db.execute("SELECT COUNT(*) FROM links").fetchone()[0]
density = actual_links / possible_links

# Connected components: Use NetworkX on link graph
```

**Verbose additions:**
```
Orphan Notes (no links):
  [[Random Idea 2023-06-15]]
  [[Quick Note on X]]
  [[Untitled Note]]
  ...

Hub Notes (≥10 connections):
  [[Index]] (77 connections)
  [[Projects]] (60 connections)
  [[People]] (43 connections)
  ...

Bridge Notes (high betweenness centrality):
  [[Systems Thinking]] - connects 3 major communities
  [[Interdisciplinary Methods]] - connects 2 communities
  ...
```

---

### Section 4: Embedding & Semantic Statistics

**Always displayed** (if embeddings exist)

```
Semantic Structure:
  Backend: sqlite-vec
  Embedding dimension: 387 (384 semantic + 3 temporal)

  Intrinsic dimensionality: 15.3 dimensions
  Diversity (Vendi Score): 142.7 effective concepts
  Shannon entropy: 2.81 bits

  Clusters detected: 7 (HDBSCAN, min_size=5)
  Clustering quality (Silhouette): 0.42 (moderate)
  Notes in gaps: 18 (7.3%)
```

**Data sources:**
```python
from sklearn.cluster import HDBSCAN
from sklearn.metrics import silhouette_score
from sklearn.neighbors import LocalOutlierFactor
from skdim.id import TwoNN
from vendi_score import vendi
from scipy.stats import entropy

# Get embeddings from most recent session
embeddings = session.get_all_embeddings()

# Intrinsic dimensionality
id_estimator = TwoNN()
intrinsic_dim = id_estimator.fit_transform(embeddings)

# Vendi Score
K = cosine_similarity(embeddings)
vendi_score = vendi.score_K(K)

# Shannon entropy (requires clustering first)
clusterer = HDBSCAN(min_cluster_size=5)
labels = clusterer.fit_predict(embeddings)
cluster_dist = np.bincount(labels[labels >= 0]) / len(labels[labels >= 0])
shannon = entropy(cluster_dist)

# Clustering quality
if len(set(labels)) > 1:
    silhouette = silhouette_score(embeddings, labels)

# Gap detection
lof = LocalOutlierFactor(n_neighbors=20, contamination=0.1)
gap_scores = lof.fit_predict(embeddings)
n_gaps = np.sum(gap_scores == -1)
```

**Verbose additions:**
```
Detected Clusters:
  1. "machine learning, neural networks, deep" (28 notes)
  2. "philosophy, ethics, epistemology, moral" (23 notes)
  3. "project management, planning, agile" (19 notes)
  4. "writing, blog, articles, communication" (15 notes)
  5. "python, programming, software, code" (12 notes)
  6. "productivity, workflow, habits, systems" (8 notes)
  7. "reading, books, literature, notes" (7 notes)
  Noise/Gaps: 18 notes (7.3%)

Cluster Naming Method: c-TF-IDF (top 5 terms)

Space Utilization:
  IsoScore: 0.67 (healthy distribution)
  Embedding space usage: 67% of available variance
  Unused dimensions: ~127 (effectively redundant)

Semantic Health:
  ✓ Good clustering structure (Silhouette: 0.42)
  ✓ High conceptual diversity (Vendi: 142.7)
  ⚠ 18 notes in low-density regions (potential gaps)
```

**Implementation notes:**
- Cluster naming: Use c-TF-IDF for speed (see Section 7 for implementation)
- IsoScore: Compute from eigenvalues of covariance matrix
- Cache these metrics to avoid recomputing on every `stats` call

---

### Section 5: Session History

**Always displayed** (if sessions exist)

```
Sessions:
  Total sessions: 15
  Date range: 2025-01-05 to 2025-01-30
  Average interval: 1.7 days

  Suggestions generated: 234 total
  Average per session: 15.6 suggestions

  Recent sessions (last 5):
    2025-01-30: 18 suggestions (12 geists active)
    2025-01-29: 12 suggestions (11 geists active)
    2025-01-28: 16 suggestions (12 geists active)
    2025-01-27: 14 suggestions (10 geists active)
    2025-01-26: 20 suggestions (12 geists active)
```

**Data sources:**
```sql
-- Session count
SELECT COUNT(*) FROM sessions;

-- Date range
SELECT MIN(date), MAX(date) FROM sessions;

-- Suggestions per session
SELECT
  ss.session_date,
  COUNT(*) as suggestion_count,
  COUNT(DISTINCT ss.geist_id) as active_geists
FROM session_suggestions ss
GROUP BY ss.session_date
ORDER BY ss.session_date DESC
LIMIT 5;

-- Total suggestions
SELECT COUNT(*) FROM session_suggestions;
```

**Verbose additions:**
```
Session Activity Over Time:
  Week 1 (Jan 05-11): 4 sessions, 62 suggestions (avg: 15.5)
  Week 2 (Jan 12-18): 3 sessions, 45 suggestions (avg: 15.0)
  Week 3 (Jan 19-25): 4 sessions, 68 suggestions (avg: 17.0)
  Week 4 (Jan 26-30): 4 sessions, 59 suggestions (avg: 14.8)

Most Active Geists (last 30 days):
  1. temporal_drift: 34 suggestions (22.7%)
  2. bridge_builder: 28 suggestions (18.7%)
  3. concept_cluster: 21 suggestions (14.0%)
  4. columbo: 18 suggestions (12.0%)
  5. creative_collision: 15 suggestions (10.0%)
  [40 more geists...]

Temporal Patterns:
  Most productive day: Monday (28% of sessions)
  Least productive day: Saturday (4% of sessions)
  Preferred time: No data (would require timestamp, not just date)
```

---

### Section 6: Temporal Embedding Analysis

**Always displayed** (if multiple sessions exist)

```
Temporal Analysis:
  Sessions with embeddings: 15
  Oldest embeddings: 2025-01-05
  Most recent: 2025-01-30

  Semantic drift analysis (last 30 days):
    Average drift rate: 0.15 per session
    Drift accelerating: Yes (+12% vs previous period)

  High-drift notes (evolving concepts):
    [[Machine Learning Ethics]] - drift: 0.73
    [[Personal Philosophy]] - drift: 0.68
    [[Software Architecture]] - drift: 0.61

  Stable anchors (unchanging meaning):
    [[Python Basics]] - drift: 0.02
    [[Daily Routines]] - drift: 0.04
    [[Meeting Templates]] - drift: 0.05
```

**Data sources:**
```python
from scipy.linalg import orthogonal_procrustes

# Get embeddings from two time points (30 days apart)
current_date = datetime.now()
past_date = current_date - timedelta(days=30)

current_emb = session.get_embeddings(current_date)
past_emb = session.get_embeddings(past_date)

# Align embedding spaces via Procrustes
R, scale = orthogonal_procrustes(past_emb, current_emb)
aligned_past = past_emb @ R

# Compute drift per note
drift_scores = 1 - cosine_similarity(aligned_past, current_emb).diagonal()

# Identify high-drift and low-drift notes
high_drift_idx = np.argsort(drift_scores)[-5:]
low_drift_idx = np.argsort(drift_scores)[:5]

# Average drift rate
avg_drift = drift_scores.mean()
```

**Requirements:**
- Only display if at least 2 sessions exist
- Default: compare current session to 30 days ago (adjustable via `--history`)
- Skip if sessions don't span enough time

**Verbose additions:**
```
Drift Distribution:
  Very stable (drift < 0.1): 45 notes (18.2%)
  Stable (drift 0.1-0.3): 128 notes (51.8%)
  Moderate (drift 0.3-0.5): 52 notes (21.1%)
  High (drift 0.5-0.7): 18 notes (7.3%)
  Very high (drift > 0.7): 4 notes (1.6%)

Temporal Clustering:
  Notes that clustered together 30 days ago but separated: 12 pairs
  Notes that were separate but now cluster: 8 pairs
  New clusters emerged: 2 (since 30 days ago)
  Clusters dissolved: 1

Diversity Evolution:
  30 days ago: Vendi Score = 128.4
  Today: Vendi Score = 142.7
  Change: +11.2% (expanding conceptual territory)
```

---

### Section 7: Geist Configuration

**Always displayed**

```
Geists:
  Code geists: 35 total (31 enabled, 4 disabled)
  Tracery geists: 10 total (10 enabled)
  Custom geists: 2 (in _geistfabrik/geists/)

  Total enabled: 43 geists

  Disabled geists:
    temporal_drift: 3 consecutive failures
    broken_custom_geist: 3 consecutive failures

  Configuration: _geistfabrik/config.yaml
  Default geists: 45 bundled (43 enabled in config)
```

**Data sources:**
```python
from geistfabrik import load_config, DEFAULT_CODE_GEISTS, DEFAULT_TRACERY_GEISTS
from geistfabrik.geist_executor import GeistExecutor

config = load_config(vault_path / "_geistfabrik" / "config.yaml")

# Default geists
default_code_count = len(DEFAULT_CODE_GEISTS)
default_tracery_count = len(DEFAULT_TRACERY_GEISTS)

# Custom geists
custom_code_dir = vault_path / "_geistfabrik" / "geists" / "code"
custom_tracery_dir = vault_path / "_geistfabrik" / "geists" / "tracery"
custom_code_count = len(list(custom_code_dir.glob("*.py"))) if custom_code_dir.exists() else 0
custom_tracery_count = len(list(custom_tracery_dir.glob("*.yaml"))) if custom_tracery_dir.exists() else 0

# Enabled/disabled from config
enabled_count = sum(1 for v in config.default_geists.values() if v)
disabled_count = len(config.default_geists) - enabled_count

# Failure tracking (would need to add to database schema)
# Could query execution logs to find recently failed geists
```

**Verbose additions:**
```
Enabled Code Geists (31):
  - anachronism_detector
  - assumption_challenger
  - blind_spot_detector
  - bridge_builder
  - bridge_hunter
  ... [26 more]

Enabled Tracery Geists (10):
  - contradictor
  - hub_explorer
  - note_combinations
  - orphan_connector
  - perspective_shifter
  ... [5 more]

Custom Geists (2):
  Code:
    - my_custom_geist.py (in _geistfabrik/geists/code/)
  Tracery:
    - None

Backend Configuration:
  Vector search backend: sqlite-vec
  Embedding model: all-MiniLM-L6-v2 (384 dims + 3 temporal)
  Timeout: 5 seconds per geist
  Max failures before disable: 3
```

---

### Section 8: Recommendations

**Always displayed** (when issues detected)

```
Recommendations:

  ⚠ Performance
    • Consider sqlite-vec backend (current: in-memory)
      Your vault has 1,847 notes - sqlite-vec provides 5-6x faster queries
      Install: uv pip install -e ".[vector-search]"
      Configure: vector_backend: sqlite-vec in config.yaml

  ⚠ Knowledge Structure
    • 23 orphan notes (9.3%) - consider linking or tagging
      Run: geistfabrik invoke --geist orphan_connector

    • 18 notes in semantic gaps (potential bridges)
      Run: geistfabrik invoke --geist bridge_builder

  ⚠ Geist Health
    • 4 geists disabled due to failures
      Test individually: geistfabrik test temporal_drift

  ✓ All checks passed
    • Vault structure is healthy
    • Embeddings are up to date
    • Configuration is valid
```

**Heuristics:**

1. **Backend recommendation:**
   - If `n_notes > 1000` and `backend == "in-memory"`: Recommend sqlite-vec

2. **Orphan alert:**
   - If `orphan_pct > 10%`: Recommend orphan_connector geist

3. **Gap alert:**
   - If `gap_pct > 5%`: Recommend bridge_builder or semantic_gap geist

4. **Disabled geist alert:**
   - If any geists disabled: Recommend testing them individually

5. **Diversity alert:**
   - If `vendi_score` decreasing over time: Alert about narrowing focus
   - If `shannon_entropy < 1.5`: Alert about over-clustering

6. **Drift alert:**
   - If `avg_drift > 0.5`: Alert about rapid conceptual change
   - If `avg_drift < 0.05`: Alert about stagnation

---

## Implementation Details

### File Structure

```
src/geistfabrik/
  cli.py                 # Add stats_command() function
  stats/                 # New module
    __init__.py
    collector.py         # Data collection from DB
    metrics.py           # Compute embedding metrics
    formatter.py         # Format output (text/JSON)
    recommendations.py   # Generate recommendations
```

### Core Algorithm

```python
def stats_command(args: argparse.Namespace) -> int:
    """Execute the stats command."""
    # 1. Load vault and config (no sync needed - read existing DB)
    vault_path = Path(args.vault) if args.vault else find_vault_root()
    db_path = vault_path / "_geistfabrik" / "vault.db"

    if not db_path.exists():
        print("Error: GeistFabrik not initialized. Run: geistfabrik init")
        return 1

    vault = Vault(vault_path, db_path)
    config = load_config(vault_path / "_geistfabrik" / "config.yaml")

    # 2. Collect statistics (fast DB queries + cached metrics)
    stats = StatsCollector(vault, config, history_days=args.history)

    # 3. Compute embedding metrics (only if embeddings exist)
    if stats.has_embeddings():
        metrics = compute_embedding_metrics(stats.get_latest_embeddings())
        stats.add_embedding_metrics(metrics)

    # 4. Generate recommendations
    recommendations = generate_recommendations(stats)

    # 5. Format output
    if args.json:
        output = JSONFormatter(stats, recommendations).format()
    else:
        output = TextFormatter(stats, recommendations, verbose=args.verbose).format()

    print(output)
    vault.close()
    return 0
```

### Caching Strategy

**Problem:** Computing embedding metrics (Vendi Score, intrinsic dimensionality, clustering) is expensive (1-2 seconds for 1000 notes).

**Solution:** Cache metrics in database, recompute only when embeddings change.

```sql
-- Add new table for cached metrics
CREATE TABLE IF NOT EXISTS embedding_metrics (
    session_date TEXT PRIMARY KEY,
    intrinsic_dim REAL,
    vendi_score REAL,
    shannon_entropy REAL,
    silhouette_score REAL,
    n_clusters INTEGER,
    n_gaps INTEGER,
    cluster_labels TEXT,  -- JSON: {0: "ml, neural, networks", 1: "philosophy, ethics"}
    computed_at TEXT NOT NULL,
    FOREIGN KEY (session_date) REFERENCES sessions(date) ON DELETE CASCADE
);
```

**Caching logic:**
```python
# Check if metrics already computed
cursor = db.execute(
    "SELECT * FROM embedding_metrics WHERE session_date = ?",
    (session_date,)
)
cached = cursor.fetchone()

if cached and not args.force_recompute:
    return cached_metrics
else:
    # Compute expensive metrics
    metrics = compute_all_metrics(embeddings)

    # Cache for next time
    db.execute("""
        INSERT OR REPLACE INTO embedding_metrics
        (session_date, intrinsic_dim, vendi_score, ..., computed_at)
        VALUES (?, ?, ?, ..., ?)
    """, (session_date, metrics.intrinsic_dim, metrics.vendi_score, ..., now))

    return metrics
```

### Performance Targets

| Vault Size | Target Time | With Cache |
|------------|-------------|------------|
| 100 notes | < 0.5s | < 0.1s |
| 500 notes | < 1.0s | < 0.2s |
| 1000 notes | < 2.0s | < 0.3s |
| 2000 notes | < 3.0s | < 0.5s |

### Dependencies

**New dependencies** (add to `pyproject.toml`):

```toml
[project.optional-dependencies]
stats = [
    "scikit-dimension>=0.3.0",  # Intrinsic dimensionality
    "vendi-score>=0.1.0",       # Vendi Score
    "hdbscan>=0.8.0",           # Clustering (already in project)
]
```

**Install:**
```bash
uv pip install -e ".[stats]"
```

### Cluster Naming Implementation

**c-TF-IDF approach** (fast, default):

```python
from sklearn.feature_extraction.text import TfidfVectorizer

def label_clusters_tfidf(notes, labels, n_terms=5):
    """Generate cluster labels using class-based TF-IDF."""
    cluster_labels = {}

    # Group notes by cluster
    clusters = {}
    for i, label in enumerate(labels):
        if label == -1:
            continue
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(notes[i])

    # Concatenate all text per cluster
    cluster_texts = {}
    for cluster_id, cluster_notes in clusters.items():
        text = " ".join([n.title + " " + n.content for n in cluster_notes])
        cluster_texts[cluster_id] = text

    # Compute TF-IDF across clusters
    vectorizer = TfidfVectorizer(
        max_features=100,
        stop_words='english',
        ngram_range=(1, 2)  # Include bigrams
    )

    tfidf_matrix = vectorizer.fit_transform(cluster_texts.values())
    feature_names = vectorizer.get_feature_names_out()

    # Extract top terms per cluster
    for i, cluster_id in enumerate(cluster_texts.keys()):
        cluster_vector = tfidf_matrix[i].toarray()[0]
        top_indices = cluster_vector.argsort()[-n_terms:][::-1]
        top_terms = [feature_names[idx] for idx in top_indices]
        cluster_labels[cluster_id] = ", ".join(top_terms)

    return cluster_labels
```

**Optional LLM upgrade** (high quality, slower):

```python
def label_clusters_llm(notes, labels, n_examples=3):
    """Generate cluster labels using LLM (requires Anthropic API key)."""
    import anthropic

    client = anthropic.Anthropic()
    cluster_labels = {}

    for cluster_id in set(labels):
        if cluster_id == -1:
            continue

        cluster_notes = [n for i, n in enumerate(notes) if labels[i] == cluster_id]
        sample_notes = random.sample(cluster_notes, min(n_examples, len(cluster_notes)))

        titles = "\n".join([f"- {note.title}" for note in sample_notes])

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=50,
            messages=[{
                "role": "user",
                "content": f"""Analyze this cluster of notes:

{titles}

Generate a concise 2-4 word label:"""
            }]
        )

        cluster_labels[cluster_id] = message.content[0].text.strip()

    return cluster_labels
```

---

## JSON Output Format

When `--json` flag is used, output structured data:

```json
{
  "vault": {
    "path": "/Users/user/Documents/MyVault",
    "database_size_mb": 12.34,
    "last_sync": "2025-01-30T14:32:15",
    "config_path": "_geistfabrik/config.yaml"
  },
  "notes": {
    "total": 247,
    "regular": 235,
    "virtual": 12,
    "average_age_days": 142,
    "oldest": "2023-06-15",
    "most_recent": "2025-01-30"
  },
  "tags": {
    "unique": 45,
    "total_instances": 312,
    "average_per_note": 1.26,
    "top_tags": [
      {"tag": "#project", "count": 23},
      {"tag": "#todo", "count": 18},
      {"tag": "#idea", "count": 15}
    ]
  },
  "links": {
    "total": 1234,
    "average_per_note": 5.0,
    "bidirectional": 234,
    "bidirectional_pct": 18.9
  },
  "graph": {
    "orphans": 23,
    "orphan_pct": 9.3,
    "hubs": 8,
    "density": 0.021,
    "largest_component_size": 224,
    "largest_component_pct": 90.7
  },
  "embeddings": {
    "backend": "sqlite-vec",
    "dimension": 387,
    "intrinsic_dimensionality": 15.3,
    "vendi_score": 142.7,
    "shannon_entropy": 2.81,
    "n_clusters": 7,
    "silhouette_score": 0.42,
    "n_gaps": 18,
    "gap_pct": 7.3,
    "clusters": [
      {"id": 0, "size": 28, "label": "machine learning, neural networks, deep"},
      {"id": 1, "size": 23, "label": "philosophy, ethics, epistemology, moral"}
    ]
  },
  "sessions": {
    "total": 15,
    "date_range": ["2025-01-05", "2025-01-30"],
    "average_interval_days": 1.7,
    "total_suggestions": 234,
    "average_suggestions_per_session": 15.6,
    "recent_sessions": [
      {"date": "2025-01-30", "suggestions": 18, "active_geists": 12},
      {"date": "2025-01-29", "suggestions": 12, "active_geists": 11}
    ]
  },
  "temporal_analysis": {
    "average_drift_rate": 0.15,
    "drift_trend": "accelerating",
    "drift_change_pct": 12.0,
    "high_drift_notes": [
      {"title": "Machine Learning Ethics", "drift": 0.73},
      {"title": "Personal Philosophy", "drift": 0.68}
    ],
    "stable_notes": [
      {"title": "Python Basics", "drift": 0.02},
      {"title": "Daily Routines", "drift": 0.04}
    ]
  },
  "geists": {
    "code_total": 35,
    "code_enabled": 31,
    "code_disabled": 4,
    "tracery_total": 10,
    "tracery_enabled": 10,
    "custom_total": 2,
    "total_enabled": 43,
    "disabled_geists": [
      {"id": "temporal_drift", "reason": "3 consecutive failures"},
      {"id": "broken_custom_geist", "reason": "3 consecutive failures"}
    ]
  },
  "recommendations": [
    {
      "type": "performance",
      "severity": "warning",
      "message": "Consider sqlite-vec backend for 1847 notes (5-6x faster queries)",
      "action": "uv pip install -e \".[vector-search]\" && update config"
    },
    {
      "type": "structure",
      "severity": "warning",
      "message": "23 orphan notes (9.3%) could be linked or tagged",
      "action": "geistfabrik invoke --geist orphan_connector"
    }
  ]
}
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_stats.py

def test_stats_basic_output(tmp_vault):
    """Test basic stats output."""
    result = stats_command(vault_path=tmp_vault)
    assert result == 0
    assert "Vault Statistics" in output

def test_stats_json_output(tmp_vault):
    """Test JSON output format."""
    result = stats_command(vault_path=tmp_vault, json=True)
    data = json.loads(result)
    assert "vault" in data
    assert "notes" in data
    assert data["notes"]["total"] > 0

def test_stats_without_embeddings(tmp_vault):
    """Test stats when no embeddings exist."""
    # Should work but skip embedding section
    result = stats_command(vault_path=tmp_vault)
    assert "Semantic Structure" not in output

def test_stats_verbose(tmp_vault):
    """Test verbose output includes additional details."""
    result = stats_command(vault_path=tmp_vault, verbose=True)
    assert "Top 10 Most Linked Notes" in output
    assert "Tag Distribution" in output
```

### Integration Tests

```python
# tests/integration/test_stats_command.py

def test_stats_on_kepano_vault():
    """Test stats on real vault (kepano testdata)."""
    result = cli_invoke(["stats", "testdata/kepano-obsidian-main"])
    assert result.exit_code == 0
    assert "247 notes" in result.output  # Kepano vault has ~247 notes

def test_stats_performance():
    """Test that stats completes in < 1s for 500 note vault."""
    import time
    start = time.time()
    result = cli_invoke(["stats", "testdata/medium-vault"])
    elapsed = time.time() - start
    assert elapsed < 1.0
```

---

## Future Enhancements

### Phase 2 (Post-v1.0)

1. **Historical trends**: `--compare YYYY-MM-DD` to compare stats across time
2. **Export formats**: `--format csv` for spreadsheet analysis
3. **Visualizations**: `--plot` to generate matplotlib charts
4. **Scheduled monitoring**: `geistfabrik stats --watch --interval 24h`
5. **Alerts**: `--alert email@example.com` when metrics cross thresholds

### Phase 3 (Advanced)

1. **ML-based insights**: Predict vault growth, suggest optimal geist mix
2. **Comparative analytics**: Compare vault to anonymized corpus of other vaults
3. **Health score**: Single 0-100 score summarizing vault quality
4. **Auto-optimization**: Suggest config changes to improve metrics

---

## Success Metrics

**Qualitative:**
- Users check vault health before/after major note reorganizations
- Users identify and fix structural issues (orphans, gaps) proactively
- Users understand their vault's conceptual structure better

**Quantitative:**
- `stats` completes in < 1s for 90% of vaults
- JSON output enables scripting/automation use cases
- Recommendations lead to measurable improvements (fewer orphans, higher diversity)

---

## References

- Intrinsic Dimensionality: `scikit-dimension` library
- Vendi Score: Friedman & Dieng (2023), "The Vendi Score"
- HDBSCAN: Campello et al. (2013), "Density-Based Clustering"
- c-TF-IDF: Grootendorst (2022), BERTopic paper
- Semantic Drift: Hamilton et al. (2016), "Diachronic Word Embeddings"
