# GeistFabrik vision

## What is GeistFabrik?

GeistFabrik (German for "spirit factory") is the system; geists are the generative prompts within it. These small programs sample your Obsidian vault and produce creative suggestions. Geists come in two forms:

- **Code geists**: Python functions that receive a vault context and perform complex analysis
- **Tracery geists**: YAML grammars using the Tracery format for procedural text generation

## Inspiration

GeistFabrik draws on Gordon Brander's explorations of tools for thought, particularly his work on Subconscious:

**"Tarot for thought"** - In "Building a Second Subconscious" (2021), Brander described creating "a creative oracle that helps provoke ideas... More tarot than flash cards. Tarot for thought." GeistFabrik embraces this vision of divergent thinking tools over convergent memory tools.

**Geists as oracles** - Brander's "Subconscious napkin sketch" (2022) introduced the concept of Geists: "little bots that live in your Subconscious... Some Geists will be focused on issuing oracular provocations. Others will take old notes and collide them in new ways, to provoke new ideas."

**Self-organizing ideas** - His essay "Self-Organizing Ideas" (2021) explored systems where "related ideas begin to clump together... Old ideas give birth to new ones. The concepts refactor themselves, evolving into thoughts, theses, outlines, articles, even books, all organically grown from the bottom-up."

**Diverge/converge feedback loops** - Brander's framework of creativity as alternating phases of divergence (generating options) and convergence (making choices), connected through cybernetic feedback loops where outputs become inputs for new creative exploration.

GeistFabrik takes these ideas and grounds them in a concrete, extensible system for Obsidian vaults—a spirit factory that generates different questions to ask of your thinking.

## Core Architecture

Geists receive a **rich execution context** rather than raw vault data. This VaultContext provides pre-computed embeddings, inferred metadata, and convenient utilities so geists can focus on creative pattern recognition instead of data wrangling.

### Vault Library (Python)

A Python library provides deep understanding of the Obsidian vault through two layers:

#### Vault (Raw Data Layer)

- Syncs filesystem to SQLite database for fast queries
- Parses all vault notes, extracting:
  - Titles, paths, content
  - Links (`[[note]]` and `[[note#heading]]` formats)  
  - Embeds/transclusions (`![[note]]` and `![[note#^block]]`)
  - Queries and other Obsidian syntax
  
- Intelligently handles:
  - Atomic notes (one concept per file)
  - Collection notes (date-separated entries within a single file)
  - Exposes both uniformly as individual notes

- Computes embeddings using sentence-transformers (offline)
- Stores vectors in SQLite using sqlite-vec extension

#### VaultContext (Rich Execution Context)

Geists receive a **VaultContext** - a rich, intelligent wrapper that provides:

- **Embeddings & Semantic Search**:
  - Pre-computed embeddings stored in SQLite
  - Fast vector similarity using sqlite-vec
  - Nearest-neighbor queries via SQL
  
- **Inferred Metadata**:
  - Creation date, tags, links, backlinks
  - User-extensible metadata (complexity, mood, reading time, etc.)
  - Stored in SQLite for fast filtering
  
- **Convenient Functions**:
  - Sampling utilities (random selection with deterministic seeds)
  - Graph operations via SQL (neighbors, clusters, orphans, hubs)
  - Temporal queries (old notes, recent notes, staleness)
  
- **Function Registry**:
  - Core vault functions built-in
  - User-added functions automatically available
  - All functions exposed to Tracery as `$vault.*`

- **Temporal Embeddings**:
  - Fresh embeddings computed each session
  - Tracks how understanding of notes evolves over time
  - Unlocks geists that detect interpretive drift, temporal patterns, and conceptual evolution

### Geist System

#### Code Geists

Python functions that receive a rich VaultContext and return suggestions.

#### Tracery Geists

YAML files using Tracery grammar with vault-aware expansions. Functions registered in the vault are automatically available as `$vault.function_name()` within Tracery grammars.

### Outputs

#### Geist Journal

**Format undecided** - two options under consideration:

**Option 1: Single reverse-chronological file**
- Location: `<vault>/Geist Journal.md`
- Newest entries prepended to top
- Date-separated with horizontal rules
- Simple, traditional journal format

**Option 2: Folder of session notes**
- Location: `<vault>/GeistFabrik Sessions/`
- One note per session: `2025-01-15.md`, `2025-01-16.md`
- Each session is a discrete artifact
- Can link to specific sessions: `[[GeistFabrik Sessions/2025-01-15]]`

Both formats contain:
- Date heading
- Geist identifier as subheading for each suggestion
- Stable block IDs for deep-linking (`^g001`, `^g002`)
- Variable-length suggestions (geist determines appropriate length)

**Duplicate Prevention**: System checks SQLite database to avoid generating suggestions for dates already processed.

### Extensibility Dimensions

#### 1. Metadata Inference

Users can add Python modules to `~/.geistfabrik/Metadata/` that infer additional properties about notes (reading time, complexity, mood, etc.).

**Note on Extensibility**: Over time, as more explicit and inferred metadata becomes available, this extension happens through the metadata system and VaultContext, not by expanding the Note class. Notes remain lightweight data structures representing vault content, while VaultContext provides the intelligence layer where metadata inference occurs.

#### 2. Vault Functions

Core provides basic functions; users can add more in `~/.geistfabrik/Functions/` that filter or select notes in custom ways.

