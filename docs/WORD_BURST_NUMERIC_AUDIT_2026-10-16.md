# Multi-agent numeric and PR audit, 2026-10-16

Audited PR #97 at `36270724f0fd214830dace52aaa98d1385f56caa`, against
`7882ed5bbf4997ee645129fac4d170e201eea4e4`. Six reviewers covered the detector,
history/storage, analysis/rendering, prose extraction/replay, shared semantic
numerics, and tests/evidence. Four feature reviewers derived probes without
reading tests or recorded results. This report records findings, not repairs.
Runtime, tests, lock and scripts are unchanged by the audit evidence commit.

The test/evidence review applies
[Hegel's review checklist](https://github.com/hegeldev/hegel-skill/blob/main/skills/hegel-review/SKILL.md)
and [Openclaw test-audit](https://github.com/openclaw/openclaw/blob/main/.agents/skills/test-audit/SKILL.md).

All five test/package CI jobs passed on the exact audited head: Linux Python
3.11/3.12, macOS Python 3.11, and package smoke Python 3.11/3.12. Run:
https://github.com/adewale/geist_fabrik/actions/runs/38980373837.

No P0/P1 finding was demonstrated. Four P2 correctness issues in the PR should
be repaired before merging. Two further PR findings concern lower-priority
numeric decisions/presentation. Three confirmed shared numeric issues predate
this PR; they are not attributed to the new detector.

## Remaining PR findings

### P2: Tab-normalized list continuations let hidden reference IDs count as prose

Location: `src/geistfabrik/lexical_index.py:129-138`.

```markdown
- [visible][secret]
	continuation

[secret]: https://invalid
```

The second line begins with a literal tab. Markdown renders the link label and
continuation, without `secret`. The extractor counts `secret` and `visible secret`;
`lexical_excerpt(content, "secret")` returns `visible][secret`. MarkdownIt expands
the tab in inline content, `.find(line)` fails against raw source, and mapping
abandons reference replacement for the entire inline block.

An independent real-Vault probe used 120 distinct notes across 12 dated weeks.
All notes used the same visible link; the last four weeks changed only the list
continuation from two spaces to a tab. Default analysis reported rising `secret`
and `visible secret` episodes, 2026-03-02 through 2026-03-29, at 100% recent
prevalence versus 33.3% across the window. Pure formatting creates false bursts.

Repair source mapping with tab-aware offsets, including multi-character normalized
expansions. Do not discard otherwise valid link replacements because another line
cannot be mapped. Extend the owning extraction property to real list indentation.

### P2: Ordinary inline-link destinations and titles still enter vocabulary

Location: `src/geistfabrik/lexical_index.py:202`.

```markdown
Before [visible](path "secret) hidden") after
```

Rendered prose is `Before visible after`, but extraction counts `hidden` and
`visible hidden`; excerpts expose the hidden title suffix. The regex ends at the
first closing parenthesis. Balanced destinations such as
`[visible](https://invalid/path(secret)hidden)` invent `visiblehidden`, and multiline
destinations/titles also enter vocabulary. This is in the PR-added lexical path;
the reference-link repair does not cover ordinary links.

Use parser-owned spans for ordinary links/images as well as references, preserving
source boundaries outside those spans. Extend the existing visible-prose owner
with balanced destinations, titles containing parentheses and multiline syntax.

### P2: Unicode casefolding fabricates words and disagrees with excerpts

Locations: `src/geistfabrik/lexical_index.py:225-226` and `:242-243`.

`extract_terms("İstanbul orchards", ngram_max=2)` counts `i`, `stanbul`, `i stanbul`
and `stanbul orchards`. Casefolding creates an internal combining mark that the
word regex excludes. Excerpts tokenize before casefolding instead, so all those
Istanbul-derived terms return no excerpt. Greek `ΐ` and `ǰ` have analogous issues.

An independent 120-note/12-week Vault probe introduced İstanbul in the final four
weeks. It produced rising findings for the fabricated terms, with 40 supporting
notes each and no matching excerpts.

Use one normalization/tokenization pipeline with raw source spans and a deliberate
policy for combining marks. A policy correction requires another extraction
version so stored vectors cannot mix incompatible token boundaries. Extend the
existing Unicode/window/excerpt owner rather than duplicating its setup.

### P2: Host timezone changes declared-date weekly cohorts

Location: `src/geistfabrik/lexical_index.py:325-326`; inherited helper conversion at
`src/geistfabrik/markdown_parser.py:303-304`.

Identical frontmatter `created: 2026-01-05T00:30:00+02:00` produces:

| Host timezone | Stored cohort | Weekly bin |
| --- | --- | --- |
| UTC | 2026-01-04 | 2025-12-29 |
| Europe/Helsinki | 2026-01-05 | 2026-01-05 |
| America/Los_Angeles | 2026-01-04 | 2025-12-29 |

Both the reviewer and primary agent reproduced this through fresh `Vault.sync()`.
The helper converts to host-local time, strips the timezone, and lexical capture
takes `.date()`. The helper predates the PR, but the new cohort service inherits
its machine-dependent interpretation. Timezone is absent from the source
fingerprint, so copied databases can retain one assignment while edited notes use
another.

Preserve the timestamp's declared calendar date for this mode, or explicitly
choose/document UTC conversion. Use timezone-aware UTC instants for observed
additions and `date` for declared cohorts. Invalidate affected derived baselines
when the interpretation changes; do not silently alter all existing date users.

### P3: A rounded-rate comparison can discard a genuine decline

Location: `src/geistfabrik/word_burst_analysis.py:305-309`.

Current count/exposure `67108865/134217729` is strictly below earlier
`67108864/134217727`: the integer cross-product difference is -1. Both float
divisions return `0.5000000037252903`, so `>=` rejects the decline. This PR-added
gate still uses rounded values after the detector's exact decisions.

Compare integer cross-products; convert rates only for reporting. The example
requires hundreds of millions of observations, so this is hardening rather than
a practical current-corpus blocker.

### P3: Percentage formatting can hide the difference being described

Location: `src/geistfabrik/default_geists/code/word_burst.py:16`.

`detect_bursts([4999, 5000], [10000, 10000], s=1.0001, gamma=0, max_states=2)`
selects `(0, 1)`, with an episode rate of 50% versus 49.995% across the window.
Independent three-significant-digit formatting renders both as `50%`. Legal
near-one configurations can therefore describe a rise while displaying equal
rates. This example is not a default-support-policy Vault benchmark.

Format the compared values jointly with enough precision to show the difference,
or retain exact counts/exposures and display them. Decimal storage alone would
not fix independent display rounding.

## Confirmed older numeric issues

### P2: Float32 centroid accumulation invents vocabulary widening

Location: `src/geistfabrik/default_geists/code/vocabulary_expansion.py:65-72`;
the same reduction also appears in `_edge_notes` at `:31-32`.

Repeating one identical normalized, 0.9-scaled float32 vector gives mean dispersion
`6.2418e-8` for 10 copies, `7.1013e-6` for 1,000, and `6.5659e-5` for 10,000.
The exact dispersion is zero for every population. Float64 centroid/distance
calculations return zero. The actual geist, supplied legal identical-vector
snapshots with populations 10/10/1000/1000, reports a widening range. The primary
agent reran this reproduction. This file differs from the PR base only in line
wrapping; the defect is pre-existing.

Retain compact float32 storage but promote centroid, subtraction and distance
reductions to float64. Treat a zero/near-zero dispersion baseline deliberately;
relative percentage thresholds can amplify numerical noise. An owner property
should ensure repeating identical vectors never creates a distribution change.

### P2 API inconsistency: Cosine similarity depends on which path populates the cache

Locations: `src/geistfabrik/embeddings.py:845-847` and cache publication in
`src/geistfabrik/vault_context.py:738-744`.

The scalar path substitutes a dot product when norms are merely within `1e-6` of
one. For a finite near-unit float32 pair, scalar-first gives `0.7999996900558131`
and batch-first gives `0.8000004148483144`. Actual VaultContext caching makes
later calls agree with whichever ran first, crossing a threshold of 0.8. The
primary agent reran the reproduction. The metric and cache code predate the PR.
Normal bundled stored meaning vectors near norm 0.9 generally avoid this branch;
the demonstrated defect affects supported near-unit API vectors.

Remove the approximate-unit shortcut or normalize consistently. Share the same
float64 cosine computation across scalar and matrix paths. Merely widening a
test tolerance would leave the behavioral threshold/call-order problem intact.

### P3: Float32 novelty comparisons can retain exact repeats at threshold 1

Location: `src/geistfabrik/filtering.py:297-315` (also diversity at `:349-357`).

The primary agent used the real bundled model offline, a real Vault and
JournalWriter history, and the exact text:
`What might orchard experiment number 7 teach us about changing observations?`
Persisted on 2026-10-14, it survives `filter_novelty` on 2026-10-16 with the valid
threshold 1.0. Identical model vectors yield float32 cosine
`0.9999998807907104`; threshold 0.85 correctly removes the repeat. An earlier
four-text batch did not reproduce the failure, illustrating reduction-layout
sensitivity. This shared behavior predates the PR.

Use consistent float64 comparison math and an explicit exact-identity rule at the
endpoint, including exact text history where appropriate. Identity is not an
epsilon-based near-duplicate decision. Keep compact storage separate from the
precision used for semantic decisions.

## Additional API range hardening

Existing scalar cosine uses scale-safe float64 normalization, but nearest-neighbor
and matrix/temporal paths do not consistently share it. A finite float32 vector
`[1e-30, 1e-30]` has scalar self-similarity approximately one while sklearn-based
nearest-neighbor search returns zero; very large finite float64 norms can overflow
in matrix paths. These were reviewer-directed API probes, not bundled-model
workflow failures. Share scale-safe row normalization or explicitly define and
reject unsupported ranges. This is separate from ordinary float32 rounding.

## What held up, proof limits and follow-up

The repaired burst detector had no new demonstrated numerical defect. Independent
production-only probes passed 1,352 nondegenerate exact-rational exhaustive cases
and 177 large-count/extreme-parameter cases against a 420-digit independent
recurrence, including 16 states and subnormal penalties. The original counted
scripts are retained as audit artifacts; their original stdout remains in the
session transcript, not a claimed archived raw run log. Finite probes are not a
proof for all possible inputs or an extreme-fallback performance benchmark.

Archived source for the original
[exact oracle](../benchmarks/results/word_burst_numeric_audit_exact_probe.py.txt),
[large-count oracle](../benchmarks/results/word_burst_numeric_audit_large_probe.py.txt)
and [shared numeric probes](../benchmarks/results/word_burst_numeric_audit_shared_probe.py.txt)
is kept as plain-text audit evidence, outside test discovery. The
[audit manifest](../benchmarks/results/word_burst_multiagent_numeric_audit.json)
records their hashes and the exact reviewed head.

The test/evidence reviewer verified archived/decompressed hashes and the green
validation counts: 1,767 unit, 81 integration, 155 AUTO, 45 firing geists and 81.89%
branch coverage. Runtime/scripts/lock match the measured/validated checkpoints.
No widened tolerances, excluded numeric failure classes or misleading green
claims were found. The existing extraction properties miss list/tab syntax,
balanced ordinary-link syntax and casefold-expanding Unicode; extend those owners.
Do not add duplicate tests at every crossed layer.

The numeric policy should distinguish exact counts and comparisons, compact
embedding storage, higher-precision reductions, deterministic calendar/instant
types, and presentation rounding. Decimal is useful for ambiguous likelihoods;
it is not a blanket replacement for vector arithmetic or source/date semantics.

No runtime or test code was changed in this audit. Repair the four PR P2 findings
before merging, then address the two lower-priority PR issues and the independently
scoped shared numeric defects. Canonical external review remains unavailable due
to the previously recorded authentication failure; no clean canonical verdict is
claimed by these independent reviews.
