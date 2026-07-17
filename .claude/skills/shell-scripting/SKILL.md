---
name: shell-scripting
description: >-
  Standards for Bash and PowerShell scripts in DAAF: preambles, quoting, error handling, cleanup, testing. Use when writing or reviewing .sh/.ps1 files (hooks, lifecycle, utilities). Not runtime safety — that is bash-safety.sh hook.
metadata:
  audience: any-agent
  domain: scripting-standards
---

# Shell Scripting Standards

Coding quality standards and best practices for all `.sh` (Bash) and `.ps1` (PowerShell) scripts within DAAF. Covers preamble conventions, quoting discipline, error handling philosophy, signal/cleanup patterns, Docker interaction, output formatting, testing strategies, and cross-platform gotchas. Use when authoring new shell scripts (hooks, Docker lifecycle, utilities), reviewing existing scripts for compliance, debugging script failures, or setting up CI for shell code.

**Boundary with `bash-safety.sh`:** This skill governs *how to write good scripts* (coding quality). The `bash-safety.sh` hook governs *what commands are safe to run* (runtime safety enforcement). A script can follow every standard in this skill and still be blocked by `bash-safety.sh` if it contains a dangerous command like `rm -rf /`. Conversely, a script that passes `bash-safety.sh` may still be poorly written if it ignores these standards.

## How to Use This Skill

### Reference File Structure

| File | Purpose | When to Read |
|------|---------|--------------|
| `bash-standards.md` | Preambles, quoting, variables, ShellCheck, signal handling, host-script Bash 3.2 portability | Writing or reviewing any `.sh` file; anything under `scripts/host/` |
| `powershell-standards.md` | Preambles, dual error system, defensive coding, PSScriptAnalyzer | Writing or reviewing any `.ps1` file |
| `error-handling.md` | Fail-closed philosophy, output conventions, exit codes, Docker errors, dependency validation | Designing error paths for any script |
| `testing.md` | BATS, Pester, CI workflows, Docker mocking, test taxonomy, DAAF safety-hook regression batteries | Setting up or running script tests; writing or modifying a `bash-safety.sh` / `enforce-single-command.sh` hook |
| `gotchas.md` | Bash traps, PowerShell surprises, cross-platform pitfalls | Debugging unexpected script behavior |

### Reading Order

1. **Writing a Bash script?** Start with `bash-standards.md`, then `error-handling.md`
2. **Writing a PowerShell script?** Start with `powershell-standards.md`, then `error-handling.md`
3. **Setting up tests?** Read `testing.md`
4. **Script behaving unexpectedly?** Go straight to `gotchas.md`
5. **Reviewing a script?** Skim `bash-standards.md` or `powershell-standards.md` for the compliance checklist, then `error-handling.md` for error-path quality

## Quick Decision Trees

### "I need to write a script"

```
What kind of script?
├─ Bash (.sh)
│   ├─ Preamble and structure → ./references/bash-standards.md
│   ├─ Error handling design → ./references/error-handling.md
│   ├─ Signal handling / cleanup → ./references/bash-standards.md
│   └─ Scratch probe that makes symlinks (self-cleaning) → ./references/bash-standards.md
├─ PowerShell (.ps1)
│   ├─ Preamble and structure → ./references/powershell-standards.md
│   ├─ Native command error handling → ./references/powershell-standards.md
│   └─ Error handling design → ./references/error-handling.md
└─ Either language
    ├─ Docker interaction → ./references/error-handling.md
    ├─ User-facing output → ./references/error-handling.md
    └─ Cross-platform concerns → ./references/gotchas.md
```

### "I need to review a script"

```
Reviewing a script?
├─ Bash compliance check
│   ├─ Preamble correct? → ./references/bash-standards.md
│   ├─ Quoting discipline? → ./references/bash-standards.md
│   ├─ ShellCheck clean? → ./references/bash-standards.md
│   └─ Error paths robust? → ./references/error-handling.md
├─ PowerShell compliance check
│   ├─ Preamble correct? → ./references/powershell-standards.md
│   ├─ Native command handling? → ./references/powershell-standards.md
│   ├─ PSScriptAnalyzer clean? → ./references/powershell-standards.md
│   └─ Error paths robust? → ./references/error-handling.md
└─ Either language
    ├─ Run parser/linter/tests in-container? → ./references/testing.md
    │   (DAAF_DEV toolchain: pwsh, Pester, PSSA, shellcheck, bats --
    │    PROBE for tools before declaring validation unavailable)
    ├─ Exit code conventions? → ./references/error-handling.md
    └─ Known gotchas present? → ./references/gotchas.md
```

