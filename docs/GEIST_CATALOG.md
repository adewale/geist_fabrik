# Geist Catalogue

**A comprehensive classification of GeistFabrik's default geists by pattern and implementation status**

GeistFabrik ships with 51 default geists following distinct patterns. This document categorizes them by their core mechanisms, tracks implementation status, and provides guidance for understanding and extending the geist ecosystem.

**Last Updated**: 2025-11-09

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| **Code Geists** | 42 (39 core + 3 harvesters) | ✅ All implemented |
| **Tracery Geists** | 9 | ✅ All implemented |
| **Total Geists** | 51 | ✅ Production ready |

**Quality**: 100% pass rate on validation spec audit (see Quality Standards below)

---

## Pattern Categories

### 1. Extraction-Based Geists (Harvester Family) 🆕

**Pattern**: `Random Note Selection → Content Extraction → Temporal Provocation`

These geists pick a random note, extract specific content types using regex, and surface them with temporal framing. They treat buried artifacts as valuable content worth revisiting.

| Geist | Extracts | Provocation |
|-------|----------|-------------|
| **question_harvester** | Questions (`?`) | "What if you revisited this question now?" |
| **todo_harvester** | TODO/FIXME/HACK markers | "What if you tackled this now?" |
| **quote_harvester** | Blockquotes (`>`) | "What if you reflected on this again?" |

**Characteristics**:
- ✅ O(1) per session (single note read)
- ✅ Fast regex extraction
- ✅ Silent abstention when content not found
- ✅ Deterministic by session date
- ✅ No cross-note analysis

---

### 2. Temporal Analysis Geists

**Pattern**: `Time-Based Comparison → Detect Change → Question Evolution`

These geists compare notes across different time periods to reveal how thinking evolves, using either creation dates or embedding drift.

| Geist | Compares | Detects |
|-------|----------|---------|
| **temporal_drift** | Old vs recent notes | Stale but important notes |
| **session_drift** | Embeddings across sessions | How interpretation evolves |
| **hermeneutic_instability** | Past vs current embeddings | Notes whose meaning changed |
| **concept_drift** | Semantic neighborhoods over time | Concept boundaries shifting |
| **temporal_clustering** | Clusters across time periods | Thinking patterns by era |
| **seasonal_patterns** | Notes by creation season | Seasonal thinking rhythms |
| **seasonal_revisit** | Same season, different years | Yearly cycles |
| **on_this_day** | Same calendar date | Anniversary reflections |
| **anachronism_detector** | Temporal contradictions | Ideas out of sync with era |
| **convergent_evolution** | Notes becoming similar | Independent paths converging |
| **divergent_evolution** | Notes becoming different | Paths diverging over time |
| **temporal_mirror** | Different time periods | Cross-temporal patterns |
| **creation_burst** | Days with 3+ notes created | Productive burst days |
| **burst_evolution** | Burst day notes over time | How burst notes evolved |

**Characteristics**:
- 📊 Uses temporal metadata (creation date, modification time)
- 🔄 Tracks change over time
- 📈 Often requires embeddings to detect semantic drift
- 🎯 Highlights evolution of thinking

---

### 3. Semantic Similarity Geists

**Pattern**: `Find Similar/Dissimilar Notes → Suggest Connections`

These geists use embeddings to find notes that are semantically related (or deliberately distant) and suggest unexpected connections.

| Geist | Strategy | Purpose |
|-------|----------|---------|
| **creative_collision** | Random dissimilar pairs | Force unexpected combinations |
| **bridge_builder** | Unlinked similar notes | Suggest missing connections |
| **bridge_hunter** | Existing links with high similarity | Strengthen explicit connections |
| **island_hopper** | Cross-cluster connections | Bridge isolated knowledge islands |

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
| **columbo** | Claims vs linked evidence | Contradictions and inconsistencies |
| **link_density_analyser** | Links per note | Under/over-linked notes |
| **hidden_hub** | Backlinks without outlinks | Important but isolated notes |
| **density_inversion** | Link density vs semantic similarity | Structure/meaning mismatches |
| **blind_spot_detector** | Recent note neighborhoods | Gaps in current thinking |

**Characteristics**:
- 🕸️ Uses graph metrics (degree, betweenness, etc.)
- 🔍 Reveals structural properties
- ⚡ Fast (database queries, no embeddings needed)
- 🎯 Actionable (suggests specific links)

---

### 5. Clustering & Pattern Geists

**Pattern**: `Group Notes → Label Clusters → Present Patterns`

These geists identify groups of related notes and present them as patterns or themes in your vault.

| Geist | Groups By | Presents |
|-------|-----------|----------|
| **concept_cluster** | Topic similarity | Conceptual neighborhoods |
| **cluster_mirror** | Semantic clustering | Hidden groupings in vault |
| **pattern_finder** | Recurring structures | Common patterns across notes |

**Characteristics**:
- 🤖 Uses unsupervised ML (clustering algorithms)
- 🏷️ Auto-generates labels (c-TF-IDF + MMR)
- 📦 Groups content thematically
- 🔬 Reveals hidden organization

