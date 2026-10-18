# Repairs from the frozen narrative evaluation

Checkpoint `5cff8faf1977dd30d2b0add962d325f1e1ec0265` implements the five
follow-ups from the [original evaluation](NARRATIVE_VAULT_EVALUATION.md).
The story, persona, ledger, lexical model thresholds and original results remain unchanged.
[Comparison and lossless receipts](../benchmarks/results/narrative_quality_fixes/summary.json)
bind the new results to their source, model and invocation settings.

## What changed

`SourceEligibility` supplies one physical-source boundary for idea queries and
final citations. Root `Templates/` is excluded even when configured privacy
filtering is disabled. Enabled privacy prefixes apply to virtual entries,
semantic neighbours, graph queries, temporal populations and clustering. A
reference fails closed if any matching alias names an excluded source. Truly
unresolved outgoing links retain their previous graph semantics. Raw notes,
lexical storage and embedding history remain intact. Lexical-only exclusions
retain their separate scope. Cluster labels include the canonical source-policy
identity so incompatible historical populations are not compared.

Recent-focus questions use a virtual entry's heading date and explicitly say
“dated”; the parent file's edit time cannot establish recent work on that entry.
Unknown or future heading dates abstain. Eligible, nonfuture physical notes
retain their modification-date behavior. Seasonal tag questions require two actual season-year occurrences,
with examples from both. December and the following January are one winter.
The wording describes dated notes rather than inferring when they were written.

The lexical question gate rejects expressions consisting entirely of English
grammatical words before grouping and sampling. It preserves meaningful mixed
phrases, Unicode terms and both directions. It shares Pattern Finder's existing
boundary vocabulary without changing that geist's extraction. Words outside the
English function-word list remain eligible; language is not detected, so a
non-English homograph of a listed word can also be rejected.

Saved evidence identity now survives the ordinary 60-day novelty window. Indexed
lookups suppress exact or overlapping episodes for the same expression, mode and
direction, while disjoint later episodes remain eligible. Uncertainty Mapper
identifies its observation using complete source content and a versioned policy,
so an unchanged hedge finding cannot become new through elapsed time alone.
Changed content can return. Generic playful prompts retain short-window revisits;
same-day and future history do not affect a historical replay, and previews do
not persist identities.

Additive schema v13 preserves abstention reasons and evidence populations with
cached results. `invoke --explain` reads the actual invocation's diagnostics;
it does not run or prime another analysis. Cache hits restore evidence counts
while recording zero decoding work. Migration invalidates only derived result
caches, preserving dictionaries, captured additions, embeddings and saved keys.

## Same story, same 48 session contexts

Both modes completed 24 sessions through production `InvokeCommand.run`, real
offline inference, every bundled Code/Tracery geist, filtering, selection and
journal writing: **2,160 successful executor calls and 240 saved questions**.
All 15 stable source controls retain identical meaning vectors. There are no
future note dates or skipped geists. The manifest and ledger hashes match the
original receipts.

| Observable regression | Before | After |
| --- | ---: | ---: |
| Template-based raw questions, both modes | 38 | 0 |
| Template-based selected questions, both modes | 16 | 0 |
| Old virtual entries called recent work, raw, both modes | 34 | 0 |
| Seasonal claims about the one clipping batch, raw, both modes | 32 | 0 |
| Function-only lexical questions under the new explicit policy, raw dated mode | 39 | 0 |
| Selected overlapping saved episodes for the same identity | 1 | 0 |
| Unchanged Repair ideas hedge prompt, selected per mode | 5 | 1 |

The exact current-prose lexical population and every session's ordered model
findings match the original, in both modes. Model findings are conserved even
when the presentation gate rejects them. Dated mode still produces word-burst
questions in 19 sessions: 41 raw questions and five selected, including rising
and declining language and a phrase. Content candidates can fill the budget
previously occupied by grammatical lenses; this is not just deleting output.

Observed additions still abstains. Its final cached explanation is now
“abstained: 9 captured observations; minimum 50 required”, with eight populated
bins and zero decoding work on the hit. The mode never switches automatically.

The full population continues producing questions: dated mode has 877 raw and
814 filtered questions; observed mode has 836 raw and 793 filtered. Respectively
29 and 28 geists produce output at least once. Seasonal output disappears on
this story because it lacks qualifying recurring evidence. Cluster/evolution
outputs can change when templates leave their population. Every geist's before
and after counts are retained in the summary; healthy emptiness is not a failure.

These repairs remove specific invalid invitations. They do not supply a new
usefulness score. Selected content still includes the broad verb “keep”, the
known cafe project and the known “supported” terminology change. Related terms
such as “cafe” and “the repair cafe” have distinct identities and can still recur.
The previous subjective 41/240 promising count is not transferred to the changed
selection. Surprise and usefulness still require reader judgment.

## Runtime, memory and storage

