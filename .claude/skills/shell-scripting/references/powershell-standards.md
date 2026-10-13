# PowerShell Standards

Comprehensive standards for writing PowerShell scripts in DAAF. Covers preamble rules, the dual error system, defensive coding patterns, output streams, and PSScriptAnalyzer integration.

---

## Preamble

Every PowerShell script starts with these lines:

```powershell
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0
```

**What each line does:**

| Line | Purpose | Nuance |
|------|---------|--------|
| `#Requires -Version 5.1` | Fail fast on unsupported environments | Checked before script body executes |
| `$ErrorActionPreference = 'Stop'` | Convert terminating errors into exceptions caught by `try/catch` | Does NOT affect native command exit codes |
| `Set-StrictMode -Version 3.0` | Catch uninitialized variables, non-existent properties | Prefer `-Version 3.0` over `-Version Latest` — Latest is non-deterministic across PS releases |

**Why not `-Version Latest`?**

`Set-StrictMode -Version Latest` resolves to whatever version the runtime supports. This means the same script may enforce different rules on different machines, creating hard-to-reproduce failures. `-Version 3.0` is deterministic.

### Strict Mode Placement in DAAF Host Scripts

The "second line" rule above is the general case. DAAF host scripts (`scripts/host/*.ps1`) carry two deliberate exceptions -- do NOT flag them as non-compliant:

- **Scripts with a `DAAF_TEST_MODE` dot-source guard place `Set-StrictMode` immediately *after* the guard, not in the preamble.** These scripts begin with a guard that returns early (skipping the main body) when the file is dot-sourced by the Pester suite, so tests can load functions without executing side effects. `Set-StrictMode` is dynamically scoped: if it ran before the guard, it would leak into and persist across the whole Pester session, changing the strictness of every other test. Placing it *after* the guard confines strict mode to the script's own execution path. The trade-off (the few guard lines run without strict mode) is intentional and documented inline in each script.

- **Dot-sourced library files carry NO `Set-StrictMode` directive.** `daaf_lib.ps1` (mirroring `daaf_lib.sh`) is a pure function library that is always dot-sourced into a caller; the caller imposes strict mode. A directive in the library would either leak into the caller's session or fight the caller's chosen version. Libraries stay directive-free; callers own the strict-mode decision.

The full rationale for each script lives in that script's inline comments; this note exists so a reviewer applying the checklist does not "correct" the placement.

---

## Character Encoding: ASCII Only

All `.ps1` host scripts must contain only ASCII characters (code points 0-127). No em-dashes (`---`), curly quotes, or other non-ASCII content -- not even in comments.

**Why:** Non-ASCII characters in a `.ps1` file require a UTF-8 BOM (byte order mark) for PowerShell 5.1 to interpret them correctly. The BOM is invisible but prepends three bytes (`EF BB BF`) to the file. When the script is executed via `irm URL | iex` (the standard `Invoke-Expression` one-liner pattern), PowerShell does not strip the BOM. The BOM character gets prepended to the first `#`, making the comment line look like a command:

```
The term '﻿#' is not recognized as the name of a cmdlet, function, script file,
or operable program.
```

This `CommandNotFoundException` is caught by `trap` handlers and masks the real error, making the failure extremely difficult to diagnose.

**Rule:** Replace all non-ASCII characters with ASCII equivalents:

| Non-ASCII | ASCII Replacement |
|-----------|-------------------|
| `---` (em-dash, U+2014) | `--` |
| `--` (en-dash, U+2013) | `--` |
| `\u2018` `\u2019` (curly single quotes) | `'` |
| `\u201C` `\u201D` (curly double quotes) | `"` |

**Verification:** Save files without BOM. In VS Code, the status bar shows "UTF-8" (no BOM) or "UTF-8 with BOM" -- ensure it shows "UTF-8" only. From the command line: `file script.ps1` should report "ASCII text", not "UTF-8 Unicode (with BOM)".

---

## The Dual Error System (Critical)

PowerShell has two fundamentally different error mechanisms. Confusing them is the single most common source of PowerShell bugs in cross-tool scripts.

### Cmdlet Errors (Terminating)

PowerShell cmdlets throw terminating errors when `$ErrorActionPreference = 'Stop'`. These are caught by `try/catch`:

```powershell
try {
    Get-Content -Path "nonexistent.txt"
}
catch {
    Write-Error "File read failed: $_"
}
```

### Native Command Errors (Exit Codes)

Native executables (`docker`, `git`, `curl`, etc.) communicate via exit codes. PowerShell does NOT auto-convert non-zero exit codes to exceptions. `try/catch` will NOT catch a `docker build` failure:

