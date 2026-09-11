# Troubleshooting

Common issues and fixes. See also [CONFIGURATION.md](CONFIGURATION.md).

## "Failed to download" / hangs on first run

The bundled embedding model is a Git-LFS file. If you cloned without LFS,
GeistFabrik downloads it from HuggingFace on first run.
- Pull the model: `git lfs pull`.
- Or work fully offline: set `GEISTFABRIK_OFFLINE=1` (also honours
  `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1`). In offline mode a missing
  local model fails loudly instead of trying the network.

## A geist stopped producing suggestions / "disabled after N failures"

Geists are disabled after `geist_execution.max_failures` (default 3)
*consecutive* failures, persisted in `geist_status`. Re-enable by:
- Fixing the geist — the next successful run resets its count; or
- `geistfabrik test <geist_id> <vault>` (a passing run clears it); or
- `rm -rf <vault>/_geistfabrik/vault.db*` to reset all state (rebuilds on next
  invoke).

See the last error with `geistfabrik invoke <vault> --verbose` (or `--debug`).

## No suggestions at all

- Many geists need a minimum vault size (e.g. 10-50 notes) or links; tiny
  vaults legitimately produce nothing.
- Check geists aren't all disabled in `config.yaml` (`default_geists:`).
- Run one geist directly: `geistfabrik test <geist_id> <vault>`.
- Notes under `filtering.boundary.exclude_paths` never surface — make sure you
  didn't exclude the folder you're testing.

## A geist is slow / times out

- `geistfabrik invoke <vault> --debug` prints per-geist timings and a diagnostic
  for any geist over 80% of the timeout.
- Raise the limit with `--timeout 60` or `geist_execution.timeout` in config.
- On large vaults (5000+ notes) try the sqlite-vec backend: install the
  `[vector-search]` extra and set `vector_search.backend: sqlite-vec`.

## Suggestions reference notes I deleted / wrong deeplinks

GeistFabrik syncs incrementally on each run. If references look stale, the
database may predate a breaking change — rebuild it:
`rm -rf <vault>/_geistfabrik/vault.db*` then `geistfabrik invoke <vault>`.

If synchronization instead reports that vault files changed repeatedly, an
editor, sync client, or other process modified Markdown during all bounded
snapshot attempts. Let that activity settle and rerun the command. No partial
database mirror from the failed attempts is committed.

## SQLite reports that the database is malformed or corrupt

GeistFabrik fails closed and leaves a malformed database untouched. It does not
pretend that creating a different empty database recovers the original data.

1. Stop commands that use the vault.
2. Preserve `_geistfabrik/vault.db` and any adjacent `-wal`/`-shm` files for
   diagnosis; do not overwrite them in place.
3. Restore a known-good backup if you need session embeddings, suggestion
   history, cached metrics, or geist failure state.
4. If losing that history is acceptable, move the damaged database and its
   companion files out of `_geistfabrik/`, then invoke GeistFabrik to rebuild
   current note-derived state from Markdown.

SQLite's `PRAGMA integrity_check` can diagnose damage but is not a recovery
mechanism. Automatic recovery of arbitrary corruption is not supported.

## Database is growing

Each session stores one embedding per note. `session_embedding_retention`
(default 730 sessions) bounds this; lower it on large or daily-updated vaults.

## `geistfabrik invoke` can't find my vault

`invoke`/`stats`/`validate` auto-detect the vault by walking up to a
`.obsidian` directory. Run from inside the vault, or pass the path explicitly.

## Validation / CI

Run `./scripts/validate.sh` before pushing — it mirrors CI (ruff, mypy
`--strict`, unused-table check, bandit, unit + integration). See CLAUDE.md.
