# GeistFabrik for Early Adopters

**Welcome, brave soul!** 🎉

This guide shows you how to safely test GeistFabrik (v0.9.0 Beta) and provide valuable feedback.

## What to Expect

**Current Status:**
- ✅ 132 tests passing (beta quality)
- ✅ All core features implemented
- ✅ 17 example geists included
- ✅ Read-only vault access (your notes are safe)

**Expect:**
- Rough edges in CLI output
- Occasional unclear error messages
- Performance not optimized for 1000+ notes

**Won't happen:**
- Data loss (GeistFabrik never modifies your notes)
- Network requests (100% local processing)
- Silent failures (comprehensive error handling)

---

## Three Ways to Test Safely

### Option 1: Sample Vault (Safest - Start Here)

Perfect for first-time exploration. Zero risk to your personal vault.

```bash
# 1. Install GeistFabrik
git clone https://github.com/adewale/geist_fabrik.git
cd geist_fabrik
uv sync

# 2. Initialize sample vault
uv run geistfabrik init testdata/kepano-obsidian-main --examples

# 3. Run geists and view suggestions
uv run geistfabrik invoke --vault testdata/kepano-obsidian-main --write

# 4. Inspect results
cat "testdata/kepano-obsidian-main/geist journal"/*.md
ls -la testdata/kepano-obsidian-main/_geistfabrik/

# 5. Clean up
rm -rf testdata/kepano-obsidian-main/_geistfabrik
rm -rf "testdata/kepano-obsidian-main/geist journal"
```

**Time:** 15 minutes
**Risk:** None

---

### Option 2: Test Vault Copy (Recommended for Real Testing)

Create a copy of your vault for realistic testing without risk.

```bash
# 1. Create test copy
cp -r ~/Documents/MyVault ~/Documents/MyVault-Test

# 2. Initialize GeistFabrik
uv run geistfabrik init ~/Documents/MyVault-Test --examples

# 3. Preview suggestions (read-only, no files created)
uv run geistfabrik invoke --vault ~/Documents/MyVault-Test

# 4. Check for similar suggestions (diff mode)
uv run geistfabrik invoke --vault ~/Documents/MyVault-Test --diff

# 5. Write session note
uv run geistfabrik invoke --vault ~/Documents/MyVault-Test --write

# 6. Open in Obsidian
# Add ~/Documents/MyVault-Test as vault
# Browse to "geist journal/" folder

# 7. Test individual geists
uv run geistfabrik test temporal_drift --vault ~/Documents/MyVault-Test
uv run geistfabrik test creative_collision --vault ~/Documents/MyVault-Test

# 8. Clean up when done
rm -rf ~/Documents/MyVault-Test
```

**Time:** 1-2 hours
**Risk:** None (copy is disposable)

---

### Option 3: Your Real Vault (For Confident Users)

Use your actual vault. Safe because GeistFabrik is read-only.

```bash
# Optional: Backup first
cp -r ~/Documents/MyVault ~/Documents/MyVault.backup

# 1. Initialize with confirmation prompts
uv run geistfabrik init ~/Documents/MyVault --examples
# You'll see warnings about what GeistFabrik will/won't do

# 2. Preview suggestions (read-only, no files created)
uv run geistfabrik invoke --vault ~/Documents/MyVault

# 3. Compare to previous sessions
uv run geistfabrik invoke --vault ~/Documents/MyVault --diff

# 4. Write your first session note
uv run geistfabrik invoke --vault ~/Documents/MyVault --write

# 5. View in Obsidian
# Navigate to "geist journal/" folder
# Open today's date (YYYY-MM-DD.md)

# 6. Remove if not for you
rm -rf ~/Documents/MyVault/_geistfabrik
rm -rf ~/Documents/MyVault/"geist journal"
# (Your original notes are untouched)
```

**Time:** Ongoing exploration
**Risk:** Very low (read-only access)

---

## What Gets Created

After `geistfabrik init ~/MyVault --examples`:

```
MyVault/
├── _geistfabrik/                    # GeistFabrik's directory
│   ├── vault.db                     # SQLite (notes + embeddings)
│   ├── geists/
│   │   ├── code/                    # 10 Python geists
│   │   └── tracery/                 # 7 YAML geists
│   ├── metadata_inference/          # 3 metadata modules
│   └── vault_functions/             # 2 query functions
└── geist journal/                   # Session notes (--write only)
    └── 2025-10-21.md                # Today's suggestions
```

