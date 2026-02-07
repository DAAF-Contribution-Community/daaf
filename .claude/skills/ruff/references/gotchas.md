# Gotchas & Best Practices

## Error Suppression

### Line-Level Suppression

```python
# Suppress specific rule on this line
x = 1  # noqa: F841

# Suppress multiple rules
from module import *  # noqa: F401, F403

# Suppress all rules on this line (avoid if possible)
x = 1  # noqa
```

### File-Level Suppression

Add at top of file:

```python
# ruff: noqa: F401
# or
# ruff: noqa: F401, E501
```

This ignores specified rules for the entire file.

### Block-Level Suppression

```python
# fmt: off
manually_formatted = [
    1,    2,    3,
    4,    5,    6,
]
# fmt: on
```

For lint rules (more granular control in config):

```toml
[tool.ruff.lint.per-file-ignores]
"path/to/file.py" = ["F401"]
```

### When to Use noqa

- **Good**: Intentional patterns that violate rules (e.g., unused import for side effects)
- **Avoid**: Using noqa to silence legitimate issues you should fix
- **Always**: Include the rule code (`# noqa: F401` not just `# noqa`)

## Common Issues

### "Line too long" with Formatter

**Problem**: E501 (line-too-long) errors even when using `ruff format`

**Solution**: Ignore E501 - the formatter handles line length, but some lines can't be split (long strings, URLs):

```toml
[tool.ruff.lint]
ignore = ["E501"]
```

### Import Sorting Conflicts

**Problem**: isort or other tools conflict with Ruff's import sorting

**Solution**: Use only Ruff for imports. Remove isort from your toolchain:

```toml
# pyproject.toml - use Ruff's isort
[tool.ruff.lint]
select = ["I"]

# Remove any [tool.isort] section
```

If you must keep isort, disable Ruff's I rules:

```toml
[tool.ruff.lint]
ignore = ["I"]
```

### Unused Imports in __init__.py

**Problem**: F401 flags imports that are intentionally re-exported

**Solution**: Per-file ignore:

```toml
[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
```

Or use `__all__` to make exports explicit:

```python
from .module import MyClass
__all__ = ["MyClass"]
```

### Assert Statements in Tests

**Problem**: S101 (use of assert) in test files

**Solution**: Ignore in tests:

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["S101"]
"test_*.py" = ["S101"]
```

### Magic Numbers in Tests

**Problem**: PLR2004 (magic value in comparison) in tests

**Solution**: Ignore in tests:

```toml
[tool.ruff.lint.per-file-ignores]
"tests/**/*.py" = ["PLR2004"]
```

## Pre-commit Integration

### Basic Setup

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.0  # Use latest version
    hooks:
      # Linter
      - id: ruff
        args: [--fix]
      # Formatter
      - id: ruff-format
```

Install hooks:

```bash
pip install pre-commit
pre-commit install
```

### Running Manually

```bash
pre-commit run ruff --all-files
pre-commit run ruff-format --all-files
```

## CI/CD Integration

### GitHub Actions

```yaml
name: Lint

on: [push, pull_request]

jobs:
  ruff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/ruff-action@v1
```

Or with more control:

```yaml
- name: Install Ruff
  run: pip install ruff

- name: Lint with Ruff
  run: ruff check --output-format=github .

- name: Check formatting
  run: ruff format --check .
```

### GitLab CI

```yaml
ruff:
  image: python:3.11
  script:
    - pip install ruff
    - ruff check --output-format=gitlab --output-file=code-quality-report.json
    - ruff format --check
  artifacts:
    reports:
      codequality: code-quality-report.json
```

### Generic CI Script

```bash
#!/bin/bash
set -e

echo "Running Ruff linter..."
ruff check .

echo "Checking formatting..."
ruff format --check

echo "All checks passed!"
```

## Best Practices

### Recommended Starter Config

```toml
[tool.ruff]
line-length = 88
target-version = "py39"

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "F",     # Pyflakes
    "I",     # isort
    "UP",    # pyupgrade
    "B",     # flake8-bugbear
    "SIM",   # flake8-simplify
]
ignore = [
    "E501",  # Line too long (formatter handles)
]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F401"]
"tests/*" = ["S101"]

[tool.ruff.format]
docstring-code-format = true
```

### Gradual Adoption

When adding Ruff to an existing project:

1. Start with minimal rules:
   ```toml
   select = ["E4", "E7", "E9", "F"]
   ```

2. Run with `--add-noqa` to suppress existing violations:
   ```bash
   ruff check --add-noqa
   ```

3. Gradually enable more rules and fix violations over time

### Workflow Patterns

**Development**:
```bash
# Quick fix and format
ruff check --fix && ruff format
```

**Pre-commit**:
```bash
# Verify before committing
ruff check && ruff format --check
```

**CI (strict)**:
```bash
# No auto-fix, fail on issues
ruff check
ruff format --check
```

### Don't Ignore Too Much

If you find yourself adding many per-file-ignores or noqa comments:
- Consider if the rule is appropriate for your project
- Maybe disable it globally in config instead
- Or fix the underlying code pattern

## Summary Checklist

| Issue | Solution |
|-------|----------|
| E501 with formatter | `ignore = ["E501"]` |
| Unused imports in __init__ | Per-file ignore F401 |
| Assert in tests | Per-file ignore S101 |
| Import sorting conflicts | Use only Ruff's `I` rules |
| Many violations on adoption | Use `--add-noqa` initially |
| CI integration | Use `--output-format=github` or `gitlab` |
| Pre-commit | Use `ruff-pre-commit` repo |
