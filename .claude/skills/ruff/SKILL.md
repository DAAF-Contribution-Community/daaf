---
name: ruff
description: Fast Python linter and formatter written in Rust. Covers linting (ruff check), formatting (ruff format), rule configuration, and auto-fixes. Use for any Python code quality, linting, or formatting task.
metadata:
  audience: python-developers
  domain: code-quality
---

# Ruff

Comprehensive skill for Python linting and formatting with Ruff. Use decision trees below to find the right guidance, then load detailed references.

## What is Ruff?

Ruff is an extremely fast Python linter and formatter written in Rust:
- **Fast**: 10-100x faster than Flake8, Pylint, Black
- **Unified**: Replaces Flake8, Black, isort, pyupgrade, and more
- **800+ rules**: Native reimplementations of 50+ Flake8 plugins
- **Auto-fix**: Many violations can be automatically fixed
- **Drop-in**: Compatible with existing Black/isort configurations

## How to Use This Skill

### Reference File Structure

Each topic in `./references/` contains focused documentation:

| File | Purpose | When to Read |
|------|---------|--------------|
| `quickstart.md` | Installation, basic commands, setup | Starting with Ruff |
| `configuration.md` | Config files, rule selection, settings | Configuring a project |
| `rules.md` | Rule categories, common rules, auto-fix | Understanding/selecting rules |
| `commands.md` | CLI reference, flags, output formats | Running Ruff commands |
| `gotchas.md` | Error suppression, CI/CD, issues | Debugging or integrating |

### Reading Order

1. **New to Ruff?** Start with `quickstart.md`
2. **Setting up a project?** Read `configuration.md`
3. **Understanding violations?** Check `rules.md`
4. **Having issues?** Check `gotchas.md` first

## Quick Decision Trees

### "I need to get started"

```
Getting started?
├─ Install Ruff → ./references/quickstart.md
├─ Run first lint check → ruff check .
├─ Format code → ruff format .
├─ Set up pyproject.toml → ./references/configuration.md
└─ VS Code integration → ./references/quickstart.md
```

### "I need to configure rules"

```
Configuring rules?
├─ Choose which rules to enable → ./references/configuration.md
├─ Ignore specific rules → ./references/configuration.md
├─ Per-file ignores → ./references/configuration.md
├─ Configure import sorting → ./references/configuration.md
└─ Set line length/Python version → ./references/configuration.md
```

### "I need to understand a rule"

```
Understanding rules?
├─ What do rule codes mean (F401, E501)? → ./references/rules.md
├─ Which rules should I enable? → ./references/rules.md
├─ Get info on specific rule → ruff rule <CODE>
├─ List all available linters → ruff linter
└─ Which rules are auto-fixable? → ./references/rules.md
```

### "I need to format/fix code"

```
Fixing or formatting?
├─ Format code (like Black) → ruff format .
├─ Auto-fix lint violations → ruff check --fix
├─ Include unsafe fixes → ruff check --fix --unsafe-fixes
├─ Preview changes without applying → ruff check --diff
└─ Sort imports only → ruff check --select I --fix
```

### "Something isn't working"

```
Having issues?
├─ Suppress a specific violation → ./references/gotchas.md
├─ Line too long errors with formatter → ./references/gotchas.md
├─ Set up pre-commit hook → ./references/gotchas.md
├─ CI/CD integration → ./references/gotchas.md
└─ Conflicts with other tools → ./references/gotchas.md
```

## Linting in Research Workflows

**Context:** In education data research pipelines (see `CLAUDE.md`), ruff is run during Stage 10 (Quality Assurance) with output captured for audit.

**Standard execution pattern:**
```bash
# Fix violations and format (standard Stage 10 commands)
ruff check . --fix
ruff format .

# For audit, capture output before/after
ruff check . 2>&1 | tee output/lint_before.txt
ruff check --fix . 2>&1 | tee output/lint_after.txt
```

**Note on script modifications:** When ruff auto-fixes violations in a script that already has an appended execution log, the autonomous deviation rules in `agent_reference/04_BOUNDARIES.md` apply—formatting fixes are allowed without creating a new script version, but substantive changes require versioning.

**See:**
- `agent_reference/02_WORKFLOW_STAGES.md` — Stage 10 (Quality Assurance)
- `agent_reference/04_BOUNDARIES.md` — Autonomous Deviation Rules

---

## Quick Reference

### Essential Commands

| Command | Purpose |
|---------|---------|
| `ruff check .` | Lint current directory |
| `ruff check --fix` | Lint and auto-fix |
| `ruff format .` | Format code (Black-compatible) |
| `ruff format --check` | Check formatting without changes |
| `ruff rule F401` | Explain a specific rule |
| `ruff check --select E,F,I` | Check specific rule categories |

### Rule Prefix Categories

| Prefix | Source | Description |
|--------|--------|-------------|
| **F** | Pyflakes | Core errors (undefined names, unused imports) |
| **E/W** | pycodestyle | Style errors and warnings |
| **I** | isort | Import sorting |
| **UP** | pyupgrade | Python upgrade suggestions |
| **B** | flake8-bugbear | Bug-prone patterns |
| **S** | flake8-bandit | Security issues |
| **C4** | flake8-comprehensions | Comprehension improvements |
| **SIM** | flake8-simplify | Code simplifications |
| **PL** | Pylint | Pylint rules (PLC, PLE, PLR, PLW) |
| **RUF** | Ruff | Ruff-specific rules |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Installation | `./references/quickstart.md` |
| Basic Commands | `./references/quickstart.md` |
| Editor Setup | `./references/quickstart.md` |
| Configuration Files | `./references/configuration.md` |
| Rule Selection | `./references/configuration.md` |
| Per-file Ignores | `./references/configuration.md` |
| Rule Categories | `./references/rules.md` |
| Common Rules | `./references/rules.md` |
| Auto-fix System | `./references/rules.md` |
| CLI Options | `./references/commands.md` |
| Output Formats | `./references/commands.md` |
| Exit Codes | `./references/commands.md` |
| Error Suppression | `./references/gotchas.md` |
| Pre-commit Hooks | `./references/gotchas.md` |
| CI/CD Integration | `./references/gotchas.md` |
