# GeistFabrik Testing Plan

This document outlines the comprehensive testing strategy for GeistFabrik, including unit tests for all components and scenario-based integration tests using the kepano Obsidian vault test data.

## Test Data Overview

**Primary Test Vault**: `testdata/kepano-obsidian-main/`
- 8 markdown files (~108 lines total)
- Mix of note types: daily notes, meetings, projects, concept notes, clippings
- YAML frontmatter with diverse metadata (categories, tags, dates, URLs, authors, topics, status)
- Links: `[[double bracket]]` format with variations (`[[Note#heading]]`)
- Transclusions: `![[note]]` and `![[note#^block]]` syntax
- Tags: both frontmatter arrays and inline `#tag` format
- Tasks: `- [x]` completed and `- [ ]` incomplete
- Real-world content from Steph Ango's public vault

## Test Organization

```
tests/
├── unit/
│   ├── test_vault.py              # Vault layer tests
│   ├── test_vault_context.py      # VaultContext layer tests
│   ├── test_note.py               # Note dataclass tests
│   ├── test_suggestion.py         # Suggestion dataclass tests
│   ├── test_embeddings.py         # Embedding computation tests
│   ├── test_sqlite_persistence.py # Database operations tests
│   ├── test_markdown_parser.py    # Markdown parsing tests
│   ├── test_metadata_system.py    # Metadata inference tests
│   ├── test_function_registry.py  # Function registration tests
│   ├── test_geist_executor.py     # Geist execution tests
│   ├── test_filtering.py          # Filtering pipeline tests
│   ├── test_session.py            # Session management tests
│   ├── test_journal_writer.py     # Journal output tests
│   ├── test_tracery.py            # Tracery integration tests
│   └── test_cli.py                # CLI argument parsing tests
├── integration/
│   ├── test_kepano_vault.py       # Full vault tests with kepano data
│   ├── test_scenarios.py          # Scenario-based integration tests
│   ├── test_end_to_end.py         # Complete workflow tests
│   └── test_temporal_embeddings.py # Multi-session temporal tests
├── fixtures/
│   ├── minimal_vault/             # Minimal test vaults for specific cases
│   ├── edge_cases/                # Edge case vaults
│   └── synthetic/                 # Generated test data
└── conftest.py                     # Pytest fixtures and configuration
```

## Unit Test Specifications

### 1. test_vault.py - Vault Layer

#### Markdown Parsing
- **test_parse_simple_note**: Parse note with title, content, no links
- **test_parse_note_with_frontmatter**: Extract YAML frontmatter metadata
- **test_parse_note_with_links**: Identify all `[[links]]` in content
- **test_parse_note_with_headings_links**: Parse `[[Note#heading]]` format
- **test_parse_note_with_block_refs**: Parse `[[Note#^blockid]]` references
- **test_parse_note_with_embeds**: Identify `![[transclusions]]`
- **test_parse_note_with_inline_tags**: Extract `#tag` and `#nested/tag`
- **test_parse_note_with_frontmatter_tags**: Extract tags from YAML array
- **test_parse_note_with_tasks**: Identify `- [ ]` and `- [x]` tasks
- **test_parse_note_dates**: Extract created/modified from frontmatter and filesystem
- **test_parse_note_with_code_blocks**: Ignore links inside code blocks
- **test_parse_note_with_escaped_brackets**: Handle `\[\[not a link\]\]`

#### File System Operations
- **test_load_all_notes**: Load all .md files from vault directory
- **test_ignore_obsidian_folder**: Skip `.obsidian/` directory
- **test_ignore_non_markdown**: Skip non-.md files
- **test_respect_exclude_paths**: Honor `exclude_paths` configuration
- **test_handle_nested_directories**: Parse notes in subdirectories
- **test_handle_unicode_filenames**: Support non-ASCII file names
- **test_handle_spaces_in_filenames**: Parse files with spaces

#### Incremental Sync
- **test_sync_initial_load**: First sync processes all files
- **test_sync_no_changes**: Second sync with no changes skips all files
- **test_sync_modified_file**: Detect and reprocess changed file via hash
- **test_sync_new_file**: Detect and process newly added file
- **test_sync_deleted_file**: Remove deleted file from database
- **test_sync_renamed_file**: Handle file rename (delete + add)
- **test_hash_computation**: Verify file hash includes content including frontmatter
- **test_hash_excludes_mtime**: Hash independent of modification time

#### Embedding Computation
- **test_compute_embedding_title**: Generate 384-dim embedding for title
- **test_compute_embedding_content**: Generate 384-dim embedding for content
- **test_truncate_long_content**: Truncate content >1000 chars before embedding
- **test_embedding_deterministic**: Same text = same embedding
- **test_embedding_model_loading**: Load sentence-transformers model once
- **test_embedding_normalization**: Embeddings are normalized vectors

### 2. test_vault_context.py - VaultContext Layer

#### Direct Vault Access
- **test_notes_delegation**: `ctx.notes()` delegates to `vault.all_notes()`
- **test_get_note_delegation**: `ctx.get_note(path)` delegates correctly
- **test_read_note_delegation**: `ctx.read(note)` returns note.content

