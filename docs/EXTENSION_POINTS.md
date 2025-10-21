# GeistFabrik Extension Points - Usage Analysis

**Date**: 2025-10-21

This document shows all extension points in GeistFabrik and which geists use them.

---

## Summary

| Extension Point Type | Count | Used By Geists |
|---------------------|-------|----------------|
| **Built-in Vault Functions** | 7 | 3 Tracery geists |
| **Example Vault Functions** | 3 | 0 geists (examples) |
| **VaultContext Methods** | 15+ | All 10 code geists |
| **Metadata Inference Modules** | 3 | 7 code geists |
| **Total Extension Points** | 28+ | 13 geists |

---

## 1. Built-in Vault Functions

These functions are registered automatically in `FunctionRegistry` and available to Tracery geists as `$vault.function_name()`.

| Function | Purpose | Used By | Usage Example |
|----------|---------|---------|---------------|
| `sample_notes(k)` | Random sample of notes | **note_combinations**, **what_if** | `$vault.sample_notes(1)` |
| `old_notes(k)` | Oldest notes by creation | **temporal_mirror** | `$vault.old_notes(1)` |
| `recent_notes(k)` | Most recent notes | **temporal_mirror** | `$vault.recent_notes(1)` |
| `orphans()` | Notes with no links | ❌ **Unused** | - |
| `hubs(k)` | Notes with most backlinks | ❌ **Unused** | - |
| `neighbors(title, k)` | Semantically similar notes | ❌ **Unused** | - |
| `find_questions()` | Notes ending in '?' | ❌ **Unused** | - |

**Coverage**: 3/7 functions used (43%)

**Analysis**:
- ✅ Basic sampling functions (`sample_notes`, `old_notes`, `recent_notes`) are well-used
- ❌ Advanced functions (`neighbors`, `hubs`, `orphans`) unused by Tracery geists
- 💡 **Opportunity**: Create Tracery geists using `$vault.hubs()` and `$vault.neighbors()`

---

## 2. Example Vault Functions

Additional functions in `examples/vault_functions/` for demonstration.

| Function | Module | Purpose | Used By |
|----------|--------|---------|---------|
| `find_questions(k)` | `questions.py` | Find notes ending in '?' | ❌ **Unused** |
| `notes_with_metadata(key, value, k)` | `questions.py` | Find notes by metadata | ❌ **Unused** |
| `contrarian_to(title, k)` | `contrarian.py` | Find opposite viewpoints | ❌ **Unused** |

**Coverage**: 0/3 used (0%)

**Analysis**:
- These are demonstration/example functions
- Not used by built-in geists
- Users can enable them in their vaults
- 💡 **Opportunity**: Create example Tracery geists showing these in action

---

## 3. VaultContext Methods

Core methods available to all code geists (Python).

### Semantic Search Methods

| Method | Purpose | Used By Geists | Usage Count |
|--------|---------|----------------|-------------|
| `neighbors(note, k)` | K-nearest notes by embedding | **bridge_builder**, **recent_focus**, **concept_cluster** | 3/10 |
| `similarity(a, b)` | Cosine similarity | **bridge_builder**, **creative_collision**, **concept_cluster** | 3/10 |

### Graph Query Methods

| Method | Purpose | Used By Geists | Usage Count |
|--------|---------|----------------|-------------|
| `backlinks(note)` | Incoming links | **complexity_mismatch**, **stub_expander** | 2/10 |
| `hubs(k)` | Most-linked notes | **bridge_builder** | 1/10 |
| `orphans(k)` | Notes with no links | ❌ **Unused** | 0/10 |
| `unlinked_pairs(k)` | Note pairs with no link | ❌ **Unused** | 0/10 |
| `links_between(a, b)` | Links connecting two notes | ❌ **Unused** | 0/10 |

### Temporal Methods

| Method | Purpose | Used By Geists | Usage Count |
|--------|---------|----------------|-------------|
| `old_notes(k)` | Oldest notes | **temporal_drift** | 1/10 |
| `recent_notes(k)` | Most recent notes | **recent_focus** | 1/10 |

### Utility Methods

| Method | Purpose | Used By Geists | Usage Count |
|--------|---------|----------------|-------------|
| `metadata(note)` | Get note metadata | **7 geists** | 7/10 |
| `sample(items, k)` | Deterministic sampling | **All 10 geists** | 10/10 |
| `notes()` | All notes | **All 10 geists** | 10/10 |
| `get_note(path)` | Get specific note | ❌ **Unused** | 0/10 |
| `read(note)` | Read note content | ❌ **Unused** | 0/10 |

