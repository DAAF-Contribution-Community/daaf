# Configuration

## Configuration Files

Ruff looks for configuration in this priority order:

1. `.ruff.toml` (highest priority)
2. `ruff.toml`
3. `pyproject.toml` (under `[tool.ruff]`)

Ruff searches from the current directory up to the project root.

### pyproject.toml Format

```toml
[tool.ruff]
line-length = 88

[tool.ruff.lint]
select = ["E", "F"]

[tool.ruff.format]
quote-style = "double"
```

### ruff.toml / .ruff.toml Format

```toml
line-length = 88

[lint]
select = ["E", "F"]

[format]
quote-style = "double"
```

## Complete Configuration Example

```toml
[tool.ruff]
# General settings
line-length = 88
indent-width = 4
target-version = "py39"

# File discovery
exclude = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
]
extend-exclude = ["tests/fixtures"]
include = ["*.py", "*.pyi", "**/pyproject.toml"]

[tool.ruff.lint]
# Rule selection
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # Pyflakes
    "I",      # isort
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "SIM",    # flake8-simplify
    "C4",     # flake8-comprehensions
]
ignore = [
    "E501",   # Line too long (handled by formatter)
    "B008",   # Function call in default argument
]

# Allow these rules to be auto-fixed
fixable = ["ALL"]
unfixable = []

# Dummy variable pattern (variables matching this are ignored)
dummy-variable-rgx = "^(_+|(_+[a-zA-Z0-9_]*[a-zA-Z0-9]+?))$"

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]           # Unused imports OK in __init__
"tests/*" = ["S101", "PLR2004"]    # Assert and magic numbers OK in tests
"scripts/*" = ["T201"]             # Print OK in scripts

[tool.ruff.lint.isort]
known-first-party = ["my_package"]
combine-as-imports = true
force-single-line = false
lines-after-imports = 2

[tool.ruff.lint.pydocstyle]
convention = "google"  # Options: "google", "numpy", "pep257"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
docstring-code-format = true
docstring-code-line-length = 80
```

## Key Settings Reference

### General Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `line-length` | Maximum line length | 88 |
| `indent-width` | Indentation width | 4 |
| `target-version` | Minimum Python version | `"py39"` |
| `exclude` | Patterns to exclude | Common dirs |
| `extend-exclude` | Additional excludes | `[]` |
| `include` | Patterns to include | `["*.py", "*.pyi"]` |

### Lint Settings (`[tool.ruff.lint]`)

| Setting | Description | Default |
|---------|-------------|---------|
| `select` | Rules to enable | `["E4", "E7", "E9", "F"]` |
| `ignore` | Rules to disable | `[]` |
| `extend-select` | Additional rules | `[]` |
| `fixable` | Rules that can be fixed | `["ALL"]` |
| `unfixable` | Rules that cannot be fixed | `[]` |
| `per-file-ignores` | File-specific ignores | `{}` |

### Format Settings (`[tool.ruff.format]`)

| Setting | Description | Default |
|---------|-------------|---------|
| `quote-style` | Quote style | `"double"` |
| `indent-style` | `"space"` or `"tab"` | `"space"` |
| `line-ending` | `"auto"`, `"lf"`, `"cr-lf"` | `"auto"` |
| `skip-magic-trailing-comma` | Ignore trailing commas | `false` |
| `docstring-code-format` | Format code in docstrings | `false` |

## Rule Selection Patterns

### Enable by Category

```toml
[tool.ruff.lint]
select = ["E", "F", "I"]  # All E, F, and I rules
```

### Enable Specific Rules

```toml
[tool.ruff.lint]
select = ["F401", "F841", "E711"]  # Only these specific rules
```

### Enable All Rules

```toml
[tool.ruff.lint]
select = ["ALL"]  # Everything (use with caution)
ignore = ["D", "ANN"]  # Then ignore what you don't want
```

### Extend Default Selection

```toml
[tool.ruff.lint]
extend-select = ["B", "UP"]  # Add to defaults, don't replace
```

### Ignore Rules

```toml
[tool.ruff.lint]
select = ["E", "F", "B"]
ignore = [
    "E501",   # Specific rule
    "B9",     # All B9xx rules
]
```

## Per-file Ignores

Ignore specific rules for specific files:

```toml
[tool.ruff.lint.per-file-ignores]
# Single file
"__init__.py" = ["F401"]

# Directory pattern
"tests/**/*.py" = ["S101", "PLR2004"]

# Multiple patterns
"scripts/*" = ["T201"]
"migrations/*" = ["E501"]
```

## isort Configuration

Configure import sorting:

```toml
[tool.ruff.lint.isort]
# First-party packages (your code)
known-first-party = ["my_package", "my_other_package"]

# Third-party overrides
known-third-party = ["fastapi"]

# Combine `from x import a, b` style
combine-as-imports = true

# Force each import on its own line
force-single-line = false

# Blank lines after imports
lines-after-imports = 2

# Section order (default is fine for most)
section-order = [
    "future",
    "standard-library", 
    "third-party",
    "first-party",
    "local-folder",
]
```

## pydocstyle Configuration

Configure docstring checking (if using `D` rules):

```toml
[tool.ruff.lint.pydocstyle]
# Convention determines which D rules apply
convention = "google"  # or "numpy", "pep257"
```

| Convention | Style |
|------------|-------|
| `google` | Google style docstrings |
| `numpy` | NumPy style docstrings |
| `pep257` | PEP 257 conventions |

## Monorepo Support

Ruff supports hierarchical configuration. Child directories can have their own config that overrides parent settings:

```
project/
├── pyproject.toml          # Base config
├── src/
│   └── pyproject.toml      # Overrides for src/
└── tests/
    └── pyproject.toml      # Overrides for tests/
```

## Show Resolved Configuration

Debug your configuration:

```bash
# Show all settings for a file
ruff check --show-settings path/to/file.py

# Show which files would be checked
ruff check --show-files
```
