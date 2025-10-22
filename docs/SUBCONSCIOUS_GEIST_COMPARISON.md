# Subconscious Geist Ideas: Feasibility Analysis

**Date**: 2025-10-22
**Source**: https://github.com/subconsciousnetwork/subconscious/wiki/Geist-ideas
**Status**: Analysis of which geist ideas from Subconscious are possible in GeistFabrik

## Summary

**17 out of 17 geist ideas are possible in GeistFabrik** 🎉

- **9 already implemented** in some form
- **8 trivially implementable** (5-15 minutes each with existing infrastructure)
- **0 impossible** with current architecture

## Already Implemented ✅

### 1. The Wheel of Fortune (Random note)
**Status**: ✅ Already exists
**Implementation**:
- `VaultContext.sample_notes(k)` - Random sampling
- `VaultContext.random_notes(k)` - Alternative random selection
- Used in multiple Tracery geists (`note_combinations`, `what_if`, etc.)

### 2. Constellation (Suggested links to related notes)
**Status**: ✅ Already exists
**Implementation**:
- `examples/geists/code/bridge_builder.py` - Suggests links between semantically similar notes
- `examples/geists/tracery/semantic_neighbours.yaml` - Surfaces related notes
- `VaultContext.unlinked_pairs()` - Finds semantically similar notes without links
- Uses sentence-transformers embeddings for semantic similarity

### 3. Recent (Frecency-weighted notes)
**Status**: ✅ Already exists
**Implementation**:
- `VaultContext.recent_notes(k)` - Most recently modified notes
- `examples/geists/code/recent_focus.py` - Analyzes recent editing patterns
- Temporal embeddings track note age and seasonal patterns
- Session-based temporal features (3 dimensions added to 384 semantic dimensions)

### 4. Fool (Concept collider)
**Status**: ✅ Already exists
**Implementation**:
- `examples/geists/code/creative_collision.py` - Combines distant concepts
- `examples/geists/tracery/note_combinations.yaml` - Random note pairings
- Uses semantic distance to find interesting juxtapositions

### 5. Librarian (Well-connected notes)
**Status**: ✅ Already exists
**Implementation**:
- `VaultContext.hubs(k)` - Notes with most connections
- `examples/geists/code/link_density_analyser.py` - Analyzes link patterns
- `examples/geists/tracery/hub_explorer.yaml` - Surfaces central notes
- Graph operations on SQLite link tables

### 6. Time Capsule (Repost old notes)
**Status**: ✅ Already exists
**Implementation**:
- `examples/geists/tracery/temporal_mirror.yaml` - Compares old and new notes
- `VaultContext.old_notes(k)` - Least recently modified notes
- `sample_old_notes(k, pool_size)` - Sample from oldest notes (follows "Sample, don't rank")
- Temporal features track note age and creation dates

### 7. Question Geist (Parse questions)
**Status**: ✅ Already exists
**Implementation**:
- `examples/geists/code/question_generator.py` - Finds and surfaces questions
- Could enhance with metadata inference for question detection

### 8. Emergent Themes (Backlink clusters)
**Status**: ✅ Already exists
**Implementation**:
- `VaultContext.hubs()` - High-backlink notes
- `examples/geists/code/concept_cluster.py` - Identifies clusters of related notes
- `VaultContext.backlinks(note)` - Get all notes linking to a note

### 9. Concept Collider (Semantic similarity)
**Status**: ✅ Already exists
**Implementation**:
- `VaultContext.neighbours(note, k)` - Semantic nearest neighbors
- `examples/geists/code/creative_collision.py` - Uses semantic distance
- `embeddings.py` - Full sentence-transformers integration with all-MiniLM-L6-v2

## Easily Implementable (5-15 minutes) ⚡

### 10. The Star (New note suggestions)
**Effort**: 5 minutes
**Approach**: Similar to existing `stub_expander.py`
```python
# Already have stub detection
stubs = [n for n in vault.notes() if len(n.content) < 200]
# Could add metadata for "incomplete" or "needs expansion"
```

### 11. Sage (Random quote reposting)
**Effort**: 10 minutes
**Approach**: Metadata inference + sampling
```python
# Add metadata_inference/quotes.py
def infer(note, vault):
    has_quote = '—' in note.content or note.content.startswith('>')
    return {"has_quote": has_quote}

# Geist
quotes = [n for n in vault.notes() if vault.metadata(n.title).get("has_quote")]
return vault.sample(quotes, 1)
```