**Database contents (`vault.db`):**
- Note metadata (titles, links, tags, timestamps)
- Embeddings (384-dim vectors, ~30MB for 1000 notes)
- Session history
- Previous suggestions (for novelty filtering)

**Not stored:**
- Full note content (read on-demand)
- Personal identifiers
- Usage analytics

---

## Safety Features You'll See

### 1. First-Run Warnings

```
⚠️  GeistFabrik will:
   • Read all markdown files in your vault
   • Create a database at _geistfabrik/vault.db
   • Compute embeddings for all notes (stored locally)
   • Create session notes in 'geist journal/' when you invoke with --write

✅ GeistFabrik will NEVER:
   • Modify your existing notes (read-only access)
   • Send data to the internet (100% local)
   • Delete any files
```

### 2. Summary Stats After Init

```
📊 Vault Summary:
   Notes found: 247
   Database size: 12.34 MB
   Example geists installed: 17
```

### 3. Diff Mode

```bash
uv run geistfabrik invoke --vault ~/MyVault --diff
# 🔍 Diff Mode: Comparing to recent sessions...
#   ✨ New: What if you combined [[Note A]] with [[Note B]]?
#   ⚠️  Similar to recent: Consider revisiting [[Old Note]]...
```

---

## Auditing Your Configuration

Every time you run `geistfabrik invoke`, you'll see a configuration audit at the start:

```
============================================================
GeistFabrik Configuration Audit
============================================================
Vault: /path/to/vault
Geists directory: /path/to/vault/_geistfabrik/geists/code
Total geists found: 17
  - Enabled: 17
Filtering: ENABLED (4-stage pipeline)
Sampling: ENABLED (count=5)
Mode: Default
============================================================
```

This shows:
- **Total geists found**: All `.py` files in the geists directory
- **Enabled/Disabled**: Geists can be auto-disabled after 3 failures
- **Filtering**: Whether the 4-stage filter pipeline is active
- **Sampling**: Whether suggestions are sampled down
- **Mode**: Current invocation mode

If you see fewer geists than expected:
- Check that geists are in `_geistfabrik/geists/code/`
- Look for disabled geists (auto-disabled after failures)
- Check the Execution Summary at the end for errors

---

## Common Questions

**Q: Will this slow down Obsidian?**
A: No. GeistFabrik only runs when you invoke it from terminal. Obsidian never sees it.

**Q: What about large vaults?**
A: Tested on 100+ notes. Initial sync for 1000 notes takes 2-5 minutes. After that, incremental syncs are fast.

**Q: Can I create custom geists?**
A: Yes! Create `_geistfabrik/geists/code/my_geist.py`:

```python
from geistfabrik import Suggestion

def suggest(vault):
    """Your custom logic."""
    suggestions = []

    for note in vault.notes():
        if interesting_condition(note):
            suggestions.append(Suggestion(
                text=f"What if you explored [[{note.title}]] further?",
                notes=[note.title],
                geist_id="my_geist"
            ))

    return vault.sample(suggestions, k=5)
```

Test it: `uv run geistfabrik test my_geist`

