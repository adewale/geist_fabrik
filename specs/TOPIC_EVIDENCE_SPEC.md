# GeistFabrik topic evidence specification

**Status**: Proposed; NOT-BUILT. Implementation and evaluation are pending.

Add shared local analysis of phrases, their source passages, relationships, and dated coverage. Use it to generate specific questions that open possibilities, following the [GeistFabrik vision](geistfabrik_vision.md).

Implement and evaluate `forming_connection` first. Undercurrents, framing shifts, and question-backed subject trails are follow-on candidates; reuse existing geists where their purposes overlap.

## Guiding principles and mandatory constraints

- **Muses, not oracles.** State a supported observation, then ask an open question. Topic overlap cannot establish an argument, contradiction, belief change, emotion, or intention. Preserve the lesson from the [retired opposition geists](research/OPPOSITION_GEISTS_RESEARCH.md).

- **Sample, don’t rank.** Scores may qualify evidence; deterministically sample qualifying candidates. Preserve bounded, filtered output, preview by default, and journal writes through the existing `--write` flow. Statistical unusualness is not importance.

- **Local, deliberate, additive.** Run during existing invocation. Keep derived data rebuildable in the existing portable SQLite database, with additive, versioned migrations. Preserve source notes. Introduce no cloud dependency, external LLM requirement, continuous monitoring, or topic dashboard.

- **Shared intelligence, small geists.** Put reusable extraction and queries behind `VaultContext`, with registry access for Tracery. Geists must not query storage directly or rebuild the corpus separately.

- **Evidence must remain inspectable.** Preserve matched wording, exact excerpts, source locations, conservative topic identities, and independent support. `forming_connection` requires same-passage co-occurrence across at least two distinct notes or dated entries; repetition inside one note is insufficient.

- **Chronology must be earned.** Record date provenance and bound comparisons by the session date. Dated entries support comparisons across writing. Changes within mutable notes require retained textual observations; creation dates, modification times, and embeddings cannot reconstruct earlier wording.

- **Respect boundaries before analysis.** Exclude the geist journal and configured excluded paths before extraction, candidate selection, and aggregate calculations.

- **Borrow selectively.** From Flux Search and Bobbin, borrow source membership, co-occurrence, contextual vocabulary, and corpus comparisons. Do not copy newsletter segmentation assumptions, editorial topic-promotion thresholds, aggressive topic merging, or popularity-based selection. Each geist owns its evidence requirements.

## Functional requirements

- **Forming connections:** identify supported recent pairings with little historical overlap and ask what the connection could become.

- **Undercurrents:** compare supported topic coverage against an explicit, size-normalized baseline.

- **Framing shifts:** compare grounded contexts across sufficiently supported, reliably dated groups.

- **Subject trails:** connect related sources across time; quote an actual earlier question rather than declaring an inquiry unfinished.

Version derived data by source content, parser, extractor, and configuration. Handle edits and deletions. Incomplete indexing or omitted extraction candidates must never establish absence. Abstain when evidence is insufficient.

## Verification and delivery gates

1. **Controlled fixtures:** demonstrate each enabled mechanism with exact expected support, baseline, source passages, and bounded output.

2. **Negative fixtures:** cover unrelated passages in one note, repeated boilerplate, overlapping labels, sparse support, excluded sources, uncertain dates, future evidence, and incomplete indexing. Require abstention or appropriately narrowed observations.

3. **Reproducibility and maintenance:** identical inputs reproduce evidence and suggestions; incremental updates match a clean rebuild after edits, deletions, and extractor changes.

4. **Operational checks:** run canonical repository validation, verify offline packaged operation, confirm source files remain unchanged, and measure cold/warm invocation cost on representative vault sizes.

5. **Utility gate:** compare repeated sessions against existing geists or a simple random-pair baseline on frozen, representative vaults. Record evidence accuracy, surprise, specificity, repetition, and whether questions opened useful possibilities—including empty sessions.

Keep new geists experimental and opt-in until correctness, performance, and utility evidence justify broader inclusion.
