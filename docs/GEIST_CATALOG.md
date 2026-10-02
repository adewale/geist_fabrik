# Geist Catalogue

**A comprehensive classification of GeistFabrik's default geists by pattern and implementation status**

GeistFabrik ships with a set of default geists following distinct patterns (counts: `geistfabrik.default_geists.TOTAL_GEIST_COUNT`). This document categorizes them by their core mechanisms, tracks implementation status, and provides guidance for understanding and extending the geist ecosystem.

**Last Updated**: 2026-10-02 (duplicate geists merged; see CHANGELOG)

---

## Summary

Code and Tracery geists live in `src/geistfabrik/default_geists/code/` and
`.../tracery/`; their counts are derived from the filesystem
(`CODE_GEIST_COUNT`, `TRACERY_GEIST_COUNT`, `TOTAL_GEIST_COUNT`). Geists whose
job duplicated another's were merged into the one truest to the vision
(2026-10); a few retired geists now live in `examples/geists/` as extension
examples.

**Retired**: columbo, dialectic_triad, antithesis_generator and
blind_spot_detector (the opposition geists) were retired because embeddings
measure topic, not stance (`specs/research/OPPOSITION_GEISTS_RESEARCH.md`).
The full map of merged and retired geists is in
[`specs/SPEC_STATUS.md`](../specs/SPEC_STATUS.md) ("Geist merges (2026-10)").

**Quality**: 100% pass rate on validation spec audit (see Quality Standards below)

---

## Pattern Categories

### 1. Extraction-Based Geists (Harvester Family) 🆕

**Pattern**: `Random Note Selection → Content Extraction → Temporal Provocation`

These geists pick a random note, extract specific content types using regex, and surface them with temporal framing. They treat buried artifacts as valuable content worth revisiting.

| Geist | Extracts | Provocation |
|-------|----------|-------------|
| **question_harvester** | Questions (`?`), preferring question-dense notes | "What if you revisited this question now?" / "Which one keeps you up at night?" |
| **todo_harvester** | TODO/FIXME/HACK/XXX markers | "What if you tackled this now?" |
| **quote_harvester** | Blockquotes (`>`) | "What if you reflected on this again?" |
| **claim_harvester** | Strong claims | "Is that still true - and what would change your mind?" |
| **hypothesis_harvester** | Hypotheses / maybe-statements | "What is the smallest experiment that would tell you if it holds?" |
| **definition_harvester** | "X is a Y" definitions, definition lists | "What if you explored this definition further?" |

**Characteristics**:
- ✅ Reads one or a few sampled notes per session (question_harvester first checks voice statistics to prefer question-dense notes)
- ✅ Fast regex extraction
- ✅ Silent abstention when content not found
- ✅ Deterministic by session date
- ✅ No cross-note analysis

---

### 2. Temporal Analysis Geists

**Pattern**: `Time-Based Comparison → Measure Difference → Ask for Inspection`

These geists compare dated note metadata or stored semantic representations.
Those signals can point to source material worth inspecting; they do not by
themselves establish a change in meaning, interpretation, or mental state.

| Geist | Compares | Detects |
|-------|----------|---------|
| **temporal_drift** | Old vs recent notes | Stale but important notes |
| **concept_drift** | A note's vector across sessions | Notes you rewrote, since which session, and toward which neighbour |
| **temporal_clustering** | Notes within a season | A season's thread (anchor + 2 closest); cross-season only when measured |
| **seasonal_patterns** | Notes by creation month and season | Month themes recurring across years; tags concentrated in one season |
| **convergent_evolution** | Unlinked pairs' stored vectors across sessions | Increased measured similarity |
| **divergent_evolution** | Linked pairs' stored vectors across sessions | Decreased measured similarity (does the link still hold?) |
| **cyclical_thinking** | A note's vector across sessions | Notes whose text returned to an earlier semantic state |
| **creation_burst** | Days with 3+ notes created | Burst days, and which of their notes you have rewritten since |

**Characteristics**:
- 📊 Uses temporal metadata (creation date, modification time)
- 🔄 Tracks change over time
- 📈 Often requires embeddings to detect semantic drift
- 🎯 Surfaces measured patterns for inspection

