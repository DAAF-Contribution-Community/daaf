# Gotchas

Known pitfalls and surprising behaviors in Bash, PowerShell, and cross-platform scripting. Each entry includes the problem, why it happens, and the fix.

---

## Bash Gotchas

### `local var=$(cmd)` Masks Exit Code

**The problem:** `local` always returns 0, so the exit code of the command substitution is lost.

```bash
# BAD: if some_command fails, $? is still 0 because local succeeded
local result=$(some_command)
echo "Exit code: $?"  # Always 0

# GOOD: separate declaration from assignment
local result
result=$(some_command)
echo "Exit code: $?"  # Reflects some_command's actual exit code
```

**Why it happens:** `local` is a builtin command. Its return code (always 0 on success) overwrites the return code from the command substitution on the right-hand side.

**ShellCheck:** This is SC2155. Run `shellcheck -x -S warning` to catch it automatically.

**Severity:** High. This is the most insidious Bash bug because it silently swallows errors. Every `local var=$(cmd)` in your codebase is a potential hidden failure.

---

### `set -e` Doesn't Catch Failures in Assignments

**The problem:** Even without `local`, command substitution failures in variable assignments are sometimes not caught by `set -e`:

```bash
set -e

# This MAY silently succeed even if cmd fails, depending on Bash version:
var=$(failing_command)

# This reliably catches the failure:
var=$(failing_command) || exit 1
```

**Why it happens:** The POSIX spec has ambiguous wording about whether assignment is a "simple command" for `set -e` purposes. Behavior varies across Bash versions and shells.

**Fix:** For critical assignments, add explicit `|| exit 1`, or validate the result immediately afterward.

---

### `2>/dev/null` on Docker Probes Loses Diagnostics

**The problem:** Redirecting stderr to `/dev/null` during Docker health checks discards the diagnostic information you need when the check fails:

```bash
# BAD: if docker info fails, you've thrown away the error message
if docker info >/dev/null 2>/dev/null; then
    echo "Docker is running"
fi

# GOOD: capture stderr for diagnostic use on failure
docker_err=$(docker info 2>&1 >/dev/null) || {
    error "Docker check failed: $docker_err"
    exit 10
}
```