### "Something is broken"

```
Script behaving unexpectedly?
├─ Bash
│   ├─ Exit code masked → ./references/gotchas.md (local var=$(cmd))
│   ├─ Variable empty/unset → ./references/bash-standards.md (nounset)
│   ├─ Pipeline hiding failure → ./references/bash-standards.md (pipefail)
│   └─ cd went to wrong dir → ./references/gotchas.md (cd without || exit)
├─ PowerShell
│   ├─ Native command error ignored → ./references/gotchas.md ($LASTEXITCODE)
│   ├─ Unexpected return value → ./references/gotchas.md (implicit returns)
│   ├─ $null in ForEach loop → ./references/gotchas.md
│   ├─ Validation not firing → ./references/gotchas.md (omitted params)
│   └─ irm | iex fails with BOM error → ./references/gotchas.md (UTF-8 BOM)
└─ Cross-platform
    ├─ Env var case mismatch → ./references/gotchas.md
    ├─ Aliases missing → ./references/gotchas.md
    └─ Exit code truncated → ./references/gotchas.md
```

### "I need to set up tests"

```
Testing shell scripts?
├─ Bash testing
│   ├─ BATS setup → ./references/testing.md
│   ├─ Mocking Docker → ./references/testing.md
│   └─ What to test → ./references/testing.md
├─ PowerShell testing
│   ├─ Pester setup → ./references/testing.md
│   ├─ Mocking native commands → ./references/testing.md
│   └─ What to test → ./references/testing.md
└─ CI integration
    ├─ GitHub Actions matrix → ./references/testing.md
    ├─ Lint-only vs full test → ./references/testing.md
    └─ Path filtering → ./references/testing.md
```

## DAAF Script Conventions (Quick Reference)

Existing patterns in DAAF scripts that this skill codifies:

| Convention | Description | Example |
|------------|-------------|---------|
| Strict preamble | `set -euo pipefail` (Bash) / `$ErrorActionPreference = 'Stop'` (PS) | Every script, first lines |
| Numbered progress | `[1/4] Checking prerequisites...` | All multi-step scripts |
| `DAAF_NESTED` flag | Suppress pause-before-exit when scripts compose | `[ "${DAAF_NESTED:-}" = "1" ] && exit $ec` |
| ERR trap pattern | Catch unexpected failures, explain recovery | `trap 'echo "ERROR: ..."; exit 1' ERR` |
| Preflight checks | Validate all dependencies before any mutation | `command -v docker` before Docker ops |
| Idempotent design | Check for prior state before acting | `[ -f "$BACKUP" ] && echo "Already backed up"` |
| Fail-closed hooks | Security hooks block on uncertainty | `trap ... ERR; exit 2` |
| Backup before destroy | Copy before overwriting | `cp -r "$TARGET" "$TARGET.bak"` |

## Bash Compliance Checklist (Summary)

| # | Requirement | Quick Check |
|---|-------------|-------------|
| 1 | `#!/usr/bin/env bash` shebang | First line |
| 2 | `set -euo pipefail` | Second line |
| 3 | All variables quoted | `"$var"`, `"$(cmd)"` |
| 4 | `local` separate from `$(cmd)` | `local x; x=$(cmd)` |
| 5 | No `eval`, no backticks | Grep for both |
| 6 | `trap cleanup EXIT` for temp files | After variable declarations |
| 7 | ShellCheck clean | `shellcheck -x -S warning` |
| 8 | Errors to stderr with action guidance | `echo "ERROR: ..." >&2` |

## PowerShell Compliance Checklist (Summary)

| # | Requirement | Quick Check |
|---|-------------|-------------|
| 1 | `$ErrorActionPreference = 'Stop'` | First line |
| 2 | `Set-StrictMode -Version 3.0` | Second line (DAAF exception: scripts with a `DAAF_TEST_MODE` dot-source guard place it immediately *after* the guard; dot-sourced libraries like `daaf_lib.ps1` carry no directive -- see `powershell-standards.md` > "Strict Mode Placement in DAAF Host Scripts") |
| 3 | `$LASTEXITCODE` checked after every native command | After docker, git, etc. |
| 4 | `[CmdletBinding()]` on functions | Function declarations |
| 5 | `$null = expr` not `\| Out-Null` | Performance |
| 6 | No reliance on `$?` for native commands | Grep for `$?` near docker/git |
| 7 | PSScriptAnalyzer clean | `Invoke-ScriptAnalyzer` |
| 8 | Errors via `Write-Error` with guidance | Error output |
| 9 | ASCII-only content (no BOM) | `file script.ps1` reports "ASCII text" |
| 10 | No interactive native commands in expression-context function calls | No `if (Fn)`, `$x = Fn` for functions with `docker exec`, `ssh`, etc. |