---

### 3. Semantic Similarity Geists

**Pattern**: `Find Similar/Dissimilar Notes → Suggest Connections`

These geists use embeddings to find notes that are semantically related (or deliberately distant) and suggest unexpected connections.

| Geist | Strategy | Purpose |
|-------|----------|---------|
| **creative_collision** | Unlinked, loosely related pairs | Unexpected combinations, framed across eras when years apart |
| **bridge_builder** | Unlinked twin of a hub, outside the hub's cluster | Missing connection, naming the hub's cluster |
| **bridge_hunter** | Two-step semantic paths between similar unlinked notes | Stepping-stone notes between two ideas |

**Characteristics**:
- 🧮 Requires embedding computation
- 🔗 Often suggests linking actions
- 🎲 May use random sampling for serendipity
- 💡 Creates "aha moments" through juxtaposition

---

### 4. Graph Analysis Geists

**Pattern**: `Analyze Link Structure → Find Patterns → Suggest Actions`

These geists examine the vault's link graph (nodes = notes, edges = links) to find structural patterns like hubs, orphans, and clusters.

| Geist | Analyzes | Finds |
|-------|----------|-------|
| **link_density_analyser** | Links per 100 words vs the vault median | Dense or sparse notes; groups isolated ones |
| **hidden_hub** | Many semantic neighbours, few linked notes | Implicit hubs worth linking |
| **orphan_connector** | Notes with no links in or out | Where it belongs: its nearest notes; long orphans: split or link? |
| **density_inversion** | Linked neighbours vs semantic similarity (uses embeddings) | Structure/meaning mismatches |

**Characteristics**:
- 🕸️ Uses graph metrics (degree, betweenness, etc.)
- 🔍 Reveals structural properties
- ⚡ Mostly database queries; hidden_hub, orphan_connector and density_inversion also use embeddings
- 🎯 Actionable (suggests specific links)

---

### 5. Clustering & Pattern Geists

**Pattern**: `Group Notes → Label Clusters → Present Patterns`

These geists identify groups of related notes and present them as patterns or themes in your vault.

| Geist | Groups By | Presents |
|-------|-----------|----------|
| **concept_cluster** | Tight semantic clusters (cohesion-checked) | A theme to name; says when none of them link |
| **cluster_mirror** | Semantic clustering | Hidden groupings in vault |
| **pattern_finder** | Recurring three-word prose phrases | Phrases repeated across unconnected notes |

**Characteristics**:
- 🤖 Uses unsupervised ML (clustering algorithms)
- 🏷️ Auto-generates labels (KeyBERT by default; TF-IDF fallback/legacy option)
- 📦 Groups content thematically
- 🔬 Reveals hidden organization

---

### 6. Metadata-Driven Geists

**Pattern**: `Analyze Note Properties → Find Outliers → Suggest Improvements`

These geists examine note metadata (word count, links, tasks, etc.) to identify notes that need attention.

| Geist | Examines | Suggests |
|-------|----------|----------|
| **stub_expander** | Short notes others link to | Develop well-linked stubs |
| **task_archaeology** | Incomplete tasks + age | Revive or archive forgotten tasks |
| **vocabulary_expansion** | Whole-vault embedding dispersion across sessions | Whether your thinking is spreading or converging |
| **structure_diversity_checker** | Note structure patterns | Add variety to writing |
| **metadata_driven_discovery** | Root TTR + staleness | Buried gems: rich old notes |

**Characteristics**:
- 📏 Uses simple metrics (counts, ratios)
- ⚡ Very fast (no embeddings, except vocabulary_expansion)
- 🎯 Actionable suggestions
- 📊 Can be metadata-inference powered

---

### 7. Contrarian & Critical Geists

**Pattern**: `Find Claims → Challenge Assumptions → Generate Counterpoints`

These geists take a skeptical stance, questioning assumptions and generating alternative perspectives.

