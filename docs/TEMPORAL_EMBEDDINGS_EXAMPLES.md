# Temporal Embeddings: Current Behavior and Examples

**Status**: Current explanatory companion; formulas and persistence behavior are
defined normatively in the [embeddings specification](../specs/EMBEDDINGS_SPEC.md).
**Version**: 1.1
**Last verified**: 2026-09-12
**Audience**: Users and contributors interpreting temporal suggestions.

GeistFabrik combines content-derived meaning with three date features. A changed
vector is evidence about stored content and dates; it is not a measurement of a
reader's understanding. Unchanged content reuses the same semantic vector when
its cache entry remains valid.

The [implementation](../src/geistfabrik/embeddings.py),
[database schema](../src/geistfabrik/schema.py), and
[temporal analysis APIs](../src/geistfabrik/temporal_analysis.py) provide the
current behavior described here.

## What is stored

Each session vector contains 387 values: 384 semantic coordinates scaled by
0.9, followed by three temporal coordinates scaled by 0.1. There is no final
normalization step. The factors scale coordinates rather than fixing their
percentage contribution to a similarity score.

For a note written at midnight on 2023-06-15 and a session at midnight on
2025-01-15:

```text
Elapsed whole days: 580
Age feature: 580 / 365 = 1.589041096
Creation season: sin(2π × 166 / 365) = 0.280230675
Session season: sin(2π × 15 / 365) = 0.255353295

Combined vector:
[0.9 × semantic[0], ..., 0.9 × semantic[383],
 0.158904110, 0.028023068, 0.025535330]
```

Age is not capped: two years contributes about 2 before weighting, and a session
before a note's creation can give a negative age. Both seasonal denominators are
365, including leap years. The seasonal sine is a date signal rather than a
winter/summer classifier; June 15 is about 0.280, not 0.978.

The bundled model includes a normalization layer, but application code does not
independently normalize arbitrary model outputs. Cosine similarity handles the
norm of the combined vector when comparing notes.

## Example 1: The same content in two sessions

Suppose `Emergence.md` has identical content in March and September.

```text
March:     [0.9 × S, 0.1 × March age, 0.1 × creation sine, 0.1 × March sine]
September: [0.9 × S, 0.1 × September age, 0.1 × creation sine, 0.1 × September sine]
```

The semantic vector S is reused. Age and session season change; creation season
does not. No semantic coordinates shift from “mechanism” to “relationality”
unless the encoded content or model changes.

Nearest neighbours may still change because other notes are added or edited,
their vectors change, or the temporal features alter the combined comparisons.
A suggestion to revisit a connection can be useful, but the model cannot infer
that the user has adopted a new interpretation from unchanged text alone.

## Example 2: Content edits and semantic convergence

Imagine a permaculture note acquires material about distributed decision-making,
while an organizational-resilience note acquires material about ecological
feedback loops. Their changed content invalidates semantic reuse, and newly
encoded vectors may become more similar.

Retained session vectors allow the system to compare these changes over time.
A convergence suggestion is a prompt to inspect both notes, not proof that the
ideas are equivalent. Large hypothetical similarity changes should not be
presented as measured results without actual session data.

## Example 3: Seasonal and historical comparisons

A vault may contain winter entries about reflection and summer entries about
gardening. Content comparisons and entry dates can support a question such as
“Do these topics recur at this time of year?”

The two sine features alone do not establish recurring interests or a
psychological seasonal pattern. Reliable interpretation needs dated source
notes, enough retained history, and inspection of the actual content.

Historical replays use the requested session date. Trajectory queries exclude
later sessions; they do not restore old source text into the current vault.
Available history also depends on retention and on whether the note still exists.

## Working API examples

These examples use public APIs that exist today. They illustrate analysis
patterns rather than reproducing the exact thresholds and wording of bundled
geists.

### Inspect a note's recent trajectory

```python
from geistfabrik import VaultContext
from geistfabrik.embeddings import cosine_similarity
from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

def recent_drift(vault: VaultContext, note):
    snapshots = EmbeddingTrajectoryCalculator(vault, note).snapshots()
    if len(snapshots) < 2:
        return None
    previous_date, previous = snapshots[-2]
    current_date, current = snapshots[-1]
    return {
        "previous_date": previous_date,
        "current_date": current_date,
        "drift": 1.0 - cosine_similarity(previous, current),
    }
```

This compares the combined semantic-plus-temporal vectors. It does not isolate
content edits from the age and seasonal contribution.

### Inspect a bounded set of possible connections

```python
from geistfabrik import Suggestion, VaultContext
from geistfabrik.temporal_analysis import EmbeddingTrajectoryCalculator

def suggest(vault: VaultContext) -> list[Suggestion]:
    suggestions = []
    candidates = vault.unlinked_pairs(count=20, candidate_limit=100)
    for note_a, note_b in candidates:
        a = EmbeddingTrajectoryCalculator(vault, note_a)
        b = EmbeddingTrajectoryCalculator(vault, note_b)
        if a.is_converging_with(b, threshold=0.15):
            suggestions.append(Suggestion(
                text=f"Revisit a possible connection between [[{note_a.link_text}]] "
                     f"and [[{note_b.link_text}]].",
                notes=[note_a.link_text, note_b.link_text],
                geist_id="example_convergence",
            ))
    return vault.sample(suggestions, count=5)
```

For a single note's current neighbourhood, use
`vault.neighbours(note, count=3, return_scores=True)`. Sampling likewise uses
`count=`; neither API uses the old `k=` keyword.

See the shipped [session-drift geist](../src/geistfabrik/default_geists/code/session_drift.py)
and [convergent-evolution geist](../src/geistfabrik/default_geists/code/convergent_evolution.py)
for actual implementations.

## Cache and storage behavior

The semantic cache is keyed by `note_path`; `model_version` contains
`all-MiniLM-L6-v2:<SHA-256 of UTF-8 content>`. Lookup checks both fields. The table
stores `embedding` and `computed_at` alongside them. There is no separate
`content_hash` column, and identical content at different paths does not share
one cache row.

When a cache row matches, the semantic model is skipped for that note. Temporal
features are inexpensive to recompute, so each session composes its own vectors.
Sync can invalidate a cache row when a source is reprocessed even if its text
has not changed; cache hit rates depend on workload.

Each stored session vector takes 1,548 bytes before database overhead.
For 1,000 notes across 20 sessions, the raw vectors alone occupy 30,960,000 bytes
(about 29.5 MiB). Semantic cache rows, note content, and indexes add to this.

One calendar date identifies one session. Re-running that date replaces its
vectors. The CLI's `session_embedding_retention` default is 730: the current
session plus the most recent 730 other sessions are retained; 0 disables pruning.
Deleted notes lose their historical embedding rows through foreign-key
cascades. Quantization, cold-storage archiving, and HNSW search are not current
storage/search guarantees.

## Interpreting cost and suggestions

Semantic model inference runs only for cache misses; actual latency depends on
hardware, available device acceleration, note count, batching, and model state.
Neither a fixed cache-hit percentage nor a universal speedup is promised here.
The in-memory and optional sqlite-vec backends serve current-session similarity
queries; temporal analyses read retained snapshots.

Geist suggestions are questions grounded in these measurements. Treat claims
about “understanding,” “unconscious patterns,” or conceptual migration as
interpretive prompts requiring review, not observations made directly by the
embedding model.

Further references: [configuration](CONFIGURATION.md),
[architecture](ARCHITECTURE.md), and
[writing geists](WRITING_GOOD_GEISTS.md).