#### Semantic Search (sqlite-vec)
- **test_neighbors_basic**: Find k nearest neighbors by embedding similarity
- **test_neighbors_excludes_self**: Neighbors don't include query note
- **test_neighbors_empty_vault**: Handle vault with <k notes
- **test_similarity_score**: Calculate cosine similarity between two notes
- **test_similarity_range**: Similarity scores in [0, 1] range
- **test_similarity_symmetric**: similarity(a, b) == similarity(b, a)

#### Graph Operations
- **test_unlinked_pairs**: Find note pairs with no link between them
- **test_unlinked_pairs_symmetric**: Don't return both (a,b) and (b,a)
- **test_orphans**: Find notes with no incoming or outgoing links
- **test_hubs**: Find most-linked-to notes
- **test_links_between**: Find all links connecting two notes
- **test_backlinks**: Find notes linking to a given note
- **test_graph_neighbors**: Find all notes connected by links

#### Temporal Queries
- **test_old_notes**: Find least recently modified notes
- **test_recent_notes**: Find most recently modified notes
- **test_notes_by_date_range**: Filter notes by creation date range
- **test_temporal_ordering**: Verify date ordering is correct

#### Metadata Access
- **test_metadata_basic**: Retrieve metadata for a note
- **test_metadata_caching**: Metadata cached within session
- **test_metadata_invalidation**: Cache invalidated when note changes
- **test_metadata_missing_note**: Handle metadata request for non-existent note

#### Deterministic Sampling
- **test_sample_deterministic**: Same seed = same sample
- **test_sample_different_seeds**: Different seeds = different samples
- **test_sample_k_greater_than_n**: Handle k > len(items)
- **test_sample_preserves_type**: Sample returns same type as input
- **test_random_notes**: Random note selection uses deterministic seed

#### Function Calls
- **test_call_function_basic**: Call registered function by name
- **test_call_function_with_args**: Pass arguments to function
- **test_call_function_unknown**: Handle unknown function name
- **test_function_receives_context**: Function receives VaultContext

### 3. test_embeddings.py - Embedding System

#### Model Management
- **test_load_model_once**: sentence-transformers model loaded once globally
- **test_model_deterministic**: Model produces consistent embeddings
- **test_model_dimensions**: Verify 384-dimensional output
- **test_model_offline**: Confirm no network calls during embedding

#### Temporal Embeddings
- **test_session_embedding_basic**: Compute session embeddings for all notes
- **test_session_embedding_storage**: Store in session_embeddings table
- **test_session_embedding_retrieval**: Retrieve embeddings by session_id
- **test_temporal_features_note_age**: Age feature calculated correctly
- **test_temporal_features_season**: Season encoded correctly (0-4 scale)
- **test_temporal_features_session_season**: Session season encoded
- **test_embedding_dimension_387**: Combined embedding is 387 dims (384+3)
- **test_embedding_weights**: Semantic and temporal weighted correctly (50/50)
- **test_multiple_sessions**: Multiple session embeddings for same note
- **test_session_id_generation**: Session IDs unique and sequential

#### Embedding Queries
- **test_embedding_similarity_search**: Find similar notes via embeddings
- **test_embedding_clustering**: Identify semantic clusters
- **test_embedding_drift_detection**: Compare embeddings across sessions
- **test_embedding_variance**: Calculate embedding variance over sessions

### 4. test_sqlite_persistence.py - Database Layer

#### Schema Creation
- **test_create_notes_table**: Notes table with correct columns
- **test_create_links_table**: Links table with foreign keys
- **test_create_embeddings_table**: sqlite-vec virtual table
- **test_create_metadata_table**: Metadata table with JSON values
- **test_create_geist_runs_table**: Geist execution history table
- **test_create_block_refs_table**: Block reference tracking
- **test_create_tags_table**: Denormalized tags table
- **test_create_sessions_table**: Session tracking table
- **test_create_session_embeddings_table**: Temporal embeddings table
- **test_create_indexes**: All necessary indexes created
- **test_foreign_key_constraints**: Foreign key enforcement enabled

#### CRUD Operations
- **test_insert_note**: Insert note into database
- **test_update_note**: Update existing note
- **test_delete_note**: Delete note and cascade to links/tags
- **test_upsert_note**: Insert or replace note atomically
- **test_insert_links**: Insert link relationships
- **test_insert_tags**: Insert tag relationships
- **test_insert_embedding**: Insert vector embedding
- **test_insert_metadata**: Insert JSON metadata
- **test_transaction_rollback**: Rollback on error

#### Queries
- **test_query_notes_by_tag**: Find notes with specific tag
- **test_query_links_source**: Find all links from a note
- **test_query_links_target**: Find all links to a note
- **test_query_vector_similarity**: sqlite-vec similarity search
- **test_query_metadata_filter**: Filter notes by metadata value
- **test_query_geist_history**: Retrieve past geist runs
- **test_query_join_notes_links**: Join notes with link data
- **test_query_session_embeddings**: Retrieve session-specific embeddings

#### Performance
- **test_index_performance_links**: Links indexed by source/target
- **test_index_performance_tags**: Tags indexed
- **test_index_performance_metadata**: Metadata key indexed
- **test_bulk_insert_performance**: Batch insert optimization

### 5. test_markdown_parser.py - Markdown Parsing