| Geist | Challenges | Generates |
|-------|-----------|-----------|
| **assumption_challenger** | Confident claims (contrasted with a similar note that hedges) and causal claims with few links | Questions about what the claim rests on |

**Tracery geists**:
- **contradictor** - Challenges existing notes with opposite perspectives

columbo, dialectic_triad and antithesis_generator, which claimed to find a
note's opposite or contradiction by embedding, were retired (see Summary).

**Characteristics**:
- 🤔 Provocative and questioning tone
- 💭 Encourages critical thinking
- ⚖️ Seeks balance and nuance

---

### 8. Creative Transformation Geists

**Pattern**: `Select Notes → Apply Transformation → Suggest Variations`

These geists apply creative transformations (SCAMPER, scale shifts, etc.) to generate novel perspectives.

| Geist | Transformation | Example |
|-------|----------------|---------|
| **method_scrambler** | SCAMPER operations | "What if you reversed the relationship between [[A]] and [[B]]?" |
| **scale_shifter** | Scale (micro ↔ macro) | Connect different abstraction levels |
| **question_generator** | Statements → Questions | Reframe declarative as inquiry |

**Tracery geists**:
- **what_if** - "What if...?" lenses, constraints and transformations, each naming a note

**Characteristics**:
- 🎨 Uses creative thinking frameworks
- 🔄 Applies systematic transformations
- 💡 Generates "What if...?" questions
- 🎲 Often combines with random sampling

---

### 9. Recency & Focus Geists

**Pattern**: `Examine Recent Activity → Highlight Patterns → Reflect On Focus`

These geists analyze what you've been working on recently to reveal patterns in your current attention.

| Geist | Examines | Reveals |
|-------|----------|---------|
| **recent_focus** | Recent notes vs older notes | An old idea your recent work resembles most |

**Characteristics**:
- 📅 Uses modification timestamps
- 🔍 Highlights current focus
- 🎯 Reveals attention patterns
- ⏱️ Time-sensitive (changes as you work)

---

### 10. Reflective Lens Geists 🆕

**Pattern**: `Observable Linguistic Signal → Reflective Provocation`

These geists avoid speculative sentiment labels and instead use measurable
voice and attention signals: tense, pronouns, hedging, questions, sentence
rhythm, semantic surprisal, and neighbourhood churn.

| Geist | Signal | Provocation |
|-------|--------|-------------|
| **self_and_other** | I/me vs we/us language | Where is thinking private vs collective? |
| **uncertainty_mapper** | Hedging density | What are you not ready to commit to? |
| **sentence_variance** | Sentence rhythm | Where does the prose speed up or fragment? |
| **surprisal** | Semantic unexpectedness | What does the outlier know? |
| **attention_shift** | Neighbourhood churn (sampled) | Where has attention moved? |
| **this_time_last_year** | Same day, ±7 days, then same season in earlier years | What has changed since then? |
| **voice_absence** | Missing voice classes | What kinds of notes are absent? |

**Characteristics**:
- 🔍 Evidence-backed prompts (names the signal it observed)
- 🧪 Pure-Python, local, testable analysis
- 🧠 Reflective lenses, not emotion/oracle labels
- ⚡ Cached at `VaultContext` level for session reuse

---

### 11. Tracery-Only Geists

These geists use Tracery grammars rather than code, demonstrating the declarative geist pattern.

| Geist | Purpose |
|-------|---------|
| **contradictor** | Asks what contradicts a sampled note |
| **hub_explorer** | Well-linked notes (3+ backlinks, 100+ words) to review and refine |
| **what_if** | "What if" lenses, constraints and transformations, each naming one of your notes |

**Extension examples** (not bundled; `examples/geists/`): `tracery/note_combinations.yaml`
(`$vault.note_pairs` + save actions), `tracery/semantic_neighbours.yaml` (the
cluster pattern), `tracery/transformation_suggester.yaml` (every Tracery
modifier), `code/metadata_outlier_detector.py` (the MetadataAnalyser API).

---

## Computational Complexity

