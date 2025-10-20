#!/usr/bin/env python3
"""Detect unused database tables in GeistFabrik schema.

Scans schema.py for table definitions and checks if they're queried anywhere in the codebase.
Exits with code 1 if unused tables are found (useful for CI/pre-commit hooks).
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Set


def extract_tables_from_schema(schema_path: Path) -> Set[str]:
    """Extract table names from schema file.

    Args:
        schema_path: Path to schema.py file

    Returns:
        Set of table names
    """
    content = schema_path.read_text()

    # Match: CREATE TABLE IF NOT EXISTS table_name (
    pattern = r"CREATE TABLE IF NOT EXISTS (\w+)"
    matches = re.findall(pattern, content)

    return set(matches)


def find_table_references(table: str, src_dir: Path) -> List[str]:
    """Find SQL references to a table in source code.

    Args:
        table: Table name to search for
        src_dir: Source directory to search

    Returns:
        List of file paths with references
    """
    references = []

    # SQL operations that indicate table usage
    patterns = [
        f"FROM {table}",
        f"INTO {table}",
        f"UPDATE {table}",
        f"DELETE FROM {table}",
        f"JOIN {table}",
    ]

    for py_file in src_dir.rglob("*.py"):
        content = py_file.read_text()

        for pattern in patterns:
            if pattern in content:
                references.append(str(py_file.relative_to(src_dir.parent)))
                break  # Found at least one reference in this file

    return references


def main() -> int:
    """Main entry point.

    Returns:
        0 if all tables are used, 1 if unused tables found
    """
    # Paths
    project_root = Path(__file__).parent.parent
    schema_path = project_root / "src" / "geistfabrik" / "schema.py"
    src_dir = project_root / "src"

    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}", file=sys.stderr)
        return 1

    # Extract tables
    tables = extract_tables_from_schema(schema_path)
    print(f"📊 Found {len(tables)} tables in schema")
    print()

    # Check usage
    unused_tables: Dict[str, int] = {}
    used_tables: Dict[str, List[str]] = {}

    for table in sorted(tables):
        refs = find_table_references(table, src_dir)
        ref_count = len(refs)

        if ref_count == 0:
            unused_tables[table] = 0
            print(f"❌ {table}: UNUSED (0 references)")
        else:
            used_tables[table] = refs
            print(f"✅ {table}: {ref_count} file(s)")
            if "--verbose" in sys.argv:
                for ref in refs:
                    print(f"   - {ref}")

    # Summary
    print()
    print("=" * 60)
    print(f"Summary: {len(used_tables)} used, {len(unused_tables)} unused")
    print("=" * 60)

    if unused_tables:
        print()
        print("⚠️  UNUSED TABLES DETECTED:")
        for table in sorted(unused_tables.keys()):
            print(f"  - {table}")
        print()
        print("These tables are defined in schema but never queried.")
        print("Consider removing them or adding code that uses them.")
        print()
        print("Run with --verbose to see which files use each table.")
        return 1

    print()
    print("✨ All tables are in use!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
