# Shared semantic primitives

Semantic consumers now share immutable prepared directions, cached identity
indexes, certified NumPy/BLAS decisions and bounded reductions. Stored note
embeddings remain float32. Scalar and explicitly requested Cartesian scores
retain the existing fixed-order float64 contract.

## Choose the operation that expresses the question

| Question | Primitive | Production consumers |
| --- | --- | --- |
| Corresponding row pairs | `UnitRows.paired`, `VaultContext.paired_similarity` | Cross-year seasonal evidence, sparse threshold refinement |
| Several independent neighbour queries | `find_similar_batch`, `VaultContext.neighbours_many` | Concept clusters, recent focus, bridge builder, method scrambler |
| Canonical threshold decisions | `UnitRows.compare` / `any_matches` | Novelty and diversity filters |
| Matching unordered pairs | `UnitRows.matching_pairs` / `scored_matching_pairs`, `VaultContext.similar_pairs` | Graph bridges, structural holes, unlinked pairs |
| Mean as a number | `UnitRows.mean_similarity`, `VaultContext.mean_similarity` | Seasonal coherence |
| Mean above a threshold | `UnitRows.mean_compare`, `VaultContext.mean_similarity_matches` | Concept clusters, density inversion, cross-season threads |
| Exact top-k with scores | `UnitRows.nearest` | In-memory search, cluster representatives |
| Exact top-k indices | `UnitRows.nearest_indices` | Shared surprisal/churn index, without Python score tuples |
| Full canonical Cartesian output | `UnitRows.cosine`, existing cosine APIs | Callers that actually need every score; compatibility |

`UnitRows` returns signed scores in [-1,1]. Vault note similarities and means
project scores onto [0,1]. Threshold comparisons distinguish `>=` from `>`;
callers must specify strict comparisons where their evidence claim requires it.
Empty mean populations have mean zero. Top-k ties preserve collection order;
surprisal/churn populations use sorted paths and exclude only the query's own
row, preserving other notes with duplicate directions.

For example, geists can batch seeds without changing their sampling policy:

```python
seeds = vault.sample(vault.notes(), count=5)
for seed, neighbours in zip(seeds, vault.neighbours_many(seeds, count=5)):
    group = [seed] + [note for note, score in neighbours[:3]]
    if vault.mean_similarity_matches(group, 0.65, inclusive=False):
        # Compose an invitation grounded in this group.
        ...
```

## State ownership and invalidation

Prepared directions own immutable float64 bytes. Contiguous selections share
those bytes and metadata; other selections copy already prepared rows without
renormalizing or revalidating them. Array views have disposable shape metadata.
The identity index uses salted process-local hashes to select buckets and
verifies actual array equality before assigning immutable group IDs. Hashes
never persist and cannot establish identity. Contiguous views share group IDs,
so identity/zero corrections and sparse refinement avoid repeated Python
lookups. A verified population of distinct nonzero directions only needs
identity correction where two contiguous views overlap in root row positions;
disjoint views skip identity masks. Zero row positions are also cached. Equal nonzero directions score exactly one; zeros
score zero, including against themselves.

The in-memory backend owns immutable raw buffers and a mutation generation.
Replacing a vector, including a replacement that keeps the mapping length
unchanged, invalidates prepared state. Public mapping operations update that
generation; returned views cannot mutate owned payloads or stored array shapes.
VaultContext shares those raw buffers instead of loading a second SQL copy.
It retains one prepared user population, including metadata, for both surprisal
and churn. Native sqlite-vec search continues using its own engine; CPU
reductions prepare its already loaded session snapshot once and support its
configured dimensions. Closed backends reject prepared access.

Neighbour results retain one largest ranked prefix per query. Both return
formats share it, and smaller requests reuse it. Missing note slots stay in
rank order so prefix reuse agrees with fresh smaller requests. Batched note
loading respects the connection's SQLite variable limit; ordinary small
requests retain the existing three-query loader.

`TextEmbeddingCache` supplies an 8 MiB accounted retention budget per embedding
computer. It uses exact text keys, immutable row bytes, unique-miss batches and
LRU eviction. Oversized entries are returned without retention. The accounting
includes keys, vector payload and a metadata allowance; it is not a bound on
process RSS, model tensors or a requested output batch. Lowering the budget
evicts immediately. A model-identity change or `EmbeddingComputer.close()`
invalidates the cache. Session inference, filtering and real-model KeyBERT
labelling use this same cache; plugin label encoders use the same bounded
primitive through weak ownership. Filtering shares prepared candidate rows
between novelty and diversity for one pipeline invocation, then releases them.

Session embedding computation retains an exact input manifest and a SQLite
change token after a successful commit. Matching input, date, computer and
retention settings with no local/external writes returns before inference,
serialization, writer-lock acquisition or backend invalidation. Loading an
accepted sqlite-vec projection absorbs only its own writes into the local token.
External commits invalidate the backend and reject the stale session. Any
unrelated local write requires full validation. This remains an O(N) input
comparison, not a constant-time watcher. Retained manifest tuples share content
strings but add metadata proportional to the note count. They retain supplied
text objects for the open Session lifetime. `Session.close()`
releases the manifest and its change token, including for injected computers.
Computer identity is checked through a weak reference with `is`, so replacing a
computer cannot collide with a recycled Python object ID or retain the old model.
Search backends publish an optional projection revision token. An unchanged
compute discards a closed, mutated or unversioned projection before returning;
the next search rebuilds it from the accepted persisted vectors. Whole-map
replacement, individual in-memory row changes and explicit backend reloads all
advance the built-in tokens. Third-party backends can return `None` to opt out
of projection reuse.

