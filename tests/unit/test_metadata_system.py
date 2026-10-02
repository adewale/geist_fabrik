"""Tests for metadata inference system (Phase 8)."""

import tempfile
from pathlib import Path
from typing import cast

import pytest

from geistfabrik import (
    MetadataConflictError,
    MetadataLoader,
    Note,
)
from geistfabrik.vault_context import VaultContext


def test_metadata_loader_initialization() -> None:
    """Test MetadataLoader initialisation."""
    loader = MetadataLoader(Path("/nonexistent"))
    assert loader.module_dir == Path("/nonexistent")
    assert loader.modules == {}


def test_metadata_loader_no_directory() -> None:
    """Test MetadataLoader with non-existent directory."""
    loader = MetadataLoader(Path("/nonexistent"))
    loader.load_modules()  # Should not raise
    assert len(loader.modules) == 0


def test_metadata_loader_empty_directory() -> None:
    """Test MetadataLoader with empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        loader = MetadataLoader(Path(tmpdir))
        loader.load_modules()
        assert len(loader.modules) == 0


def test_load_valid_metadata_module() -> None:
    """Test loading a valid metadata module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        # Create a valid metadata module
        module_file = module_dir / "test_module.py"
        module_file.write_text("""
def infer(note, vault):
    return {"test_key": "test_value"}
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        assert "test_module" in loader.modules
        assert callable(loader.modules["test_module"])


def test_load_module_without_infer_function() -> None:
    """Test loading module without infer function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "bad_module.py"
        module_file.write_text("""
def some_other_function():
    pass
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()  # Should skip invalid module

        assert "bad_module" not in loader.modules


def test_load_module_with_syntax_error() -> None:
    """Test loading module with syntax errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "syntax_error.py"
        module_file.write_text("""
def infer(note, vault):
    return {invalid syntax here
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()  # Should skip module with syntax error

        assert "syntax_error" not in loader.modules


def test_infer_all_basic() -> None:
    """Test basic metadata inference."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "basic.py"
        module_file.write_text("""
def infer(note, vault):
    return {
        "word_count_custom": len(note.content.split()),
        "has_title": bool(note.title)
    }
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        # Create a dummy note
        from datetime import datetime

        note = Note(
            path="test.md",
            title="Test Note",
            content="Hello world this is a test",
            links=[],
            tags=[],
            created=datetime.now(),
            modified=datetime.now(),
        )

        # Create a mock vault context (minimal)
        class MockVault:
            pass

        metadata, failed_modules = loader.infer_all(note, cast(VaultContext, MockVault()))

        assert metadata["word_count_custom"] == 6
        assert metadata["has_title"] is True
        assert failed_modules == []


def test_metadata_conflict_detection() -> None:
    """Test that metadata key conflicts are detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        # Create two modules with conflicting keys
        module1 = module_dir / "module1.py"
        module1.write_text("""
def infer(note, vault):
    return {"conflicting_key": "value1"}
""")

        module2 = module_dir / "module2.py"
        module2.write_text("""
def infer(note, vault):
    return {"conflicting_key": "value2"}
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        from datetime import datetime

        note = Note(
            path="test.md",
            title="Test",
            content="Test",
            links=[],
            tags=[],
            created=datetime.now(),
            modified=datetime.now(),
        )

        class MockVault:
            pass

        # Should raise conflict error
        with pytest.raises(MetadataConflictError):
            loader.infer_all(note, cast(VaultContext, MockVault()))


def test_module_returns_non_dict() -> None:
    """Test handling of module returning non-dict."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "bad_return.py"
        module_file.write_text("""
def infer(note, vault):
    return "not a dict"
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        from datetime import datetime

        note = Note(
            path="test.md",
            title="Test",
            content="Test",
            links=[],
            tags=[],
            created=datetime.now(),
            modified=datetime.now(),
        )

        class MockVault:
            pass

        # Should skip module with invalid return
        metadata, failed_modules = loader.infer_all(note, cast(VaultContext, MockVault()))
        assert len(metadata) == 0
        assert "bad_return" in failed_modules


def test_module_runtime_error() -> None:
    """Test handling of runtime errors in modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "runtime_error.py"
        module_file.write_text("""
def infer(note, vault):
    raise ValueError("Something went wrong")
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        from datetime import datetime

        note = Note(
            path="test.md",
            title="Test",
            content="Test",
            links=[],
            tags=[],
            created=datetime.now(),
            modified=datetime.now(),
        )

        class MockVault:
            pass

        # Should skip module with runtime error
        metadata, failed_modules = loader.infer_all(note, cast(VaultContext, MockVault()))
        assert len(metadata) == 0
        assert "runtime_error" in failed_modules


def test_is_valid_value() -> None:
    """Test metadata value validation."""
    loader = MetadataLoader(None)

    # Valid types
    assert loader._is_valid_value(None) is True
    assert loader._is_valid_value("string") is True
    assert loader._is_valid_value(123) is True
    assert loader._is_valid_value(45.6) is True
    assert loader._is_valid_value(True) is True
    assert loader._is_valid_value([1, 2, 3]) is True
    assert loader._is_valid_value({"key": "value"}) is True

    # Invalid types
    assert loader._is_valid_value(object()) is False
    assert loader._is_valid_value(lambda x: x) is False


def test_get_module_keys() -> None:
    """Test getting keys provided by a module."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "test.py"
        module_file.write_text("""
def infer(note, vault):
    return {"key1": 1, "key2": 2}
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        from datetime import datetime

        note = Note(
            path="test.md",
            title="Test",
            content="Test",
            links=[],
            tags=[],
            created=datetime.now(),
            modified=datetime.now(),
        )

        class MockVault:
            pass

        loader.infer_all(note, cast(VaultContext, MockVault()))

        keys = loader.get_module_keys("test")
        assert "key1" in keys
        assert "key2" in keys


def test_clear_cache() -> None:
    """Test clearing the key-to-module mapping cache."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "test.py"
        module_file.write_text("""
def infer(note, vault):
    return {"cached_key": "value"}
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        from datetime import datetime

        note = Note(
            path="test.md",
            title="Test",
            content="Test",
            links=[],
            tags=[],
            created=datetime.now(),
            modified=datetime.now(),
        )

        class MockVault:
            pass

        loader.infer_all(note, cast(VaultContext, MockVault()))
        assert len(loader._key_to_module) > 0

        loader.clear_cache()
        assert len(loader._key_to_module) == 0


def test_skip_private_modules() -> None:
    """Test that private modules (starting with _) are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        private_module = module_dir / "_private.py"
        private_module.write_text("""
def infer(note, vault):
    return {"should_not_load": True}
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules()

        assert "_private" not in loader.modules


def test_enabled_modules_filter() -> None:
    """Test loading only enabled modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module1 = module_dir / "enabled.py"
        module1.write_text("""
def infer(note, vault):
    return {"enabled": True}
""")

        module2 = module_dir / "disabled.py"
        module2.write_text("""
def infer(note, vault):
    return {"disabled": True}
""")

        loader = MetadataLoader(module_dir)
        loader.load_modules(enabled_modules=["enabled"])

        assert "enabled" in loader.modules
        assert "disabled" not in loader.modules


def test_analyser_outliers_most_extreme_first_within_a_population(tmp_path: Path) -> None:
    """outliers() orders by |z| (most extreme first) and honours `notes`.

    Regression: outliers came back in vault order, so a geist taking
    outliers[0] as "the most extreme" could name a milder one.
    """
    from geistfabrik.metadata_system import MetadataAnalyser
    from tests.fixtures.helpers import VaultBuilder

    builder = VaultBuilder(tmp_path)
    for i in range(20):
        builder.note(f"Plain {i:02d}", "w " * 10)
    # "Aaa" sorts first in vault order but is the milder outlier.
    builder.note("Aaa Mild", "w " * 400)
    builder.note("Zzz Extreme", "w " * 600)
    ctx = builder.build()
    analyser = MetadataAnalyser(ctx)

    assert [n.title for n in analyser.outliers("word_count", threshold=2.0)] == [
        "Zzz Extreme",
        "Aaa Mild",
    ]
    # Restricted to the plain notes there is no spread, hence no outliers.
    plain = [n for n in ctx.notes() if n.title.startswith("Plain")]
    assert analyser.outliers("word_count", notes=plain) == []
    assert analyser.distribution("word_count", notes=plain)["p50"] == 13.0
