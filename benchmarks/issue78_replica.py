"""Replica of GitHub issue #78's benchmark conditions (3,175-note vault).

Builds a synthetic vault matching the issue's scale, injects a deterministic
hash-based stub model (timings of the similarity/graph machinery depend on
N and dimensionality, not embedding values), then runs the issue's headline
geists sequentially on one shared VaultContext - mirroring a real session.

Written to run UNCHANGED on both the current branch and the issue's commit
(3b248e6), so the two runs are directly comparable:
    uv run python benchmarks/issue78_replica.py
    (cd <worktree-of-3b248e6> && uv run python .../issue78_replica.py)

Avoids every API renamed since the issue (count=/link_text/...): only
Vault/Session/VaultContext construction and geist.suggest() are used.
"""

import hashlib
import importlib
import os
import random
import sys
import time

# Cluster labeling (keybert default) lazily constructs a real model; force the
# offline path so both runs fall back to fast deterministic labels instead of
# attempting a HuggingFace download. Identical effect on both commits.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("GEISTFABRIK_OFFLINE", "1")
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from geistfabrik import Session, Vault
from geistfabrik.embeddings import EmbeddingComputer
from geistfabrik.function_registry import FunctionRegistry
from geistfabrik.vault_context import VaultContext

NOTE_COUNT = 3175  # issue #78's vault size
SESSION_DATE = datetime(2024, 3, 15)

GEISTS = [
    "columbo",
    "hidden_hub",
    "island_hopper",
    "method_scrambler",
    "cluster_evolution_tracker",
    "temporal_drift",
    "task_archaeology",
    "blind_spot_detector",
]

TOPICS = [
    "machine learning", "garden design", "stoic philosophy", "woodworking",
    "distributed systems", "watercolour painting", "running training",
    "sourdough baking", "music theory", "urban planning", "astronomy",
    "negotiation tactics", "typography", "permaculture", "chess openings",
]


class StubModel:
    """Deterministic hash-based encoder (no network, no torch inference)."""

    def encode(self, texts, convert_to_numpy=True, show_progress_bar=False, batch_size=8):
        single = isinstance(texts, str)
        items = [texts] if single else texts
        out = []
        for t in items:
            seed = int.from_bytes(hashlib.sha256(str(t).encode()).digest()[:4], "big")
            rng = np.random.RandomState(seed)
            v = rng.randn(384).astype(np.float32)
            out.append(v / np.linalg.norm(v))
        arr = np.array(out, dtype=np.float32)
        return arr[0] if single else arr


def build_vault(root: Path) -> None:
    rng = random.Random(78)
    hubs = [f"Hub {t.title()}" for t in TOPICS]
    for i, h in enumerate(hubs):
        (root / f"{h}.md").write_text(
            f"# {h}\nCentral reference on {TOPICS[i]}. "
            f"Recurring questions about {TOPICS[i]} methods appear here.\n"
        )
    for i in range(NOTE_COUNT - len(hubs)):
        topic = TOPICS[i % len(TOPICS)]
        words = [rng.choice(topic.split()) for _ in range(3)]
        body = [
            f"# Note {i:04d} {topic.title()}",
            f"Thinking about {topic} and the practice of {words[0]} {words[1]}.",
            f"The {topic} methods keep recurring across projects.",
        ]
        if rng.random() < 0.5:
            body.append(f"See [[Hub {topic.title()}]] for the core ideas.")
        if rng.random() < 0.2:
            body.append(f"Also relates to [[Note {rng.randrange(NOTE_COUNT - 15):04d} "
                        f"{TOPICS[rng.randrange(len(TOPICS))].title()}]].")
        if rng.random() < 0.15:
            body.append("- [ ] follow up on this\n- [x] initial read done")
        if rng.random() < 0.3:
            body.append(f"#{topic.split()[0]}")
        (root / f"Note {i:04d} {topic.title()}.md").write_text("\n".join(body) + "\n")


def main() -> None:
    with TemporaryDirectory() as tmp:
        vault_path = Path(tmp)
        build_vault(vault_path)

        vault = Vault(str(vault_path), ":memory:")
        vault.sync()

        # Spread created/modified over 3 years before the session date so
        # temporal geists (staleness, old_notes) have real work to do.
        rng = random.Random(7878)
        rows = vault.db.execute("SELECT path FROM notes").fetchall()
        for (path,) in rows:
            age = rng.randrange(5, 1100)
            ts = (SESSION_DATE - timedelta(days=age)).isoformat()
            vault.db.execute(
                "UPDATE notes SET created = ?, modified = ? WHERE path = ?", (ts, ts, path)
            )
        vault.db.commit()

        computer = EmbeddingComputer()
        computer._model = StubModel()  # inject: identical on both commits

        t0 = time.perf_counter()
        session = Session(SESSION_DATE, vault.db, computer=computer)
        session.compute_embeddings(vault.all_notes())
        embed_s = time.perf_counter() - t0

        context = VaultContext(
            vault, session, seed=20240315, function_registry=FunctionRegistry()
        )
        n = len(context.notes())
        print(f"vault: {n} notes | embedding phase: {embed_s:.1f}s (stub model)", flush=True)
        print(f"{'geist':<28} {'time (s)':>9} {'suggestions':>12}")
        print("-" * 53)

        total = 0.0
        for gid in GEISTS:
            try:
                mod = importlib.import_module(f"geistfabrik.default_geists.code.{gid}")
            except ImportError:
                print(f"{gid:<28} {'(absent)':>9}")
                continue
            t0 = time.perf_counter()
            try:
                suggestions = mod.suggest(context)
                elapsed = time.perf_counter() - t0
                total += elapsed
                print(f"{gid:<28} {elapsed:>9.3f} {len(suggestions):>12}", flush=True)
            except Exception as e:  # the issue-era cluster_evolution_tracker crashes
                elapsed = time.perf_counter() - t0
                total += elapsed
                print(f"{gid:<28} {elapsed:>9.3f}  ERROR: {type(e).__name__}", flush=True)
        print("-" * 53)
        print(f"{'total (these geists)':<28} {total:>9.3f}")
        vault.close()


if __name__ == "__main__":
    sys.exit(main())