#### Link Formats
- **test_parse_basic_link**: `[[Note]]`
- **test_parse_aliased_link**: `[[Note|alias]]`
- **test_parse_heading_link**: `[[Note#Heading]]`
- **test_parse_block_link**: `[[Note#^blockid]]`
- **test_parse_embed**: `![[Note]]`
- **test_parse_embed_block**: `![[Note#^blockid]]`
- **test_parse_multiple_links**: Multiple links in one line
- **test_parse_nested_brackets**: `[[Note with [[nested]]]]` (invalid)

#### Frontmatter
- **test_parse_yaml_frontmatter**: Extract YAML between `---`
- **test_parse_empty_frontmatter**: Handle empty frontmatter
- **test_parse_malformed_frontmatter**: Handle invalid YAML
- **test_parse_frontmatter_arrays**: Parse YAML arrays
- **test_parse_frontmatter_nested**: Parse nested YAML objects
- **test_parse_frontmatter_dates**: Parse date fields
- **test_parse_frontmatter_tags**: Extract tags array

#### Tags
- **test_parse_inline_tag**: `#tag`
- **test_parse_nested_tag**: `#parent/child/grandchild`
- **test_parse_tag_with_dash**: `#my-tag`
- **test_parse_tag_unicode**: `#emoji🔥tag`
- **test_ignore_tag_in_code**: Don't parse tags in code blocks
- **test_ignore_tag_in_url**: Don't parse `http://example.com#anchor`

#### Special Cases
- **test_parse_code_blocks**: Identify and skip code block content
- **test_parse_inline_code**: Skip inline `code`
- **test_parse_escaped_characters**: Handle `\[\[escaped\]\]`
- **test_parse_html_comments**: Skip `<!-- comments -->`
- **test_parse_empty_note**: Handle note with no content
- **test_parse_only_frontmatter**: Handle note with only frontmatter

#### Block References
- **test_identify_block_ids**: Find `^blockid` markers
- **test_generate_block_id**: Generate unique block ID
- **test_block_id_format**: Verify format `^gYYYYMMDD-NNN`
- **test_block_id_persistence**: Same block keeps same ID

### 6. test_metadata_system.py - Metadata Inference

#### Module Loading
- **test_load_metadata_modules**: Discover modules in metadata_inference/ directory
- **test_load_order_from_config**: Load in configured order
- **test_skip_missing_modules**: Skip modules not found
- **test_verify_infer_function**: Verify module exports `infer()`
- **test_detect_key_conflicts**: Error on duplicate metadata keys
- **test_module_isolation**: Modules don't affect each other

#### Inference Execution
- **test_infer_all_modules**: Run all modules for a note
- **test_infer_metadata_caching**: Cache results per session
- **test_infer_metadata_invalidation**: Invalidate on note change
- **test_infer_error_handling**: Continue on module failure
- **test_infer_metadata_types**: Support dict values (string, int, float, bool, list)

#### Built-in Metadata
- **test_metadata_word_count**: Calculate word count
- **test_metadata_link_count**: Count outgoing links
- **test_metadata_tag_count**: Count tags
- **test_metadata_created_date**: Extract creation date
- **test_metadata_modified_date**: Extract modification date
- **test_metadata_file_size**: Track file size

#### Custom Metadata Examples
- **test_metadata_reading_time**: words / 200
- **test_metadata_link_density**: links / words
- **test_metadata_has_tasks**: Detect `- [ ]` tasks
- **test_metadata_is_question**: Title ends with `?`
- **test_metadata_staleness**: Days since modification

### 7. test_function_registry.py - Function System

#### Registration
- **test_register_function**: Register function by name
- **test_register_with_decorator**: `@vault_function("name")`
- **test_register_duplicate**: Error on duplicate function name
- **test_discover_user_functions**: Auto-discover in vault_functions/ directory
- **test_function_metadata**: Store function docstring and signature

#### Built-in Functions
- **test_function_sample_notes**: Random k notes
- **test_function_unlinked_pairs**: k unlinked pairs
- **test_function_neighbors**: k similar notes
- **test_function_old_notes**: k least recently modified
- **test_function_tagged**: k notes with tag
- **test_function_recent_notes**: k most recently modified
- **test_function_orphans**: k notes with no links
- **test_function_hubs**: k most linked notes

#### Function Execution
- **test_call_by_name**: Call function by string name
- **test_call_with_args**: Pass positional arguments
- **test_call_with_kwargs**: Pass keyword arguments
- **test_call_receives_context**: Function receives VaultContext
- **test_call_unknown_function**: Raise error for unknown function
- **test_call_function_error**: Handle function exception

#### Tracery Bridge
- **test_tracery_namespace**: Create `$vault.*` namespace
- **test_tracery_function_call**: Call function from Tracery
- **test_tracery_function_args**: Pass arguments from Tracery
- **test_tracery_function_error**: Handle error in Tracery context

### 8. test_geist_executor.py - Geist Execution

#### Loading
- **test_load_code_geists**: Discover .py files in geists/code/
- **test_load_tracery_geists**: Discover .yaml files in geists/tracery/
- **test_verify_code_geist_interface**: Verify `suggest()` function exists
- **test_verify_tracery_geist_schema**: Verify YAML schema
- **test_skip_disabled_geists**: Skip geists disabled in config
- **test_geist_id_uniqueness**: Ensure unique geist IDs