### 12. Oracle (Repost /prompt or /oblique tags)
**Effort**: 5 minutes
**Approach**: Direct tag filtering
```python
def suggest(vault: VaultContext) -> List[Suggestion]:
    prompts = [n for n in vault.notes()
               if "/prompt" in n.tags or "/oblique" in n.tags]
    if not prompts:
        return []

    selected = vault.sample(prompts, 1)[0]
    return [Suggestion(
        text=f"Today's oracle: {selected.content[:200]}",
        notes=[selected.title],
        geist_id="oracle"
    )]
```

### 13. Farmer (Zettelkasten elaboration prompts)
**Effort**: 10 minutes
**Approach**: Tracery geist with targeted questions
```yaml
type: geist-tracery
id: farmer
description: Zettelkasten-style elaboration prompts

tracery:
  origin:
    - "What assumptions underlie [[#note#]]?"
    - "What would contradict [[#note#]]?"
    - "How does [[#note#]] connect to #recent_topic#?"
    - "What are the implications of [[#note#]]?"
    - "Can you provide an example of [[#note#]]?"

  note:
    - "$vault.sample_notes(1)"

  recent_topic:
    - "$vault.recent_notes(1)"

count: 2
```

### 14. Magician (Pattern-tag prompts)
**Effort**: 10 minutes
**Approach**: Tag filtering + Tracery
```yaml
type: geist-tracery
id: magician
description: Targeted prompts for notes tagged /pattern

tracery:
  origin:
    - "How does the pattern in [[#pattern_note#]] apply to [[#other_note#]]?"
    - "What breaks the pattern in [[#pattern_note#]]?"
    - "Where else might you see the pattern from [[#pattern_note#]]?"

  pattern_note:
    - "$vault.notes_with_tag('/pattern', 1)"

  other_note:
    - "$vault.sample_notes(1)"

count: 2
```

Note: Would need to add `notes_with_tag` vault function:
```python
@vault_function("notes_with_tag")
def notes_with_tag(vault: "VaultContext", tag: str, k: int = 1) -> List[str]:
    """Get k notes with a specific tag."""
    tagged = [n for n in vault.notes() if tag in n.tags]
    sampled = vault.sample(tagged, min(k, len(tagged)))
    return [note.title for note in sampled]
```

### 15. Naturalist (Nature analogy prompts)
**Effort**: 5 minutes
**Approach**: Pure Tracery geist
```yaml
type: geist-tracery
id: naturalist
description: Nature analogy prompts

tracery:
  origin:
    - "[[#note#]] is like #nature_thing# because #reason#"
    - "If [[#note#]] were a #nature_system#, it would #behavior#"
    - "The #nature_pattern# in [[#note#]] suggests #insight#"

  note:
    - "$vault.sample_notes(1)"

  nature_thing:
    - "a forest ecosystem"
    - "a river delta"
    - "mycelium networks"
    - "coral reefs"
    - "ant colonies"
    - "bird migration patterns"

  reason:
    - "both grow through connection"
    - "both adapt over time"
    - "both create emergent complexity"
    - "both follow simple rules that create rich behavior"

  nature_system:
    - "tree"
    - "watershed"
    - "organism"
    - "season"

  behavior:
    - "grow toward light"
    - "branch and merge"
    - "lie dormant then bloom"

  nature_pattern:
    - "branching"
    - "cycles"
    - "symbiosis"
    - "succession"

  insight:
    - "everything is connected"
    - "growth isn't linear"
    - "systems co-evolve"

count: 2
```

### 16. Tarot Geist (Tarot spreads as templates)
**Effort**: 15 minutes
**Approach**: Tracery with spread patterns
```yaml
type: geist-tracery
id: tarot
description: Use tarot spreads as templates for note interpretation

tracery:
  origin:
    - "#three_card_spread#"
    - "#celtic_cross_mini#"
    - "#past_present_future#"

  three_card_spread:
    - "Current situation: [[#note1#]]. Challenge: [[#note2#]]. Outcome: [[#note3#]]"
    - "Mind: [[#note1#]]. Body: [[#note2#]]. Spirit: [[#note3#]]"
    - "Thesis: [[#note1#]]. Antithesis: [[#note2#]]. Synthesis: [[#note3#]]"

  celtic_cross_mini:
    - "You: [[#note1#]]. What crosses you: [[#note2#]]. Foundation: [[#old#]]. Path forward: [[#stub#]]"

  past_present_future:
    - "Past: [[#old#]]. Present: [[#recent#]]. Future: [[#stub#]]"

  note1:
    - "$vault.sample_notes(1)"
  note2:
    - "$vault.sample_notes(1)"
  note3:
    - "$vault.sample_notes(1)"
  old:
    - "$vault.sample_old_notes(1, 10)"
  recent:
    - "$vault.sample_recent_notes(1, 10)"
  stub:
    - "$vault.stubs(1)"

count: 1
```