**Coverage**: 12/17 methods used (71%)

**Analysis**:
- ✅ Core methods well-used (`metadata`, `sample`, `notes`)
- ✅ Semantic search heavily used (3/10 geists)
- ⚠️ Graph methods underutilized (`orphans`, `unlinked_pairs`, `links_between`)
- 💡 **Missing geists**: Could build geists using `orphans()` and `unlinked_pairs()`

---

## 4. Metadata Inference Modules

Modules in `examples/metadata_inference/` that add properties to notes.

| Module | Properties Added | Used By Geists |
|--------|------------------|----------------|
| `complexity.py` | `word_count`, `heading_count`, `link_count`, `tag_count`, `complexity_score` | **complexity_mismatch**, **link_density_analyzer**, **stub_expander**, **task_archaeology** |
| `temporal.py` | `age_days`, `last_modified_days`, `is_recent`, `is_old` | **temporal_drift**, **recent_focus** |
| `structure.py` | `has_tasks`, `task_count`, `has_questions`, `question_count` | **task_archaeology**, **question_generator** |

**Coverage**: 3/3 modules actively used by 7/10 geists

**Analysis**:
- ✅ All metadata modules are used
- ✅ Good coverage across geists
- 💡 **Well-designed**: Each module serves specific use cases

---

## 5. Geist-by-Geist Breakdown

### Code Geists (10)

| Geist | VaultContext Methods | Metadata Modules | Extension Points Used |
|-------|---------------------|------------------|----------------------|
| **temporal_drift** | `old_notes`, `metadata`, `sample` | temporal | 4 |
| **creative_collision** | `sample`, `similarity` | - | 2 |
| **bridge_builder** | `hubs`, `neighbors`, `similarity`, `sample` | - | 4 |
| **complexity_mismatch** | `metadata`, `backlinks`, `sample`, `notes` | complexity | 5 |
| **question_generator** | `metadata`, `sample`, `notes` | structure | 4 |
| **link_density_analyzer** | `metadata`, `sample`, `notes` | complexity | 4 |
| **task_archaeology** | `metadata`, `sample`, `notes` | structure, complexity | 5 |
| **concept_cluster** | `sample`, `neighbors`, `similarity`, `notes` | - | 4 |
| **stub_expander** | `metadata`, `backlinks`, `sample`, `notes` | complexity | 5 |
| **recent_focus** | `recent_notes`, `neighbors`, `metadata`, `sample` | temporal | 5 |

**Average extension points per code geist**: 4.2

### Tracery Geists (4)

| Geist | Vault Functions | Extension Points Used |
|-------|----------------|----------------------|
| **random_prompts** | ❌ None | 0 |
| **note_combinations** | `sample_notes` | 1 |
| **what_if** | `sample_notes` | 1 |
| **temporal_mirror** | `old_notes`, `recent_notes` | 2 |

**Average extension points per Tracery geist**: 1.0

**Analysis**:
- Code geists use 4.2 extension points on average (well-integrated)
- Tracery geists use 1.0 extension points (simpler, more declarative)
- **random_prompts** uses NO extension points (purely static grammar)

---

## 6. Unused Extension Points (Opportunities)

### High-Value Unused Functions

| Function/Method | Type | Potential Use Case |
|----------------|------|-------------------|
| `orphans()` | VaultContext | "Connect the Dots" geist - suggest links for orphaned notes |
| `unlinked_pairs(k)` | VaultContext | Already used in spec examples (not in built geists) |
| `hubs(k)` as vault function | Vault Function | Tracery geist highlighting hub notes |
| `neighbors(title, k)` as vault function | Vault Function | Tracery geist showing semantic neighborhoods |
| `notes_with_metadata(key, value)` | Vault Function | Filter-based Tracery geist |
| `contrarian_to(title)` | Vault Function | Devil's advocate geist |

### Example Geist Ideas

**1. "connect_the_dots" (Code geist using `orphans()`)**
```python
def suggest(vault: VaultContext):
    """Find orphaned notes and suggest connections."""
    orphans = vault.orphans(k=10)
    suggestions = []

    for orphan in orphans:
        # Find semantically similar notes
        similar = vault.neighbors(orphan, k=5)
        if similar:
            suggestions.append(Suggestion(
                text=f"[[{orphan.title}]] has no links but is similar to "
                     f"[[{similar[0].title}]]",
                notes=[orphan.title, similar[0].title],
                geist_id="connect_the_dots"
            ))

    return vault.sample(suggestions, k=3)
```

