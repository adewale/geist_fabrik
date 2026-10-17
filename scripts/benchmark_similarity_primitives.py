#!/usr/bin/env python3
"""Matched before/after timings, allocations and observable semantic results.

Each feature runs in an isolated process. Source selection happens before import;
both revisions use the same interpreter, libraries, seeds and input shapes.
Timing and tracemalloc runs are separate. Raw prototype timings are not mixed
with the production primitive measurements.
"""

import argparse
import hashlib
import heapq
import json
import os
import resource
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

FEATURES = (
    "prepare",
    "canonical_matrix",
    "threshold_matrix",
    "ambiguous_threshold",
    "paired",
    "batch_topk",
    "mean",
    "mean_decision",
    "surprisal",
    "threshold_pairs",
    "scored_top_pairs",
    "text_cache",
    "labels",
    "filter_pipeline",
)


def owned_bytes(value, seen=None):
    """Owned Python buffers/containers; excludes borrowed classes and callables."""
    import gc
    from collections.abc import Mapping
    from types import MappingProxyType

    import numpy as np

    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, np.ndarray):
        return size + (owned_bytes(value.base, seen) if value.base is not None else 0)
    if isinstance(value, MappingProxyType):
        # Include the retained backing dict, not just the proxy header.
        return size + sum(owned_bytes(item, seen) for item in gc.get_referents(value))
    if hasattr(value, "__dict__") and type(value).__module__.startswith("geistfabrik"):
        # Custom mappings can manufacture disposable views from __getitem__.
        # Walk their actual retained storage before the generic mapping branch.
        return size + owned_bytes(vars(value), seen)
    if isinstance(value, Mapping):
        return size + sum(owned_bytes(k, seen) + owned_bytes(v, seen) for k, v in value.items())
    if isinstance(value, (tuple, list)):
        return size + sum(owned_bytes(v, seen) for v in value)
    return size