**Q: What if a geist crashes?**
A: System continues. Geists have:
- 5-second timeout
- Error isolation (one failure doesn't stop others)
- Execution logs
- Auto-disable after 3 failures

**Q: Can I remove example geists?**
A: Yes! Delete unwanted geists:
```bash
rm ~/MyVault/_geistfabrik/geists/code/temporal_drift.py
```

---

## Providing Feedback

**Most valuable feedback:**

1. **Useful suggestions:** "This geist suggestion was surprisingly helpful because..."
2. **Unexpected behavior:** "I expected X but got Y"
3. **Confusion:** "I couldn't figure out how to..."
4. **Errors:** "This error message confused me:"

**How to report:**
- GitHub Issues: https://github.com/adewale/geist_fabrik/issues
- Include: OS, Python version, GeistFabrik version (0.9.0)
- Steps to reproduce
- Expected vs actual behavior
- Anonymize note titles if needed

---

## Experiment Ideas

### 1. Geist Tournament

Test each geist and rank them:

```bash
for geist in temporal_drift creative_collision bridge_builder; do
    echo "Testing $geist..."
    uv run geistfabrik test $geist
done
```

Which ones resonate? Which feel like noise?

### 2. Custom Geist Development

Create a geist reflecting your thinking:
- Tag archaeologist: Find under-tagged notes
- Link suggester: Connect related notes
- Question extractor: Pull all questions
- Topic mapper: Identify emergent themes

### 3. Temporal Analysis

Run on the same date multiple times:

```bash
# Day 1
uv run geistfabrik invoke --vault ~/MyVault --date 2025-01-15 --write

# Day 30 (vault has evolved)
uv run geistfabrik invoke --vault ~/MyVault --date 2025-01-15 --write --force

# Compare how suggestions changed as your vault grew
```

### 4. Full Geist Firehose (Advanced - Maximum Testing)

⚠️ **DANGER ZONE** ⚠️

Run ALL geists with ALL raw suggestions (no filtering) against a vault copy. This is the most comprehensive test but generates the most output.

**🚨 CRITICAL: Only run against a COPY of your vault, never the original! 🚨**

**Understanding the difference:**
- `--full`: All **filtered** suggestions (quality checks applied, no sampling)
- `--nofilter`: All **raw** suggestions (no filtering, no quality checks)

```bash
# Step 1: Create a fresh copy
cp -r ~/Documents/MyVault ~/Documents/MyVault-FullTest
cd ~/Documents/MyVault-FullTest

# Step 2: Backup (extra safety)
tar -czf ../MyVault-FullTest-backup.tar.gz .

# Step 3: Initialize with all examples
uv run geistfabrik init ~/Documents/MyVault-FullTest --examples

# Step 4a: Try --full first (filtered but not sampled)
uv run geistfabrik invoke --vault ~/Documents/MyVault-FullTest --full --write

# Step 4b: For TRUE firehose, use --nofilter (completely unfiltered)
uv run geistfabrik invoke --vault ~/Documents/MyVault-FullTest --nofilter --write --force

# Step 5: Review the flood of suggestions
cat ~/Documents/MyVault-FullTest/"geist journal"/$(date +%Y-%m-%d).md

# Step 6: Count how many suggestions were generated
grep -c "^## " ~/Documents/MyVault-FullTest/"geist journal"/$(date +%Y-%m-%d).md

# Step 7: Analyze which geists are most active
grep "^## " ~/Documents/MyVault-FullTest/"geist journal"/$(date +%Y-%m-%d).md | \
  sort | uniq -c | sort -rn

# Step 8: Clean up when done
rm -rf ~/Documents/MyVault-FullTest
rm ../MyVault-FullTest-backup.tar.gz
```

**What to expect:**

With `--full` (filtered):
- 10-50 suggestions (quality-checked)
- Redundant suggestions removed
- Notes must exist in vault
- Good for thorough review

With `--nofilter` (raw):
- 50-200+ suggestions (completely unfiltered)
- You'll see EVERYTHING every geist thinks
- May include low-quality, redundant, or broken suggestions
- Some suggestions may reference non-existent notes
- Perfect for understanding raw geist output

**Why this is dangerous:**
- While GeistFabrik never modifies your notes, running with `--nofilter` generates a LOT of data
- The session note can be overwhelming (10+ pages with `--nofilter`)
- You'll see the "raw feed" with all its flaws
- Some geists may crash or timeout (this is expected in beta)

**Best for:**
- Understanding what filtering removes (`--full` vs `--nofilter`)
- Debugging custom geists (see raw output)
- Seeing maximum divergent thinking
- Stress-testing the system
- Understanding vault patterns

**NOT recommended for:**
- Daily use (way too noisy, especially `--nofilter`)
- Your actual vault (use a copy!)
- Production workflows
- First-time users (start with default mode)

---

## Known Limitations (v0.9.0)

1. **Command-line only** - No GUI
2. **English-centric** - Embeddings optimized for English
3. **Obsidian-specific** - Designed for Obsidian vaults
4. **Single vault** - One at a time
5. **Fixed embedding model** - Can't swap without code changes

---

## Emergency Stop

If anything goes wrong:

```bash
# Stop execution: Ctrl+C

# Remove GeistFabrik completely:
rm -rf ~/MyVault/_geistfabrik
rm -rf ~/MyVault/"geist journal"

# Your notes are untouched and safe.
```

---

## Next Steps After Testing

1. **Share feedback** - Open issues for bugs or suggestions
2. **Create custom geists** - Make it yours
3. **Join discussions** - GitHub Discussions
4. **Watch for 1.0** - Coming in 1-2 months

---

**Thank you for testing!** Your feedback shapes how GeistFabrik evolves.

*Let's build a tool that asks different questions than you would ask yourself.*

---

*Last updated: 2025-10-21 (v0.9.0)*
