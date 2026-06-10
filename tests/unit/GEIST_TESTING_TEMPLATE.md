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

   Never `datetime.now()` in fixtures: session embeddings include a
   session-season feature, so wall-clock fixtures literally compute
   different embeddings depending on the calendar day the tests run.
   Backdate notes via `UPDATE notes SET created = ?, modified = ?` relative
   to SESSION_DATE (see tests/unit/test_builtin_metadata.py for the pattern).

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

Unit tests run under `SentenceTransformerStub` (SHA256-derived, deterministic,
unit-norm). Useful consequences when designing trigger fixtures:

- Identical text ⇒ similarity 1.0. Near-duplicate content is how you
  guarantee a "high similarity" trigger fires under the stub.
- Different text ⇒ effectively random similarity around 0. Do not write
  fixtures that need two *different* texts to be "similar" — that is not
  controllable under the stub; restructure the test or mark it `slow`.

## Minimum viable test file (~40 lines of intent)

```python
"""Tests for my_geist."""

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from geistfabrik import Session, Vault
from geistfabrik.default_geists.code import my_geist
from geistfabrik.vault_context import VaultContext
from tests.fixtures.helpers import assert_valid_suggestions

SESSION_DATE = datetime(2024, 3, 15)


def make_context(notes: dict[str, str], backdate_days: int = 0) -> VaultContext:
    tmpdir = TemporaryDirectory()
    vault_path = Path(tmpdir.name)
    for name, content in notes.items():
        (vault_path / name).write_text(content)
    vault = Vault(str(vault_path), ":memory:")
    vault.sync()
    if backdate_days:
        old = SESSION_DATE - timedelta(days=backdate_days)
        vault.db.execute(
            "UPDATE notes SET created = ?, modified = ?", (old.isoformat(), old.isoformat())
        )
        vault.db.commit()
    session = Session(SESSION_DATE, vault.db)
    session.compute_embeddings(vault.all_notes())
    ctx = VaultContext(vault, session, seed=20240315)
    ctx._tmpdir = tmpdir  # keep tempdir alive
    return ctx


def test_fires_on_designed_trigger():
    # Trigger arithmetic: my_geist needs >= 3 stale linked notes;
    # 300-day backdate gives staleness ~0.91 (> 0.7 threshold).
    ctx = make_context({...}, backdate_days=300)
    suggestions = my_geist.suggest(ctx)
    assert_valid_suggestions(suggestions, "my_geist", must_reference=["Planted Note"])


def test_below_threshold_is_empty():
    ctx = make_context({...two notes only...})
    assert my_geist.suggest(ctx) == []
```

## Self-check before committing

Scan your new file for: assertions that all live inside a `for`/`if` over
possibly-empty output; any `datetime.now()`; any `assert len(x) >= 0`; any
absolute elapsed-time assert. Then run:

```bash
uv run pytest tests/unit/test_<geist>.py -m "not slow and not benchmark"
./scripts/validate.sh
```