A fresh Session still validates and composes the population. Conditional UPSERTs
write only changed BLOBs, and an unchanged hash is not rewritten. Unchanged
populations retain cluster labels; a changed vector, membership or vault hash
clears all labels because clustering describes the entire population. Semantic
composition uses float32 both before and after persistent cache reuse. All
persistent changes and retention pruning remain one owned transaction.

## Why optimized decisions preserve canonical answers

Canonical normalization and dot products use one explicit adjacent-pair binary64
tree. Products are materialized first, then separate elementwise additions
combine adjacent components at each level; an odd final component carries
unchanged. Every pair therefore executes the same arithmetic independently of
population shape, tile size or NumPy iterator buffers. `einsum(optimize=False)`
did not provide that guarantee above its internal buffering boundary.

This changes some final bits relative to earlier PR builds, including at 384
dimensions. A seeded 32-row comparison found a maximum score difference of
`1.53e-16`. Prepared state is rebuilt in memory; stored embeddings are unchanged.
Threshold decisions and stable ties now consistently use the new canonical
scores. Full canonical matrices and corresponding-pair scores cost more than
the old reduction; certified BLAS decisions retain their optimized estimates.

Let `d` be the prepared dimension, `E` be binary64 machine epsilon and
`gamma(n) = n*E/(1-n*E)`, rounded upward. Every prepared component has magnitude
at most one, so `sum(abs(a_i*b_i)) <= d`. Either reduction uses at most `2d`
rounded operations along a dependency path. A conservative absolute bound on
the difference between BLAS and the fixed-order reduction is therefore

```
2 * gamma(2d) * d + 4 * d * binary64_normal_minimum
```

The implementation rounds the bound upward, caps it at the full score range,
and rounds interval endpoints outward. The additive term covers underflow,
including flushing tiny intermediates to zero. Clipping is 1-Lipschitz and
both paths apply identical verified identity/zero corrections. This reasoning
assumes the CPU IEEE binary64 operations provided by the supported NumPy/BLAS
stack; it does not authorize reduced-precision GPU kernels.

A threshold decision uses BLAS only when the whole enclosure lies on one side
of the threshold. Ambiguous cells use the canonical kernel, without a guessed
epsilon. Dense ambiguous tiles recompute a canonical tile instead of expanding
one D-dimensional vector per uncertain cell. Mean decisions additionally bound
nonnegative summation and division, using canonical `math.fsum` if ambiguous.

Top-k retains candidates whose upper enclosure reaches the tile's kth lower
enclosure and can beat the already retained canonical kth score. Later tiles
contain larger row indices, so an upper bound equal to the existing kth score
cannot win its stable tie. Verified identities and zeros already have exact
scores and bypass refinement; an entirely exact tile bypasses BLAS too. Other
candidates use the canonical kernel. Partial selection sorts the winning
frontier by score and row index. Every tile's local winners are sufficient for
the global winners. A true nonidentity tie may still require scoring all
candidates: correctness never depends on an arbitrary refinement cutoff.
Sparse pair refinement batches candidates across queries and
bounds vector copies by dimension. Canonical product/scratch chunks fit the
score budget, except for the intrinsic work of one oversized vector. Completed
chunks release both working arrays before allocating the next chunk. Requested
outputs, input vectors, array metadata and native iterator scratch are separate
from this payload allowance. Unlinked-pair discovery streams scored
matches into the standard-library stable top-k heap, retaining only the requested
result count.

The default score tile budget is 1 MiB, in both dimensions. Bounds, masks,
indices and output arrays need additional memory; this is not a 1 MiB limit
on an entire operation. Requested inputs/outputs are separate. Streamed means
also tile wide peer collections. Surprisal bounds centroid materialization by
both neighbour count and vector dimension.

## Compatibility and side effects

Canonical scalar, Cartesian, paired and returned top-k scores remain exactly
consistent. Certified decision APIs preserve canonical threshold decisions.
Surprisal and churn now use this canonical ordering instead of their previous
separate BLAS/argpartition policy. Tied or nearly tied neighbour membership,
centroid rounding, resulting surprisal and churn can therefore change. The
historical and current paths normalize once, avoiding false churn introduced
by normalizing one epoch twice.

Canonical means use `fsum` rather than an incidental NumPy/Python accumulation
order; the last bit can change. Density inversion now checks graph density
before semantic work. Greedy diversity preserves keep-first ordering while
avoiding its full square matrix. Cached inference retains local text in RAM
and can change inference batch membership by deduplicating misses. Real-model
raw-vector differences, prompt parity, work counts and memory effects are
measured in the accompanying benchmark report.

NumPy, threadpoolctl and the existing sqlite-vec engine supply the numerical
and native-search work. This adds no approximate index or dependency. Mutable
raw inputs are never put into an unbounded global normalized-vector cache.

See the [first-pass measurements](SIMILARITY_PRIMITIVES_BENCHMARK.md) and the
[canonical-neighbourhood and Session refinement measurements](SIMILARITY_REFINEMENT_BENCHMARK.md).
