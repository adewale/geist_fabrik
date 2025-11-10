# Sentence-Transformers Models

This directory contains bundled sentence-transformers models for offline use.

## Current State

✅ **Models are pre-bundled in this repository via Git LFS**

When you clone this repository with Git LFS installed, the models are automatically downloaded. GeistFabrik checks for models in this directory first before falling back to HuggingFace cache.

- **Model files tracked with Git LFS**: `model.safetensors` (87MB), `tokenizer.json` (695KB)
- **Local-first**: Models loaded from `models/all-MiniLM-L6-v2/` directory
- **Fallback**: Automatic download from HuggingFace if local models not found

## Current Model

- **all-MiniLM-L6-v2**: A lightweight sentence embedding model (~80-90MB)
  - 384-dimensional embeddings
  - Fast inference
  - Good balance of speed and quality

## Re-downloading the Model

If you need to re-download the model (e.g., after deleting it):

```bash
# From the project root
uv run python scripts/download_model.py
```

This will download the model from HuggingFace and save it to `models/all-MiniLM-L6-v2/`.

**Note**: You typically don't need to run this command. The models are already bundled in the repository via Git LFS.

## Git LFS Setup

✅ **Git LFS is already configured for this repository**

Model files are tracked with Git LFS in `.gitattributes`:
- `models/**/*.safetensors` - Model weights (87MB)
- `models/**/tokenizer.json` - Tokenizer file (695KB)

To clone this repository with models:

```bash
# Install Git LFS (one-time setup, if not already installed)
git lfs install

# Clone repository (models download automatically via LFS)
git clone https://github.com/adewale/geist_fabrik.git

# Verify models are present
ls -lh models/all-MiniLM-L6-v2/
```

## Fallback Behaviour

If the local model is not found, GeistFabrik will automatically download it from HuggingFace on first use. The local model is checked first to enable:

1. **Offline usage** - No internet connection required
2. **Faster startup** - No download wait time
3. **Reproducibility** - Guaranteed model version
4. **Privacy** - No external API calls

## File Structure

```
models/
└── all-MiniLM-L6-v2/
    ├── config.json
    ├── config_sentence_transformers.json
    ├── model.safetensors  (or pytorch_model.bin)
    ├── tokenizer_config.json
    ├── tokenizer.json
    ├── special_tokens_map.json
    └── vocab.txt
```

## Model Size

The complete model directory is approximately **80-90MB**, consisting of:
- Model weights: ~85MB
- Tokenizer files: ~1MB
- Config files: <1MB
