# Circular Dependencies Analysis - GeistFabrik

**Date**: 2025-11-10
**Status**: Current Codebase Analysis + Proposed Solutions

---

## Executive Summary

Analysis of GeistFabrik's dependency graph reveals **3 circular dependencies**:

1. ✅ **ClusterAnalyser ↔ stats.py** - Being resolved via `cluster_labeling` extraction
2. ⚠️ **VaultContext ↔ metadata_system** - Currently mitigated with TYPE_CHECKING
3. ⚠️ **VaultContext ↔ function_registry** - Currently mitigated with TYPE_CHECKING

**Verdict**: Two existing circular dependencies use TYPE_CHECKING to avoid runtime issues, but represent architectural coupling. One future circular dependency is being resolved during abstraction implementation.

---

## Dependency Graph

### Full Dependency Map

```
vault_context → vault, metadata_system, stats, models, config,
                function_registry, embeddings

vault → config_loader, date_collection, markdown_parser, models, schema

embeddings → config, models, vector_search

filtering → config, embeddings, models

function_registry → vault_context (TYPE_CHECKING)

geist_executor → models, vault_context

journal_writer → models

metadata_system → models, vault_context (TYPE_CHECKING)

stats → config_loader, embeddings

tracery → models, vault_context
```

### Dependency Depth from VaultContext

```
Level 0: vault_context
Level 1: vault, metadata_system, stats, models, config,
         function_registry, embeddings
Level 2: markdown_parser, config_loader, date_collection,
         schema, vector_search
```

---

## Circular Dependency #1: ClusterAnalyser ↔ stats.py

### Problem (Future)

When implementing ClusterAnalyser abstraction:

```
ClusterAnalyser ──[needs labeling]──> stats.EmbeddingMetricsComputer
stats.py        ──[needs clustering]──> ClusterAnalyser
```

### Current State

```
VaultContext.get_clusters()
    ├─→ Runs HDBSCAN directly (duplication)
    └─→ Imports stats.EmbeddingMetricsComputer for labeling

stats.EmbeddingMetricsComputer
    └─→ Runs HDBSCAN directly (duplication)
```

**Issue**: Both VaultContext and stats.py run HDBSCAN independently. No circular dependency yet, but refactoring to ClusterAnalyser would create one.

### Solution: Extract Labeling to Shared Module ✅

**Architecture**:

```
cluster_labeling.py          ← Shared, stateless functions
        ↑
        ├──────────┬──────────────┐
        │          │              │
ClusterAnalyser    stats.py       VaultContext
(clustering)       (metrics)
```

**Implementation**:
1. Extract `_label_clusters_tfidf()`, `_label_clusters_keybert()`, `_apply_mmr_filtering()` from stats.py
2. Create `cluster_labeling.py` with stateless functions
3. ClusterAnalyser imports cluster_labeling for labeling
4. stats.py imports ClusterAnalyser for clustering
5. stats.py imports cluster_labeling if needed for standalone labeling

**Benefits**:
- ✅ No circular dependency
- ✅ Single source of truth for clustering (ClusterAnalyser)
- ✅ Single source of truth for labeling (cluster_labeling)
- ✅ Both stats.py and ClusterAnalyser can use labeling independently

**Status**: **Being resolved** in reuse abstractions spec (Phase 3)

---

## Circular Dependency #2: VaultContext ↔ metadata_system

### The Cycle

```python
# vault_context.py
from .metadata_system import MetadataLoader  # Runtime import

# metadata_system.py
if TYPE_CHECKING:
    from .vault_context import VaultContext  # Type-only import
```

**Cycle**: VaultContext → metadata_system → VaultContext

### Current Mitigation

Uses `TYPE_CHECKING` to avoid runtime circular import:

```python
# metadata_system.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vault_context import VaultContext

class MetadataLoader:
    def infer_all(self, note: Note, vault: "VaultContext") -> Tuple[Dict, List]:
        #                                ^^^^^^^^^^^^^^^^^
        # String annotation, not runtime import
```

**How it works**:
- `TYPE_CHECKING` is `False` at runtime, `True` during type checking
- Import only happens during static analysis (mypy, IDE)
- At runtime, `"VaultContext"` is a string, not actual class reference
- No runtime circular import

### Architectural Issue

**Problem**: Tight coupling between VaultContext and metadata_system.

**Why the dependency exists**:
- VaultContext needs MetadataLoader to manage metadata modules
- MetadataLoader needs VaultContext type hint for `infer(note, vault)` signature

### Solution Options

#### Option A: Keep TYPE_CHECKING (Current) ✅

**Pros**:
- Already implemented
- No runtime issues
- Works with type checkers