#### Code Geist Execution
- **test_execute_code_geist**: Call `suggest(ctx)`
- **test_code_geist_receives_context**: Context passed correctly
- **test_code_geist_returns_suggestions**: Return List[Suggestion]
- **test_code_geist_empty_return**: Handle empty list return
- **test_code_geist_timeout**: Timeout after 5 seconds
- **test_code_geist_error**: Handle exception in geist
- **test_code_geist_isolation**: Geist failure doesn't affect others

#### Tracery Geist Execution
- **test_execute_tracery_geist**: Expand Tracery grammar
- **test_tracery_vault_functions**: `$vault.function()` calls work
- **test_tracery_multiple_expansions**: Generate multiple suggestions
- **test_tracery_recursion_limit**: Respect max_depth
- **test_tracery_error_handling**: Handle invalid grammar
- **test_tracery_deterministic**: Same seed = same output

#### Timeout Handling
- **test_timeout_signal**: SIGALRM used for timeout
- **test_timeout_cleanup**: Signal cleaned up after execution
- **test_timeout_configurable**: Timeout from config
- **test_timeout_logs_error**: Timeout logged with test command

#### Failure Tracking
- **test_failure_count_increment**: Track failures per geist
- **test_disable_after_three_failures**: Auto-disable after 3 failures
- **test_failure_count_reset**: Reset on successful execution
- **test_disabled_geist_skipped**: Skip disabled geists
- **test_log_test_command**: Log command to reproduce failure

### 9. test_filtering.py - Filtering Pipeline

#### Boundary Enforcement
- **test_filter_excluded_paths**: Remove suggestions referencing excluded paths
- **test_filter_respects_config**: Use exclude_paths from config
- **test_filter_partial_path_match**: Match subdirectories
- **test_filter_case_sensitive_paths**: Path matching is case-sensitive

#### Novelty Checking
- **test_filter_duplicate_text**: Remove exact duplicate suggestions
- **test_filter_similar_embeddings**: Remove embeddings above threshold (0.85)
- **test_filter_novelty_window**: Check against last N days
- **test_filter_uses_geist_runs**: Query geist_runs table
- **test_filter_novelty_per_geist**: Check novelty per geist, not global

#### Diversity Within Batch
- **test_filter_diversity**: Remove near-duplicates within batch
- **test_filter_diversity_threshold**: Use 0.85 similarity threshold
- **test_filter_diversity_embedding**: Use embedding similarity
- **test_filter_diversity_preserves_order**: Keep first occurrence

#### Quality Baseline
- **test_filter_min_length**: Remove suggestions < min_length
- **test_filter_max_length**: Remove suggestions > max_length
- **test_filter_missing_geist_id**: Remove suggestions without geist_id
- **test_filter_missing_notes**: Remove suggestions without note references
- **test_filter_exact_duplicates_in_batch**: Remove exact text duplicates

#### Filter Configuration
- **test_filter_enable_disable**: Enable/disable filters via config
- **test_filter_strategies_order**: Apply filters in configured order
- **test_filter_thresholds**: Respect threshold configurations
- **test_filter_all_filters**: Integration of all filters

### 10. test_session.py - Session Management

#### Session Creation
- **test_create_session**: Create session with date
- **test_session_id_generation**: Generate unique session ID
- **test_session_vault_state_hash**: Compute vault content hash
- **test_session_already_exists**: Detect existing session for date
- **test_session_storage**: Store session in sessions table

#### Embedding Computation
- **test_compute_session_embeddings**: Compute for all notes
- **test_session_embedding_storage**: Store in session_embeddings table
- **test_session_embedding_dimensions**: 387 dims (384 + 3)
- **test_session_temporal_features**: Include age, season features
- **test_session_embedding_caching**: Use cached embeddings within session

#### Vault State Hashing
- **test_vault_hash_deterministic**: Same vault = same hash
- **test_vault_hash_content_only**: Hash independent of mtimes
- **test_vault_hash_includes_frontmatter**: Include YAML frontmatter
- **test_vault_hash_change_detection**: Hash changes when content changes
- **test_vault_hash_excludes_sessions**: Don't hash session notes

#### Multi-Session Queries
- **test_get_recent_sessions**: Retrieve last N sessions
- **test_get_session_by_date**: Retrieve specific session
- **test_compare_embeddings_across_sessions**: Track embedding drift
- **test_session_pruning**: Prune old sessions (not implemented yet)

### 11. test_journal_writer.py - Journal Output

#### Note Generation
- **test_generate_session_note**: Create YYYY-MM-DD.md file
- **test_session_note_location**: Write to geist journal/ folder
- **test_session_note_title**: Title format "GeistFabrik Session – YYYY-MM-DD"
- **test_session_note_exists**: Don't overwrite existing session

#### Suggestion Formatting
- **test_format_suggestion_heading**: `## geist_id ^blockid`
- **test_format_block_id**: `^gYYYYMMDD-NNN` format
- **test_format_suggestion_text**: Suggestion text on next line
- **test_format_multiple_suggestions**: One per geist
- **test_format_preserves_links**: Keep `[[links]]` intact
- **test_format_variable_length**: Support any suggestion length

#### Block ID Management
- **test_block_id_sequential**: NNN increments sequentially
- **test_block_id_date_prefix**: Uses session date
- **test_block_id_uniqueness**: No duplicate block IDs in session
- **test_block_id_persistence**: Same suggestion = same block ID (if re-run)

