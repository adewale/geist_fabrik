# uv: Comprehensive Best Practices Guide

A comprehensive guide to using uv, the fast Python package installer and project manager by Astral.

**Last Updated:** October 2025
**uv Version:** 0.9.4 (as of October 17, 2025)

---

## Table of Contents

1. [Introduction](#introduction)
2. [Project Setup](#project-setup)
3. [Dependency Management](#dependency-management)
4. [Virtual Environment Management](#virtual-environment-management)
5. [Installation and Sync](#installation-and-sync)
6. [CI/CD Integration](#cicd-integration)
7. [Commands and Workflows](#commands-and-workflows)
8. [Migration from pip/poetry](#migration-from-pippoetry)
9. [Best Practices](#best-practices)
10. [Advanced Features](#advanced-features)

---

## Introduction

### What is uv?

uv is an extremely fast Python package and project manager, written in Rust. It's designed as a single tool to replace pip, pip-tools, pipx, poetry, pyenv, twine, virtualenv, and more.

**Official Documentation:** https://docs.astral.sh/uv/

### Key Features

- **Speed**: 10-100x faster than pip, 10x faster than Poetry
- **Python Installation**: Automatically downloads and manages Python versions
- **Project Management**: Complete project lifecycle from init to publish
- **Drop-in Replacement**: Compatible with pip, pip-tools, and virtualenv commands
- **Workspace Support**: Monorepo management with shared lockfiles
- **Script Execution**: PEP 723 inline script metadata support
- **Tool Management**: Similar to pipx for CLI tools

### Installation

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# With pip
pip install uv

# With Homebrew
brew install uv

# With pipx
pipx install uv
```

---

## Project Setup

### Initializing a New Project

```bash
# Create a new project
uv init my-project
cd my-project

# Initialize in an existing directory
uv init
```

This creates:
- `pyproject.toml` - Project configuration
- `README.md` - Project documentation
- `.python-version` - Python version pin
- `.gitignore` - Git ignore file
- `main.py` - Sample entry point
- `.venv/` - Virtual environment (on first run)

### Directory Structure Best Practices

**Basic Application Structure:**
```
my-project/
├── .venv/                  # Virtual environment (auto-created)
├── .python-version         # Python version (e.g., 3.12)
├── pyproject.toml          # Project configuration
├── uv.lock                 # Lockfile (auto-generated)
├── README.md
├── .gitignore
├── src/
│   └── my_project/         # Source code
│       ├── __init__.py
│       └── main.py
└── tests/
    └── test_main.py
```

**Workspace/Monorepo Structure:**
```
my-monorepo/
├── pyproject.toml          # Root workspace config
├── uv.lock                 # Shared lockfile
├── packages/
│   ├── package-a/
│   │   ├── pyproject.toml
│   │   └── src/
│   └── package-b/
│       ├── pyproject.toml
│       └── src/
└── apps/
    └── web-app/
        ├── pyproject.toml
        └── src/
```

### pyproject.toml Configuration

#### Minimal Application

```toml
[project]
name = "my-app"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []
```

#### Complete Library/Package

```toml
[project]
name = "my-library"
version = "0.1.0"
description = "A fantastic Python library"
readme = "README.md"
authors = [
    { name = "Your Name", email = "you@example.com" }
]
license = { text = "MIT" }
requires-python = ">=3.11"
keywords = ["example", "library"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "requests>=2.31.0",
    "pydantic>=2.0.0",
]

[project.optional-dependencies]
# Optional features
excel = ["openpyxl>=3.1.0", "pandas>=2.0.0"]
plot = ["matplotlib>=3.7.0"]

[project.urls]
Homepage = "https://github.com/username/my-library"
Documentation = "https://my-library.readthedocs.io"
Repository = "https://github.com/username/my-library"
Changelog = "https://github.com/username/my-library/blob/main/CHANGELOG.md"

[project.scripts]
my-cli = "my_library.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.3.5",
    "pytest-cov>=5.0.0",
    "ruff>=0.6.2",
    "mypy>=1.0.0",
]
docs = [
    "mkdocs>=1.6.0",
    "mkdocs-material>=9.5.0",
]

[tool.uv]
# Custom package indexes
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"

# Custom sources for specific packages
[tool.uv.sources]
torch = { index = "pytorch-cpu" }

# Default dependency groups to install
default-groups = ["dev"]
```

#### Application with FastAPI

```toml
[project]
name = "my-api"
version = "0.1.0"
description = "FastAPI application"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastapi[standard]>=0.112.0",
    "uvicorn>=0.30.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "sqlalchemy>=2.0.0",
]

[project.scripts]
start = "my_api.main:app"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "pytest>=8.3.5",
    "httpx>=0.27.0",  # For testing FastAPI
    "ruff>=0.6.2",
    "mypy>=1.0.0",
]

[tool.uv]
dev-dependencies = [
    "fastapi-cli>=0.0.5",
]
```

---

## Dependency Management

### Adding Dependencies

```bash
# Add a production dependency
uv add requests

# Add with version constraint
uv add "requests>=2.31.0,<3.0"
uv add "requests==2.31.0"
uv add "requests~=2.31.0"  # Compatible release

# Add from git
uv add git+https://github.com/psf/requests

# Add from git with specific branch/tag/commit
uv add "requests @ git+https://github.com/psf/requests@main"
uv add "requests @ git+https://github.com/psf/requests@v2.31.0"

# Add from local path
uv add --editable ./local-package

# Add with extras
uv add "fastapi[standard]"
uv add "pandas[excel,plot]"

# Add to a specific dependency group
uv add --group dev pytest
uv add --group test pytest-cov
uv add --group docs mkdocs

# Legacy dev dependencies (deprecated, use --group instead)
uv add --dev pytest
```

### Version Constraint Operators

uv follows PEP 440 version specifiers:

| Operator | Description | Example |
|----------|-------------|---------|
| `==` | Exact version | `requests==2.31.0` |
| `!=` | Exclude version | `requests!=2.30.0` |
| `>=` | Greater than or equal | `requests>=2.31.0` |
| `<=` | Less than or equal | `requests<=2.31.0` |
| `>` | Greater than | `requests>2.30.0` |
| `<` | Less than | `requests<3.0.0` |
| `~=` | Compatible release | `requests~=2.31.0` (>=2.31.0, <2.32.0) |
| `==.*` | Prefix matching | `python-dateutil==2.8.*` |

**Combined constraints:**
```toml
dependencies = [
    "requests>=2.31.0,<3.0",
    "django>2.1,!=2.2.0",
]
```

### Removing Dependencies

```bash
# Remove a dependency
uv remove requests

# Remove from a specific group
uv remove --group dev pytest
```

### Upgrading Dependencies

```bash
# Upgrade a specific package
uv lock --upgrade-package requests

# Upgrade multiple packages
uv lock --upgrade-package requests --upgrade-package urllib3

# Upgrade all dependencies
uv lock --upgrade

# Upgrade and sync environment
uv sync --upgrade
```

### Dependency Groups

uv uses PEP 735 dependency groups for organising different types of dependencies:

```toml
[dependency-groups]
dev = [
    "pytest>=8.3.5",
    "ruff>=0.6.2",
]
test = [
    "pytest==8.3.3",
    "pytest-cov==5.0.0",
    "coverage>=7.0.0",
]
docs = [
    "mkdocs==1.6.1",
    "mkdocs-material>=9.5.0",
]
```

**Installing dependency groups:**
```bash
# Install with dev group (default)
uv sync

# Exclude dev group
uv sync --no-dev

# Install specific groups
uv sync --group test
uv sync --group test --group docs

# Install all groups
uv sync --all-groups
```

**Configure default groups:**
```toml
[tool.uv]
default-groups = ["dev", "test"]
```

### Optional Dependencies (Extras)

For libraries with optional features:

```toml
[project.optional-dependencies]
excel = ["openpyxl>=3.1.0", "pandas>=2.0.0"]
plot = ["matplotlib>=3.7.0"]
all = ["openpyxl>=3.1.0", "pandas>=2.0.0", "matplotlib>=3.7.0"]
```

**Installing with extras:**
```bash
uv sync --extra excel
uv sync --extra excel --extra plot
uv sync --all-extras
```

### Platform-Specific Dependencies

Use environment markers for platform or Python version constraints:

```bash
# Add platform-specific dependency
uv add "jax; sys_platform == 'linux'"
uv add "pywin32; sys_platform == 'win32'"
uv add "pyobjc; sys_platform == 'darwin'"
```

**In pyproject.toml:**
```toml
dependencies = [
    "jax; sys_platform == 'linux'",
    "pywin32; sys_platform == 'win32'",
    "some-package>=1.0; python_version >= '3.11'",
]
```

**Advanced: Platform-specific sources:**
```toml
[project.optional-dependencies]
cpu = ["torch"]
cu124 = ["torch"]

[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"

[[tool.uv.index]]
name = "pytorch-cu124"
url = "https://download.pytorch.org/whl/cu124"

[tool.uv.sources]
torch = [
    { index = "pytorch-cpu", marker = "extra == 'cpu'" },
    { index = "pytorch-cu124", marker = "extra == 'cu124'" },
]
```

Then install with:
```bash
uv sync --extra cpu     # For CPU version
uv sync --extra cu124   # For CUDA 12.4 version
```

### Lock Files (uv.lock)

uv automatically generates and maintains `uv.lock`, a cross-platform lockfile containing:
- Exact resolved versions of all dependencies
- Transitive dependencies
- Hashes for verification
- Source URLs

**Key points:**
- Generated automatically on first `uv run`, `uv sync`, or `uv lock`
- Should be committed to version control
- Human-readable TOML format, but don't edit manually
- Platform-independent (one lock file for all platforms)
- Updates automatically when `pyproject.toml` changes

**Lock file workflow:**
```bash
# Generate/update lock file without syncing
uv lock

# Lock and sync environment
uv sync

# Lock with specific Python version
uv lock --python 3.12

# Verify lock file is up to date
uv lock --check
```

---

## Virtual Environment Management

### Automatic Virtual Environment Management

uv automatically creates and manages virtual environments:

- **Auto-discovery**: Searches for `.venv` in current and parent directories
- **Auto-creation**: Creates `.venv` on first project command
- **Auto-sync**: Syncs environment with lock file before `uv run`

**Search order for environments:**
1. Active `VIRTUAL_ENV` environment variable
2. Active Conda `CONDA_PREFIX` environment
3. `.venv` in current or parent directory
4. Prompts to create if none found

### Manual Virtual Environment Management

```bash
# Create a virtual environment
uv venv

# Create with specific Python version
uv venv --python 3.12
uv venv --python python3.11

# Create with specific name/location
uv venv my-env
uv venv /path/to/env

# Activate the environment
# On Unix/macOS:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate

# Deactivate
deactivate
```

### Integration with Existing Environments

```bash
# Use existing environment
source .venv/bin/activate
uv pip install -r requirements.txt

# Create environment and install
uv venv
uv pip install -r requirements.txt
```

### Virtual Environment Configuration

**Custom location:**
```toml
[tool.uv]
# Relative to project root
virtual-env-path = "venv"

# Or absolute path
virtual-env-path = "/path/to/envs/my-project"
```

**Environment variables:**
```bash
# Set custom cache directory
export UV_CACHE_DIR=/path/to/cache

# Set custom virtual environment directory
export UV_PROJECT_ENVIRONMENT=/path/to/venv
```

### Best Practices

1. **Use `.venv` name**: IDEs and tools expect this location
2. **Add to .dockerignore**: Prevent including venv in Docker images
3. **Add to .gitignore**: Already included by `uv init`
4. **Let uv manage it**: Don't manually modify the virtual environment

---

## Installation and Sync

### uv sync vs uv pip install

**Use `uv sync` for projects:**
- Works with `pyproject.toml` and `uv.lock`
- Installs project in editable mode by default
- Ensures lock file and environment are up to date
- Recommended for project development

```bash
# Sync project and dependencies
uv sync

# Sync without dev dependencies
uv sync --no-dev

# Sync without installing project itself
uv sync --no-install-project

# Sync in non-editable mode
uv sync --no-editable

# Sync with specific extras
uv sync --extra test --extra docs

# Sync all extras
uv sync --all-extras

# Sync with specific groups
uv sync --group test

# Sync frozen (error if lock out of date)
uv sync --frozen

# Sync and upgrade
uv sync --upgrade
```

**Use `uv pip install` for legacy workflows:**
- Drop-in replacement for pip
- Doesn't modify `pyproject.toml` or `uv.lock`
- Useful for requirements.txt workflows

```bash
# Install from requirements.txt
uv pip install -r requirements.txt

# Install package
uv pip install requests

# Install in editable mode
uv pip install -e .
uv pip install -e ./local-package

# Install from PyPI with version
uv pip install "requests>=2.31.0"

# Install from git
uv pip install git+https://github.com/psf/requests
```

### Installing Dependencies Only

```bash
# Install dependencies without the project
uv sync --no-install-project

# Useful for Docker builds
uv sync --frozen --no-dev --no-install-project
```

### Installing in Editable Mode

By default, `uv sync` installs your project in editable mode, meaning changes to source code are immediately reflected.

```bash
# Default: editable mode
uv sync

# Disable editable mode
uv sync --no-editable

# Legacy pip style
uv pip install -e .
```

### Installing Extras

```bash
# Install specific extras
uv sync --extra excel
uv sync --extra excel --extra plot

# Install all extras
uv sync --all-extras

# Add extras to lock file
uv lock --extra excel
```

---

## CI/CD Integration

### GitHub Actions

#### Basic Setup with Official Action

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
          cache-dependency-glob: "uv.lock"

      - name: Set up Python
        run: uv python install

      - name: Install dependencies
        run: uv sync --all-groups

      - name: Run tests
        run: uv run pytest

      - name: Run linter
        run: uv run ruff check .
```

#### Advanced Setup with Caching

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python-version: ['3.11', '3.12', '3.13']

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          enable-cache: true
          cache-dependency-glob: |
            uv.lock
            **/pyproject.toml

      - name: Set up Python ${{ matrix.python-version }}
        run: uv python install ${{ matrix.python-version }}

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run tests
        run: uv run pytest --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage.xml
```

#### Using hynek/setup-cached-uv

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4
      - uses: hynek/setup-cached-uv@v2

      - name: Set up Python
        run: uv python install

      - run: uv sync --frozen
      - run: uv run pytest
```

This action automatically:
- Installs uv
- Configures caching based on OS, workflow, job, and `pyproject.toml` hash
- Expires cache weekly

#### Cache Optimization

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Set up Python
        run: uv python install

      # Cache dependencies
      - name: Cache uv
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/uv
            .venv
          key: uv-${{ runner.os }}-${{ hashFiles('uv.lock') }}
          restore-keys: |
            uv-${{ runner.os }}-

      - name: Install dependencies
        run: uv sync --frozen

      - name: Run tests
        run: uv run pytest

      - name: Prune cache
        run: uv cache prune --ci
```

### Docker Integration

#### Multi-Stage Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

# Build stage
FROM python:3.13-slim AS build

# Copy uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.9.4 /uv /uvx /bin/

WORKDIR /app

# Enable bytecode compilation and copy mode for better performance
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Install dependencies first (for better caching)
COPY uv.lock pyproject.toml ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY . .

# Install project
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Runtime stage
FROM python:3.13-slim AS runtime

# Add virtualenv to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Create non-root user
RUN groupadd -g 1001 appgroup && \
    useradd -u 1001 -g appgroup -m -d /app -s /bin/false appuser

WORKDIR /app

# Copy application and venv from build stage
COPY --from=build --chown=appuser:appgroup /app .

USER appuser

# Run application
ENTRYPOINT ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### .dockerignore

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Virtual environments
.venv/
venv/
env/
ENV/

# uv
.uv/
uv.lock  # Include if you want to use it
.python-version

# Tests
.pytest_cache/
.coverage
htmlcov/
*.cover

# IDE
.vscode/
.idea/
*.swp
*.swo

# Git
.git/
.gitignore

# Documentation
docs/
*.md

# Other
.env
.DS_Store
```

### GitLab CI

```yaml
image: python:3.12

variables:
  UV_CACHE_DIR: .uv-cache

cache:
  paths:
    - .uv-cache/
    - .venv/
  key:
    files:
      - uv.lock

before_script:
  - curl -LsSf https://astral.sh/uv/install.sh | sh
  - export PATH="$HOME/.local/bin:$PATH"
  - uv python install
  - uv sync --frozen

test:
  script:
    - uv run pytest

lint:
  script:
    - uv run ruff check .
    - uv run mypy .
```

### Best Practices for CI/CD

1. **Use `--frozen` flag**: Prevents lock file updates in CI
2. **Cache strategically**: Cache both `~/.cache/uv` and `.venv`
3. **Use `uv cache prune --ci`**: Clean up after builds to save space
4. **Verify lock file**: Add a step to check lock file is up to date
5. **Separate stages**: Install dependencies before installing project
6. **Use specific Python versions**: Don't rely on system Python
7. **Run in non-editable mode**: Use `--no-editable` for production builds

---

## Commands and Workflows

### Common Daily Commands

```bash
# Project initialization
uv init my-project              # Create new project
uv init                         # Initialize existing directory

# Python management
uv python install               # Install Python from .python-version
uv python install 3.12          # Install specific version
uv python list                  # List installed versions
uv python pin 3.12              # Pin project to Python version

# Dependency management
uv add requests                 # Add dependency
uv add --group dev pytest       # Add to dependency group
uv remove requests              # Remove dependency
uv lock                         # Update lock file
uv lock --upgrade               # Upgrade all dependencies
uv lock --upgrade-package pkg   # Upgrade specific package

# Environment management
uv sync                         # Sync environment with lock file
uv sync --frozen                # Error if lock file out of date
uv sync --no-dev                # Exclude dev dependencies
uv sync --group test            # Install test group

# Running code
uv run python script.py         # Run script in project environment
uv run pytest                   # Run tests
uv run python -m myapp          # Run module
uv run --with httpx -- python   # Run with temporary dependency

# Tool management
uv tool install ruff            # Install CLI tool globally
uv tool run black .             # Run tool without installing
uvx black .                     # Shorthand for tool run
uv tool list                    # List installed tools
uv tool uninstall ruff          # Remove tool

# pip compatibility
uv pip install requests         # Install package (pip style)
uv pip install -r requirements.txt  # Install from requirements
uv pip list                     # List installed packages
uv pip freeze                   # Output installed packages

# Build and publish
uv build                        # Build package
uv publish                      # Publish to PyPI

# Cache management
uv cache clean                  # Clean cache
uv cache prune                  # Remove unused entries
uv cache dir                    # Show cache directory

# Information
uv --version                    # Show uv version
uv python list                  # List Python installations
uv tree                         # Show dependency tree
```

### Running Scripts with PEP 723

Create self-contained scripts with inline dependencies:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests<3",
#     "rich",
# ]
# ///

import requests
from rich.pretty import pprint

resp = requests.get("https://api.github.com")
pprint(resp.json())
```

Make executable and run:
```bash
chmod +x script.py
./script.py
```

Or run directly:
```bash
uv run script.py
```

### Tool Management

```bash
# Install tools globally
uv tool install ruff
uv tool install black
uv tool install mypy

# Run tool once without installing
uv tool run black .
uvx black .  # Shorthand

# Run with specific version
uvx "black==24.0.0" .

# Run with additional dependencies
uv tool run --with pandas -- python -c "import pandas; print(pandas.__version__)"

# List installed tools
uv tool list

# Update tool
uv tool install --upgrade ruff

# Uninstall tool
uv tool uninstall ruff
```

### Build and Publish

```bash
# Build package (wheel and sdist)
uv build

# Build specific format
uv build --wheel
uv build --sdist

# Publish to PyPI
uv publish

# Publish to test PyPI
uv publish --publish-url https://test.pypi.org/legacy/

# Publish with token
uv publish --token $PYPI_TOKEN
```

---

## Migration from pip/poetry

### From pip + requirements.txt

**Before:**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
python script.py
```

**After:**
```bash
# Convert requirements.txt to pyproject.toml (manual or use tool)
# Create basic pyproject.toml
cat > pyproject.toml << EOF
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    # Copy from requirements.txt
]

[dependency-groups]
dev = [
    # Copy from requirements-dev.txt
]
EOF

# Initialize and run
uv sync
uv run python script.py
```

**Using migration tool:**
```bash
uvx migrate-to-uv
```

### From Poetry

**Automated migration:**
```bash
# Install migration tool
uvx migrate-to-uv

# Migrate project
cd my-project
uvx migrate-to-uv
```

This will:
- Convert `poetry.lock` to `uv.lock`
- Convert Poetry-specific `pyproject.toml` sections
- Remove `poetry.toml`
- Preserve dependency versions

**Manual migration:**

1. **Update pyproject.toml:**

Before (Poetry):
```toml
[tool.poetry]
name = "my-project"
version = "0.1.0"
description = "My project"
authors = ["Your Name <you@example.com>"]

[tool.poetry.dependencies]
python = "^3.11"
requests = "^2.31.0"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0.0"
```

After (uv):
```toml
[project]
name = "my-project"
version = "0.1.0"
description = "My project"
requires-python = ">=3.11"
authors = [
    { name = "Your Name", email = "you@example.com" }
]

dependencies = [
    "requests>=2.31.0,<3.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0.0,<9.0",
]
```

2. **Remove Poetry files:**
```bash
rm poetry.lock poetry.toml
```

3. **Initialize uv:**
```bash
uv sync
```

**Command mapping:**

| Poetry | uv |
|--------|-----|
| `poetry install` | `uv sync` |
| `poetry add requests` | `uv add requests` |
| `poetry add --group dev pytest` | `uv add --group dev pytest` |
| `poetry remove requests` | `uv remove requests` |
| `poetry update` | `uv lock --upgrade && uv sync` |
| `poetry update requests` | `uv lock --upgrade-package requests && uv sync` |
| `poetry run python script.py` | `uv run python script.py` |
| `poetry run pytest` | `uv run pytest` |
| `poetry build` | `uv build` |
| `poetry publish` | `uv publish` |
| `poetry shell` | `source .venv/bin/activate` |
| `poetry env info` | `uv python list` |

### From pipenv

**Automated migration:**
```bash
uvx migrate-to-uv
```

**Manual migration:**

1. Convert Pipfile to pyproject.toml
2. Remove Pipfile and Pipfile.lock
3. Run `uv sync`

### Key Differences from Other Tools

| Feature | pip | Poetry | uv |
|---------|-----|--------|-----|
| Speed | Baseline | ~10x faster | ~100x faster |
| Lock files | No (unless pip-tools) | Yes | Yes |
| Dependency resolution | Basic | Full | Full |
| Virtual env management | Manual (venv) | Automatic | Automatic |
| Python installation | No | No | Yes |
| Build backend | No | Yes | No (uses other backends) |
| Written in | Python | Python | Rust |

---

## Best Practices

### 1. pyproject.toml Organisation

```toml
# Group related sections logically
[project]
# Core metadata first

[project.urls]
# Project links

[project.scripts]
# Entry points

[project.optional-dependencies]
# Optional extras

[build-system]
# Build configuration

[dependency-groups]
# Development dependencies

[tool.uv]
# uv-specific configuration

[tool.ruff]
# Other tool configurations
```

### 2. Version Pinning Strategies

**For Applications (deployed code):**
```toml
# Use ranges, let lock file pin exact versions
dependencies = [
    "requests>=2.31.0,<3.0",
    "pydantic>=2.0.0,<3.0",
]
```

**For Libraries (published packages):**
```toml
# Use wider ranges for compatibility
dependencies = [
    "requests>=2.28.0",
    "pydantic>=2.0.0",
]
```

**Avoid:**
```toml
# Too restrictive for libraries
dependencies = [
    "requests==2.31.0",  # Bad: pins exact version
]
```

### 3. Handling Platform-Specific Dependencies

**Use environment markers:**
```toml
dependencies = [
    "pywin32>=306; sys_platform == 'win32'",
    "pyobjc-framework-Cocoa>=10.0; sys_platform == 'darwin'",
    "uvloop>=0.19.0; sys_platform != 'win32'",
]
```

**For complex cases, use optional dependencies:**
```toml
[project.optional-dependencies]
windows = ["pywin32>=306"]
macos = ["pyobjc-framework-Cocoa>=10.0"]
linux = ["uvloop>=0.19.0"]
```

### 4. Common Pitfalls to Avoid

#### Don't mix uv add and manual edits

```bash
# Bad: Mix of uv commands and manual edits
uv add requests
# Manually edit pyproject.toml to add flask
uv lock  # Lock file may be inconsistent

# Good: Use uv commands consistently
uv add requests
uv add flask
```

#### Don't commit .venv to git

```gitignore
# Always in .gitignore
.venv/
venv/
*.pyc
__pycache__/
```

#### Do commit uv.lock

```bash
# Always commit lock file for reproducibility
git add uv.lock pyproject.toml
git commit -m "Update dependencies"
```

#### Don't use uv pip install in projects

```bash
# Bad: Doesn't update pyproject.toml or lock file
uv pip install requests

# Good: Updates project configuration
uv add requests
```

#### Be careful with multiple package indexes

```toml
# Bad: May cause security issues
[[tool.uv.index]]
url = "https://private-index.com/simple"

# Good: Use index-strategy and explicit sources
[tool.uv]
index-strategy = "unsafe-best-match"  # Or "first-match"

[tool.uv.sources]
private-package = { index = "private-index" }
```

#### Don't manually edit uv.lock

```bash
# Bad: Manual edits will be overwritten
vim uv.lock

# Good: Use uv commands
uv lock --upgrade-package requests
```

### 5. Cache Management

```bash
# Check cache size
du -sh ~/.cache/uv

# Clean cache periodically
uv cache clean

# Prune unused entries
uv cache prune

# In CI, clean after build
uv cache prune --ci
```

**Set cache location (if needed):**
```bash
export UV_CACHE_DIR=/path/to/cache
```

### 6. Project Structure Best Practices

**Use src layout for packages:**
```
my-package/
├── src/
│   └── my_package/
│       ├── __init__.py
│       └── main.py
├── tests/
├── pyproject.toml
└── README.md
```

**Flat layout for applications:**
```
my-app/
├── my_app/
│   ├── __init__.py
│   └── main.py
├── tests/
├── pyproject.toml
└── README.md
```

### 7. Dependency Organisation

```toml
# Organise dependencies by purpose
dependencies = [
    # Core dependencies
    "fastapi>=0.112.0",
    "pydantic>=2.0.0",

    # Database
    "sqlalchemy>=2.0.0",
    "alembic>=1.12.0",

    # Utilities
    "python-dotenv>=1.0.0",
    "pydantic-settings>=2.0.0",
]

[dependency-groups]
# Testing
test = [
    "pytest>=8.3.5",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
]

# Linting and formatting
lint = [
    "ruff>=0.6.2",
    "mypy>=1.0.0",
]

# Development tools
dev = [
    "ipython>=8.12.0",
    "ipdb>=0.13.13",
]
```

### 8. Environment Variables

```bash
# Commonly used uv environment variables
export UV_CACHE_DIR=~/.cache/uv          # Cache directory
export UV_INDEX_URL=https://pypi.org/simple  # Default index
export UV_EXTRA_INDEX_URL=...            # Additional indexes
export UV_PYTHON=python3.12              # Default Python
export UV_PROJECT_ENVIRONMENT=.venv      # Virtual environment location
export UV_COMPILE_BYTECODE=1             # Compile .pyc files
export UV_LINK_MODE=copy                 # Use copy instead of hardlinks
```

### 9. Security Best Practices

**Verify package hashes:**
```bash
# Lock file includes hashes by default
uv lock
```

**Use trusted indexes:**
```toml
[tool.uv]
# Only use trusted indexes
[[tool.uv.index]]
name = "pypi"
url = "https://pypi.org/simple"
default = true
```

**Audit dependencies:**
```bash
# List all dependencies including transitive
uv tree

# Check for known vulnerabilities (use external tool)
uvx safety check
uvx pip-audit
```

### 10. Performance Optimization

**Use cache effectively:**
```dockerfile
# In Docker, mount cache
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen
```

**Precompile bytecode:**
```bash
export UV_COMPILE_BYTECODE=1
uv sync
```

**Use system linkage when possible:**
```bash
# Default is hardlinks (fastest)
export UV_LINK_MODE=hardlink
```

---

## Advanced Features

### Workspaces (Monorepos)

**Root pyproject.toml:**
```toml
[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[tool.uv]
dev-dependencies = [
    "pytest>=8.3.5",
    "ruff>=0.6.2",
]
```

**Package pyproject.toml:**
```toml
[project]
name = "package-a"
version = "0.1.0"
dependencies = []

[tool.uv.sources]
# Depend on workspace member
package-b = { workspace = true }
```

**Commands:**
```bash
# Sync entire workspace
uv sync

# Work on specific package
cd packages/package-a
uv run pytest
```

### Inline Script Metadata (PEP 723)

Create self-contained scripts:

```python
#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx",
#     "beautifulsoup4",
#     "rich",
# ]
# ///

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()
response = httpx.get("https://example.com")
soup = BeautifulSoup(response.text, "html.parser")
console.print(soup.title.string)
```

**Add dependencies to existing script:**
```bash
uv add --script script.py httpx
```

### Custom Package Indexes

```toml
[tool.uv]
# Add custom index
[[tool.uv.index]]
name = "pytorch-cpu"
url = "https://download.pytorch.org/whl/cpu"
explicit = true  # Only used when explicitly specified

# Map packages to specific indexes
[tool.uv.sources]
torch = { index = "pytorch-cpu" }
torchvision = { index = "pytorch-cpu" }
```

### Pre-release and Development Versions

```bash
# Allow pre-releases
uv add --pre "package>=1.0.0a1"

# Install development version from git
uv add "package @ git+https://github.com/org/package@main"
```

**In pyproject.toml:**
```toml
[tool.uv]
prerelease = "allow"  # or "explicit", "if-necessary", "disallow"

[tool.uv.sources]
dev-package = { git = "https://github.com/org/package", branch = "main" }
```

### Dependency Resolution Configuration

```toml
[tool.uv]
# Resolution strategy
resolution = "highest"  # or "lowest", "lowest-direct"

# Index strategy
index-strategy = "first-match"  # or "unsafe-best-match"

# Exclude specific versions
exclude-newer = "2024-01-01T00:00:00Z"
```

### Build Dependencies

```toml
[tool.uv]
# Add build dependencies for specific packages
[tool.uv.extra-build-dependencies]
cchardet = ["cython"]
```

---

## Resources

### Official Documentation
- **uv Docs**: https://docs.astral.sh/uv/
- **GitHub Repository**: https://github.com/astral-sh/uv
- **Astral Blog**: https://astral.sh/blog

### Standards
- **PEP 440**: Version Identification and Dependency Specification
- **PEP 508**: Dependency Specification for Python Software Packages
- **PEP 517**: Backend Interface for Build Systems
- **PEP 518**: Specifying Minimum Build System Requirements (pyproject.toml)
- **PEP 621**: Storing Project Metadata in pyproject.toml
- **PEP 723**: Inline Script Metadata
- **PEP 735**: Dependency Groups in pyproject.toml

### Community Resources
- **Real Python Tutorial**: https://realpython.com/python-uv/
- **SaaS Pegasus Deep Dive**: https://www.saaspegasus.com/guides/uv-deep-dive/
- **DataCamp Tutorial**: https://www.datacamp.com/tutorial/python-uv
- **Migration Tool**: https://github.com/mkniewallner/migrate-to-uv

### Comparison Articles
- Poetry vs uv: https://www.loopwerk.io/articles/2024/python-poetry-vs-uv/
- pip vs uv: https://realpython.com/uv-vs-pip/

---

## Changelog

- **October 2025**: Guide created based on uv 0.9.4
- Includes latest features: PEP 735 dependency groups, workspace support, inline script metadata
- Based on official documentation and community best practices

---

## Contributing

This guide is based on research from official uv documentation, community blog posts, and real-world usage. For corrections or additions, please refer to the latest official documentation at https://docs.astral.sh/uv/.