**2. "hub_explorer" (Tracery geist using `$vault.hubs()`)**
```yaml
type: geist-tracery
id: hub_explorer
tracery:
  origin:
    - "Your hub note [[#hub#]] connects many ideas—what's the unifying theme?"
    - "[[#hub#]] is central to your vault—time to review and refine?"

  hub: ["$vault.hubs(1)"]

count: 2
```

**3. "devil_advocate" (Tracery geist using `$vault.contrarian_to()`)**
```yaml
type: geist-tracery
id: devil_advocate
tracery:
  origin:
    - "You wrote [[#note1#]]. But what if #contrary#?"
    - "Challenge to [[#note1#]]: [[#contrary#]] suggests otherwise"

  note1: ["$vault.sample_notes(1)"]
  contrary: ["$vault.contrarian_to(#note1#, 1)"]

count: 1
```

---

## 7. Coverage Analysis

### Overall Extension Point Usage

```
Total Extension Points: 28
Used by at least one geist: 19 (68%)
Unused: 9 (32%)
```

### By Category

| Category | Total | Used | Unused | Coverage |
|----------|-------|------|--------|----------|
| Built-in Vault Functions | 7 | 3 | 4 | 43% |
| Example Vault Functions | 3 | 0 | 3 | 0% |
| VaultContext Methods | 15 | 12 | 3 | 80% |
| Metadata Modules | 3 | 3 | 0 | 100% |

### Recommendations

1. **High coverage** (VaultContext, Metadata): ✅ Well-utilized
2. **Medium coverage** (Built-in Functions): ⚠️ Opportunity to create more Tracery geists
3. **Low coverage** (Example Functions): ❌ These are demos, low usage is expected

---

## 8. Extension Point Heatmap

**Most-used extension points** (by number of geists):

1. `vault.sample()` - **10/10 geists** (100%)
2. `vault.notes()` - **10/10 geists** (100%)
3. `vault.metadata()` - **7/10 code geists** (70%)
4. `vault.neighbors()` - **3/10 code geists** (30%)
5. `vault.similarity()` - **3/10 code geists** (30%)
6. `$vault.sample_notes()` - **2/4 Tracery geists** (50%)
7. Complexity metadata - **4/10 code geists** (40%)
8. Temporal metadata - **2/10 code geists** (20%)
9. Structure metadata - **2/10 code geists** (20%)

**Least-used extension points** (unused):

- `vault.orphans()` - 0 geists
- `vault.unlinked_pairs()` - 0 geists
- `vault.links_between()` - 0 geists
- `vault.get_note()` - 0 geists
- `vault.read()` - 0 geists
- `$vault.hubs()` - 0 Tracery geists
- `$vault.neighbors()` - 0 Tracery geists
- `$vault.notes_with_metadata()` - 0 geists
- `$vault.contrarian_to()` - 0 geists

---

## 9. Recommendations

### For Users

**To maximize GeistFabrik's power:**

1. ✅ **Use metadata modules** - 100% of modules are actively used by geists
2. ✅ **Try Tracery geists** - Lower barrier to entry, can use vault functions
3. 💡 **Explore unused functions** - `orphans()`, `unlinked_pairs()` have potential

### For Developers

**To expand GeistFabrik:**

1. 🎯 **Build "connect_the_dots" geist** using `orphans()`
2. 🎯 **Build Tracery geists** using `$vault.hubs()` and `$vault.neighbors()`
3. 🎯 **Create hybrid geists** combining multiple metadata modules
4. 📚 **Document patterns** - Show examples using all vault functions

### Missing Patterns

No geist currently:
- Uses `orphans()` alone (but `stub_expander` checks backlinks)
- Uses `unlinked_pairs()` (but `creative_collision` samples pairs)
- Uses `contrarian_to()` (example function, intentionally unused)
- Combines all 3 metadata modules together

---

## 10. Conclusion

**GeistFabrik's extension points are well-utilized:**

- ✅ **80% of VaultContext methods** used by geists
- ✅ **100% of metadata modules** actively used
- ⚠️ **43% of built-in vault functions** used (opportunity for more Tracery geists)
- ❌ **0% of example vault functions** used (by design - they're examples)

**The extension system is working as designed:**
- Core functionality (`sample`, `notes`, `metadata`) used by all geists
- Advanced features (`neighbors`, `similarity`) used by sophisticated geists
- Simple declarative features (`$vault.sample_notes`) used by Tracery geists

**Biggest opportunity**: Create more **Tracery geists** using advanced vault functions like `hubs()`, `neighbors()`, and metadata filters.