#### File Operations
- **test_create_sessions_folder**: Create folder if doesn't exist
- **test_write_utf8**: Use UTF-8 encoding
- **test_atomic_write**: Write atomically (temp file + rename)
- **test_preserve_existing**: Don't overwrite if session exists

### 12. test_tracery.py - Tracery Integration

#### Grammar Parsing
- **test_parse_yaml_grammar**: Load grammar from YAML
- **test_parse_origin**: Identify origin rule
- **test_parse_symbols**: Extract symbol rules
- **test_parse_arrays**: Parse rule arrays
- **test_validate_grammar**: Validate required fields

#### Expansion
- **test_expand_simple**: Expand basic `#symbol#`
- **test_expand_recursive**: Expand nested symbols
- **test_expand_multiple_options**: Random selection from array
- **test_expand_deterministic**: Same seed = same expansion
- **test_expand_max_depth**: Respect recursion limit

#### Vault Function Integration
- **test_expand_vault_function**: Call `$vault.function()`
- **test_vault_function_args**: Pass arguments to function
- **test_vault_function_result**: Use function return in expansion
- **test_vault_function_error**: Handle function error
- **test_vault_function_empty_result**: Handle empty result

#### Modifiers
- **test_modifier_capitalize**: `.capitalize` works
- **test_modifier_plural**: `.s` pluralization
- **test_modifier_article**: `.a` adds a/an
- **test_modifier_chain**: Chain multiple modifiers

#### Push-Pop Stack
- **test_push_variable**: `[var:value]` saves value
- **test_pop_variable**: Use saved `#var#`
- **test_variable_scope**: Variables scoped to expansion
- **test_variable_override**: Later assignment overrides

### 13. test_cli.py - Command Line Interface

#### Argument Parsing
- **test_parse_invoke_default**: `geistfabrik invoke`
- **test_parse_invoke_geist**: `--geist name`
- **test_parse_invoke_geists**: `--geists a,b,c`
- **test_parse_invoke_full**: `--full` flag
- **test_parse_invoke_date**: `--date YYYY-MM-DD`
- **test_parse_test_command**: `geistfabrik test geist_id`
- **test_parse_test_vault**: `--vault path`
- **test_parse_test_session**: `--session-id N`
- **test_parse_invalid_args**: Error on invalid arguments

#### Invocation Modes
- **test_default_mode**: Filtered + sampled (~5)
- **test_single_geist_mode**: Only one geist's suggestions
- **test_multi_geist_mode**: Subset of geists
- **test_full_mode**: All filtered suggestions
- **test_replay_mode**: Regenerate specific date

#### Configuration
- **test_load_config**: Load config.yaml
- **test_config_defaults**: Use defaults if config missing
- **test_config_override**: CLI args override config
- **test_vault_path_detection**: Auto-detect vault path
- **test_database_path**: Use configured database path

#### Error Handling
- **test_vault_not_found**: Error if vault doesn't exist
- **test_invalid_date_format**: Error on malformed date
- **test_unknown_geist**: Error on unknown geist name
- **test_help_text**: Show help with `--help`

## Integration Test Specifications

### test_kepano_vault.py - Kepano Test Vault

#### Full Vault Loading
```python
def test_load_kepano_vault():
    """Load entire kepano vault and verify structure"""
    # Load all 8 markdown files
    # Verify note count, titles, paths
    # Check frontmatter extraction
    # Validate link parsing
    # Confirm tag extraction
```

#### Specific Note Tests
```python
def test_parse_evergreen_notes():
    """Parse 'Evergreen notes turn ideas into objects that you can manipulate.md'"""
    # Verify frontmatter: categories, created, url, author, published, topics, tags, status
    # Extract links: [[evergreen]], [[Evergreen]], [[A company is a superorganism]], etc.
    # Confirm nested link structure
    # Validate quote block with embedded link

def test_parse_daily_note():
    """Parse '2023-09-12.md'"""
    # Extract frontmatter tags: daily
    # Find transclusion: ![[Daily.base]]
    # Verify minimal content structure

def test_parse_meeting_note():
    """Parse '2023-09-12 Meeting with Steph.md'"""
    # Extract rich frontmatter: categories, type, date, org, loc, people, topics, tags
    # Parse links: [[Meetings]], [[Obsidian]], [[Steph Ango]], [[Emergence]], [[Out of Control]]
    # Verify metadata structure

def test_parse_project_note():
    """Parse 'Minimal Theme.md'"""
    # Extract frontmatter: categories, type, org, year, tags, url, status
    # Find completed tasks: - [x]
    # Validate project metadata

def test_parse_transclusion_note():
    """Parse 'Product usage analysis.md'"""
    # Parse link: [[Buy wisely]]
    # Parse transclusion with heading: ![[Products.base#Cost per use]]
    # Verify transclusion tracking (not execution)
```

#### Link Graph Analysis
```python
def test_kepano_link_graph():
    """Analyze link structure across kepano vault"""
    # Build link graph from all notes
    # Identify orphans (if any)
    # Find most-linked notes (hubs)
    # Calculate graph metrics
    # Verify bidirectional link tracking

def test_kepano_backlinks():
    """Test backlink calculation"""
    # Find all notes linking to [[Emergence]]
    # Find all notes linking to [[Obsidian]]
    # Verify backlink counts
```