**Critical Role**: Vault functions are how **metadata becomes available to Tracery geists**. While code geists can directly call `vault.metadata(note)`, Tracery geists can only use functions. Each metadata type needs a corresponding function to be Tracery-accessible.

Example: A `by_complexity()` function makes complexity metadata available to Tracery as `$vault.by_complexity('high', 3)`.

#### 3. Tracery Extensions

All registered vault functions automatically become available in Tracery grammars as `$vault.function_name()`.

### System Properties

- **Identity**: Each geist has unique ID, used in journal headings
- **All geists run**: Every geist executes each session; filtering prevents overwhelm
- **Read-only & Additive**: Never modifies existing vault notes; only writes Geist Journal
- **Deterministic**: Same vault state + date = same suggestions
- **Location**: System data in `~/.geistfabrik/`, journal in vault
- **Ritual, not routine**: Intermittent and deliberate engagement, not automatic consumption

## Invocation Modes

GeistFabrik supports multiple invocation modes:

**Default mode** - Filtered and sampled suggestions
```bash
$ geistfabrik invoke
```
- All geists run
- Filtering removes duplicates, enforces boundaries, checks novelty
- Random sample of ~5 suggestions written to journal

**Single geist mode** - Focus on one geist
```bash
$ geistfabrik invoke --geist columbo
```
- Only Columbo's suggestions (post-filter) appear in journal
- Useful for testing or focusing on specific pattern

**Subset mode** - Multiple specific geists
```bash
$ geistfabrik invoke --geists columbo,drift,skeptic
```
- Only specified geists' suggestions appear

**Full mode** - All suggestions
```bash
$ geistfabrik invoke --full
```
- All filtered suggestions written to journal (no sampling)
- "Drinking from the firehose"
- Could be 50-200 suggestions

All modes respect determinism: same vault state + date + mode = same output.

## Success Metrics

### Technical Performance
- All geists run every session; filtering and sampling prevent overwhelm
- Fast startup via incremental SQLite sync (only process changed files)
- Sub-second queries for graph operations and semantic search
- 5-minute effort to add new capabilities at any layer
- Session invocations are deterministic and idempotent
- Complete vault intelligence in single portable database file

### User Growth Indicators
- **Extensibility in practice**: User's geist pool grows over time
- **Personal divergence**: Custom geists reflect individual thinking patterns
- **Vault evolution**: New geists emerge as vault develops
- **Experimentation**: User tries and discards experimental geists

Success = User has 2-3x more geists after a year of use

### Qualitative Experience
GeistFabrik succeeds when it generates:
- **Surprise** - "I never would have thought to connect these"
- **Delight** - Reading the journal feels like opening a gift
- **Serendipity** - The right suggestion at the unexpected moment
- **Divergence** - Suggestions pull thinking in new directions, not toward conclusions
- **Novelty** - Fresh perspectives on familiar notes
- **Questions** - "What if...?" not "Here's the answer"
- **Play** - Engaging with suggestions feels exploratory, not obligatory

The system asks different questions than you would ask yourself.

### Failure Modes
- Suggestions become predictable or repetitive
- User feels obligated to act on every suggestion
- Setup/configuration becomes burdensome
- System requires constant tuning to stay useful
- Suggestions feel random rather than provocative
- Journal becomes a checklist instead of a source of wonder
- User never adds custom geists (too much friction)
- Growing geist pool degrades performance (doesn't scale)
- Default mode becomes overwhelming (filtering failed)
- Filtering too aggressive (interesting suggestions lost)

## Future: Sharing Extensions

GeistFabrik's power multiplies when users share their extensions with each other and contribute them back to the project.

### What Gets Shared

**Geists** - Different ways of seeing connections
- Domain-specific geists (academic research, software development, creative writing)
- Methodological geists (TRIZ, First Principles, Dialectical)
- Personality-specific geists (skeptic, synthesizer, archaeologist)

**Metadata Modules** - Different ways of understanding notes
- Discipline-specific metrics (code complexity, argument strength, empirical grounding)
- Cognitive metrics (abstraction level, confidence, novelty)
- Social metrics (audience, formality, stance)

**Vault Functions** - Different ways of querying
- Domain queries (papers by methodology, code by paradigm)
- Temporal queries (seasonal patterns, weekly rhythms)
- Relational queries (contrarians, complements, prerequisites)

### Community Exchange

Users develop personal collections reflecting how they think:
- The researcher's toolkit (citation networks, methodology patterns, gap detection)
- The writer's toolkit (narrative structures, character relationships, thematic echoes)
- The systems thinker's toolkit (feedback loops, emergence patterns, scale transitions)

Sharing happens organically:
- "Here's my Socratic geist—it finds assumptions to question"
- "I built a function for finding prerequisite knowledge chains"
- "My formality detector helps me maintain consistent tone"

### Contributing Back

Extensions that prove broadly useful return to the project:
- Well-designed geists become part of the shipped set
- Robust metadata modules join the standard library
- Elegant vault functions become core utilities

The line between user and contributor blurs—GeistFabrik grows through accumulated collective insight about how to see patterns in thought.

### The Vision

Over time, GeistFabrik becomes a system that ships with 20 geists but supports 200+. Each user's extensions reflect their unique way of seeing. Success isn't measured by how many users adopt GeistFabrik, but by how many users extend it—and how many of those extensions prove useful to others.