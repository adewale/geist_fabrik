"""Tests for function registry system (Phase 9)."""

import tempfile
from pathlib import Path
from typing import Any, List

import pytest

from geistfabrik import (
    DuplicateFunctionError,
    FunctionRegistry,
    FunctionRegistryError,
    vault_function,
)


@pytest.fixture(autouse=True)
def clear_global_registry():
    """Clear the global function registry before each test."""
    from geistfabrik.function_registry import _GLOBAL_REGISTRY

    _GLOBAL_REGISTRY.clear()
    yield
    _GLOBAL_REGISTRY.clear()


def test_function_registry_initialization() -> None:
    """Test FunctionRegistry initialisation."""
    registry = FunctionRegistry()
    assert registry.function_dir is None
    # Should have built-in functions
    assert len(registry.functions) > 0
    assert "sample_notes" in registry.functions


def test_function_registry_with_directory() -> None:
    """Test FunctionRegistry with custom directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = FunctionRegistry(Path(tmpdir))
        assert registry.function_dir == Path(tmpdir)


def test_built_in_functions_loaded() -> None:
    """Test that built-in functions are automatically loaded."""
    registry = FunctionRegistry()

    expected_functions = [
        "sample_notes",
        "old_notes",
        "recent_notes",
        "orphans",
        "hubs",
        "neighbours",
    ]

    for func_name in expected_functions:
        assert func_name in registry.functions
        assert callable(registry.functions[func_name])


def test_vault_function_decorator() -> None:
    """Test @vault_function decorator."""
    from geistfabrik.function_registry import _GLOBAL_REGISTRY

    @vault_function("test_func")
    def my_test_function(vault: Any, arg1: str) -> str:
        return f"Hello {arg1}"

    assert "test_func" in _GLOBAL_REGISTRY
    assert _GLOBAL_REGISTRY["test_func"] == my_test_function


def test_vault_function_decorator_duplicate() -> None:
    """Test that duplicate function names raise error."""

    @vault_function("dup_func")
    def func1(vault: Any) -> None:
        pass

    # Should raise error for duplicate
    with pytest.raises(DuplicateFunctionError):

        @vault_function("dup_func")
        def func2(vault: Any) -> None:
            pass


def test_vault_function_decorator_invalid_signature() -> None:
    """Test that functions without vault parameter raise error."""
    # Should raise error - no vault parameter
    with pytest.raises(FunctionRegistryError):

        @vault_function("bad_func")
        def bad_function(something_else: str) -> None:
            pass


def test_manual_register_function() -> None:
    """Test manually registering a function."""
    registry = FunctionRegistry()

    def custom_func(vault: Any, k: int = 5) -> List[Any]:
        return []

    registry.register("custom", custom_func)

    assert "custom" in registry.functions
    assert registry.functions["custom"] == custom_func


def test_manual_register_duplicate_raises_error() -> None:
    """Test that registering duplicate names raises error."""
    registry = FunctionRegistry()

    def func1(vault: Any) -> None:
        pass

    registry.register("test_dup", func1)

    def func2(vault: Any) -> None:
        pass

    with pytest.raises(DuplicateFunctionError):
        registry.register("test_dup", func2)


def test_call_function() -> None:
    """Test calling a registered function."""
    registry = FunctionRegistry()

    def add_numbers(vault: Any, a: int, b: int) -> int:
        return a + b

    registry.register("add", add_numbers)

    class MockVault:
        pass

    result = registry.call("add", MockVault(), 3, 5)
    assert result == 8


def test_call_nonexistent_function() -> None:
    """Test calling a function that doesn't exist."""
    registry = FunctionRegistry()

    class MockVault:
        pass

    with pytest.raises(FunctionRegistryError):
        registry.call("does_not_exist", MockVault())


def test_call_function_with_error() -> None:
    """Test calling a function that raises an error."""
    registry = FunctionRegistry()

    def error_func(vault: Any) -> None:
        raise ValueError("Test error")

    registry.register("error_func", error_func)

    class MockVault:
        pass

    with pytest.raises(FunctionRegistryError):
        registry.call("error_func", MockVault())