| Complexity | Pattern | Examples |
|------------|---------|----------|
| **O(1)** | Single note operations | Harvesters, metadata-driven |
| **O(N)** | Linear scans | Recent focus, pattern finder |
| **O(N log N)** | Sorted operations | Temporal patterns, hubs |
| **O(N²)** | Pairwise comparisons | Creative collision, bridge builder |
| **O(N² + clustering)** | ML algorithms | Clustering geists |

---

## Data Requirements

| Requires | Geists |
|----------|--------|
| **Content only** | Harvesters, pattern_finder |
| **Metadata only** | stub_expander, task_archaeology |
| **Links only** | link_density_analyser |
| **Embeddings** | All semantic similarity + temporal drift geists, recent_focus |
| **Multiple sessions** | concept_drift, attention_shift, convergent/divergent_evolution, cyclical_thinking, vocabulary_expansion |

---

## Adding New Geists: Decision Tree

```
┌─ Want to surface buried content?
│  └─ YES → Use Harvester pattern
│     - Pick random note
│     - Extract with regex
│     - Surface 1-3 items
│     - Example: question_harvester
│
├─ Want to track change over time?
│  └─ YES → Use Temporal pattern
│     - Compare snapshots
│     - Detect drift
│     - Question evolution
│     - Example: concept_drift
│
├─ Want to find unexpected connections?
│  └─ YES → Use Semantic Similarity pattern
│     - Compute embeddings
│     - Find similar/dissimilar
│     - Suggest links
│     - Example: creative_collision
│
├─ Want to analyze vault structure?
│  └─ YES → Use Graph Analysis pattern
│     - Query link database
│     - Calculate metrics
│     - Find outliers
│     - Example: hidden_hub
│
├─ Want to identify note properties?
│  └─ YES → Use Metadata-Driven pattern
│     - Check word count, links, etc.
│     - Find outliers
│     - Suggest improvements
│     - Example: stub_expander
│
└─ Want to challenge thinking?
   └─ YES → Use Contrarian pattern
      - Find confident claims
      - Generate counterpoints
      - Question assumptions
      - Example: assumption_challenger
```

---

## Performance Characteristics

| Pattern | Time | Space | Embeddings? | Notes Read |
|---------|------|-------|-------------|------------|
| **Harvester** | O(1) | O(1) | ❌ | 1 |
| **Temporal** | O(N) | O(N) | ✅ | All |
| **Semantic Similarity** | O(N²) worst case | O(N) | ✅ | Sample |
| **Graph Analysis** | O(N + E) | O(1) | ❌ | None (DB) |
| **Clustering** | O(N² + cluster) | O(N) | ✅ | All |
| **Metadata-Driven** | O(N) | O(1) | ❌ | All |
| **Contrarian** | O(N) | O(N) | Optional | Sample |
| **Transformation** | O(N) | O(N) | Optional | Sample |

---

## Usage by Vault Size

### Small Vaults (<50 notes)
**Best suited**:
- ✅ Harvesters (always O(1))
- ✅ Metadata-driven geists
- ✅ Graph analysis (sparse graphs)

**Less useful**:
- ⚠️ Clustering geists (need critical mass)
- ⚠️ Temporal patterns (need history)

### Medium Vaults (50-500 notes)
**Best suited**:
- ✅ All harvester patterns
- ✅ Semantic similarity geists
- ✅ Temporal analysis (if vault has history)
- ✅ Light clustering

**Performance considerations**:
- ⚡ O(N²) geists may slow down
- 💾 Embeddings fit in memory

### Large Vaults (500+ notes)
**Best suited**:
- ✅ All patterns work well
- ✅ Clustering reveals structure
- ✅ Temporal patterns rich
- ✅ Graph analysis finds hubs

**Performance considerations**:
- 🚀 Use sampling where possible
- 💾 Consider sqlite-vec backend
- ⚡ Cache aggressively

---

## Quality Standards

All default geists pass validation per `specs/geist_validation_spec.md`:

### Code Geists (100% compliance)
- ✅ Required: `suggest()` function, proper signature, valid Python, correct return type
- ✅ Recommended: Module docstrings, type hints, function docstrings, no dangerous imports
- ✅ Geist IDs match filenames
- ✅ No dangerous imports (os.system, subprocess, eval, exec, socket, http)

