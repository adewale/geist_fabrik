# Geist Testing Template

How to write a geist test that can actually fail. The previous version of
this template taught patterns that pass on dead geists (`assert len(x) >= 0`,
assertions inside `for s in suggestions:` loops over possibly-empty lists) —
several bundled geists shipped broken with green tests as a result. Follow
the rules below instead; they are distilled from the testing-best-practices
research (weak-oracle and always-true-condition anti-patterns, designed-to-
trigger fixtures, deterministic time).

## The Iron Rules

1. **Designed-to-trigger fixture.** Every test file has at least one fixture
   *constructed so the geist's trigger condition provably holds*, with a
   comment stating the trigger arithmetic ("staleness > 0.7 needs
   days_since_modified > 70; this fixture backdates 300 days"). If you cannot
   build a fixture that makes the geist fire, you do not yet understand the
   trigger condition — resolve that before writing tests.

2. **The happy-path test asserts NON-EMPTY output.**

   ```python
   suggestions = my_geist.suggest(context)
   assert suggestions, "fixture is designed to trigger; empty output means the geist is dead"
   ```

   Never `assert len(x) >= 0` (always true). Loops over suggestions are
   permitted only AFTER a non-emptiness assertion in the same test.
   Tests that are genuinely about emptiness (empty vault, below threshold)
   keep their `== []` asserts — that is the one legitimate use.

3. **Behavioral assertions about content, not just shape.** At least one test
   ties output to fixture specifics: the suggestion references the notes the
   fixture planted, the text mentions the planted pattern, counts respect the
   geist's documented caps. Type/shape checks (`isinstance`, `hasattr`) go
   through the shared helper, never hand-rolled:

   ```python
   from tests.fixtures.helpers import assert_valid_suggestions

   assert_valid_suggestions(suggestions, "my_geist", must_reference=["Planted Note"])
   ```

4. **Exclusion tests verify BOTH directions.** A journal-exclusion test that
   only asserts "no journal refs" passes on a dead geist. Plant both journal
   notes AND triggering regular notes; assert the regular notes appear and
   the journal notes do not (`assert_valid_suggestions` does the "not"
   direction via `must_not_reference`).

5. **Pinned time, pinned seed — never wall-clock.** Build sessions at a fixed
   date and pass an explicit seed, so a failure replays exactly:

   ```python
   SESSION_DATE = datetime(2024, 3, 15)
   SEED = 20240315
   ```

   Never `datetime.now()` in fixtures: built-in metadata (`age_days`,
   `days_since_modified`, `staleness`) is measured from the session date, so
   notes dated from the wall clock land on different sides of a geist's
   thresholds depending on the day the tests run. (Stored session embeddings
   also carry calendar features; they are never compared, but they change
   the stored bytes.)
   Backdate notes with `VaultBuilder.note(..., created=..., modified=...)`
   (`tests/fixtures/helpers.py`), relative to `SESSION_DATE`; session history
   comes from `.build(history=[...])` and `tests/fixtures/temporal.py`.

6. **Boundary pair for thresholds.** If the geist needs N of something,
   write the pair: N-1 → `[]`, N → non-empty. This turns "insufficient data"
   from a vague test into a specification of the threshold.

7. **Determinism check.** Same seed + same session date ⇒ identical
   suggestion texts across two VaultContexts. (Only needed per-geist when the
   geist has randomness beyond `vault.sample`/`vault.rng`.)

8. **Regression tests are named for the bug and written before the fix.**
   `test_<geist>_<one_line_bug>_issue_<n>()`, with the original symptom in
   the docstring.

9. **No boilerplate.** Do NOT copy a `clear_global_registry` fixture (a
   shared autouse fixture in tests/conftest.py handles it). Do NOT assert
   absolute wall-clock durations (`elapsed < 2.0` is CI-flake bait; assert
   the *behaviour* — status, log entry, return value — instead).

## Stub-embedding facts you can exploit

Unit tests run under `SentenceTransformerStub` (`tests/stubs.py`), a
deterministic bag-of-words embedding. Similarity tracks shared vocabulary:

- Identical text ⇒ similarity 1.0.
- Notes that share most of their content words are highly similar; notes with
  disjoint vocabulary are near 0. To make two *different* notes "similar",
  give them a common block of distinctive words; to keep notes apart, give
  them disjoint vocabulary.
- Words shorter than three characters and a few stopwords are ignored.

## Backdating notes

`Note.created` is the note's frontmatter `created:`, else a date at the start
of its file name (`2023-09-12.md`), else the earliest of the file's mtime,
ctime and (where the platform records it) birth time. `Note.modified` is
frontmatter `modified:`, else `updated:`, else the mtime. So for an undated
note, `os.utime(path, (t, t))` before `vault.sync()` backdates both `created`
and `modified`; a declared date wins over file timestamps. `VaultBuilder`
does this for you, and when given both `created` and `modified` it also
writes them into the database after syncing, so they can differ (see rule 5).

## Minimum viable test file (~40 lines of intent)

```python
"""Tests for my_geist."""

from datetime import timedelta
from pathlib import Path

from geistfabrik.default_geists.code import my_geist
from tests.fixtures.helpers import SESSION_DATE, VaultBuilder, assert_valid_suggestions


def test_fires_on_designed_trigger(tmp_path: Path) -> None:
    # Trigger arithmetic: my_geist needs >= 3 stale linked notes; a 300-day
    # backdate gives staleness ~0.91 (> 0.7 threshold).
    old = SESSION_DATE - timedelta(days=300)
    builder = VaultBuilder(tmp_path)
    for i in range(3):
        builder.note(f"Planted {i}", f"Old idea {i} [[Planted {(i + 1) % 3}]]", created=old)
    builder.journal("2024-03-14", "Session output that must never be suggested")

    suggestions = my_geist.suggest(builder.build())

    assert_valid_suggestions(suggestions, "my_geist", must_reference=["Planted 0"])


def test_below_threshold_is_empty(tmp_path: Path) -> None:
    old = SESSION_DATE - timedelta(days=300)
    builder = VaultBuilder(tmp_path)
    for i in range(2):  # one short of the trigger
        builder.note(f"Planted {i}", f"Old idea {i} [[Planted {1 - i}]]", created=old)

    assert my_geist.suggest(builder.build()) == []
```

## Self-check before committing

Scan your new file for: assertions that all live inside a `for`/`if` over
possibly-empty output; any `datetime.now()`; any `assert len(x) >= 0`; any
absolute elapsed-time assert. Then run:

```bash
uv run pytest tests/unit/test_<geist>.py -m "not slow and not benchmark"
./scripts/validate.sh
```
