# CLI Commands Reference

## ruff check

Lint Python files.

### Basic Usage

```bash
ruff check                     # Lint current directory
ruff check .                   # Same as above
ruff check path/to/file.py    # Lint specific file
ruff check src/ tests/        # Lint multiple directories
ruff check --fix              # Auto-fix violations
```

### Rule Selection Flags

| Flag | Description |
|------|-------------|
| `--select RULES` | Enable specific rules (comma-separated) |
| `--ignore RULES` | Disable specific rules |
| `--extend-select RULES` | Add rules to existing selection |
| `--fixable RULES` | Rules that can be fixed |
| `--unfixable RULES` | Rules that cannot be fixed |

```bash
# Enable only specific rules
ruff check --select F401,E711

# Enable rule categories
ruff check --select E,F,I

# Add to config selection
ruff check --extend-select B

# Ignore specific rules
ruff check --ignore E501,W503
```

### Fix Flags

| Flag | Description |
|------|-------------|
| `--fix` | Apply safe fixes |
| `--unsafe-fixes` | Also apply unsafe fixes (requires --fix) |
| `--fix-only` | Fix without reporting remaining issues |
| `--diff` | Show diff without applying changes |
| `--show-fixes` | Show what was fixed |

```bash
# Apply safe fixes only
ruff check --fix

# Apply all fixes including unsafe
ruff check --fix --unsafe-fixes

# Preview what would change
ruff check --diff

# Fix and don't report remaining violations
ruff check --fix-only
```

### Output Format Flags

| Flag | Description |
|------|-------------|
| `--output-format FORMAT` | Output format |
| `--show-source` | Show source code with violations |
| `--statistics` | Show violation counts |
| `-q, --quiet` | Minimal output |
| `-v, --verbose` | Verbose output |

Available formats:
- `concise` (default) - One line per violation
- `full` - Includes source code
- `json` - JSON output
- `json-lines` - JSON Lines format
- `github` - GitHub Actions annotations
- `gitlab` - GitLab CI Code Quality format
- `pylint` - Pylint-compatible format
- `azure` - Azure DevOps format
- `sarif` - SARIF format

```bash
# JSON output
ruff check --output-format=json

# GitHub Actions (shows annotations in PR)
ruff check --output-format=github

# Show statistics
ruff check --statistics
```

### File Selection Flags

| Flag | Description |
|------|-------------|
| `--exclude PATTERN` | Exclude files matching pattern |
| `--extend-exclude PATTERN` | Add to existing excludes |
| `--force-exclude` | Enforce excludes even for explicit paths |
| `--respect-gitignore/--no-respect-gitignore` | Use .gitignore |

```bash
# Exclude additional patterns
ruff check --extend-exclude "migrations/*"

# Force check even excluded files
ruff check path/to/excluded.py --no-force-exclude
```

### Other Useful Flags

| Flag | Description |
|------|-------------|
| `--watch` | Re-lint on file changes |
| `--add-noqa` | Add noqa comments to all violations |
| `--show-files` | List files that would be checked |
| `--show-settings` | Show resolved configuration |
| `--config PATH` | Use specific config file |
| `--isolated` | Ignore config files |

```bash
# Watch mode for development
ruff check --watch

# Add noqa comments to all current violations
ruff check --add-noqa

# Debug: see what files would be checked
ruff check --show-files

# Debug: see resolved settings
ruff check --show-settings path/to/file.py
```

## ruff format

Format Python files (Black-compatible).

### Basic Usage

```bash
ruff format                    # Format current directory
ruff format .                  # Same as above
ruff format path/to/file.py   # Format specific file
ruff format src/ tests/       # Format multiple directories
```

### Check Mode (No Changes)

```bash
# Exit non-zero if files would be reformatted
ruff format --check

# Show diff of what would change
ruff format --diff

# Both: show diff and exit non-zero
ruff format --check --diff
```

### Format Options

| Flag | Description |
|------|-------------|
| `--line-length N` | Override line length |
| `--target-version VERSION` | Override Python version |
| `--config PATH` | Use specific config file |
| `--isolated` | Ignore config files |

```bash
# Use different line length
ruff format --line-length 100

# Target specific Python version
ruff format --target-version py311
```

### File Selection

Same as `ruff check`:

```bash
ruff format --exclude "migrations/*"
ruff format --extend-exclude "generated/*"
```

## Exit Codes

### ruff check

| Code | Meaning |
|------|---------|
| 0 | No violations (or all fixed with --fix) |
| 1 | Violations found |
| 2 | Invalid configuration or internal error |

### ruff format

| Code | Meaning |
|------|---------|
| 0 | Success (files formatted or already formatted) |
| 1 | Files would be reformatted (with --check) |
| 2 | Invalid configuration or error |

## Utility Commands

### ruff rule

Get information about a specific rule:

```bash
ruff rule F401
ruff rule E501
ruff rule B006
```

### ruff linter

List all available linters:

```bash
ruff linter
```

### ruff clean

Clear Ruff's cache:

```bash
ruff clean
```

### ruff config

List all available configuration options:

```bash
ruff config
```

### ruff version

Show version information:

```bash
ruff version
ruff --version
```

## Common Workflows

### Lint and Format Together

```bash
# Fix lint issues, then format
ruff check --fix && ruff format

# Or in CI: check both without changes
ruff check && ruff format --check
```

### Sort Imports Only

```bash
ruff check --select I --fix
```

### Check Before Commit

```bash
# Quick check
ruff check --select E,F,I && ruff format --check

# Thorough check
ruff check && ruff format --check
```

### CI Pipeline

```bash
# Strict mode: fail on any issue
ruff check --output-format=github
ruff format --check
```

### Fix Everything Possible

```bash
ruff check --fix --unsafe-fixes
ruff format
```
