# GeistFabrik 2.0 Wishlist

Insights from ranking v1.0 geists against Gordon Brander's philosophy of "muses not oracles."

## Core Finding: The Divergence Gradient

Our 45 geists form a clear spectrum from **pure provocation** to **vault maintenance**:

```
Divergent                                            Convergent
Provocations ─────→ Discoveries ─────→ Organization ─────→ Maintenance
(Tier S)            (Tier A)           (Tier B)            (Tier C)
```

Brander's philosophy celebrates the left side. v1.0 has a mix across the entire spectrum.

## Tier S: Pure Brander - Oracular Provocations

**Philosophy**: "More tarot than flash cards. Tarot for thought."

**Examples**:
- `what_if` - Literally embodies "What if...?" questions
- `creative_collision` - Direct implementation of "collide notes in new ways"
- `method_scrambler` - Cross-domain provocations (underrated!)
- `contradictor` - Forces opposite perspectives
- `columbo` - Socratic "just one more thing" questioning

**Characteristics**:
- Pure divergence, zero convergence
- Ask questions you wouldn't ask yourself
- Create surprising juxtapositions
- Never prescriptive
- Feel like opening a fortune cookie, not a todo list

**v2.0 Opportunity**: Double down. These are the soul of GeistFabrik.

## Tier A: Serendipitous Discovery

**Philosophy**: "I never would have thought to connect these"

**Examples**:
- `anachronism_detector` - Temporal displacement creates surprise
- `scale_shifter` - Zoom in/out provokes new perspectives
- `blind_spot_detector` - Reveals overlooked connections (note: not prescriptive)
- `hermeneutic_instability` - Notes whose meaning has shifted
- `on_this_day` / `seasonal_revisit` - Temporal serendipity

**Characteristics**:
- Highly divergent with some discovery element
- Create unexpected connections
- Reveal patterns you wouldn't see
- Frame as provocations, not prescriptions

**v2.0 Opportunity**: Strong alignment. Keep and expand.

## Tier B: Self-Organization Support

**Philosophy**: "Related ideas begin to clump together" (self-organizing ideas)

**Examples**:
- `bridge_builder` / `bridge_hunter` / `island_hopper` - Cluster connections
- `convergent_evolution` / `divergent_evolution` - Semantic movement
- `concept_cluster` / `pattern_finder` - Organic grouping
- `hidden_hub` - Semantic centrality
- `temporal_mirror` - Cross-time comparisons

**Characteristics**:
- Support organic knowledge growth
- Less provocative, more supportive
- Help ideas evolve and cluster naturally
- Discovery-oriented but not pure provocation

**v2.0 Question**: Are these geists or system features? Should they be background intelligence rather than provocations?

## Tier C: Maintenance & Hygiene

**Philosophy**: Useful but **not aligned with "muses not oracles"**

**Examples**:
- `task_archaeology` - "Here are your incomplete tasks"
- `stub_expander` - "Here's what needs expansion"
- `temporal_drift` - "These notes are stale"
- `link_density_analyser` - Statistics reporting
- `structure_diversity_checker` - Analytics dashboard

**Characteristics**:
- Convergent, not divergent
- Prescriptive: "You should..."
- Point toward specific actions
- Vault health, not thought provocation
- Feel obligatory, not exploratory

**v2.0 Question**: Do these belong in GeistFabrik at all? Or should they be separate "vault utilities"?

---

## Key Surprises from v1.0 Analysis

### 1. Naming vs Function Mismatch

**Evocative names often hide prescriptive functions:**
- `task_archaeology` sounds like discovery, functions as guilt-trip
- `temporal_drift` sounds organic, functions as maintenance nag
- `hub_explorer` sounds provocative, functions as status report

**Procedural names often hide pure provocation:**
- `method_scrambler` sounds dry, is incredibly Brander-aligned
- `creative_collision` sounds mechanical, is pure oracular magic

**Lesson**: Name geists for what they **provoke**, not what they **touch**.