#### Tag Analysis
```python
def test_kepano_tags():
    """Extract and analyze all tags"""
    # Collect all unique tags
    # Both frontmatter and inline
    # Verify: daily, meetings, projects, clippings, 0🌲
    # Test tag filtering and queries

def test_kepano_nested_tags():
    """Test nested/hierarchical tags if present"""
    # Identify parent/child tag relationships
    # Test queries at different hierarchy levels
```

#### Metadata Extraction
```python
def test_kepano_frontmatter_variety():
    """Test all frontmatter variations in kepano vault"""
    # categories (array of links)
    # type (array)
    # date, created, published (dates)
    # url (string)
    # author, people, org, loc (various formats)
    # topics (links)
    # tags (array)
    # status (link)
    # year (number)
```

#### Embedding Tests
```python
def test_kepano_embeddings():
    """Generate embeddings for all kepano notes"""
    # Compute embeddings for all 8 notes
    # Verify 384 dimensions
    # Test semantic similarity between related notes
    # Find neighbors for "Evergreen notes"
    # Compare "Meetings" vs "Projects" semantic distance

def test_kepano_semantic_clusters():
    """Identify semantic clusters in kepano vault"""
    # Even with 8 notes, should cluster
    # Concept notes vs daily notes vs meeting notes
```

### test_scenarios.py - Scenario-Based Integration Tests

#### Scenario 1: First-Time Vault Setup
```python
def test_scenario_first_time_setup():
    """User runs GeistFabrik on kepano vault for first time"""
    # Step 1: Initialize vault from kepano testdata
    # Step 2: Sync parses all 8 files
    # Step 3: Compute embeddings for all notes
    # Step 4: Build SQLite database
    # Step 5: Verify all data stored correctly
    # Measure: Sync time, database size, embedding count
```

#### Scenario 2: Daily Invocation
```python
def test_scenario_daily_invocation():
    """User invokes GeistFabrik for daily suggestions"""
    # Step 1: Load pre-synced kepano vault
    # Step 2: Create session for 2025-01-15
    # Step 3: Execute all geists
    # Step 4: Filter suggestions
    # Step 5: Sample ~5 suggestions
    # Step 6: Write session note
    # Verify: Session note created, block IDs correct, suggestions formatted
```

#### Scenario 3: Incremental Sync
```python
def test_scenario_incremental_sync():
    """User modifies one note, runs GeistFabrik again"""
    # Step 1: Initial sync of kepano vault
    # Step 2: Modify "Minimal Theme.md" (add task)
    # Step 3: Run sync again
    # Verify: Only 1 file reprocessed
    # Verify: Embeddings recomputed for modified note
    # Verify: Other 7 notes untouched
    # Measure: Sync time << initial sync
```

#### Scenario 4: Adding New Note
```python
def test_scenario_add_new_note():
    """User creates new note in vault"""
    # Step 1: Initial sync of kepano vault (8 notes)
    # Step 2: Add "New Concept.md" with links to existing notes
    # Step 3: Run sync
    # Verify: 9 notes in database
    # Verify: Links from new note indexed
    # Verify: Backlinks to existing notes updated
    # Verify: New note has embedding
```

#### Scenario 5: Deleting Note
```python
def test_scenario_delete_note():
    """User deletes a note from vault"""
    # Step 1: Initial sync (8 notes)
    # Step 2: Delete "Product usage analysis.md"
    # Step 3: Run sync
    # Verify: 7 notes in database
    # Verify: Links to deleted note marked as broken
    # Verify: Embedding removed
```

#### Scenario 6: Geist Development Workflow
```python
def test_scenario_geist_development():
    """Developer creates and tests new geist"""
    # Step 1: Create simple code geist
    # Step 2: Test with `geistfabrik test new_geist --vault kepano`
    # Step 3: Verify suggestions generated
    # Step 4: Modify geist logic
    # Step 5: Re-test
    # Verify: Isolated testing works, suggestions updated
```

#### Scenario 7: Multi-Day Sessions
```python
def test_scenario_multi_day_sessions():
    """User runs GeistFabrik over multiple days"""
    # Step 1: Run session for 2025-01-15
    # Step 2: Run session for 2025-01-16
    # Step 3: Run session for 2025-01-17
    # Verify: Three session notes created
    # Verify: Different suggestions each day (deterministic but date-seeded)
    # Verify: Novelty filter prevents recent duplicates
```

#### Scenario 8: Temporal Embedding Evolution
```python
def test_scenario_temporal_embeddings():
    """Track embedding evolution across sessions"""
    # Step 1: Session 2025-01-15 (compute embeddings)
    # Step 2: Session 2025-01-16 (compute again, no content changes)
    # Step 3: Session 2025-01-30 (15 days later)
    # Verify: Three sets of embeddings for same notes
    # Verify: Temporal features differ (session date changes)
    # Verify: Can compare drift between sessions
```

#### Scenario 9: Full Firehose Mode
```python
def test_scenario_full_mode():
    """User invokes with --full to see all suggestions"""
    # Step 1: Run `geistfabrik invoke --full` on kepano
    # Verify: All filtered suggestions in session note
    # Verify: Likely 20+ suggestions (all geists × all opportunities)
    # Verify: No sampling applied
```