**Cons**:
- Still represents architectural coupling
- TYPE_CHECKING is a workaround, not a solution

#### Option B: Dependency Inversion

Extract shared interface:

```python
# metadata_protocol.py
from typing import Protocol, Dict, Any

class VaultReader(Protocol):
    """Minimal interface for metadata inference."""
    def get_note(self, path: str) -> Note: ...
    def notes(self) -> List[Note]: ...
    # Only methods needed by metadata modules

# metadata_system.py
from .metadata_protocol import VaultReader

class MetadataLoader:
    def infer_all(self, note: Note, vault: VaultReader) -> Tuple[Dict, List]:
        #                                ^^^^^^^^^^^
        # Protocol, not concrete class
```

**Pros**:
- ✅ No circular dependency (Protocol doesn't import VaultContext)
- ✅ Clearer interface segregation
- ✅ Better testability (can mock VaultReader)

**Cons**:
- More complex architecture
- Requires refactoring metadata modules

#### Option C: Pass Database Instead of VaultContext

```python
# metadata_system.py
class MetadataLoader:
    def infer_all(self, note: Note, db: sqlite3.Connection,
                  config: Config) -> Tuple[Dict, List]:
        # Metadata modules only need DB + config, not full VaultContext
```

**Pros**:
- ✅ No VaultContext dependency
- ✅ Clearer about what metadata modules can access

**Cons**:
- Breaks existing metadata module API
- Less convenient for custom metadata modules

### Recommendation

**Keep current TYPE_CHECKING approach** for now. It works correctly and the coupling is reasonable (VaultContext is the execution context for metadata inference).

Consider Protocol-based dependency inversion if:
- Need to test metadata system independently
- Want to use metadata system in contexts other than VaultContext
- Adding many more dependencies between the two

**Status**: **Acceptable as-is** (TYPE_CHECKING mitigation sufficient)

---

## Circular Dependency #3: VaultContext ↔ function_registry

### The Cycle

```python
# vault_context.py
from .function_registry import FunctionRegistry  # Runtime import

# function_registry.py
if TYPE_CHECKING:
    from .vault_context import VaultContext  # Type-only import
```

**Cycle**: VaultContext → function_registry → VaultContext

### Current Mitigation

Uses `TYPE_CHECKING` (same pattern as metadata_system):

```python
# function_registry.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vault_context import VaultContext

class FunctionRegistry:
    def call(self, name: str, vault: "VaultContext", *args, **kwargs) -> Any:
        #                            ^^^^^^^^^^^^^^^^^
        # String annotation
```

### Architectural Issue

**Problem**: Tight coupling between VaultContext and function_registry.

**Why the dependency exists**:
- VaultContext creates and holds FunctionRegistry instance
- FunctionRegistry needs VaultContext type hint for `@vault_function` decorated functions
- Vault functions take `vault: VaultContext` as first parameter

### Solution Options

#### Option A: Keep TYPE_CHECKING (Current) ✅

Same as metadata_system. Works correctly.

#### Option B: Dependency Inversion with Protocol

```python
# vault_protocol.py
class VaultOperations(Protocol):
    """Minimal interface for vault functions."""
    def notes(self) -> List[Note]: ...
    def similarity(self, a: Note, b: Note) -> float: ...
    def neighbours(self, note: Note, k: int) -> List[Note]: ...
    # Only methods exposed to vault functions

# function_registry.py
from .vault_protocol import VaultOperations

class FunctionRegistry:
    def call(self, name: str, vault: VaultOperations, *args, **kwargs) -> Any:
        #                            ^^^^^^^^^^^^^^^
```

**Pros**:
- ✅ No circular dependency
- ✅ Explicit about what functions can access
- ✅ Prevents vault functions from accessing internal VaultContext state

**Cons**:
- Breaks existing vault functions API
- All custom vault functions need updating

#### Option C: Generic Type Variable

```python
# function_registry.py
from typing import TypeVar, Generic

VaultType = TypeVar('VaultType')

class FunctionRegistry(Generic[VaultType]):
    def call(self, name: str, vault: VaultType, *args, **kwargs) -> Any:
        # Generic vault type, no import needed
```

**Pros**:
- ✅ No circular dependency
- ✅ Works with any vault type

**Cons**:
- Less type safety (any type accepted)
- More complex type annotations

### Recommendation

**Keep current TYPE_CHECKING approach** for now. The coupling is fundamental to how vault functions work - they need access to VaultContext.

Consider Protocol-based approach if:
- Want to restrict what vault functions can access
- Need stronger API boundaries
- Want to version the vault function API separately

**Status**: **Acceptable as-is** (TYPE_CHECKING mitigation sufficient)

---

## Other Potential Issues

### Not Circular, But Watch For

#### 1. Deep Dependency Chain

```
vault_context → embeddings → vector_search
vault_context → vault → markdown_parser
```

**Not circular**, but changes to low-level modules (vector_search, markdown_parser) ripple up.

**Mitigation**: These are stable foundational modules, rarely change.

#### 2. Many Modules Depend on vault_context

```
function_registry → vault_context
metadata_system → vault_context
geist_executor → vault_context
tracery → vault_context
```

**Not circular** (one-way dependencies), but VaultContext is a hub.

**Why this is okay**:
- VaultContext is designed as execution context
- It's the interface between vault data and geist execution
- Hub pattern is intentional architecture

#### 3. stats.py Imports Nothing Internal

```
stats.py → config_loader, embeddings
```

**Good**: stats.py is relatively independent. Only external dependencies are for configuration and embeddings.

**After refactoring**: stats.py will import ClusterAnalyser, but no circular dependency (ClusterAnalyser won't import stats).

---

## Summary of Findings

| Dependency | Type | Severity | Mitigation | Status |
|------------|------|----------|------------|--------|
| **ClusterAnalyser ↔ stats.py** | Future | 🔴 High | Extract labeling to shared module | ✅ Being resolved |
| **VaultContext ↔ metadata_system** | Current | 🟡 Medium | TYPE_CHECKING | ✅ Acceptable |
| **VaultContext ↔ function_registry** | Current | 🟡 Medium | TYPE_CHECKING | ✅ Acceptable |
| **VaultContext as hub** | Design | 🟢 Low | Intentional architecture | ✅ By design |

---

## Recommendations

### Immediate Actions

1. ✅ **Proceed with cluster_labeling extraction** (Phase 3 of reuse abstractions)
   - Prevents future circular dependency
   - Improves modularity

2. ✅ **Keep TYPE_CHECKING mitigations** for metadata_system and function_registry
   - Works correctly
   - No runtime issues
   - Coupling is acceptable for these use cases

### Future Considerations

3. **Consider Protocol-based dependency inversion** if:
   - Need stronger API boundaries
   - Want to test modules independently
   - Add more dependencies between VaultContext and other modules

4. **Monitor VaultContext complexity**
   - It's a hub by design, but could become bloated
   - Consider splitting if it grows beyond ~1000 lines
   - New abstractions (clustering, temporal, etc.) help keep it focused

### Not Recommended

- ❌ Don't refactor existing TYPE_CHECKING patterns unless causing issues
- ❌ Don't create Protocol wrappers prematurely
- ❌ Don't split VaultContext just to reduce dependencies (it's a hub by design)

---

## Testing for Circular Dependencies

Use this script to detect circular dependencies:

```bash
python3 << 'EOF'
import os, re
from collections import defaultdict, deque

deps = defaultdict(set)
src_dir = 'src/geistfabrik'

def extract_imports(filepath):
    imports = set()
    with open(filepath) as f:
        for line in f:
            # from .module import ...
            m = re.match(r'^\s*from\s+\.(\w+)\s+import', line)
            if m:
                imports.add(m.group(1))
    return imports

for f in os.listdir(src_dir):
    if f.endswith('.py') and f != '__init__.py':
        mod = f[:-3]
        filepath = os.path.join(src_dir, f)
        deps[mod] = extract_imports(filepath)

def find_cycles(graph):
    cycles = []
    visited, rec_stack = set(), []

    def dfs(node):
        if node in rec_stack:
            idx = rec_stack.index(node)
            cycles.append(rec_stack[idx:] + [node])
            return
        if node in visited:
            return
        visited.add(node)
        rec_stack.append(node)
        for neighbor in graph.get(node, []):
            dfs(neighbor)
        rec_stack.pop()

    for node in graph:
        dfs(node)
    return cycles

cycles = find_cycles(deps)
if cycles:
    print("CIRCULAR DEPENDENCIES FOUND:")
    for cycle in cycles:
        print(f"  {' → '.join(cycle)}")
else:
    print("No circular dependencies!")
EOF
```

**Run this script**:
- Before major refactorings
- After adding new modules
- During code review

---

## Conclusion

GeistFabrik has **2 existing circular dependencies** that are properly mitigated with TYPE_CHECKING, and **1 future circular dependency** being resolved through extraction of shared labeling module.

**Overall dependency health**: ✅ **GOOD**

- No runtime circular imports
- TYPE_CHECKING used correctly
- Future issue being proactively addressed
- Dependency graph is relatively clean and intentional

**Next steps**: Proceed with cluster_labeling extraction as planned in Phase 3 of reuse abstractions implementation.
