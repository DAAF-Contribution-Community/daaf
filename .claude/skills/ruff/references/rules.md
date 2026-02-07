# Rules System

## Rule Prefix Categories

Ruff implements 800+ rules from various linters. Each rule has a code like `F401` where the prefix indicates the source.

### Core Linters

| Prefix | Source | Description |
|--------|--------|-------------|
| **F** | Pyflakes | Core Python errors (unused imports, undefined names) |
| **E** | pycodestyle | Style errors (indentation, whitespace) |
| **W** | pycodestyle | Style warnings |
| **C90** | mccabe | Complexity checking |
| **I** | isort | Import sorting |
| **N** | pep8-naming | Naming conventions |
| **D** | pydocstyle | Docstring style |
| **UP** | pyupgrade | Python version upgrade suggestions |
| **YTT** | flake8-2020 | Python 3.10+ compatibility |
| **ANN** | flake8-annotations | Type annotation issues |
| **ASYNC** | flake8-async | Async/await issues |
| **S** | flake8-bandit | Security issues |
| **BLE** | flake8-blind-except | Blind except clauses |
| **FBT** | flake8-boolean-trap | Boolean positional arguments |
| **B** | flake8-bugbear | Bug-prone patterns |
| **A** | flake8-builtins | Shadowing builtins |
| **COM** | flake8-commas | Trailing commas |
| **CPY** | flake8-copyright | Copyright notices |
| **C4** | flake8-comprehensions | Comprehension improvements |
| **DTZ** | flake8-datetimez | Timezone-aware datetime |
| **T10** | flake8-debugger | Debugger statements (breakpoint, pdb) |
| **DJ** | flake8-django | Django-specific rules |
| **EM** | flake8-errmsg | Exception message formatting |
| **EXE** | flake8-executable | Executable scripts |
| **FA** | flake8-future-annotations | Future annotations |
| **ISC** | flake8-implicit-str-concat | Implicit string concatenation |
| **ICN** | flake8-import-conventions | Import alias conventions |
| **LOG** | flake8-logging | Logging best practices |
| **G** | flake8-logging-format | Logging format strings |
| **INP** | flake8-no-pep420 | Implicit namespace packages |
| **PIE** | flake8-pie | Misc. improvements |
| **T20** | flake8-print | Print statements |
| **PYI** | flake8-pyi | Stub file (.pyi) issues |
| **PT** | flake8-pytest-style | Pytest style |
| **Q** | flake8-quotes | Quote consistency |
| **RSE** | flake8-raise | Exception raising |
| **RET** | flake8-return | Return statement issues |
| **SLF** | flake8-self | Private member access |
| **SLOT** | flake8-slots | __slots__ usage |
| **SIM** | flake8-simplify | Code simplifications |
| **TID** | flake8-tidy-imports | Import restrictions |
| **TCH** | flake8-type-checking | TYPE_CHECKING imports |
| **INT** | flake8-gettext | i18n/gettext |
| **ARG** | flake8-unused-arguments | Unused function arguments |
| **PTH** | flake8-use-pathlib | Prefer pathlib over os.path |
| **TD** | flake8-todos | TODO comment formatting |
| **FIX** | flake8-fixme | FIXME/TODO/XXX comments |
| **ERA** | eradicate | Commented-out code |
| **PD** | pandas-vet | Pandas-specific issues |
| **PGH** | pygrep-hooks | Misc. grep-based checks |
| **PL** | Pylint | Pylint rules (see subcategories) |
| **TRY** | tryceratops | Exception handling |
| **FLY** | flynt | f-string conversion |
| **NPY** | NumPy | NumPy-specific rules |
| **PERF** | Perflint | Performance suggestions |
| **FURB** | refurb | Modernization suggestions |
| **RUF** | Ruff | Ruff-specific rules |

### Pylint Subcategories

| Prefix | Category |
|--------|----------|
| **PLC** | Convention |
| **PLE** | Error |
| **PLR** | Refactor |
| **PLW** | Warning |

## Most Commonly Used Rules

### Import Rules

| Code | Name | Description | Fixable |
|------|------|-------------|---------|
| F401 | unused-import | Imported but unused | Yes |
| F403 | undefined-local-with-import-star | `from x import *` used | No |
| I001 | unsorted-imports | Imports not sorted | Yes |
| I002 | missing-required-import | Required import missing | Yes |