### 2. Tracery Geists Punch Above Their Weight

**Top tier dominated by simple Tracery geists:**
- `what_if`
- `contradictor`
- `random_prompts`
- `note_combinations`

**Why**: Simplicity enforces purity. Tracery can't be clever or helpful—only oracular. The medium matches the message.

**v2.0 Opportunity**: Lean harder into Tracery for pure provocations. Use code geists for complex analysis when needed.

### 3. The "Recent Focus" Problem

`recent_focus` seems like it would create useful context, but it's actually **anti-Brander**:
- Narrows focus to current work (convergent)
- Reinforces existing thinking patterns
- Opposite of serendipity

**Lesson**: Beware geists that reinforce attention patterns rather than disrupting them.

### 4. Discovery ≠ Provocation

**Compare**:
- `hub_explorer` (Tier B): "Here are your hubs" (reporting)
- `blind_spot_detector` (Tier A): "You might be overlooking this" (provocation)

Both discover patterns, but framing makes all the difference:
- **Reporting**: Tells you what is
- **Provocation**: Makes you question what might be

### 5. The "Should" Test

Simple heuristic for identifying prescriptive geists:

**If the suggestion implies "you should...", it's prescriptive:**
- ✗ "You should expand [[Stub Note]]"
- ✗ "You should complete [[Old Task]]"
- ✗ "You should link [[Orphan Note]]"

**If it implies "what if...", it's provocative:**
- ✓ "What if [[Note A]] and [[Note B]] are actually about the same thing?"
- ✓ "Your [[Claim]] contradicts your [[Evidence]]—deliberate?"
- ✓ "[[Old Note]] feels historically misplaced in its cluster"

**v2.0 Design Rule**: Every geist passes the "should" test.

---

## Ideas for v2.0

### 1. Pure Provocation Mode

**Concept**: A mode that runs **only Tier S/A geists**—pure oracular provocations with zero maintenance.

```yaml
mode: pure_brander
tiers: [S, A]  # Only divergent provocations
```

Users who want "tarot for thought" get exactly that.

### 2. Separate Vault Utilities

**Concept**: Move Tier C geists to a separate `vault-health` command:

```bash
# Provocations (geists)
geistfabrik invoke

# Maintenance (utilities)
geistfabrik vault-health
```

This separates **muses** from **oracles**.

### 3. New Pure Provocation Geists

**Ideas inspired by the analysis:**

**heretic** - Finds your most strongly-held claims and generates heretical counters
```
"Your [[Democracy Note]] assumes majority = wisdom. What if it's tyranny of the median?"
```

**category_breaker** - Finds notes that don't fit their neighbors
```
"[[This Note]] is in your 'Philosophy' cluster but reads like engineering. Misclassified or bridge?"
```

**temporal_scrambler** - Pairs notes from maximally different time periods
```
"[[2020 Note]] + [[2024 Note]] = 4 years of drift. Still the same person?"
```

**confidence_challenger** - Finds certain claims and asks for doubt
```
"[[Your Claim]] has no hedging words. What would make you less certain?"
```

**absent_voice** - Identifies missing perspectives in clusters
```
"Your [[Economics]] cluster has no notes from labor's perspective. Intentional blindspot?"
```

**style_mirror** - Compares how you write about different topics
```
"You write [[Science]] notes with hedging but [[Politics]] notes with certainty. Why?"
```

All pure Tier S provocations. No prescriptions, only questions.

### 4. Tracery-First Development

**Principle**: Default to Tracery for new geists. Only use code when necessary.

**Why**:
- Tracery enforces oracular simplicity
- Can't accidentally become prescriptive
- Easier for users to extend
- Top-tier geists are already Tracery-heavy

**When to use code**:
- Complex semantic analysis required
- Multi-step reasoning needed
- Performance-critical operations

### 5. Geist Personality System

**Concept**: Geists have explicit personalities that shape their provocations:

```yaml
type: geist-tracery
id: socratic
personality:
  voice: questioning
  stance: skeptical
  provocation_level: high
tracery:
  origin: "#question#"
```

