# Tracery Vault Function Pre-Population Specification

## Problem Statement

GeistFabrik's Tracery implementation currently evaluates `$vault.*` function calls **during expansion**, which violates idiomatic Tracery behavior. This causes geists with `count > 1` to generate duplicate suggestions when vault functions return deterministic results.

### Current (Incorrect) Behavior

```yaml
# hub_explorer.yaml
hub: ["$vault.hubs(1)"]
count: 2
origin: "[[#hub#]] is central to your vault..."
```

**What happens now:**
1. Tracery expansion begins
2. First suggestion: expand `#hub#` → inline evaluate `$vault.hubs(1)` → "Gordon Brander"
3. Second suggestion: expand `#hub#` → inline evaluate `$vault.hubs(1)` → "Gordon Brander"
4. Result: Both suggestions reference the same hub

**Why this is wrong:**
- `$vault.hubs(1)` is evaluated twice, returning the same deterministic result
- The `hub` symbol is an array with one element: the literal string `"$vault.hubs(1)"`
- No variation possible across multiple expansions

### Correct (Idiomatic Tracery) Behavior

In standard Tracery, symbols are **pre-populated arrays** that each expansion independently samples from.

```python
# Standard Tracery
grammar = {
    'animal': ['cat', 'dog', 'bird'],
    'origin': 'I saw a #animal#'
}

# Three expansions sample independently:
flatten('#origin#')  # → "I saw a cat"
flatten('#origin#')  # → "I saw a bird"
flatten('#origin#')  # → "I saw a dog"
```

**Each expansion independently picks from the `animal` array.**

## Proposed Architecture

### Pre-Population Phase (Before Tracery Expansion)

When loading a Tracery geist, detect and execute all `$vault.*` function calls to populate grammar symbols:

**Step 1: Load YAML**
```yaml
hub: ["$vault.hubs(5)"]
```

**Step 2: Detect Vault Functions**
- Pattern match: `$vault.function_name(args)`
- Found in symbol: `hub`

**Step 3: Execute and Expand**
```python
result = vault.hubs(5)
# Returns: ["Gordon Brander", "Evergreen notes", "Tools for thought", "Obsidian", "Minimal Theme"]
```

**Step 4: Replace Symbol Array**
```python
# Original grammar
grammar['hub'] = ["$vault.hubs(5)"]

# After pre-population
grammar['hub'] = ["Gordon Brander", "Evergreen notes", "Tools for thought", "Obsidian", "Minimal Theme"]
```

**Step 5: Tracery Expansion Proceeds**
- `#hub#` now randomly samples from 5 pre-populated options
- Each expansion can return different hub

### Multiple Vault Functions in One Symbol

Vault functions can be mixed with static options:

```yaml
note:
  - "$vault.sample_notes(3)"
  - "$vault.recent_notes(2)"
  - "a note you haven't written yet"
```

**After pre-population:**
```yaml
note:
  - "Note A"
  - "Note B"
  - "Note C"
  - "Yesterday's thought"
  - "This morning's insight"
  - "a note you haven't written yet"
```

Symbol `note` now has 6 options (3 + 2 + 1).

### Multiple Vault Functions with Arguments

```yaml
tagged_note:
  - "$vault.tagged('project', 2)"
  - "$vault.tagged('idea', 2)"
```

**After pre-population:**
```yaml
tagged_note:
  - "Project X"
  - "Project Y"
  - "Random Idea"
  - "Half-baked Thought"
```

## Implementation Changes

### Current Implementation (tracery.py:350-387)

```python
def _expand_vault_functions(self, text: str) -> str:
    """Expand $vault.* function calls during text expansion"""
    # This happens DURING expansion, not before
    pattern = r"\$vault\.([a-z_]+)\(([^)]*)\)"

    def replace_function(match: re.Match[str]) -> str:
        # Called inline during each expansion
        result = self.vault_context.call_function(func_name, *args)
        return self._format_list(result)

    return re.sub(pattern, replace_function, text)
```

**Problem:** Functions execute during expansion, returning formatted strings, not populating symbol arrays.

### Proposed Implementation