## Exit Code Conventions

| Code | Meaning | Used By |
|------|---------|---------|
| 0 | Success | All scripts |
| 1 | General error | All scripts |
| 2 | Blocked (hook convention) | `.claude/hooks/*.sh` |
| 10-19 | Docker failures | Docker lifecycle scripts |
| 20-29 | Configuration errors | Setup/config scripts |
| 30-39 | Dependency errors | Preflight validation scripts |

## Topic Index

| Topic | Reference File |
|-------|---------------|
| Bash shebang and preamble | `./references/bash-standards.md` |
| Bash quoting rules | `./references/bash-standards.md` |
| Bash variable handling | `./references/bash-standards.md` |
| ShellCheck integration | `./references/bash-standards.md` |
| Bash signal handling and cleanup | `./references/bash-standards.md` |
| Probe / test-harness hygiene (self-cleaning symlinks, workspace invariant checker) | `./references/bash-standards.md` |
| Bash never-do list | `./references/bash-standards.md` |
| Host-script Bash 3.2 portability (macOS `/bin/bash`) | `./references/bash-standards.md` |
| Banned Bash-4.x-only constructs for host scripts | `./references/bash-standards.md` |
| BSD vs GNU userland pitfalls (`sed -i`, `date -d`, `stat`, `readlink -f`) | `./references/bash-standards.md` |
| In-container command availability (Dockerfile-installed set) | `./references/bash-standards.md` |
| PowerShell preamble | `./references/powershell-standards.md` |
| PowerShell ASCII-only encoding | `./references/powershell-standards.md` |
| PowerShell dual error system | `./references/powershell-standards.md` |
| PowerShell defensive coding | `./references/powershell-standards.md` |
| PowerShell output streams | `./references/powershell-standards.md` |
| PSScriptAnalyzer | `./references/powershell-standards.md` |
| Fail-closed principle | `./references/error-handling.md` |
| User-facing output formatting | `./references/error-handling.md` |
| Exit code conventions | `./references/error-handling.md` |
| Docker error handling | `./references/error-handling.md` |
| Dependency validation | `./references/error-handling.md` |
| NO_COLOR and TTY detection | `./references/error-handling.md` |
| BATS test framework | `./references/testing.md` |
| Pester test framework | `./references/testing.md` |
| CI workflow setup | `./references/testing.md` |
| Docker mocking strategies | `./references/testing.md` |
| Test taxonomy (lint/unit/smoke/integration) | `./references/testing.md` |
| In-container validation toolchain (DAAF_DEV: pwsh, Pester, PSScriptAnalyzer, shellcheck, bats) | `./references/testing.md` |
| Safety-hook regression batteries (`test_safety_hooks.sh`, `test_enforce_single_command.sh`) | `./references/testing.md` |
| What to test and what to skip | `./references/testing.md` |
| Bash exit code masking | `./references/gotchas.md` |
| Bash set -e edge cases | `./references/gotchas.md` |
| PowerShell `exit` in dot-sourced functions | `./references/gotchas.md` |
| PowerShell $LASTEXITCODE vs $? | `./references/gotchas.md` |
| PowerShell UTF-8 BOM breaks iex | `./references/gotchas.md` |
| PowerShell implicit returns | `./references/gotchas.md` |
| PowerShell $null pipeline behavior | `./references/gotchas.md` |
| Cross-platform env var casing | `./references/gotchas.md` |
| Cross-platform alias differences | `./references/gotchas.md` |
| Cross-platform exit code truncation | `./references/gotchas.md` |
| Cross-platform path separators | `./references/gotchas.md` |
| Cross-language octal `printf` escaping (`\\357`/`\\011` to `sh`) | `./references/gotchas.md` |
| Detached-container (`docker run -d`) diagnostics routing | `./references/error-handling.md` |
