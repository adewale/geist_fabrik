"""Before/after micro-benchmarks for this session's performance changes.

Each case runs the SHIPPED ("after") code path and an inline reconstruction of
the previous ("before") implementation on the same synthetic data, so the
speedup is attributable to the change rather than to the machine.

Run:  uv run python benchmarks/perf_before_after.py
"""

import time

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine

from geistfabrik.schema import init_db
from geistfabrik.vector_search import InMemoryVectorBackend


def _time(fn, repeats):
    # Best-of to reduce noise; report milliseconds.
    best = float("inf")
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best * 1000.0


def _row(name, before_ms, after_ms):
    speedup = before_ms / after_ms if after_ms else float("inf")
    print(f"{name:<46} {before_ms:>9.3f} {after_ms:>9.3f} {speedup:>7.1f}x")


def bench_find_similar(n=10000, dim=387, count=11, queries=50):
    """find_similar top-k: argpartition (after) vs full stable argsort (before)."""
    rng = np.random.default_rng(0)
    db = init_db(None)
    db.execute("INSERT INTO sessions (date, created_at) VALUES ('2024-01-01', '')")
    sid = db.execute("SELECT session_id FROM sessions").fetchone()[0]
    for i in range(n):
        vec = rng.standard_normal(dim).astype(np.float32)
        db.execute("INSERT INTO notes (path,title,content,created,modified,file_mtime) "
                   "VALUES (?,?,?,?,?,0)", (f"n{i}.md", f"n{i}", "c", "", ""))
        db.execute("INSERT INTO session_embeddings (session_id, note_path, embedding) "
                   "VALUES (?,?,?)", (sid, f"n{i}.md", vec.tobytes()))
    db.commit()
    backend = InMemoryVectorBackend(db)
    backend.load_embeddings("2024-01-01")
    qs = [rng.standard_normal(dim).astype(np.float32) for _ in range(queries)]
    matrix, paths = backend._matrix, backend._paths

    def after():
        for q in qs:
            backend.find_similar(q, count=count)

    def before():
        for q in qs:
            scores = sklearn_cosine(q.reshape(1, -1), matrix)[0]
            order = np.argsort(-scores, kind="stable")[:count]
            [(paths[int(i)], float(scores[int(i)])) for i in order]

    _row(f"find_similar end-to-end (N={n}, k={count}, {queries}q)",
         _time(before, 5), _time(after, 5))

    # Isolate the part that actually changed: top-k extraction from a fixed
    # score vector (the cosine matmul dominates end-to-end and is identical
    # in both paths, masking the sort speedup).
    scores = sklearn_cosine(qs[0].reshape(1, -1), matrix)[0]

    def sort_before():
        np.argsort(-scores, kind="stable")[:count]

    def sort_after():
        part = np.argpartition(-scores, count - 1)[:count]
        kth = scores[part].min()
        cand = np.flatnonzero(scores >= kth)
        cand[np.argsort(-scores[cand], kind="stable")][:count]

    _row(f"  └─ top-k sort only (N={n}, k={count})",
         _time(sort_before, 200), _time(sort_after, 200))


def bench_orphans(n=6000, link_frac=0.5):
    """orphans: set-difference O(N+M) (after) vs LEFT-JOIN OR-clause O(N*M) (before)."""
    db = init_db(None)
    for i in range(n):
        db.execute("INSERT INTO notes (path,title,content,created,modified,file_mtime) "
                   "VALUES (?,?,?,?,?,0)", (f"n{i}.md", f"Note {i}", "c", "", ""))
    rng = np.random.default_rng(1)
    for i in range(int(n * link_frac)):
        tgt = int(rng.integers(0, n))
        db.execute("INSERT INTO links (source_path, target) VALUES (?,?)",
                   (f"n{i}.md", f"Note {tgt}"))
    db.commit()

    def after():
        sources = {r[0] for r in db.execute("SELECT DISTINCT source_path FROM links")}
        targets = {r[0] for r in db.execute("SELECT DISTINCT target FROM links")}
        out = []
        for path, title in db.execute("SELECT path, title FROM notes ORDER BY modified DESC"):
            if path in sources or path in targets or title in targets:
                continue
            if path.endswith(".md") and path[:-3] in targets:
                continue
            out.append(path)
        return out

    def before():
        cur = db.execute("""
            SELECT n.path FROM notes n
            LEFT JOIN links l1 ON l1.source_path = n.path
            LEFT JOIN links l2 ON (l2.target = n.path OR l2.target = n.title
                                   OR l2.target || '.md' = n.path)
            WHERE l1.source_path IS NULL AND l2.target IS NULL
            ORDER BY n.modified DESC
        """)
        return cur.fetchall()

    _row(f"orphans  (N={n}, M={int(n * link_frac)})", _time(before, 3), _time(after, 3))


def bench_filter_diversity(s=200, dim=384):
    """filter_diversity: one S*S matrix (after) vs per-pair Python loop (before)."""
    rng = np.random.default_rng(2)
    emb = rng.standard_normal((s, dim)).astype(np.float32)
    threshold = 0.85

    def after():
        sim = sklearn_cosine(emb)
        keep = [True] * s
        for i in range(s):
            if not keep[i]:
                continue
            for j in range(i + 1, s):
                if keep[j] and float(sim[i, j]) >= threshold:
                    keep[j] = False
        return keep

    def before():
        from geistfabrik.embeddings import cosine_similarity
        keep = [True] * s
        for i in range(s):
            if not keep[i]:
                continue
            for j in range(i + 1, s):
                if keep[j] and cosine_similarity(emb[i], emb[j]) >= threshold:
                    keep[j] = False
        return keep

    _row(f"filter_diversity  (S={s})", _time(before, 3), _time(after, 3))


if __name__ == "__main__":
    print(f"{'case':<46} {'before':>9} {'after':>9} {'speedup':>8}")
    print("-" * 76)
    bench_find_similar()
    bench_orphans()
    bench_filter_diversity()