These are single local real-model replays, not controlled replicated speedup
estimates. Runtime includes the observer; peak RSS includes Python, Torch and
the model, and is not incremental geist memory.

| Measurement | Dated before → after | Observed before → after |
| --- | ---: | ---: |
| Median invocation | 3.40 → 2.97 s | 2.79 → 2.71 s |
| Maximum invocation | 5.27 → 3.65 s | 3.96 → 9.34 s |
| Peak whole-process RSS | 1,071 → 1,029 MiB | 1,065 → 1,029 MiB |
| Final database | 8.58 → 8.59 MiB | 8.57 → 8.58 MiB |

The observed-mode maximum got worse. Its November invocation spent 4.12 seconds
executing geists and 4.09 seconds filtering; the spike was not confined to word
bursts. One run does not establish its cause or a tail-latency guarantee. Median
and RSS reductions likewise do not prove a causal optimization from these fixes.
An additional complete observed-mode replay produced identical raw, filtered
and selected questions in every session: 1,080 more successful calls. Its median
was 3.03 seconds, maximum 5.46 seconds, and the November session took 3.36 seconds.
Both runs are retained; the spread rules out treating the first run's median
as a measured speedup. Repeat whole-process peak RSS was 1,015 MiB.
The extra evidence index occupies 4 KiB in each final database. Total database
growth is 16 KiB dated and 8 KiB observed, including changed saved text and cached
diagnostics. Evidence lookup tests require indexed search rather than loading
all historical prompts or embedding them. The shared identity index adds
session preparation work; the result-cache version change requires one fresh
analysis but does not erase captured history.

Matched capacity checks reuse the earlier frozen 10,000-note files and
current-policy dictionaries, with the same explicitly synthetic 104-week dates.
The source is scrambled prose, not an authored vault. Each phase runs in its own
process on a copied database; no embedding inference or full CLI is measured.
One trial per phase gives these actual executor measurements:

| Vocabulary | Fresh before → after | Cached before → after | Peak RSS before → after |
| --- | ---: | ---: | ---: |
| Words/pairs, 42,990 terms | 12.67 → 12.87 s | 0.535 → 0.590 s | 1,240 → 1,242 MiB |
| Through triples, 821,665 terms | 37.69 → 37.43 s | 0.431 → 0.480 s | 2,059 → 2,057 MiB |

All 4,257 pair-mode and 6,767 triple-mode findings match exactly across phases
and the prior archived result digests. Each final capacity database grows by
4 KiB. Cached execution adds roughly 50–55 ms in these runs while performing
the stronger full-source checks; the measurement does not isolate that cause
from scheduling variation. Fresh default pairs remain below the 30-second
budget. Triples use an explicit 120-second budget and remain beyond the default
budget; the presentation gate does not solve collection/decoding capacity.

The 32-snapshot temporal smoke corpus also completed 448 executor calls with
real embeddings across 13 distinct temporal/similarity geists, counting both
word-burst modes. All 64 ordered lexical analyses match the earlier archive,
including rising/declining words and phrases. Unchanged sync extracts zero
sources, and repeated Session computation encodes zero texts and writes zero
embedding rows. Stable meaning controls do not change. These lexical executor
calls are analysis-primed; they are not cold-decode latency measurements.
The ten-note Kepano excerpt, using actual declared dates and no overlay,
correctly abstains with four dated observations; it supplies no usefulness claim.

## Verification and remaining limits

A separate adversarial reviewer read implementation and contracts without the
tests. It found inconsistent hidden-alias handling in pairwise link and orphan
queries. Both were repaired and checked against the other graph surfaces,
preserving legitimate unresolved links. Its independent 2,000 generated interval
comparisons agreed with the direct overlap oracle.

The Openclaw test audit mapped nine independent properties to their strongest
owners, added the saved-key migration/second-reopen lifecycle regression, and
removed exact query-count/index-name coupling. Hypothesis properties cover
normalization, lexical eligibility, independent calendar-set overlap and
virtual-entry recency; a real-analysis regression protects unchanged dictionary
counts and model findings. Paired isolated-source proof
has **nine intended behavioral failures before repair and all ten checks passing
after repair**; the tenth is an intentional conservation check passing both.
The proof archive preserves commands and full failures, not collection errors.

The complete `scripts/validate.sh` run passes **2,063 unit tests, 81 integration
tests, all 155 automated acceptance criteria and 83.63% branch coverage**, plus
all 45 geist firing contracts, strict typing, lint, security/workflow checks,
package construction and installed-wheel real-model offline inference. The
full log and exact validation status are retained separately with the receipts.

Canonical autoreview previously failed HTTP 401 and produced no report. No
credentials have been restored, and independent review is not a canonical clean
verdict. Optional trigrams still require capacity judgment on large recurrent
phrase vocabularies. This fixture has short English prose, no task lists and few
captured edits; owner-rated usefulness on real vaults remains unproven.