### Variable Rules

| Code | Name | Description | Fixable |
|------|------|-------------|---------|
| F841 | unused-variable | Variable assigned but never used | Yes |
| F811 | redefined-while-unused | Redefinition of unused name | No |
| F821 | undefined-name | Undefined name | No |

### Style Rules

| Code | Name | Description | Fixable |
|------|------|-------------|---------|
| E501 | line-too-long | Line exceeds max length | No |
| E711 | none-comparison | Comparison to None (use `is`) | Yes |
| E712 | true-false-comparison | Comparison to True/False | Yes |
| W291 | trailing-whitespace | Trailing whitespace | Yes |
| W293 | blank-line-with-whitespace | Blank line contains whitespace | Yes |

### Bug-prone Patterns (flake8-bugbear)

| Code | Name | Description | Fixable |
|------|------|-------------|---------|
| B006 | mutable-argument-default | Mutable default argument | No |
| B007 | unused-loop-control-variable | Unused loop variable | Yes |
| B008 | function-call-in-default-argument | Function call in default arg | No |
| B015 | useless-comparison | Pointless comparison | No |
| B018 | useless-expression | Useless expression | No |

### Upgrade Rules (pyupgrade)

| Code | Name | Description | Fixable |
|------|------|-------------|---------|
| UP008 | super-call-with-parameters | Use `super()` without args | Yes |
| UP035 | deprecated-import | Use `collections.abc` | Yes |
| UP036 | outdated-version-block | Remove outdated version blocks | Yes |

### Simplify Rules

| Code | Name | Description | Fixable |
|------|------|-------------|---------|
| SIM102 | collapsible-if | Nested if can be collapsed | Yes |
| SIM105 | suppressible-exception | Use `contextlib.suppress` | Yes |
| SIM110 | reimplemented-builtin | Use `any()` or `all()` | Yes |
| SIM118 | in-dict-keys | Use `key in dict` not `in dict.keys()` | Yes |

## Auto-fix System

### Safe vs Unsafe Fixes

**Safe fixes**: Guaranteed to preserve code meaning
```bash
ruff check --fix              # Only safe fixes
```

**Unsafe fixes**: May change behavior (review carefully)
```bash
ruff check --fix --unsafe-fixes
```

### Controlling Fixable Rules

```toml
[tool.ruff.lint]
# All rules can be fixed
fixable = ["ALL"]

# Never auto-fix these (require manual review)
unfixable = ["B", "F841"]

# Promote unsafe fix to safe
extend-safe-fixes = ["F601"]

# Demote safe fix to unsafe
extend-unsafe-fixes = ["UP034"]
```

### Fix-Related Flags

| Flag | Description |
|------|-------------|
| `--fix` | Apply safe fixes |
| `--fix --unsafe-fixes` | Apply all fixes |
| `--fix-only` | Fix without reporting remaining issues |
| `--diff` | Show changes without applying |
| `--show-fixes` | List what was fixed |

## Getting Rule Information

### Explain a Rule

```bash
ruff rule F401
```

Output includes:
- Rule name and code
- Description
- Whether it's fixable
- Example code (what it catches)

### List All Linters

```bash
ruff linter
```

Shows all available linter categories with rule counts.

### View Rules for a Linter

Check the docs at https://docs.astral.sh/ruff/rules/ or filter by prefix:

```bash
ruff check --select B --show-settings 2>&1 | grep -A 100 "rules:"
```

## Recommended Rule Sets

### Minimal (Safe Start)

```toml
select = ["E4", "E7", "E9", "F"]  # Ruff's default
```

### Balanced (Good Coverage)

```toml
select = ["E", "F", "I", "UP", "B"]
ignore = ["E501"]
```

### Comprehensive

```toml
select = [
    "E", "W",    # pycodestyle
    "F",         # Pyflakes
    "I",         # isort
    "UP",        # pyupgrade
    "B",         # bugbear
    "SIM",       # simplify
    "C4",        # comprehensions
    "RUF",       # Ruff-specific
]
ignore = ["E501"]
```

### Maximum (Use with Caution)

```toml
select = ["ALL"]
ignore = [
    "D",     # pydocstyle (requires docstrings everywhere)
    "ANN",   # annotations (requires full typing)
    "ERA",   # eradicate (false positives on comments)
]
```
