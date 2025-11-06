# Geist Typology

**A classification of geists by their underlying patterns and strategies**

GeistFabrik's 41 default geists follow distinct patterns. This document categorizes them by their core mechanisms, making it easy to understand how they work and identify opportunities for new geist families.

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

**Inspiration**:
- Seeing only questions reveals inquiry structure [@pomeranian99]
- Forgotten TODOs represent deferred intentions
- Quotes map intellectual influences over time

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
| **congruence_mirror** | Similarity vs link structure | Reveal implicit/explicit gaps |

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
| **cluster_mirror** | Semantic clusters (HDBSCAN) | Automatically labeled clusters |
| **concept_cluster** | Topic similarity | Conceptual neighborhoods |
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

**Characteristics**:
- 🎨 Uses creative thinking frameworks
- 🔄 Applies systematic transformations
- 💡 Generates "What if..." questions
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

## Typology Matrix

### By Computational Complexity

| Complexity | Pattern | Examples |
|------------|---------|----------|
| **O(1)** | Single note operations | Harvesters, metadata-driven |
| **O(N)** | Linear scans | Recent focus, pattern finder |
| **O(N log N)** | Sorted operations | Old notes, hubs |
| **O(N²)** | Pairwise comparisons | Creative collision, bridge builder |
| **O(N² + clustering)** | ML algorithms | Cluster mirror, temporal clustering |

### By Data Requirements

| Requires | Geists |
|----------|--------|
| **Content only** | Harvesters, pattern_finder |
| **Metadata only** | stub_expander, task_archaeology, recent_focus |
| **Links only** | hidden_hub, link_density_analyser, orphan_connector |
| **Embeddings** | All semantic similarity + temporal drift geists |
| **Multiple sessions** | session_drift, hermeneutic_instability |

### By Output Type

| Output | Pattern | Examples |
|--------|---------|----------|
| **Question** | "What if...?" | Most geists |
| **Observation** | "X and Y relate..." | Congruence mirror (implicit) |
| **Challenge** | "I think you're lying..." | Columbo, assumption_challenger |
| **Quote** | Direct content from notes | Harvesters |

---

## Patterns for Future Geist Families

### Proven Patterns Ready for Extension

**1. Harvester Family** (✅ Implemented)
- Pattern: Extract content type → Surface with temporal framing
- Existing: question, todo, quote
- **Potential**: hypothesis, claim, definition, link references

**2. Temporal Family** (Partially implemented)
- Pattern: Compare across time → Detect evolution
- Existing: 11 geists
- **Potential**: velocity (rate of change), acceleration (change in rate)

**3. Graph Family** (Partially implemented)
- Pattern: Network analysis → Structural insights
- Existing: 5 geists
- **Potential**: betweenness centrality, community detection, path analysis

**4. Transformation Family** (Partially implemented)
- Pattern: Apply framework → Generate variations
- Existing: 3 geists
- **Potential**: Six Thinking Hats, TRIZ, morphological analysis

### Unexplored Patterns

**5. Linguistic Family** (Not yet implemented)
- Pattern: Analyze language → Suggest style improvements
- **Potential**: readability_checker, jargon_detector, passive_voice_finder

**6. Cross-Reference Family** (Not yet implemented)
- Pattern: Match content patterns → Find related material
- **Potential**: definition_matcher, example_finder, citation_suggester

**7. Dialogue Family** (Not yet implemented)
- Pattern: Simulate conversation → Generate responses
- **Potential**: socratic_questioner, devils_advocate, rubber_duck

---

## Design Patterns by Principle

### "Muses, Not Oracles"

**Strong Examples**:
- Harvesters: Surface questions without answering
- Columbo: Challenge without prescribing
- Cluster mirror: Show patterns without interpreting

**Anti-pattern**: Geists that tell you what to do instead of asking what if

### "Sample, Don't Rank"

**Strong Examples**:
- Creative collision: Random sampling, no ranking
- Harvesters: 1-3 items sampled, not all matches
- Temporal mirror: Sample from periods, don't rank

**Anti-pattern**: Geists that return "top 10" ranked lists

### "Questions, Not Answers"

**Strong Examples**:
- Question harvester: Surfaces existing questions
- Assumption challenger: Questions confident claims
- What if: Pure question generation

**Anti-pattern**: Geists that provide solutions or explanations

---

## Usage Patterns by Vault Size

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

## Performance Characteristics by Pattern

| Pattern | Time Complexity | Space | Embeddings? | Notes Read |
|---------|----------------|-------|-------------|------------|
| **Harvester** | O(1) | O(1) | ❌ | 1 |
| **Temporal** | O(N) | O(N) | ✅ | All |
| **Semantic Similarity** | O(N²) worst case | O(N) | ✅ | Sample |
| **Graph Analysis** | O(N + E) | O(1) | ❌ | None (DB) |
| **Clustering** | O(N² + cluster) | O(N) | ✅ | All |
| **Metadata-Driven** | O(N) | O(1) | ❌ | All |
| **Contrarian** | O(N) | O(N) | Optional | Sample |
| **Transformation** | O(N) | O(N) | Optional | Sample |

---

## Conclusion

GeistFabrik's geist ecosystem follows clear patterns that can be identified, extended, and combined. The **Harvester Family** demonstrates how a simple pattern (extract → surface) can be applied to multiple content types while maintaining consistent behavior.

When designing new geists:
1. **Identify the pattern** - Which category does it fit?
2. **Check performance** - What's the computational cost?
3. **Maintain principles** - Muses not oracles, questions not answers
4. **Consider reusability** - Can this become a family?

The typology reveals opportunities for new geist families (linguistic, cross-reference, dialogue) and shows how existing patterns can be extended systematically.

---

**Version**: 1.0
**Date**: 2025-11-06
**Geists Catalogued**: 41 (38 code + 3 harvester additions)