#### Scenario 10: Single Geist Focus
```python
def test_scenario_single_geist_mode():
    """User focuses on one geist's output"""
    # Step 1: Run `geistfabrik invoke --geist connection_finder`
    # Verify: Only connection_finder suggestions in session
    # Verify: Other geists still executed (for future use)
    # Verify: Filtering still applied
```

### test_end_to_end.py - Complete Workflows

#### E2E Test 1: Zero to First Suggestion
```python
def test_e2e_zero_to_first_suggestion():
    """Complete workflow from empty system to first suggestion"""
    # 1. No database exists
    # 2. Point to kepano vault
    # 3. Run `geistfabrik invoke`
    # 4. System creates database
    # 5. Syncs all files
    # 6. Computes embeddings
    # 7. Loads geists
    # 8. Executes geists
    # 9. Filters suggestions
    # 10. Samples suggestions
    # 11. Writes session note
    # Verify: Session note exists with valid suggestions
```

#### E2E Test 2: Deterministic Replay
```python
def test_e2e_deterministic_replay():
    """Same vault + date produces identical output"""
    # 1. Run session for 2025-01-15
    # 2. Record output suggestions
    # 3. Delete session note
    # 4. Re-run session for 2025-01-15
    # 5. Compare outputs
    # Verify: Exactly identical suggestions, order, block IDs
```

#### E2E Test 3: Extensibility Workflow
```python
def test_e2e_add_metadata_function_geist():
    """Add custom metadata, function, and geist"""
    # 1. Start with working system
    # 2. Add metadata_inference/complexity.py
    # 3. Add vault_functions/complex_notes.py using complexity metadata
    # 4. Add geists/tracery/complexity_connector.yaml using $vault.complex_notes()
    # 5. Run invoke
    # Verify: New geist executes, uses metadata, calls function, produces suggestions
```

#### E2E Test 4: Error Recovery
```python
def test_e2e_error_recovery():
    """System handles errors gracefully"""
    # 1. Working system
    # 2. Add geist that times out
    # 3. Run invoke
    # 4. Verify: Other geists still execute
    # 5. Verify: Timeout logged with test command
    # 6. Fix geist
    # 7. Run test command from log
    # Verify: Geist now works
```

#### E2E Test 5: Performance at Scale
```python
def test_e2e_performance_scaling():
    """Test with larger synthetic vault"""
    # 1. Generate synthetic vault (100 notes, realistic structure)
    # 2. Run initial sync
    # 3. Measure: Sync time, database size, memory
    # 4. Run invoke
    # 5. Measure: Execution time, suggestions generated
    # 6. Modify 5 notes
    # 7. Run sync
    # 8. Measure: Incremental sync time
    # Verify: Meets performance targets from spec
```

### test_temporal_embeddings.py - Multi-Session Temporal Tests

#### Temporal Test 1: Embedding Drift Detection
```python
def test_temporal_drift_detection():
    """Detect when note understanding changes"""
    # 1. Session 1 (2025-01-15): Compute embeddings
    # 2. Session 2 (2025-01-16): Recompute (no content change)
    # 3. Calculate drift between sessions
    # Verify: Temporal features changed, semantic features identical
    # Verify: Can identify notes with high drift
```

#### Temporal Test 2: Seasonal Patterns
```python
def test_temporal_seasonal_patterns():
    """Temporal features encode seasons correctly"""
    # 1. Session in January (winter)
    # 2. Session in July (summer)
    # 3. Same note, same content
    # Verify: Seasonal feature differs
    # Verify: Can cluster notes by creation season
```

#### Temporal Test 3: Note Age Evolution
```python
def test_temporal_note_age():
    """Note age feature increases over time"""
    # 1. Note created 2023-09-12
    # 2. Session 2025-01-15: age ~490 days
    # 3. Session 2025-02-15: age ~520 days
    # Verify: Age feature increases correctly
    # Verify: Older notes cluster separately
```

#### Temporal Test 4: Convergent Evolution
```python
def test_temporal_convergent_evolution():
    """Detect notes developing toward each other"""
    # 1. Session 1: Note A and B distant
    # 2. Modify Note A to become more similar to B
    # 3. Session 2: Note A and B closer
    # 4. Session 3: Even closer
    # Verify: Can detect convergence trend
```

#### Temporal Test 5: Divergent Evolution
```python
def test_temporal_divergent_evolution():
    """Detect linked notes growing apart"""
    # 1. Note A links to Note B
    # 2. Session 1: A and B semantically similar
    # 3. Modify both to become more distinct
    # 4. Session 2: A and B more distant
    # Verify: Can detect divergence despite link
```

## Test Fixtures and Utilities

### conftest.py - Pytest Configuration

```python
# Fixtures for test organization

@pytest.fixture
def kepano_vault_path():
    """Path to kepano test vault"""
    return Path("testdata/kepano-obsidian-main")

@pytest.fixture
def temp_database():
    """Temporary SQLite database for testing"""
    # Create temp file, yield path, cleanup after test

@pytest.fixture
def minimal_vault():
    """Minimal 2-note vault for unit tests"""
    # Create temp vault with simple structure

@pytest.fixture
def vault_with_embeddings():
    """Pre-loaded vault with embeddings computed"""
    # Setup vault + database + embeddings

@pytest.fixture
def mock_embedding_model():
    """Mock sentence-transformers model for fast tests"""
    # Return deterministic fake embeddings

@pytest.fixture
def sample_suggestions():
    """List of Suggestion objects for testing"""
    # Generate varied test suggestions

@pytest.fixture
def mock_geist():
    """Simple mock geist for testing"""
    # Return minimal geist implementation
```