```python
class TraceryEngine:
    def __init__(self, grammar: Dict[str, List[str]], seed: int | None = None):
        self.grammar = grammar
        self.rng = random.Random(seed)
        self.vault_context: VaultContext | None = None
        self.max_depth = 50
        self.modifiers = self._default_modifiers()
        self._preprocessed = False  # Track if pre-population done

    def set_vault_context(self, ctx: VaultContext) -> None:
        """Set vault context and pre-populate vault functions."""
        self.vault_context = ctx
        self._preprocess_vault_functions()

    def _preprocess_vault_functions(self) -> None:
        """Execute all $vault.* calls and expand symbol arrays."""
        if self._preprocessed or not self.vault_context:
            return

        pattern = r"\$vault\.([a-z_]+)\(([^)]*)\)"

        for symbol, rules in self.grammar.items():
            expanded_rules = []

            for rule in rules:
                # Check if this rule is a vault function call
                match = re.fullmatch(pattern, rule.strip())

                if match:
                    # Execute vault function
                    func_name = match.group(1)
                    args_str = match.group(2).strip()

                    # Parse arguments
                    args = []
                    if args_str:
                        raw_args = [arg.strip().strip("\"'") for arg in args_str.split(",")]
                        args = [self._convert_arg(arg) for arg in raw_args]

                    # Call function and get results
                    result = self.vault_context.call_function(func_name, *args)

                    # If result is a list, expand into multiple rules
                    if isinstance(result, list):
                        expanded_rules.extend([str(item) for item in result])
                    else:
                        expanded_rules.append(str(result))
                else:
                    # Static rule, keep as-is
                    expanded_rules.append(rule)

            # Replace symbol's rules with expanded version
            self.grammar[symbol] = expanded_rules

        self._preprocessed = True

    def expand(self, text: str, depth: int = 0) -> str:
        """Expand text template - no longer needs vault function handling."""
        if depth > self.max_depth:
            raise RecursionError(f"Tracery expansion exceeded max depth ({self.max_depth})")

        # Find and expand #symbols#
        pattern = r"#([^#]+)#"

        def replace_symbol(match: re.Match[str]) -> str:
            symbol = match.group(1)
            expanded = self._expand_symbol(symbol, depth + 1)
            return expanded

        expanded = re.sub(pattern, replace_symbol, text)

        # No longer need _expand_vault_functions here
        return expanded
```

## Geist Authoring Guidelines

### Requesting Multiple Options

**Bad (no variation possible):**
```yaml
hub: ["$vault.hubs(1)"]
count: 2
```
Both suggestions will reference the same hub.

**Good (variation possible):**
```yaml
hub: ["$vault.hubs(5)"]
count: 2
```
Each suggestion can reference different hubs from the pool of 5.

### Right-Sizing the Pool

**General rule:** Request **2-3x more options than `count`** to ensure variety:

```yaml
# Generating 2 suggestions → request 5 options
count: 2
note: ["$vault.sample_notes(5)"]

# Generating 3 suggestions → request 8 options
count: 3
note: ["$vault.sample_notes(8)"]
```

### When Vault Returns Fewer Items

```yaml
hub: ["$vault.hubs(10)"]
```

If vault only has 3 hubs:
- Function returns: `["Hub A", "Hub B", "Hub C"]`
- Symbol array has 3 options (not 10)
- Suggestions may still repeat if `count > 3`

**This is expected behavior** - geists adapt to vault contents.

### Mixing Vault and Static Options

```yaml
origin: "What if [[#subject#]] were #verb.ed#?"
subject:
  - "$vault.sample_notes(3)"
  - "everything you believe"
  - "the opposite"
verb:
  - "question"
  - "invert"
  - "dissolve"
```

The `subject` symbol will have 5 options (3 dynamic + 2 static).

## Edge Cases

### Empty Results

```yaml
orphan: ["$vault.orphans(5)"]
```

If vault has no orphans:
- Function returns: `[]`
- Symbol array is empty: `orphan: []`
- Expansion of `#orphan#` fails (no options to choose from)
- Tracery expansion fails gracefully
- Geist returns empty suggestion list

**This is correct behavior** - geist only generates suggestions when data exists.

### Single Result

```yaml
oldest: ["$vault.oldest_note()"]
```

Returns: `["My First Note"]`
- Symbol array has 1 option
- All expansions return same note
- But multiple suggestions are still generated with different surrounding text

```yaml
origin:
  - "Your oldest note [[#oldest#]] might hold #insight#"
  - "[[#oldest#]] was written when #context#"
```

Both suggestions reference same oldest note, but with different provocations.

### Function Call in Origin

```yaml
# This should NOT work
origin: "Consider $vault.sample_notes(1)"
```

Vault functions should only appear in **symbol definitions**, not in origin or other templates.

**Why:** Pre-processing only scans symbol arrays, not template text.