---

### 6. Metadata-Driven Geists

**Pattern**: `Analyze Note Properties → Find Outliers → Suggest Improvements`

These geists examine note metadata (word count, links, tasks, etc.) to identify notes that need attention.

| Geist | Examines | Suggests |
|-------|----------|----------|
| **stub_expander** | Word count + links | Develop short but connected notes |
| **task_archaeology** | Incomplete tasks + age | Revisit forgotten tasks |
| **complexity_mismatch** | Content complexity metrics | Notes with unexpected complexity |
| **vocabulary_expansion** | Unique word usage | Notes with limited vocabulary |
| **structure_diversity_checker** | Note structure patterns | Add variety to writing |
| **metadata_driven_discovery** | Metadata patterns | Unexpected property combinations |

**Characteristics**:
- 📏 Uses simple metrics (counts, ratios)
- ⚡ Very fast (no embeddings)
- 🎯 Actionable suggestions
- 📊 Can be metadata-inference powered

---

### 7. Contrarian & Critical Geists

**Pattern**: `Find Claims → Challenge Assumptions → Generate Counterpoints`

These geists take a skeptical stance, questioning assumptions and generating alternative perspectives.

| Geist | Challenges | Generates |
|-------|-----------|-----------|
| **assumption_challenger** | Confident claims | Questions about assumptions |
| **antithesis_generator** | Thesis statements | Opposing viewpoints |
| **columbo** | Consistency between notes | "I think you're lying about..." |
| **dialectic_triad** | Thesis + antithesis | Synthesis opportunities |

**Tracery geists**:
- **contradictor** - Challenges existing notes with opposite perspectives

**Characteristics**:
- 🤔 Provocative and questioning tone
- 🎭 Often adopts personas (Columbo detective)
- 💭 Encourages critical thinking
- ⚖️ Seeks balance and nuance

---

### 8. Creative Transformation Geists

**Pattern**: `Select Notes → Apply Transformation → Suggest Variations`

These geists apply creative transformations (SCAMPER, scale shifts, etc.) to generate novel perspectives.

| Geist | Transformation | Example |
|-------|----------------|---------|
| **method_scrambler** | SCAMPER operations | "What if you reversed [[A]] and [[B]]?" |
| **scale_shifter** | Scale (micro ↔ macro) | Connect different abstraction levels |
| **question_generator** | Statements → Questions | Reframe declarative as inquiry |

**Tracery geists**:
- **perspective_shifter** - View notes through different lenses
- **transformation_suggester** - Showcase all Tracery modifiers
- **what_if** - Generate "What if...?" prompts

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
| **recent_focus** | Recently modified notes | Current areas of attention |
| **blind_spot_detector** | Recent semantic neighborhoods | Gaps in current thinking |

**Characteristics**:
- 📅 Uses modification timestamps
- 🔍 Highlights current focus
- 🎯 Reveals attention patterns
- ⏱️ Time-sensitive (changes as you work)

---

### 10. Tracery-Only Geists

These geists use Tracery grammars rather than code, demonstrating the declarative geist pattern.

| Geist | Purpose |
|-------|---------|
| **hub_explorer** | Highlights hub notes with many connections |
| **note_combinations** | Suggests combining random notes creatively |
| **orphan_connector** | Suggests connections for orphaned notes |
| **random_prompts** | Generates random creative prompts |
| **semantic_neighbours** | Shows semantic neighborhoods |

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
| **Metadata only** | stub_expander, task_archaeology, recent_focus |
| **Links only** | hidden_hub, link_density_analyser, orphan_connector |
| **Embeddings** | All semantic similarity + temporal drift geists |
| **Multiple sessions** | session_drift, hermeneutic_instability |

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
│     - Example: session_drift
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
- Columbo: Challenge without prescribing
- Pattern finders: Show patterns without interpreting

**Anti-pattern**: Geists that tell you what to do instead of asking what if

### "Sample, Don't Rank"
**Strong examples**:
- Creative collision: Random sampling, no ranking
- Harvesters: 1-3 items sampled, not all matches
- Temporal mirror: Sample from periods, don't rank

**Anti-pattern**: Geists that return "top 10" ranked lists

### "Questions, Not Answers"
**Strong examples**:
- Question harvester: Surfaces existing questions
- Assumption challenger: Questions confident claims
- What if: Pure question generation

**Anti-pattern**: Geists that provide solutions or explanations

---

## Conclusion

When designing new geists:
1. **Identify the pattern** - Which category does it fit?
2. **Check performance** - What's the computational cost?
3. **Maintain principles** - Muses not oracles, questions not answers
4. **Consider reusability** - Can this become a family?

The catalogue reveals clear patterns that can be identified, extended, and combined. The **Harvester Family** demonstrates how a simple pattern (extract → surface) can be applied to multiple content types while maintaining consistent behaviour and performance characteristics.

---

**Version**: 2.0
**Date**: 2025-11-06
**Geists Catalogued**: 50 (41 code + 9 Tracery)
