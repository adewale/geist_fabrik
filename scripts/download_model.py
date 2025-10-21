#!/usr/bin/env python3
"""Download the sentence-transformers model for offline use.

This script downloads the all-MiniLM-L6-v2 model from HuggingFace and saves it
to the models/ directory. Run this once to enable offline model usage.

Usage:
    python scripts/download_model.py
"""

import sys
from pathlib import Path

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("❌ sentence-transformers not installed")
    print("   Run: pip install sentence-transformers")
    sys.exit(1)


def download_model():
    """Download the model to local directory."""
    model_name = "all-MiniLM-L6-v2"
    local_path = Path(__file__).parent.parent / "models" / model_name

    print(f"📥 Downloading {model_name}...")
    print("   This will download ~80-90MB from HuggingFace")
    print(f"   Saving to: {local_path}")

    try:
        # Download model
        model = SentenceTransformer(model_name)

        # Save to local directory
        local_path.parent.mkdir(parents=True, exist_ok=True)
        model.save(str(local_path))

        print("✅ Model saved successfully!")
        print(f"   Location: {local_path}")

        # Check size
        import subprocess

        result = subprocess.run(["du", "-sh", str(local_path)], capture_output=True, text=True)
        if result.returncode == 0:
            size = result.stdout.split()[0]
            print(f"   Size: {size}")

        print("\n📝 Next steps:")
        print("   1. Add to git: git add models/")
        print("   2. Commit: git commit -m 'Add bundled sentence-transformers model'")
        print("   3. (Optional) Use Git LFS for large files: git lfs track 'models/**/*.bin'")

        return True

    except Exception as e:
        print(f"❌ Download failed: {e}")
        print("\nPossible issues:")
        print("  - No internet connection")
        print("  - HuggingFace is down or blocked")
        print("  - Network firewall blocking access")
        return False


if __name__ == "__main__":
    success = download_model()
    sys.exit(0 if success else 1)