def worker(feature, phase, trials):
    import sqlite3
    from datetime import datetime

    import numpy as np
    from threadpoolctl import threadpool_limits

    from geistfabrik.embeddings import EmbeddingComputer
    from geistfabrik.filtering import SuggestionFilter
    from geistfabrik.models import Suggestion
    from geistfabrik.vector_math import UnitRows
    from geistfabrik.vector_search import InMemoryVectorBackend

    rng = np.random.default_rng(20261018)
    a_raw = rng.normal(size=(1000, 384)).astype(np.float32)
    b_raw = rng.normal(size=(1000, 384)).astype(np.float32)
    b_raw[:25] = a_raw[:25]
    a, b = UnitRows(a_raw), UnitRows(b_raw)
    retained = 0
    observed = {}
    work = {
        "normalization_rows": 0,
        "canonical_pairs": 0,
        "fast_pairs": 0,
        "identity_index_rows": 0,
    }
    original_init = UnitRows.__init__
    original_cosine = UnitRows.cosine

    def counted_init(self, values, *args, **kwargs):
        work["normalization_rows"] += len(values)
        original_init(self, values, *args, **kwargs)

    def counted_cosine(self, other, *args, **kwargs):
        work["canonical_pairs"] += len(self.values) * len(other.values)
        if phase == "before":
            work["identity_index_rows"] += len(other.values)
        return original_cosine(self, other, *args, **kwargs)

    UnitRows.__init__ = counted_init
    UnitRows.cosine = counted_cosine
    if hasattr(UnitRows, "_estimate"):
        original_estimate = UnitRows._estimate

        def counted_estimate(self, other, *args, **kwargs):
            work["fast_pairs"] += len(self.values) * len(other.values)
            return original_estimate(self, other, *args, **kwargs)

        UnitRows._estimate = counted_estimate

    if hasattr(UnitRows, "_install"):
        original_install = UnitRows._install

        def counted_install(self, matrix, keys):
            work["identity_index_rows"] += len(matrix)
            return original_install(self, matrix, keys)

        UnitRows._install = counted_install

    if hasattr(UnitRows, "paired"):
        original_paired = UnitRows.paired

        def counted_paired(self, other, *args, **kwargs):
            work["canonical_pairs"] += len(self.values)
            return original_paired(self, other, *args, **kwargs)

        UnitRows.paired = counted_paired

    def summarize(value):
        return value

    prepared_holder = []
    if hasattr(UnitRows, "_selected_pairs"):
        original_selected = UnitRows._selected_pairs

        def counted_selected(self, other, rows, columns):
            work["canonical_pairs"] += len(rows)
            return original_selected(self, other, rows, columns)

        UnitRows._selected_pairs = counted_selected

    if feature == "prepare":
        raw = rng.normal(size=(10000, 384)).astype(np.float32)

        def run():
            prepared_holder[:] = [UnitRows(raw)]
            return {"rows": len(prepared_holder[0].values)}

    elif feature == "canonical_matrix":
        retained = owned_bytes((a, b))

        def run():
            return a.cosine(b)

        def summarize(matrix):
            return {
                "shape": list(matrix.shape),
                "digest": hashlib.sha256(matrix.tobytes()).hexdigest(),
            }

    elif feature in {"threshold_matrix", "ambiguous_threshold"}:
        threshold = 0.85
        if feature == "ambiguous_threshold":
            left = np.zeros((256, 384))
            left[:, 0] = 1
            right = np.zeros((256, 384))
            right[:, 0] = 0.8
            right[:, 1] = 0.6
            right[::3, 0] = np.nextafter(0.8, 1)
            a, b, threshold = UnitRows(left), UnitRows(right), 0.8
        retained = owned_bytes((a, b))

        def run():
            return a.cosine(b) >= threshold if phase == "before" else a.compare(b, threshold)

        def summarize(matches):
            return {
                "matches": int(matches.sum()),
                "digest": hashlib.sha256(matches.tobytes()).hexdigest(),
            }

    elif feature == "paired":
        retained = owned_bytes((a, b))

        def run():
            return np.diag(a.cosine(b)) if phase == "before" else a.paired(b)

        def summarize(scores):
            return {"pairs": len(scores), "digest": hashlib.sha256(scores.tobytes()).hexdigest()}

    elif feature == "batch_topk":
        raw = rng.normal(size=(10000, 384)).astype(np.float32)
        queries = rng.normal(size=(20, 384)).astype(np.float32)
        db = sqlite3.connect(":memory:")
        backend = InMemoryVectorBackend(db)
        backend.embeddings = {f"n{i:05d}": row for i, row in enumerate(raw)}
        backend._rebuild_matrix()
        retained = owned_bytes(backend)

        def run():
            if phase == "before":
                found = [backend.find_similar(query, count=10) for query in queries]
            else:
                found = backend.find_similar_batch(queries, count=10)
            return found

        def summarize(found):
            return {
                "queries": len(found),
                "digest": hashlib.sha256(json.dumps(found).encode()).hexdigest(),
            }

    elif feature == "surprisal":
        from geistfabrik.vault_context import _surprisal_blocked

        embeddings = {f"n{i:04d}": row for i, row in enumerate(a_raw)}

        def run():
            return _surprisal_blocked(embeddings, 10)

        def summarize(values):
            return {
                "values": values,
                "digest": hashlib.sha256(json.dumps(values).encode()).hexdigest(),
            }

    elif feature in {"mean", "mean_decision"}:
        retained = owned_bytes(a)

        def run():
            if phase == "before":
                matrix = np.clip(a.cosine(a), 0, 1)
                value = float(matrix[np.triu_indices(len(matrix), k=1)].mean())
            elif feature == "mean_decision":
                return {"above_03": a.mean_compare(0.3, inclusive=False)}
            else:
                value = a.mean_similarity()
            return (
                {"above_03": value > 0.3}
                if feature == "mean_decision"
                else {"value": value, "above_03": value > 0.3}
            )

    elif feature == "scored_top_pairs":
        retained = owned_bytes(a)

        def run():
            if phase == "before":
                matrix = a.cosine(a)
                pairs = [
                    (i, j, float(matrix[i, j]))
                    for i in range(len(matrix))
                    for j in range(i + 1, len(matrix))
                    if matrix[i, j] >= 0.15
                ]
                return sorted(pairs, key=lambda item: item[2], reverse=True)[:10]
            return heapq.nlargest(10, a.scored_matching_pairs(0.15), key=lambda item: item[2])

        def summarize(pairs):
            return {
                "matches": len(pairs),
                "digest": hashlib.sha256(json.dumps(pairs).encode()).hexdigest(),
            }

    elif feature == "threshold_pairs":
        retained = owned_bytes(a)

        def run():
            if phase == "before":
                matrix = a.cosine(a)
                pairs = [
                    (i, j)
                    for i in range(len(matrix))
                    for j in range(i + 1, len(matrix))
                    if matrix[i, j] >= 0.15
                ]
            else:
                pairs = list(a.matching_pairs(0.15))
            return pairs

        def summarize(pairs):
            return {
                "matches": len(pairs),
                "digest": hashlib.sha256(json.dumps(pairs).encode()).hexdigest(),
            }

    else:
        # Actual bundled inference; encode counters supply inputs, never decisions.
        os.environ["GEISTFABRIK_OFFLINE"] = "1"
        real = EmbeddingComputer()
        real.device = "cpu"
        model = real.model
        encoder_work = {"calls": 0, "texts": 0}

        class Encoder:
            def encode(self, sentences, **kwargs):
                encoder_work["calls"] += 1
                encoder_work["texts"] += 1 if isinstance(sentences, str) else len(sentences)
                return model.encode(sentences, **kwargs)

        topics = [
            "orchard pruning and apple grafting",
            "jazz piano improvisation",
            "ocean tides and coral reefs",
            "Roman road construction",
            "computer compiler optimization",
            "sourdough bread fermentation",
            "planetary orbits and telescopes",
            "ceramic glazes and pottery kilns",
        ]
        texts = [
            f"What changes when we revisit {topics[i % len(topics)]} through experiment {i}?"
            for i in range(64)
        ]
        if feature == "text_cache":

            def run():
                encoder_work.update(calls=0, texts=0)
                computer = EmbeddingComputer(model=Encoder())
                first = computer.compute_batch_semantic(texts + texts[:16])
                second = computer.compute_batch_semantic(texts[:32])
                return {
                    "encoded": dict(encoder_work),
                    "cache_bytes": getattr(
                        getattr(computer, "text_cache", None), "retained_bytes", 0
                    ),
                    "embedding_values": np.concatenate([first, second]).tolist(),
                    "digest": hashlib.sha256(first.tobytes() + second.tobytes()).hexdigest(),
                }
        elif feature == "labels":
            from geistfabrik.cluster_labeling import label_keybert

            db = sqlite3.connect(":memory:")
            db.execute("CREATE TABLE notes(path TEXT, title TEXT, content TEXT)")
            paths = [f"note{i}" for i in range(32)]
            db.executemany(
                "INSERT INTO notes VALUES (?,?,?)",
                [
                    (path, f"Research {i}", (topics[i // 8] + ". ") * 5)
                    for i, path in enumerate(paths)
                ],
            )
            labels = np.repeat(np.arange(4), 8)

            def run():
                encoder_work.update(calls=0, texts=0)
                computer = EmbeddingComputer(model=Encoder())
                first = label_keybert(paths, labels, db, computer=computer)
                second = label_keybert(paths, labels, db, computer=computer)
                assert first == second
                assert all(not label.startswith("Cluster ") for label in first.values())
                return {
                    "encoded": dict(encoder_work),
                    "cache_bytes": getattr(
                        getattr(computer, "text_cache", None), "retained_bytes", 0
                    ),
                    "labels": {str(int(key)): value for key, value in first.items()},
                }
        else:
            db = sqlite3.connect(":memory:")
            db.execute(
                "CREATE TABLE session_suggestions(session_date TEXT, geist_id TEXT, "
                "suggestion_text TEXT, block_id TEXT, created_at TEXT)"
            )
            history = [
                f"Earlier notes about {topics[i % len(topics)]}: observation {i}."
                for i in range(128)
            ] + texts[:8]
            db.executemany(
                "INSERT INTO session_suggestions VALUES ('2026-01-01','g',?,?,'now')",
                [(text, str(i)) for i, text in enumerate(history)],
            )
            db.commit()
            suggestions = [
                Suggestion(text=text, notes=["Orchards"], geist_id="g")
                for text in texts + texts[8:16]
            ]

            def run():
                encoder_work.update(calls=0, texts=0)
                computer = EmbeddingComputer(model=Encoder())
                filtering = SuggestionFilter(
                    db,
                    computer,
                    config={
                        "strategies": ["novelty", "diversity"],
                        "novelty": {"enabled": True, "window_days": 60, "threshold": 0.98},
                        "diversity": {"enabled": True, "threshold": 0.85},
                    },
                )
                result = filtering.filter_all(suggestions, datetime(2026, 1, 2))
                return {
                    "encoded": dict(encoder_work),
                    "cache_bytes": getattr(
                        getattr(computer, "text_cache", None), "retained_bytes", 0
                    ),
                    "survivors": len(result),
                    "digest": hashlib.sha256(
                        json.dumps([s.text for s in result]).encode()
                    ).hexdigest(),
                }

    with threadpool_limits(limits=1):
        durations = []
        for _ in range(trials):
            prepared_holder.clear()
            started = time.perf_counter()
            output = run()
            durations.append(time.perf_counter() - started)
            observed = summarize(output)
            output = None
        for key in work:
            work[key] = 0
        prepared_holder.clear()
        tracemalloc.start()
        tracemalloc.reset_peak()
        output = run()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        observed = summarize(output)
    if prepared_holder:
        observed["owned_prepared_bytes"] = owned_bytes(prepared_holder[0])
    return {
        "seconds": durations,
        "median_seconds": statistics.median(durations),
        "traced_peak_bytes": peak,
        "traced_retained_bytes": current,
        "fixture_owned_bytes": retained,
        "process_peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "work": work,
        "result": observed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--worker", choices=FEATURES)
    args = parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker, args.phase, args.trials)))
        return
    if args.source is None or args.output is None:
        parser.error("--source and --output are required")
    report = {
        "python": sys.version,
        "seed": 20261018,
        "timing_threads": 1,
        "source_commit": subprocess.check_output(
            ["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True
        ).strip(),
        "runtime_source_sha256": {
            str(path.relative_to(args.source)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((args.source / "src/geistfabrik").rglob("*.py"))
        },
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "phase": args.phase,
        "trials": args.trials,
        "features": {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for feature in FEATURES:
        environment = dict(os.environ, PYTHONPATH=str(args.source / "src"), GEISTFABRIK_OFFLINE="1")
        completed = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                feature,
                "--phase",
                args.phase,
                "--trials",
                str(args.trials),
            ],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"{feature} failed ({completed.returncode}): {completed.stderr}")
        report["features"][feature] = json.loads(completed.stdout)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
        print(feature, report["features"][feature]["median_seconds"], flush=True)
    assert report["runtime_source_sha256"] == {
        str(path.relative_to(args.source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((args.source / "src/geistfabrik").rglob("*.py"))
    }, "runtime source changed during measurement"


if __name__ == "__main__":
    main()