**Personalities**:
- **socratic**: Questions everything (columbo, assumption_challenger)
- **joker**: Unexpected juxtapositions (creative_collision, method_scrambler)
- **oracle**: Cryptic hints (what_if, random_prompts)
- **archaeologist**: Deep time perspectives (on_this_day, temporal_mirror)
- **heretic**: Challenges orthodoxy (contradictor, antithesis_generator)

Users can disable/enable by personality: "I want more skeptics, fewer jokers today."

### 6. The "Provocation Slider"

**Concept**: Users tune how provocative vs supportive they want their session:

```yaml
provocation_level: 0.8  # 0.0 = pure maintenance, 1.0 = pure provocation
```

- **0.0-0.3**: Mostly Tier B/C (organization and maintenance)
- **0.4-0.6**: Balanced mix across all tiers
- **0.7-1.0**: Mostly Tier S/A (pure provocations)

Adaptive to user's current needs without permanently disabling geists.

### 7. Anti-Patterns to Avoid

**Based on v1.0 experience:**

❌ **Don't create geists that**:
- Tell users what they "should" do
- Report statistics without provoking thought
- Reinforce existing attention patterns
- Feel like obligations or guilt-trips
- Point toward convergent actions

✓ **Do create geists that**:
- Ask questions users wouldn't ask themselves
- Create surprising juxtapositions
- Disrupt comfortable patterns
- Feel playful and exploratory
- Open possibilities rather than close them

### 8. Naming Convention Improvements

**v1.0 Problem**: Names describe mechanism, not provocation.

**v2.0 Principle**: Names should evoke the *feeling* of the provocation.

**Examples**:

| v1.0 Name | What It Does | Better v2.0 Name |
|-----------|--------------|------------------|
| `task_archaeology` | Finds incomplete tasks | `unfinished_business` or just... delete it |
| `temporal_drift` | Finds stale notes | `the_forgotten` |
| `link_density_analyser` | Counts links | Delete (pure analytics) |
| `hub_explorer` | Shows hub notes | `the_commons` |
| `method_scrambler` | Cross-domain methods | `cross_pollinator` ⭐ |

**Test**: Does the name make you curious or dutiful?
- **Curious**: Good geist name
- **Dutiful**: Bad geist name (or bad geist)

---

## Architectural Questions for v2.0

### 1. Should Tier C Exist?

**Question**: Are maintenance geists actually geists, or are they vault utilities that snuck into the geist system?

**Options**:
- **Keep them**: Users find them useful
- **Separate them**: Different command/mode for maintenance vs provocation
- **Delete them**: GeistFabrik is *only* about provocation

**Leans toward**: Separate them. Let users choose "muse mode" vs "oracle mode" explicitly.

### 2. Should Tier B Be Background Intelligence?

**Question**: Should self-organization geists (bridge_builder, concept_cluster, etc.) run in the background and inform other geists rather than generating their own suggestions?

**Current**: They generate suggestions like "[[Note A]] and [[Note B]] could bridge these clusters"

**Alternative**: They build a "bridge map" that other provocative geists use:
- `creative_collision` uses bridge map to avoid suggesting existing bridges
- `blind_spot_detector` uses cluster map to find gaps
- Background intelligence, not surface suggestions

**Trade-off**:
- **Pro**: Keeps journal focused on pure provocations
- **Con**: Users lose visibility into self-organization

### 3. What's the Right Tier Mix?

**v1.0 Distribution**:
- Tier S: 9 geists (20%)
- Tier A: 11 geists (24%)
- Tier B: 18 geists (40%)
- Tier C: 7 geists (16%)

**Brander-Optimal Distribution** (speculative):
- Tier S: 50% (pure provocations)
- Tier A: 30% (serendipitous discoveries)
- Tier B: 15% (self-organization support)
- Tier C: 5% (or separate entirely)

**Question**: Should we rebalance toward more provocation?

---

## Success Metrics for v2.0

### Qualitative Tests

