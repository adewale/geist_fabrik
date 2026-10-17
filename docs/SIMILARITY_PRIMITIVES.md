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
| Exact top-k with scores | `UnitRows.nearest` | In-memory search, cluster representatives, shared surprisal/churn index |
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
The identity index stores compact BLAKE2b digests and row groups, verifying
actual array equality before any digest match can establish identity. Zero row
positions are also cached. Equal nonzero directions score exactly one; zeros
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

## Why optimized decisions preserve canonical answers

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

Top-k retains every candidate whose upper enclosure reaches the kth lower
enclosure, canonically scores those candidates, then sorts by score and row
index. Every tile's local winners are sufficient for the global winners. A
true tie may require all candidates: correctness never depends on an arbitrary
refinement cutoff. Sparse pair refinement batches candidates across queries and
bounds vector copies by dimension. Unlinked-pair discovery streams scored
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

See [matched measurements and verification](SIMILARITY_PRIMITIVES_BENCHMARK.md).
