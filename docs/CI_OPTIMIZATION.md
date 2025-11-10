# CI Optimisation Summary

## Problem Analysis

CI builds were taking 14-19 minutes due to:

### 1. **Large Dependency Downloads (Primary Issue)**
- **Root Cause**: Installing PyTorch with CUDA support downloads 2.4GB+ of nvidia-* packages
- **Impact**: 6 matrix jobs × 2.4GB = 14.4GB total downloads per CI run
- **Details**:
  - torch: 858MB
  - nvidia-cudnn-cu12: 674MB
  - nvidia-cusparselt-cu12: 273MB
  - nvidia-nccl-cu12: 307MB
  - nvidia-cufft-cu12: 184MB
  - nvidia-cuda-nvrtc-cu12: 84MB
  - Plus 10+ additional nvidia packages

### 2. **Excessive Test Matrix**
- **Root Cause**: Testing on 3 operating systems × 2 Python versions = 6 parallel jobs
- **Impact**: All 6 jobs download dependencies independently
- **Necessity**: Don't need full cross-product for every commit

### 3. **Insufficient Caching**
- **Root Cause**: sentence-transformers model (all-MiniLM-L6-v2) downloaded on first test run
- **Impact**: Additional ~90MB download + model initialisation time per job

## Solutions Implemented

### Solution 1: Reduce Test Matrix (33% fewer jobs)
**Before**: 6 jobs (3 OS × 2 Python)
**After**: 4 jobs (Linux × 2 Python + macOS + Windows)

**Rationale**:
- Linux is the primary deployment platform → test both Python 3.11 and 3.12
- macOS/Windows are secondary → test Python 3.11 only
- Reduces total job count from 6 to 4 (33% reduction)

**Changes**:
```yaml
strategy:
  matrix:
    os: [ubuntu-latest]
    python-version: ["3.11", "3.12"]
    include:
      - os: macos-latest
        python-version: "3.11"
      - os: windows-latest
        python-version: "3.11"
```

### Solution 2: Add Model Caching
**Added**: GitHub Actions cache for sentence-transformers models

**Changes**:
```yaml
- name: Cache sentence-transformers models
  uses: actions/cache@v4
  with:
    path: ~/.cache/torch/sentence_transformers
    key: ${{ runner.os }}-sentence-transformers-${{ hashFiles('**/pyproject.toml') }}
    restore-keys: |
      ${{ runner.os }}-sentence-transformers-
```

**Impact**:
- First run: Downloads model (~90MB, ~30s)
- Subsequent runs: Uses cached model (~1s)

### Solution 3: Dependency Caching (Already Enabled)
`setup-uv@v5` with `enable-cache: true` already caches Python dependencies.

**How it works**:
- First run: Downloads all dependencies including CUDA packages (~2.4GB, ~5-10 minutes)
- Subsequent runs: Uses cached packages if lockfile unchanged (~30s)

## Expected Results

### First Run (Cold Cache)
- **Before**: 14-19 minutes
- **After**: 10-12 minutes (matrix reduction benefit only)
- **Breakdown**:
  - Dependency install: ~8 minutes (CUDA packages)
  - Model download: ~30 seconds
  - Tests: ~2 minutes
  - Linting/type checking: ~1 minute

### Subsequent Runs (Warm Cache)
- **Target**: 2-4 minutes
- **Breakdown**:
  - Dependency install: ~30 seconds (cached)
  - Model load: ~1 second (cached)
  - Tests: ~2 minutes
  - Linting/type checking: ~1 minute

### Cache Invalidation
Cache is invalidated when:
- `uv.lock` changes (dependency updates)
- `pyproject.toml` changes (model cache key)
- Cache expires (GitHub Actions deletes caches after 7 days of no access)

## Why We Didn't Eliminate CUDA Packages

### Attempted Solution: CPU-only PyTorch
We tried several approaches to install CPU-only PyTorch:
1. Using `--index-url https://download.pytorch.org/whl/cpu`
2. Pre-installing torch before `uv sync`
3. Filtering torch from requirements and installing separately

### Why It Didn't Work
- uv's lockfile (`uv.lock`) already has torch with CUDA dependencies resolved
- `uv sync` installs exactly what's in the lockfile
- Overriding the index URL during sync doesn't work with locked dependencies
- CPU-only packages would save ~2GB per install but add complexity

### Trade-off Decision
**Caching is Good Enough**:
- First run penalty: 8-10 minutes for dependency install
- Subsequent runs: ~30 seconds with cache
- Most CI runs will hit the cache
- Simpler workflow is easier to maintain

### Future Optimisation
If first-run times become problematic, we can:
1. Create a CPU-only lockfile specifically for CI
2. Use pip instead of uv in CI (doesn't respect lockfile)
3. Self-hosted runners with pre-populated cache
4. Split into separate "quick" and "full" CI workflows

## Monitoring

Track these metrics in CI runs:
- Total workflow duration
- Dependency install time (should be ~30s with cache, ~8min without)
- Test execution time (should stay ~2min)
- Cache hit rate (should be >80% once stabilized)

## Related Issues

- Process leak issue: Fixed in commits `efedcd0` and `beafb28`
- Thread limits: Added in `.github/workflows/test.yml` and `src/geistfabrik/embeddings.py`
