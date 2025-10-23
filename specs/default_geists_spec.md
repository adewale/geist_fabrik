# Default Geists Specification

## Overview

GeistFabrik ships with a curated set of default geists bundled in the package. These provide immediate value on first run without requiring users to write their own. Users can enable or disable any default geist via configuration.

## Core Principles

1. **Useful by default** - System generates interesting suggestions out of the box
2. **Easily customizable** - Toggle defaults on/off via config, add your own custom geists
3. **Not prescriptive** - Defaults demonstrate patterns, not mandatory behaviors
4. **Backward compatible** - Custom geists continue working exactly as before

## Architecture

### Package Structure

```
src/geistfabrik/
  default_geists/
    code/
      blind_spot_detector.py
      dialectic_triad.py
      structure_diversity_checker.py
      metadata_driven_discovery.py
      on_this_day.py
    tracery/
      contradictor.yaml
      hub_explorer.yaml
      note_combinations.yaml
      orphan_connector.yaml
      perspective_shifter.yaml
      random_prompts.yaml
      semantic_neighbours.yaml
      temporal_mirror.yaml
      what_if.yaml
```

### Execution Order

1. Load default geists from package (`geistfabrik.default_geists`)
2. Check config for enabled/disabled status
3. Load custom geists from vault (`<vault>/_geistfabrik/geists`)
4. Execute all enabled geists (both default and custom)

### Configuration

In `<vault>/_geistfabrik/config.yaml`:

```yaml
default_geists:
  # Code geists (default: enabled)
  blind_spot_detector: true
  dialectic_triad: true
  structure_diversity_checker: true
  metadata_driven_discovery: true
  on_this_day: true

  # Tracery geists (default: enabled)
  contradictor: true
  hub_explorer: true
  note_combinations: true
  orphan_connector: true
  perspective_shifter: true
  random_prompts: true
  semantic_neighbours: true
  temporal_mirror: true
  what_if: true
```

**To disable a default geist:**

```yaml
default_geists:
  contradictor: false          # Disable this geist
  blind_spot_detector: false   # Disable this geist
  # ... rest default to true
```

**If config missing entirely:** All defaults enabled

**If `default_geists` section missing:** All defaults enabled

**If specific geist not listed:** Defaults to enabled

This means users only need to add entries for geists they want to disable.

### Simplified User Config

Most users will have a minimal config:

```yaml
# Only disable what you don't want
default_geists:
  contradictor: false
```

All unlisted geists remain enabled.

## Default Geist List

### Code Geists (5)

| Geist ID | Description | Default | Status |
|----------|-------------|---------|--------|
| **blind_spot_detector** | Identifies semantic gaps in recent thinking | enabled | ✅ Implemented |
| **dialectic_triad** | Creates thesis-antithesis pairs for synthesis | enabled | ✅ Implemented |
| **structure_diversity_checker** | Detects repetitive writing patterns | enabled | ✅ Implemented |
| **metadata_driven_discovery** | Finds unexpected metadata patterns | enabled | ✅ Implemented |
| **on_this_day** | Surfaces notes from same date in previous years | enabled | 🔨 Pending |

### Tracery Geists (9)

| Geist ID | Description | Default | Status |
|----------|-------------|---------|--------|
| **contradictor** | Challenge assumptions with opposing perspectives | enabled | ✅ Implemented |
| **hub_explorer** | Highlight hub notes with many connections | enabled | ✅ Implemented |
| **note_combinations** | Combine random notes creatively | enabled | ✅ Implemented |
| **orphan_connector** | Suggest connections for orphaned notes | enabled | ✅ Implemented |
| **perspective_shifter** | Reframe notes from different angles | enabled | ✅ Implemented |
| **random_prompts** | General creative prompts | enabled | ✅ Implemented |
| **semantic_neighbours** | Show semantic neighbourhoods | enabled | ✅ Implemented |
| **temporal_mirror** | Compare old and new notes temporally | enabled | ✅ Implemented |
| **what_if** | "What if" prompts for divergent thinking | enabled | ✅ Implemented |

## Default Config Generation

When a new vault is initialized, `_geistfabrik/config.yaml` is created with:

```yaml
default_geists:
  # Default geists are enabled by default
  # Set to false to disable specific geists

  # Code geists
  blind_spot_detector: true
  dialectic_triad: true
  structure_diversity_checker: true
  metadata_driven_discovery: true
  on_this_day: true

  # Tracery geists
  contradictor: true
  hub_explorer: true
  note_combinations: true
  orphan_connector: true
  perspective_shifter: true
  random_prompts: true
  semantic_neighbours: true
  temporal_mirror: true
  what_if: true
```

This makes the full list of defaults visible and easily toggleable.

## Migration Path

### For New Users
- Works immediately on first `uv run geistfabrik invoke`
- Config file shows all available defaults
- Change `true` to `false` to disable any geist

### For Existing Users
- Custom geists continue working unchanged
- No breaking changes to APIs
- New config section is optional (defaults to all enabled)
- Can add `default_geists` section to control defaults

## The "On This Day" Geist

Replaces the seasonal concept with something simpler and more universal:

```python
def suggest(vault: "VaultContext") -> list[Suggestion]:
    """Surface notes from same calendar date in previous years."""
    from datetime import datetime

    today = datetime.now()
    same_date_notes = []

    for note in vault.notes():
        created = note.created
        # Same month and day, different year
        if created.month == today.month and created.day == today.day and created.year < today.year:
            years_ago = today.year - created.year
            same_date_notes.append((note, years_ago))

    suggestions = []
    for note, years_ago in same_date_notes[:3]:
        if years_ago == 1:
            time_phrase = "One year ago today"
        else:
            time_phrase = f"{years_ago} years ago today"

        text = f"{time_phrase}, you wrote [[{note.title}]]. What's changed since then?"
        suggestions.append(Suggestion(
            text=text,
            notes=[note.title],
            geist_id="on_this_day"
        ))

    return vault.sample(suggestions, min(2, len(suggestions)))
```

Works globally (not hemisphere-specific), simple date matching, focuses on personal history rather than seasonal patterns.

## Implementation Notes

1. **Config schema**: Add `default_geists` dict mapping geist_id → bool
2. **Default values**: Missing entries default to `true` (enabled)
3. **Loader logic**:
   - Load all default geists from package
   - Filter by config: `if config.default_geists.get(geist_id, True)`
   - Load custom geists (always enabled)
4. **Config generation**: When initializing vault, write full default config showing all geists
5. **Built-in functions**: `contrarian_to()` is now a built-in vault function
6. **Documentation**: Move examples/ to documentation format explaining how to build extensions
7. **File migrations**:
   - Move 4 implemented code geists from examples/ to src/geistfabrik/default_geists/code/
   - Create new on_this_day.py geist
   - Remove seasonal_revisit.py (replaced by on_this_day)
   - Move 9 Tracery geists from examples/ to src/geistfabrik/default_geists/tracery/
   - Keep 10 example code geists in examples/ as learning material (with documentation)

## Documentation Structure

The `examples/` directory becomes documentation-focused:

```
examples/
  README.md                          # Overview of extensibility
  BUILDING_GEISTS.md                 # How to write code & Tracery geists
  BUILDING_VAULT_FUNCTIONS.md       # How to create vault functions
  BUILDING_METADATA_INFERENCE.md    # How to add metadata modules
  geists/
    code/                            # Keep 10 example geists as learning material
      temporal_drift.py
      creative_collision.py
      ... (8 more)
    README.md                        # Explains example patterns
```

## Config Schema Details

Dict-based approach (recommended for flexibility):

```python
@dataclass
class Config:
    """GeistFabrik configuration."""

    enabled_modules: List[str] = field(default_factory=list)
    default_geists: Dict[str, bool] = field(default_factory=dict)
    # ... other config

    def is_default_geist_enabled(self, geist_id: str) -> bool:
        """Check if default geist is enabled. Defaults to True."""
        return self.default_geists.get(geist_id, True)
```

This allows the system to gracefully handle new defaults added in future versions without breaking existing configs.

## Testing Strategy

- Unit tests for each default geist
- Integration test: disabled defaults don't execute
- Integration test: custom geists work alongside defaults
- Migration test: existing custom geists unaffected
- Test that missing config entries default to enabled
- Test that missing config section defaults all to enabled
- Test that contrarian_to() works as built-in function

## Success Metrics

- New user runs `invoke` and gets interesting suggestions immediately
- User can see full list of defaults in config file
- Disabling a geist is as simple as changing `true` to `false`
- Custom geists continue working without any code changes
- Default geists provide clear patterns for users to learn from
- Examples/ documentation teaches extension patterns effectively
