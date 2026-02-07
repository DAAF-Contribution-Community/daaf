# Quickstart

## Installation

### Using uv (Recommended)

```bash
# Add to project
uv add --dev ruff

# Install globally
uv tool install ruff
```

### Using pip

```bash
pip install ruff
```

### Using pipx (Global Install)

```bash
pipx install ruff
```

### Standalone Installer

```bash
# macOS / Linux
curl -LsSf https://astral.sh/ruff/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/ruff/install.ps1 | iex"
```

### Other Package Managers

```bash
# Homebrew
brew install ruff

# Conda
conda install -c conda-forge ruff
```

## Basic Commands

### Linting

```bash
# Lint current directory
ruff check .

# Lint specific file or directory
ruff check path/to/code/

# Lint and auto-fix violations
ruff check --fix

# Show what would be fixed (no changes)
ruff check --diff
```

### Formatting

```bash
# Format current directory
ruff format .

# Format specific file
ruff format path/to/file.py

# Check if files are formatted (no changes)
ruff format --check

# Show formatting diff (no changes)
ruff format --diff
```

### Combined Workflow

```bash
# Fix lint issues, then format
ruff check --fix && ruff format

# Or fix imports only, then format
ruff check --select I --fix && ruff format
```

## First Project Setup

Create a minimal `pyproject.toml`:

```toml
[tool.ruff]
line-length = 88
target-version = "py39"  # Minimum Python version

[tool.ruff.lint]
select = [
    "E",     # pycodestyle errors
    "F",     # Pyflakes
    "I",     # isort
    "UP",    # pyupgrade
    "B",     # flake8-bugbear
]
ignore = [
    "E501",  # Line too long (formatter handles this)
]

[tool.ruff.format]
docstring-code-format = true
```

Run your first check:

```bash
ruff check .
ruff format --check
```

## Editor Integration

### VS Code

1. Install the **Ruff** extension (`charliermarsh.ruff`)

2. Add to `.vscode/settings.json`:

```json
{
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit",
      "source.organizeImports.ruff": "explicit"
    }
  }
}
```

This enables:
- Format on save
- Auto-fix lint issues on save
- Auto-sort imports on save

### Other Editors

Ruff supports LSP (Language Server Protocol). Most editors can use:

```bash
ruff server
```

Check editor-specific documentation for LSP client setup.

## Verify Installation

```bash
# Check version
ruff --version

# List all available linters
ruff linter

# Get help
ruff --help
ruff check --help
ruff format --help
```

## Next Steps

- Configure rules: [configuration.md](./configuration.md)
- Understand rule categories: [rules.md](./rules.md)
- Learn CLI options: [commands.md](./commands.md)

## Official Resources

- Docs: https://docs.astral.sh/ruff/
- GitHub: https://github.com/astral-sh/ruff
- Rules Reference: https://docs.astral.sh/ruff/rules/
