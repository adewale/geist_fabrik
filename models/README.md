# Sentence-Transformers Models

This directory contains bundled sentence-transformers models for offline use.

## Current Model

- **all-MiniLM-L6-v2**: A lightweight sentence embedding model (~80-90MB)
  - 384-dimensional embeddings
  - Fast inference
  - Good balance of speed and quality

## Downloading the Model

To download the model for offline use:

```bash
# From the project root
python scripts/download_model.py
```

This will download the model from HuggingFace and save it to `models/all-MiniLM-L6-v2/`.

## Git LFS (Recommended)

Since the model files are large (~80-90MB), we recommend using Git LFS:

```bash
# Install Git LFS (one-time setup)
git lfs install

# Track model files with LFS
git lfs track "models/**/*.bin"
git lfs track "models/**/*.safetensors"

# Add and commit
git add .gitattributes models/
git commit -m "Add bundled sentence-transformers model"
```

## Fallback Behavior

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