**The "Fortune Cookie" Test**:
Open a session note. Does it feel like:
- ✓ Opening a fortune cookie (curiosity, surprise, delight)
- ✗ Opening your todo list (obligation, guilt, duty)

**The "Questions > Answers" Test**:
Count suggestions by type:
- ✓ Provocative questions: "What if...?", "Why...?", "What about...?"
- ✗ Prescriptive statements: "You should...", "Consider expanding...", "Link this..."

Target ratio: 80% questions, 20% statements (and those statements should be provocative observations, not prescriptions)

**The "Surprise" Test**:
User reaction should be:
- ✓ "Whoa, I never thought about that connection!"
- ✗ "Yeah, I know, I should finish that task."

### Quantitative Metrics

**Geist Tier Distribution**:
- v1.0: 20% S, 24% A, 40% B, 16% C
- v2.0 Goal: 50% S, 30% A, 15% B, 5% C

**User Extension Growth**:
- Success = 2-3x more geists after one year
- Those extensions should be mostly Tier S/A (provocative)

**Engagement Patterns**:
- Time spent reading suggestions (up = good)
- Time spent acting on suggestions (neutral)
- Frequency of "I never thought of that" moments (track via optional feedback)

---

## Implementation Strategy

### Phase 1: Classification
- Tag all v1.0 geists with tiers (S/A/B/C)
- Add `provocation_level` metadata to each geist
- Update config.yaml to show tiers

### Phase 2: Separation
- Create `vault-health` command for Tier C utilities
- Add `--mode pure` flag for Tier S/A only
- Make default mode configurable

### Phase 3: New Provocations
- Implement 5-10 new Tier S geists (Tracery-first)
- Focus on missing perspectives and surprising connections
- Test with "Fortune Cookie" and "Questions > Answers" metrics

### Phase 4: Community
- Document tier system for geist developers
- Create contribution guidelines emphasizing provocation over prescription
- Share tier ranking of v1.0 geists as learning tool

---

## Questions for Future Consideration

1. **Should GeistFabrik have an explicit "I need maintenance" mode?**
   - Or should maintenance be a different tool entirely?

2. **Can we automatically detect prescriptive geists?**
   - NLP analysis of suggestion text for "should" patterns?
   - Flag during development/review?

3. **Should users be able to tune provocation level per-session?**
   - "Today I want maximum chaos" vs "Today I want gentle nudges"

4. **What's the relationship between provocation and actionability?**
   - Pure provocations are less actionable
   - Is that okay? (Yes, per Brander)
   - Should we even measure "actions taken"?

5. **Should geists compose?**
   - e.g., `columbo` questions the output of `creative_collision`
   - Multi-stage provocations might be deeper
   - But adds complexity

6. **How do we handle user-contributed geists that are prescriptive?**
   - Tier labeling system helps
   - But enforcing philosophy in open source is hard
   - Documentation and examples might be enough

---

## Closing Thoughts

v1.0 GeistFabrik has **excellent range**—from pure oracular provocations to practical vault maintenance. This makes it useful and accessible.

v2.0 GeistFabrik should have **laser focus**—optimized for Brander's vision of "muses not oracles." This means:

1. **More pure provocations** (double Tier S geists)
2. **Separate maintenance from muses** (vault-health vs invoke)
3. **Tracery-first development** (enforces simplicity)
4. **Better naming** (evoke feeling, not mechanism)
5. **Explicit tier system** (users understand provocation vs prescription)

The core insight: **GeistFabrik should make you think differently, not organize better.**

When you open your geist journal, it should feel like:
- Opening a pack of tarot cards
- Consulting an oracle
- Reading a book of koans
- Playing with ideas

Not like:
- Checking your email
- Reading a todo list
- Getting performance feedback
- Doing homework

That's the difference between a muse and an oracle. v1.0 has both. v2.0 should choose.

---

*Based on analysis of 45 default geists against Gordon Brander's philosophy of divergent thinking tools, conducted 2025-10-26*