def test_get_function_names() -> None:
    """Test getting list of function names."""
    registry = FunctionRegistry()

    def custom1(vault: Any) -> None:
        pass

    def custom2(vault: Any) -> None:
        pass

    registry.register("zzz_custom1", custom1)
    registry.register("aaa_custom2", custom2)

    names = registry.get_function_names()

    assert isinstance(names, list)
    assert "zzz_custom1" in names
    assert "aaa_custom2" in names
    # Should be sorted
    custom_names = [n for n in names if n.startswith(("zzz_", "aaa_"))]
    assert custom_names == sorted(custom_names)


def test_has_function() -> None:
    """Test checking if function exists."""
    registry = FunctionRegistry()

    assert registry.has_function("sample_notes") is True
    assert registry.has_function("nonexistent") is False


def test_load_function_module() -> None:
    """Test loading functions from a module file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        # Create a module with decorated function
        module_file = module_dir / "test_funcs.py"
        module_file.write_text("""
from geistfabrik import vault_function

@vault_function("test_loaded")
def loaded_function(vault, k=5):
    return ["test"]
""")

        registry = FunctionRegistry(module_dir)
        registry.load_modules()

        assert "test_loaded" in registry.functions


def test_load_module_with_syntax_error() -> None:
    """Test loading module with syntax errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module_file = module_dir / "syntax_error.py"
        module_file.write_text("""
from geistfabrik import vault_function

@vault_function("bad")
def bad_func(vault):
    return {invalid syntax
""")

        registry = FunctionRegistry(module_dir)
        registry.load_modules()  # Should not crash

        assert "bad" not in registry.functions


def test_load_enabled_modules_only() -> None:
    """Test loading only enabled modules."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        module1 = module_dir / "enabled.py"
        module1.write_text("""
from geistfabrik import vault_function

@vault_function("enabled_func")
def enabled(vault):
    return []
""")

        module2 = module_dir / "disabled.py"
        module2.write_text("""
from geistfabrik import vault_function

@vault_function("disabled_func")
def disabled(vault):
    return []
""")

        registry = FunctionRegistry(module_dir)
        registry.load_modules(enabled_modules=["enabled"])

        assert "enabled_func" in registry.functions
        assert "disabled_func" not in registry.functions


def test_skip_private_modules() -> None:
    """Test that private modules (starting with _) are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        module_dir = Path(tmpdir)

        private_module = module_dir / "_private.py"
        private_module.write_text("""
from geistfabrik import vault_function

@vault_function("private_func")
def private(vault):
    return []
""")

        registry = FunctionRegistry(module_dir)
        registry.load_modules()

        assert "private_func" not in registry.functions


def test_function_with_kwargs() -> None:
    """Test calling function with keyword arguments."""
    registry = FunctionRegistry()

    def func_with_kwargs(vault: Any, a: int, b: int = 10) -> int:
        return a + b

    registry.register("kwargs_func", func_with_kwargs)

    class MockVault:
        pass

    result1 = registry.call("kwargs_func", MockVault(), 5)
    assert result1 == 15

    result2 = registry.call("kwargs_func", MockVault(), 5, b=20)
    assert result2 == 25


def test_function_accesses_vault() -> None:
    """Test that function can access vault context."""
    registry = FunctionRegistry()

    def use_vault(vault: Any) -> str:
        return vault.test_value

    registry.register("use_vault", use_vault)

    class MockVault:
        test_value = "success"

    result = registry.call("use_vault", MockVault())
    assert result == "success"


def test_load_modules_no_directory() -> None:
    """Test load_modules with no directory."""
    registry = FunctionRegistry()
    registry.load_modules()  # Should not crash

    # Should still have built-in functions
    assert "sample_notes" in registry.functions


def test_load_modules_empty_directory() -> None:
    """Test load_modules with empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = FunctionRegistry(Path(tmpdir))
        registry.load_modules()

        # Should have built-in functions
        assert "sample_notes" in registry.functions


def test_function_returns_list() -> None:
    """Test function that returns a list."""
    registry = FunctionRegistry()

    def return_list(vault: Any) -> List[str]:
        return ["a", "b", "c"]

    registry.register("return_list", return_list)

    class MockVault:
        pass

    result = registry.call("return_list", MockVault())
    assert result == ["a", "b", "c"]


def test_function_returns_none() -> None:
    """Test function that returns None."""
    registry = FunctionRegistry()

    def return_none(vault: Any) -> None:
        pass

    registry.register("return_none", return_none)

    class MockVault:
        pass

    result = registry.call("return_none", MockVault())
    assert result is None