Would need to add `stubs` vault function:
```python
@vault_function("stubs")
def stubs(vault: "VaultContext", k: int = 5) -> List[str]:
    """Get k stub notes (short/incomplete notes)."""
    stub_notes = [n for n in vault.notes() if len(n.content) < 200]
    sampled = vault.sample(stub_notes, min(k, len(stub_notes)))
    return [note.title for note in sampled]
```

### 17. Spaced Repetition (Resurface scheduling)
**Effort**: 15 minutes
**Approach**: Code geist with interval-based scheduling
```python
from datetime import datetime, timedelta
from geistfabrik.models import Suggestion
from geistfabrik.vault_context import VaultContext

def suggest(vault: VaultContext) -> List[Suggestion]:
    """Surface notes due for review based on spaced repetition intervals."""

    # Standard spaced repetition intervals (days)
    intervals = [1, 3, 7, 14, 30, 90, 180, 365]

    now = vault.session.date
    candidates = []

    for note in vault.notes():
        days_since_modified = (now - note.modified).days

        # Check if note age matches any interval (±1 day tolerance)
        for interval in intervals:
            if abs(days_since_modified - interval) <= 1:
                candidates.append(note)
                break

    if not candidates:
        return []

    # Sample from candidates
    selected = vault.sample(candidates, min(3, len(candidates)))

    return [
        Suggestion(
            text=f"Time to revisit [[{note.title}]] (last modified {(now - note.modified).days} days ago)",
            notes=[note.title],
            geist_id="spaced_repetition"
        )
        for note in selected
    ]
```

## Architectural Compatibility

All geist ideas from Subconscious are compatible with GeistFabrik's architecture because we have:

### Core Capabilities
- ✅ **Semantic search** - sentence-transformers embeddings (384 dimensions)
- ✅ **Temporal tracking** - Note creation/modification dates, temporal embeddings (3 dimensions)
- ✅ **Graph operations** - SQLite-backed link tables, backlinks, hubs, orphans
- ✅ **Tag filtering** - Full tag extraction and querying
- ✅ **Metadata system** - Extensible metadata inference modules
- ✅ **Tracery grammars** - Declarative template-based geists
- ✅ **Sampling utilities** - Deterministic randomness via `VaultContext.rng`

### Design Principles
- ✅ **"Sample, don't rank"** - More flexible than deterministic ranking
  - Can implement weighted sampling while avoiding preferential attachment
  - Maintains variety and serendipity
- ✅ **Extensibility at every layer** - Metadata, functions, geists all user-extensible
- ✅ **Deterministic randomness** - Same seed = same suggestions (reproducible)
- ✅ **Read-only vault access** - Never destructive

### Implementation Patterns

**Code Geists** (Python):
- Full access to VaultContext
- Can implement complex logic
- Timeout handling (5 seconds default)
- Return `List[Suggestion]`

**Tracery Geists** (YAML):
- Declarative templates
- Call vault functions via `$vault.function_name(args)`
- Compose with grammar rules
- Best for creative/variative suggestions

**Metadata Inference**:
- Add new properties to notes
- Export `infer(note, vault) -> Dict`
- Properties flow through VaultContext

**Vault Functions**:
- Bridge between Tracery and VaultContext
- Decorated with `@vault_function("name")`
- Return strings or lists for Tracery consumption

## Philosophical Alignment

GeistFabrik's design actually **exceeds** Subconscious's geist concept in several ways:

1. **Temporal embeddings** - Track how understanding evolves over time, not just content changes
2. **Deterministic randomness** - Same date + vault = same suggestions (reproducible serendipity)
3. **Three-dimensional extensibility** - Metadata, functions, AND geists are all extensible
4. **"Sample, don't rank"** - Avoids preferential attachment while maintaining variety

The architecture treats geists as **muses, not oracles** - provocative rather than prescriptive, asking "What if...?" rather than "Here's how."

## Next Steps

If implementing the missing geists:

1. **Quick wins** (5 min each):
   - Oracle (tag filtering)
   - Naturalist (pure Tracery)
   - The Star (already have logic)

2. **Medium effort** (10-15 min each):
   - Sage (metadata + sampling)
   - Farmer (Tracery + questions)
   - Magician (new vault function)
   - Tarot (Tracery spreads)
   - Spaced Repetition (code geist)

3. **Infrastructure** (one-time, 5 min):
   - Add `notes_with_tag()` vault function
   - Add `stubs()` vault function
   - Add quote detection metadata inference

All implementations would follow existing patterns and require no architectural changes.

## References

- **Source**: https://github.com/subconsciousnetwork/subconscious/wiki/Geist-ideas
- **GeistFabrik Spec**: `specs/geistfabrik_spec.md`
- **Example Geists**: `examples/geists/`
- **Architecture**: See `CLAUDE.md` for project overview