**Correct approach:**
```yaml
origin: "Consider [[#note#]]"
note: ["$vault.sample_notes(1)"]
```

## Testing Strategy

### Unit Tests

```python
def test_vault_function_preprocessing():
    """Vault functions should expand symbol arrays before Tracery runs."""
    grammar = {
        'origin': '#note#',
        'note': ['$vault.sample_notes(3)']
    }

    engine = TraceryEngine(grammar, seed=42)

    # Mock vault context
    vault = MockVaultContext()
    vault.register_function('sample_notes', lambda v, k: ['Note A', 'Note B', 'Note C'])

    engine.set_vault_context(vault)

    # Check grammar was pre-populated
    assert engine.grammar['note'] == ['Note A', 'Note B', 'Note C']
    assert '$vault' not in str(engine.grammar)

def test_multiple_expansions_vary():
    """Multiple expansions should sample independently."""
    grammar = {
        'origin': '#note#',
        'note': ['$vault.sample_notes(5)']
    }

    engine = TraceryEngine(grammar, seed=42)

    vault = MockVaultContext()
    vault.register_function('sample_notes',
                           lambda v, k: ['A', 'B', 'C', 'D', 'E'])

    engine.set_vault_context(vault)

    # Generate 10 expansions
    results = [engine.expand('#origin#') for _ in range(10)]

    # Should have variety (not all the same)
    assert len(set(results)) > 1

def test_mixed_static_and_vault():
    """Symbol arrays can mix vault functions and static options."""
    grammar = {
        'origin': '#item#',
        'item': ['$vault.sample_notes(2)', 'static option']
    }

    engine = TraceryEngine(grammar, seed=42)

    vault = MockVaultContext()
    vault.register_function('sample_notes', lambda v, k: ['Note A', 'Note B'])

    engine.set_vault_context(vault)

    # Should have 3 options total
    assert engine.grammar['item'] == ['Note A', 'Note B', 'static option']

def test_empty_vault_result():
    """Empty vault function results should leave symbol empty."""
    grammar = {
        'origin': '#orphan#',
        'orphan': ['$vault.orphans(5)']
    }

    engine = TraceryEngine(grammar, seed=42)

    vault = MockVaultContext()
    vault.register_function('orphans', lambda v, k: [])

    engine.set_vault_context(vault)

    # Symbol should be empty
    assert engine.grammar['orphan'] == []

    # Expansion should fail gracefully
    result = engine.expand('#origin#')
    assert result == '#orphan#'  # Unexpanded
```

### Integration Test

```python
def test_hub_explorer_variety():
    """hub_explorer geist should generate different hubs across suggestions."""
    geist = TraceryGeist.from_yaml('hub_explorer.yaml', seed=42)

    # Create vault with 5 hubs
    vault = create_test_vault_with_hubs(5)

    suggestions = geist.suggest(vault)

    # Should generate 2 suggestions (count: 2)
    assert len(suggestions) == 2

    # Extract referenced notes
    notes = [s.notes for s in suggestions]

    # Should reference different hubs (with high probability)
    # Note: Might occasionally be same due to random sampling
    # Run multiple times or check distribution
```

## Migration Path

### Phase 1: Update TraceryEngine Implementation
- Implement `_preprocess_vault_functions()`
- Call during `set_vault_context()`
- Remove vault function handling from `expand()`

### Phase 2: Update Existing Geists
Audit all default Tracery geists and update function calls:

```bash
# Find geists with count > 1 and vault functions
grep -l "count: [2-9]" src/geistfabrik/default_geists/tracery/*.yaml | \
  xargs grep -l "\$vault"
```

For each, ensure vault functions request enough options:
- If `count: 2`, vault functions should request 4-5 items
- If `count: 3`, vault functions should request 6-8 items

### Phase 3: Update Documentation
- Update `CLAUDE.md` with correct behavior
- Add examples to `tracery_research.md`
- Create user-facing guide for geist authoring

## Benefits

1. **Idiomatic Tracery:** Matches how standard Tracery works
2. **Variation:** Multiple suggestions naturally vary across expansions
3. **Performance:** Vault functions execute once per symbol, not once per expansion
4. **Composability:** Symbols can mix vault and static options freely
5. **Predictability:** Authors understand what `count: N` means

## Open Questions

1. Should we warn if `count > len(symbol_array)` for vault-populated symbols?
2. Should we provide a `$vault.sample_notes(*)` syntax meaning "all notes"?
3. How do we handle vault function errors during pre-population? (Current: fail silently and log)