### Minimal Test Vaults

#### fixtures/minimal_vault/
```
note1.md:
  Title: "First Note"
  Content: "This is a simple note."
  Links: None
  Tags: None

note2.md:
  Title: "Second Note"
  Content: "This links to [[First Note]]."
  Links: [[First Note]]
  Tags: None
```

#### fixtures/edge_cases/unicode_vault/
```
- Notes with Unicode characters in titles and content
- Emoji in filenames: "📝 Note.md"
- Non-ASCII links: [[Café Concept]]
- Mixed scripts: [[日本語ノート]]
```

#### fixtures/edge_cases/complex_links/
```
- Circular links: A → B → C → A
- Self-links: [[Note]] within Note.md
- Broken links: [[NonExistent Note]]
- Aliased links: [[Note|Different Name]]
- Heading links: [[Note#Section]]
- Block links: [[Note#^block123]]
```

#### fixtures/edge_cases/malformed/
```
- Invalid YAML frontmatter
- Unclosed code blocks
- Malformed links: [[Incomplete
- Mixed line endings (CRLF vs LF)
- Empty files
- Files with only frontmatter
```

## Performance Benchmarks

### Performance Test Suite

```python
class PerformanceTests:
    """Benchmark critical operations"""

    def test_benchmark_initial_sync(self, large_vault):
        """Measure initial sync time for 1000 notes"""
        # Target: < 2 minutes

    def test_benchmark_incremental_sync(self, vault_with_one_change):
        """Measure incremental sync with 1 changed file"""
        # Target: < 1 second

    def test_benchmark_embedding_computation(self, notes_1000):
        """Measure embedding computation for 1000 notes"""
        # Target: ~100 seconds (0.1s per note)

    def test_benchmark_semantic_search(self, vault_with_embeddings):
        """Measure k-NN search time"""
        # Target: < 100ms for k=10

    def test_benchmark_graph_query(self, large_vault):
        """Measure graph operation time"""
        # Target: < 50ms for unlinked_pairs

    def test_benchmark_geist_execution(self, all_geists):
        """Measure total geist execution time"""
        # Target: < 30 seconds for 100 geists

    def test_benchmark_session_creation(self, vault_1000):
        """Measure complete session creation"""
        # Target: < 3 minutes total (sync + embeddings + execution)
```

## Test Execution Strategy

### Test Organization
```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/integration/test_kepano_vault.py

# Run specific test
pytest tests/unit/test_vault.py::test_parse_note_with_links

# Run with coverage
pytest --cov=geistfabrik --cov-report=html

# Run performance benchmarks
pytest tests/performance/ --benchmark-only
```

### Continuous Integration

```yaml
# .github/workflows/test.yml (example)
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]

    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run unit tests
        run: pytest tests/unit/ -v

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Generate coverage report
        run: pytest --cov=geistfabrik --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### Test Data Management

```bash
# Keep test data in Git LFS for larger vaults
git lfs track "tests/fixtures/large_vault/**/*.md"

# Generate synthetic test data
python scripts/generate_test_vault.py --notes 1000 --output tests/fixtures/large_vault

# Update kepano test data
python scripts/update_kepano_subset.py
```

## Success Metrics

### Coverage Targets
- **Unit tests**: >90% code coverage
- **Integration tests**: All major workflows covered
- **Edge cases**: All known edge cases have tests

### Quality Gates
- All tests pass before merge
- No decrease in code coverage
- Performance benchmarks within targets
- No new linting errors

### Documentation
- Every test has clear docstring
- Complex scenarios have inline comments
- README explains how to run tests
- Failure messages are actionable

## Future Test Additions

When implementing new features:

1. **Geist rotation system**: Test rotating through 100+ geists
2. **Pruning system**: Test session embedding pruning logic
3. **Conflict resolution**: Test metadata key conflict detection
4. **Export/import**: Test vault portability
5. **Multi-vault support**: Test working with multiple vaults
6. **Plugin system**: Test loading third-party extensions
7. **Real-time sync**: Test file watching for live updates
8. **Advanced Tracery**: Test custom modifiers, complex grammars
9. **Clustering algorithms**: Test various clustering approaches
10. **Natural language geists**: Test LLM-based geists (if added)

## Test Development Guidelines

1. **Test naming**: `test_<component>_<scenario>_<expected_result>`
2. **Arrange-Act-Assert**: Clear structure in every test
3. **One assertion per test**: Or related assertions only
4. **Fixtures over setup**: Use pytest fixtures, not setup/teardown
5. **Isolation**: Tests don't depend on each other
6. **Fast tests**: Unit tests run in milliseconds
7. **Realistic data**: Integration tests use realistic vaults
8. **Error messages**: Assertion messages explain what failed
9. **Parameterization**: Use `@pytest.mark.parametrize` for variations
10. **Mocking**: Mock external dependencies (file I/O, network)

---

This testing plan ensures GeistFabrik is thoroughly tested at every layer, from individual functions to complete end-to-end workflows, using both synthetic minimal examples and realistic test data from the kepano vault.