```powershell
# BAD: docker failure is silently ignored
try {
    docker build -t myimage .    # Exit code 1 — NOT caught
}
catch {
    Write-Error "This never fires for native command failures"
}

# GOOD: explicit exit code check
docker build -t myimage .
if ($LASTEXITCODE -ne 0) {
    throw "docker build failed (exit code: $LASTEXITCODE)"
}
```

### The Assert-ExitCode Helper

For scripts with many native command calls, define a helper:

```powershell
function Assert-ExitCode {
    param(
        [Parameter(Mandatory)]
        [string]$Command
    )
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed (exit code: $LASTEXITCODE)"
    }
}

# Usage:
docker compose up -d
Assert-ExitCode "docker compose up"

git pull origin main
Assert-ExitCode "git pull"
```

### $LASTEXITCODE vs $?

| Variable | What It Tracks | Reliable For |
|----------|---------------|--------------|
| `$LASTEXITCODE` | Exit code of the last native command | Native commands (docker, git, curl) — always use this |
| `$?` | Whether the last operation "succeeded" | Cmdlets only — unreliable for native commands |

**Never use `$?` to check Docker or Git results.** Stderr output from native commands can cause `$?` to return `$false` even when the command succeeded (exit code 0).

### PS 7.4+ Automatic Conversion

PowerShell 7.4+ introduces `$PSNativeCommandUseErrorActionPreference = $true`, which auto-converts non-zero exit codes to errors. However:

- Scripts targeting PS 5.1 cannot use this
- For cross-version compatibility, always check `$LASTEXITCODE` explicitly

---

## Defensive Coding

### CmdletBinding and Parameter Validation

```powershell
function Install-DaafComponent {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$ComponentName,

        [ValidateSet('Install', 'Update', 'Remove')]
        [string]$Action = 'Install'
    )

    # ... implementation ...
}
```

**Note on validation:** Parameter validation attributes fire only when the parameter is *supplied*. Omitted parameters bypass validation entirely — if a parameter has no default and is not `[Mandatory]`, it may be `$null` or empty at runtime despite `[ValidateNotNullOrEmpty()]`.

### Suppress Unwanted Output

Every unhandled expression in a function body becomes part of the return value. This is one of PowerShell's most surprising behaviors:

```powershell
# BAD: ArrayList.Add() returns the index — it becomes part of the return value
function Get-ProcessedItems {
    $list = [System.Collections.ArrayList]::new()
    $list.Add("item1")   # Returns 0 — leaked into output
    $list.Add("item2")   # Returns 1 — leaked into output
    return $list
}
# Result: 0, 1, item1, item2  (not just item1, item2)

# GOOD: suppress the return value
function Get-ProcessedItems {
    $list = [System.Collections.ArrayList]::new()
    $null = $list.Add("item1")
    $null = $list.Add("item2")
    return $list
}
```

Use `$null = expression` to suppress unwanted output. Avoid `| Out-Null` — it creates a pipeline and is up to 40x slower.

### Empty Collection Safety

`$null` in a pipeline executes `ForEach-Object` once with `$_` set to `$null`:

```powershell
# BAD: if $items is $null, the loop body runs once with $_ = $null
$items | ForEach-Object { Process-Item $_ }

# GOOD: wrap in @() to ensure an empty array, not $null
@($items) | ForEach-Object { Process-Item $_ }

# ALSO GOOD: null-check first
if ($null -ne $items) {
    $items | ForEach-Object { Process-Item $_ }
}
```

### Launching Child Processes (Start-Process)

Prefer direct invocation (`& $exe @argArray`, then check `$LASTEXITCODE`) — PowerShell quotes each element and the exit code is reliable. Caveat: on Windows PowerShell 5.1 the direct-call path is reported to still mishandle an embedded `"` or a trailing backslash before the closing quote of a spaced argument (see `gotchas.md` > "Embedded Double-Quotes in Native Command Arguments on Windows"). PowerShell 7.3+ reworked native argument passing (`$PSNativeCommandArgumentPassing`), but that preference governs `&` / direct invocation only, NOT `Start-Process`: on pwsh 7.6 an `-ArgumentList @($script, 'a b', 'q"z')` array reached the child as `<a><b><qz>` under both `Legacy` and `Standard`, while `& sh $script 'a b' 'q"z'` gave `<a b><q"z>` under `Standard` (observed 2026-09-29, Linux). Reach for `Start-Process` only when you need what it uniquely provides: console-handle inheritance for an interactive child (`-NoNewWindow`, used by `daaf.ps1`'s delegates) or a Process object to poll while showing progress (`backup_daaf.ps1`'s `docker cp`). When you do, two rules are mandatory:

1. **Pass `-ArgumentList` ONE pre-joined string, every element quoted by `ConvertTo-DaafNativeArg`.** An array is joined with bare spaces and never quoted, so any path with a space splits into several arguments.
2. **Cache `.Handle` immediately after launch, read `ExitCode` defensively, and treat `$null` as UNKNOWN.** On Windows — Windows PowerShell 5.1 and PowerShell 6.0–7.4.0, with `-NoNewWindow` and/or `-RedirectStandard*` — an uncached `-PassThru` object's `ExitCode` reads `$null` (PowerShell#5421, #20400; fixed in 7.4.1); unknown is never success.

```powershell
# Drop $null first: a $null $ScriptArgs would otherwise become an explicit "" argument.
$argString = (@('-NoProfile', '-File', $childPath) + @($ScriptArgs | Where-Object { $null -ne $_ }) |
    ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '
$proc = Start-Process -FilePath $hostExe -ArgumentList $argString -NoNewWindow -PassThru
try { $null = $proc.Handle } catch { Write-Verbose "Could not cache the process handle: $_" }
$proc.WaitForExit()
$ec = $null
try { $ec = $proc.ExitCode } catch { $ec = $null }
if ($null -eq $ec) { <# UNKNOWN: warn or fail closed #> }
elseif ($ec -ne 0) { <# FAILURE #> }
```

`ConvertTo-DaafNativeArg` is defined canonically in `scripts/host/daaf_lib.ps1`. A standalone script that does not dot-source the library carries an INLINE COPY (header comment `INLINE COPY of daaf_lib.ps1 ConvertTo-DaafNativeArg`) that must stay byte-identical, and must be added to the inline-copy list in `tests/powershell/native_arg_quoting.Tests.ps1`, which also enforces both rules structurally across `scripts/host/*.ps1`. Full rationale, sources, and BAD/GOOD examples: `gotchas.md` > "`Start-Process -ArgumentList` Joins an Array With Bare Spaces (No Quoting)" and "`Start-Process -PassThru` `ExitCode` Reads `$null` Unless `.Handle` Is Cached".

---

## Output Streams

PowerShell has multiple output streams. Use the right one for each purpose:

| Cmdlet | Stream | When to Use |
|--------|--------|-------------|
| `Write-Output` | Success (1) | Data output that should be capturable by callers |
| `Write-Host` | Information (6) | Display-only status with color (appropriate for CLI tools) |
| `Write-Error` | Error (2) | Actual error conditions |
| `Write-Warning` | Warning (3) | Non-fatal concerns the user should know about |
| `Write-Verbose` | Verbose (4) | Troubleshooting detail (visible with `-Verbose`) |
| `Write-Debug` | Debug (5) | Developer-level tracing (visible with `-Debug`) |

### Color Conventions

```powershell
Write-Host "[1/3] Checking prerequisites..." -ForegroundColor Cyan
Write-Host "SUCCESS: All checks passed" -ForegroundColor Green
Write-Host "WARNING: Using fallback path" -ForegroundColor Yellow
Write-Error "FAILED: Docker not found. Install Docker Desktop from https://docs.docker.com/get-docker/"
```

### Progress Indicators

```powershell
$steps = 4
Write-Host "[1/$steps] Checking prerequisites..." -ForegroundColor Cyan
# ...
Write-Host "[2/$steps] Backing up current state..." -ForegroundColor Cyan
# ...
Write-Host "[3/$steps] Applying changes..." -ForegroundColor Cyan
# ...
Write-Host "[4/$steps] Verifying results..." -ForegroundColor Cyan
Write-Host "Done." -ForegroundColor Green
```

---

## PSScriptAnalyzer