### Tracery Geists (100% compliance)
- ✅ Required: Valid YAML, type field, id field, tracery grammar with origin
- ✅ Recommended: Description fields, valid vault function calls, defined symbols
- ✅ All vault function references validated against function_registry
- ✅ No undefined symbol references

### Testing Requirements
All geists have comprehensive tests that:
- ✅ Use stub-based testing (NOT mocks)
- ✅ Use existing test vault (`testdata/kepano-obsidian-main/`)
- ✅ Execute quickly (< 1 second per test)
- ✅ Provide deterministic output (using session seeds)

---

## Design Principles

### "Muses, Not Oracles"
**Strong examples**:
- Harvesters: Surface questions without answering
- Assumption challenger: Challenge without prescribing
- Pattern finders: Show patterns without interpreting

**Anti-pattern**: Geists that tell you what to do instead of asking what if

### "Sample, Don't Rank"
**Strong examples**:
- Creative collision: Random sampling, no ranking
- Harvesters: 1-3 items sampled, not all matches
- This time last year: Sample one note from the anniversary window, don't rank

**Anti-pattern**: Geists that return "top 10" ranked lists

### "Questions, Not Answers"
**Strong examples**:
- Question harvester: Surfaces existing questions
- Assumption challenger: Questions confident claims
- What if: Pure question generation

**Anti-pattern**: Geists that provide solutions or explanations

---

## Implementation Patterns

### Geist Journal Exclusion

**Pattern**: Geist journal notes (`geist journal/`) are the engine's own session output, not the user's writing. `VaultContext` excludes them from every vault-wide lookup, so geists need no filtering of their own.

**Why**: Journal notes quote and wikilink every note they suggest. Treated as vault content they caused circular references (the engine suggesting its own output), statistical skew (templated text and metadata), false patterns (session dates forming "bursts" and "periods"), inflated backlinks (every suggested note became a hub) and crowding (near-identical session notes filling top-N results such as `unlinked_pairs()` and `recent_notes()`).

**Behaviour**:
- `notes()`, `neighbours()`, `backlinks()`, `outgoing_links()`, `graph_neighbours()`, `hubs()`, `orphans()`, `recent_notes()`, `old_notes()`, `random_notes()`, `unlinked_pairs()`, `get_clusters()`, `get_all_embeddings()`, `surprisal_scores()`, `neighbour_churn()` and `session_embeddings_by_session()` never return or count journal notes. Vault functions built on them (for example `contrarian_to`, `sample_notes`) inherit this.
- Journal notes are dropped *before* any top-N cut, so they cannot crowd out user notes.
- Explicit access still works: `get_note(path)`, `get_embedding(path)` and `resolve_link_target()` return a journal note when asked for it, so a user's own link to a session note still resolves.
- `notes_excluding_journal()` is kept as an alias of `notes()` for older geists.

**Implementation**:
```python
# ✅ Correct - VaultContext already excludes the geist journal
def suggest(vault: VaultContext) -> list[Suggestion]:
    notes = vault.notes()
    for note in notes:
        similar = vault.neighbours(note, count=5)  # no journal notes here either

# ❌ Unnecessary - filtering again is dead code
similar = [n for n in vault.neighbours(note) if not n.path.startswith("geist journal/")]
```

**Tests**: `tests/unit/test_vault_context.py::test_no_vault_wide_lookup_returns_a_journal_note` owns the contract; each geist's `*_excludes_geist_journal` test plants journal notes that would otherwise qualify.

## Conclusion

When designing new geists:
1. **Identify the pattern** - Which category does it fit?
2. **Check performance** - What's the computational cost?
3. **Maintain principles** - Muses not oracles, questions not answers
4. **Consider reusability** - Can this become a family?

The catalogue reveals clear patterns that can be identified, extended, and combined. The **Harvester Family** demonstrates how a simple pattern (extract → surface) can be applied to multiple content types while maintaining consistent behaviour and performance characteristics.

---

**Version**: 2.1
**Date**: 2026-10-02