**When `2>/dev/null` is acceptable:** Only for truly expected, uninformative stderr output (e.g., deprecation warnings you've already evaluated and decided to suppress).

---

### `cd dir` Without Error Handling

**The problem:** `cd` can fail (directory doesn't exist, no permissions), and with `set -e` the behavior is inconsistent depending on context:

```bash
# BAD: if cd fails, script continues in wrong directory
cd "$some_dir"
rm -rf ./*.tmp  # Now deleting files in the wrong directory

# GOOD: explicit failure handling
cd "$some_dir" || { error "Cannot cd to $some_dir"; exit 1; }
```

**ShellCheck:** This is SC2164.

---

### Backtick Substitution Cannot Nest

```bash
# BAD: backticks cannot nest — inner backticks need escaping
result=`echo \`date\``

# GOOD: $() nests cleanly
result=$(echo $(date))
```

Backticks are also harder to read. Always use `$(...)`.

---

### Word Splitting in Conditionals

```bash
# BAD: if var is empty, this becomes [ = "value" ] — syntax error
if [ $var = "value" ]; then

# GOOD: quotes prevent word splitting
if [ "$var" = "value" ]; then

# ALSO GOOD: [[ doesn't word-split
if [[ $var = "value" ]]; then
```

---

### Unquoted Glob Expansion

```bash
# BAD: if *.log matches nothing, the literal string "*.log" is passed
for f in *.log; do
    echo "Processing $f"
done
# If no .log files exist, prints "Processing *.log"

# GOOD: check if glob matches
shopt -s nullglob
for f in ./*.log; do
    echo "Processing $f"
done
# If no .log files exist, loop body never executes
```

---

## PowerShell Gotchas

### `$?` Is Unreliable for Native Commands

**The problem:** `$?` checks whether the last *PowerShell operation* succeeded, but stderr output from native commands can make `$?` return `$false` even when the command exited 0:

```powershell
# BAD: docker writes informational messages to stderr, causing $? = $false
docker compose up -d
if (-not $?) {
    Write-Error "Docker failed"  # False alarm
}

# GOOD: check the actual exit code
docker compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker compose failed (exit code: $LASTEXITCODE)"
}
```

**Rule:** Use `$LASTEXITCODE` for ALL native command checks. Use `$?` only for PowerShell cmdlets.

---

### `$ErrorActionPreference = 'Stop'` Ignores Native Exit Codes

**The problem:** `$ErrorActionPreference` only affects PowerShell cmdlet errors. Native command non-zero exit codes are not converted to exceptions:

```powershell
$ErrorActionPreference = 'Stop'

# This does NOT throw, even though docker exits with code 1
docker build -t badimage .

# You MUST check $LASTEXITCODE manually
docker build -t badimage .
if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed"
}
```

**Why it happens:** PowerShell treats native executables as black boxes. Their stderr output and exit codes are outside PowerShell's error handling system (unless `$PSNativeCommandUseErrorActionPreference = $true` in PS 7.4+).

---

### Implicit Return Values

**The problem:** Every expression in a function that produces output becomes part of the return value:

```powershell
# BAD: function returns @(0, 1, "result") instead of just "result"
function Get-Data {
    $list = [System.Collections.ArrayList]::new()
    $list.Add("item1")    # .Add() returns index 0
    $list.Add("item2")    # .Add() returns index 1
    return "result"
}

# GOOD: suppress unwanted output
function Get-Data {
    $list = [System.Collections.ArrayList]::new()
    $null = $list.Add("item1")
    $null = $list.Add("item2")
    return "result"
}
```

**Other common sources of leaked output:**
- `[void]` cast expressions
- `.Remove()`, `.Insert()` methods on collections
- Variable assignments that happen to produce output
- `if` expressions that evaluate to a value

---

### `$null` in Pipeline Executes ForEach-Object Once

**The problem:** `$null` piped to `ForEach-Object` executes the loop body once, with `$_` set to `$null`:

```powershell
# BAD: if Get-Items returns $null, ForEach still executes once
$items = Get-Items  # Returns $null
$items | ForEach-Object { Process-Item $_ }
# Process-Item is called once with $null

# GOOD: wrap in @() for safe empty array
@($items) | ForEach-Object { Process-Item $_ }
# ForEach-Object is never called if array is empty

# ALSO GOOD: explicit null check
if ($null -ne $items) {
    $items | ForEach-Object { Process-Item $_ }
}
```

---

### `-Version Latest` on Set-StrictMode

**The problem:** `Set-StrictMode -Version Latest` resolves to whatever version your PowerShell runtime supports. This means the same script enforces different rules on different machines:

```powershell
# BAD: non-deterministic across PS versions
Set-StrictMode -Version Latest

# GOOD: explicit and reproducible
Set-StrictMode -Version 3.0
```

**Why `-Version 3.0`?** It catches the most common issues (uninitialized variables, non-existent properties) without introducing the more aggressive (and sometimes surprising) checks from later versions.

---

### Parameter Validation on Omitted Parameters

**The problem:** Validation attributes fire only when the parameter is *supplied*. If a parameter is omitted entirely, validation is bypassed:

```powershell
function Do-Thing {
    param(
        [ValidateNotNullOrEmpty()]
        [string]$Name  # Not Mandatory
    )
    # If called as Do-Thing (no -Name), $Name is "" and validation did NOT fire
    Write-Host "Name: '$Name'"
}

# Fix: combine with [Mandatory] if the parameter is required
function Do-Thing {
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Name
    )
}
```

---

## Cross-Platform Gotchas

### Environment Variable Case Sensitivity

**The problem:** Environment variable names are case-insensitive on Windows but case-sensitive on Linux:

```powershell
# Windows: both of these access the same variable
$env:PATH
$env:Path

# Linux: these are DIFFERENT variables
$env:PATH   # System PATH
$env:Path    # Undefined (or user-defined)
```

**Fix:** Always use the exact casing that the convention requires (`PATH` on Linux, `Path` on Windows). For cross-platform scripts, use `$env:PATH` consistently.

---

### Aliases Removed on Linux/macOS PowerShell

**The problem:** PowerShell on Windows includes aliases like `ls` (for `Get-ChildItem`), `cat` (for `Get-Content`), `cp` (for `Copy-Item`). On Linux and macOS, these aliases are removed because they conflict with the native commands:

```powershell
# BAD: works on Windows, fails on Linux (calls native ls, different output format)
$files = ls *.txt

# GOOD: use full cmdlet names
$files = Get-ChildItem -Filter "*.txt"
```

**PSScriptAnalyzer** catches this with the `PSAvoidUsingCmdletAliases` rule.

---

### Exit Codes Above 255 Truncated on Linux

**The problem:** Linux processes use 8-bit exit codes (0-255). Any exit code above 255 is truncated:

```powershell
# On Linux: exit 256 becomes exit 0 (256 % 256 = 0)
# On Linux: exit 300 becomes exit 44 (300 % 256 = 44)
exit 256  # Looks like success on Linux!
```

**Fix:** Keep all exit codes in the range 0-125. Codes 126-255 have special meanings in some shells.

---

### Path Separators

**The problem:** Windows uses `\`, Linux/macOS use `/`. String concatenation with path separators breaks cross-platform:

```powershell
# BAD: backslash path fails on Linux
$configPath = "$BaseDir\config\settings.json"

# GOOD: Join-Path handles separators correctly
$configPath = Join-Path $BaseDir "config" "settings.json"

# ALSO GOOD in PowerShell 6+: forward slash works everywhere
$configPath = "$BaseDir/config/settings.json"
```

In Bash, `/` is always the separator. No cross-platform concern within Bash itself, but be aware when generating paths that PowerShell scripts will consume.

---

## Quick Lookup

| Gotcha | Language | Severity | ShellCheck/Analyzer |
|--------|----------|----------|---------------------|
| `local var=$(cmd)` masks exit | Bash | High | SC2155 |
| `set -e` in assignments | Bash | Medium | — |
| `2>/dev/null` on probes | Bash | Medium | — |
| `cd` without `\|\| exit` | Bash | Medium | SC2164 |
| Backtick nesting | Bash | Low | SC2006 |
| `$?` for native commands | PowerShell | High | — |
| `$ErrorActionPreference` scope | PowerShell | High | — |
| Implicit return values | PowerShell | High | — |
| `$null` in ForEach pipeline | PowerShell | Medium | — |
| `-Version Latest` | PowerShell | Medium | — |
| Parameter validation bypass | PowerShell | Medium | — |
| Env var case sensitivity | Cross-platform | Medium | — |
| Alias removal on Linux | Cross-platform | Medium | PSAvoidUsingCmdletAliases |
| Exit code truncation | Cross-platform | Low | — |
| Path separator differences | Cross-platform | Medium | — |