[PSScriptAnalyzer](https://github.com/PowerShell/PSScriptAnalyzer) is the standard linter for PowerShell scripts.

### Running the Analyzer

```powershell
Invoke-ScriptAnalyzer -Path ./scripts -Recurse -EnableExit
```

`-EnableExit` sets a non-zero exit code when violations are found, useful for CI pipelines.

### Configuration File

Create `PSScriptAnalyzerSettings.psd1` in `.github/linters/` and check it in:

```powershell
@{
    Severity = @('Error', 'Warning')
    Rules    = @{
        PSAvoidUsingCmdletAliases         = @{ Enable = $true }
        PSAvoidUsingInvokeExpression       = @{ Enable = $true }
        PSUseDeclaredVarsMoreThanAssignments = @{ Enable = $true }
        PSAvoidUsingWriteHost              = @{ Enable = $false }  # We use Write-Host for CLI output
    }
}
```

### Key Rules

| Rule | What It Catches | Why It Matters |
|------|----------------|----------------|
| `PSAvoidUsingCmdletAliases` | `ls`, `cat`, `cp` instead of full cmdlet names | Aliases are removed on Linux/macOS PowerShell |
| `PSAvoidUsingInvokeExpression` | `Invoke-Expression` (PowerShell's `eval`) | Same injection risks as Bash `eval` |
| `PSUseDeclaredVarsMoreThanAssignments` | Variables assigned but never read | Dead code that confuses readers |
| `PSAvoidUsingWriteHost` | `Write-Host` usage | Disabled in DAAF config — we use it intentionally for CLI tools |

---

## Script Structure

```powershell
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

# --- Config ---
$BaseDir = $PSScriptRoot
$MaxRetries = 3

# --- Helpers ---
function Assert-ExitCode {
    param([Parameter(Mandatory)][string]$Command)
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed (exit code: $LASTEXITCODE)"
    }
}

# --- Preflight ---
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker not found. Install from https://docs.docker.com/get-docker/"
    exit 1
}

# --- Main ---
Write-Host "[1/3] Starting operation..." -ForegroundColor Cyan
# ...
Write-Host "[2/3] Processing..." -ForegroundColor Cyan
# ...
Write-Host "[3/3] Finalizing..." -ForegroundColor Cyan

Write-Host "Done." -ForegroundColor Green
```

---

## Compliance Checklist

| # | Item | Check |
|---|------|-------|
| 1 | `#Requires -Version 5.1` | First line |
| 2 | `$ErrorActionPreference = 'Stop'` | Near top |
| 3 | `Set-StrictMode -Version 3.0` (not `-Version Latest`) | Near top -- but see "Strict Mode Placement in DAAF Host Scripts": scripts with a `DAAF_TEST_MODE` guard place it *after* the guard; dot-sourced libraries (`daaf_lib.ps1`) carry no directive |
| 4 | `$LASTEXITCODE` checked after every native command | After docker, git, etc. |
| 5 | No reliance on `$?` for native commands | Grep for `if \($\?` near native calls |
| 6 | `[CmdletBinding()]` on all functions | Function declarations |
| 7 | `[ValidateNotNullOrEmpty()]` on string parameters | Parameter blocks |
| 8 | `$null = expr` not `\| Out-Null` | Performance |
| 9 | No implicit returns leaking into function output | Review all expressions in functions |
| 10 | PSScriptAnalyzer clean | `Invoke-ScriptAnalyzer -Path . -Recurse -EnableExit` |
| 11 | No `Invoke-Expression` | Grep for `Invoke-Expression` |
| 12 | Full cmdlet names (no aliases like `ls`, `cat`) | PSScriptAnalyzer rule |
| 13 | Progress steps use `[N/M]` format | Visual scan |
| 14 | ASCII-only content (no em-dashes, curly quotes, no BOM) | `file script.ps1` should report "ASCII text" |
| 15 | Functions with interactive native commands never called in expression context | No `if (Fn)`, `$x = Fn`, or `Fn \|` for functions containing `docker exec`, `ssh`, etc. -- use script-scoped variables for return values (see gotchas.md) |
| 16 | `Start-Process -ArgumentList` is one pre-joined string built with `ConvertTo-DaafNativeArg` | No `-ArgumentList @(...)`; see "Launching Child Processes" above (enforced by `native_arg_quoting.Tests.ps1`) |
| 17 | `Start-Process -PassThru` caches `.Handle` at once; a `$null` exit code is UNKNOWN, never success | No `$ec -and`, `-not $ec`, `[int]$ec`, or pre-set `$ec = 0` (see gotchas.md) |
| 18 | No `Get-ChildItem -Recurse ... -ErrorAction SilentlyContinue` as an authoritative count or size | Windows PowerShell 5.1 silently skips folders past the path-length limit; count container-side or capture `-ErrorVariable` and report a lower bound (see gotchas.md > "Windows PowerShell 5.1 `Get-ChildItem -Recurse` Silently Skips Long Paths") |
| 19 | A kept docker stderr capture (`2>&1` into a variable) runs under an explicit `'Continue'`; stderr read back for display is kept in memory, not in a file; an emptiness or stdout-only check uses `2>$null` instead | Windows PowerShell 5.1 drops redirected native stderr under `SilentlyContinue` (`2>&1` and `2>>` file both observed); under `'Continue'` a file gets PowerShell's formatted error record, not the raw line, so stderr read back for display is kept in memory instead; stdout-marker-only reads may stay, allowlisted with a reason (see gotchas.md > "Windows PowerShell 5.1 Drops Native stderr Under `SilentlyContinue`, Even With `2>&1`"; enforced by `native_stderr_capture.Tests.ps1`) |
