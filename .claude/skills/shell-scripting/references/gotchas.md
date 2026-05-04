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

### `exit` in Dot-Sourced Script Functions Does Not Terminate the Host

**The problem:** When a script is loaded via `. script.ps1` (dot-sourcing), `exit N` inside a function defined in that script does not terminate the calling process. Instead, it unwinds the dot-sourced scope and returns control to the caller -- with exit code 0:

```powershell
# inner.ps1
function Stop-WithError {
    Write-Host "Error detected"
    exit 1   # Caller expects this to terminate the process
}
Stop-WithError
Write-Host "This should not print"  # Does not print (exit unwinds script scope)

# caller.ps1
. ./inner.ps1
Write-Host "Back in caller -- exit 1 did NOT terminate"  # This DOES print!
# Process exits with code 0
```

**When run directly** (`pwsh -File inner.ps1`), `exit 1` terminates the process with code 1 as expected. The bug is specific to dot-sourced invocation.

**Why it happens:** Dot-sourcing (`. script.ps1`) runs the script in the caller's scope, not a child scope. The `exit` keyword unwinds to the scope boundary of the dot-sourced content, then returns to the caller rather than terminating the host process. This is a long-standing PowerShell behavior, not a bug in any specific version.

**When this bites:** Pester test wrappers that define mock functions and then dot-source the script under test:
```powershell
# test_wrapper.ps1
function docker { $global:LASTEXITCODE = 1; return }  # Mock
. './real_script.ps1'                                    # Dot-source
# real_script.ps1 detects error, calls exit 1
# But exit 1 just returns here -- wrapper exits 0
```

**Fix:** Use `[Environment]::Exit(N)` for non-zero exit codes. This terminates the CLR process unconditionally, regardless of how the script was loaded:

```powershell
function Wait-ForUser {
    param([int]$ExitCode = 0)
    if (-not $env:DAAF_NESTED) { Read-Host "Press Enter to close" }
    # [Environment]::Exit() bypasses scope unwinding -- always terminates
    if ($ExitCode -ne 0) { [Environment]::Exit($ExitCode) }
    exit $ExitCode  # For success (0), plain exit is safe and less disruptive
}
```

**Why not `[Environment]::Exit()` for all exits?** It bypasses PowerShell cleanup (finally blocks, Dispose). More importantly, it kills the entire process -- including the Pester test host if the script is called via `&` (call operator) in non-subprocess tests. Using it only for non-zero exits keeps success-path tests (dry-run, smoke) safe while fixing error-path tests that run in subprocesses.

**Severity:** High. The failure is completely silent -- the script appears to detect the error (prints error messages), but the process exit code is 0. Test assertions on `$LASTEXITCODE` fail with no indication of why.

---

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

### `$LASTEXITCODE` Starts as `$null`, Not 0

**The problem:** Before any native command has run in a session, `$LASTEXITCODE` is `$null`. Naive checks like `$LASTEXITCODE -ne 0` then evaluate `$null -ne 0` which is `$true`, falsely indicating failure:

```powershell
# BAD: fires a false positive before any native command has run
if ($LASTEXITCODE -ne 0) {
    throw "Command failed"  # Triggers when $LASTEXITCODE is $null
}

# GOOD: guard against $null
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Command failed"
}

# ALSO GOOD: explicit null check
if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Command failed"
}
```

**Why it happens:** PowerShell only sets `$LASTEXITCODE` when a native executable actually runs. Functions, cmdlets, and mock overrides of native commands (e.g., defining a `docker` function for dry-run testing) do not update `$LASTEXITCODE`. If your script overrides `docker` with a PowerShell function, `$LASTEXITCODE` stays at whatever it was before — often `$null`.

**When this bites:** CI smoke tests, dry-run modes, or any scenario where native commands are mocked with PowerShell functions. The mock function must explicitly set `$global:LASTEXITCODE = 0` if downstream code checks the exit code.

**Severity:** Medium. The failure is immediate and obvious (a thrown exception), but it's confusing because there is no actual command failure.

---

### Single-Element Pipeline Array Unwrapping

**The problem:** When a pipeline returns exactly one object, PowerShell unwraps it from an array to a scalar. Indexing into the result then indexes into the string's characters instead of array elements:

```powershell
# BAD: if docker returns exactly one container name, $result is a string
$result = docker ps --format '{{.Names}}'
$first = $result[0]           # Returns first CHARACTER, not first element
$first.Trim()                 # Fails: [char] has no Trim() method

# GOOD: force array context with @()
$result = @(docker ps --format '{{.Names}}')
$first = $result[0]           # Always returns first element (string)
$first.Trim()                 # Works
```

**Why it happens:** PowerShell's pipeline is designed to stream individual objects. When a pipeline produces a single object, PowerShell "unwraps" the implicit single-element array and returns the bare object. Two or more items return an `[Object[]]` array, but one item returns the raw scalar. This means `[0]` on a string indexes characters, not array positions.

**When this bites:** Any script that collects Docker/git output into a variable and indexes into it. The bug only manifests when exactly one line is returned — zero lines give `$null` (caught by null checks) and two or more lines give an array (indexing works). The single-line case silently produces wrong results.

**Severity:** High. The failure mode is silent and data-dependent — the same code works in testing with multiple containers but fails in production with one.

---

### Embedded Double-Quotes in Native Command Arguments on Windows

**The problem:** When PowerShell on Windows passes a string containing `"` characters to a native executable (like `docker.exe`), the Windows C runtime argument parser (`CommandLineToArgvW`) can misinterpret quoting boundaries, silently truncating or mangling the argument. Multi-command `sh -c` pipelines are especially vulnerable:

```powershell
# BAD: PowerShell "" escapes produce literal " that Windows misparses
$out = docker run --rm busybox sh -c "awk '{printf ""%d\n"", s/1024}'"
# Result: awk receives a garbled program — "Unexpected token" or silent truncation

# ALSO BAD: PowerShell single-quotes with sh double-quotes — literal " in the string
$out = docker run --rm busybox sh -c 'stat -c "%s" file | awk "{s+=\$1} END {print s}"'
# Result: Windows splits the argument at spaces between the " pairs

# GOOD: PowerShell double-quotes with sh single-quotes — no " in the result
$out = docker run --rm busybox sh -c "stat -c %s file | awk '{s+=`$1} END {print s}'"
# Result: string has no embedded " — Windows passes it intact
```

**Why it happens:** On Windows, native executables receive their arguments as a single command-line string, not a pre-parsed array. The C runtime's `CommandLineToArgvW` re-parses that string using its own rules where `"` toggles quoted/unquoted state. When embedded `"` characters appear — whether from PowerShell `""` escapes or from literal `"` inside single-quoted strings — they create ambiguous boundaries that cause argument splitting or truncation. The failure is **completely silent**: no error, no warning, just wrong or missing output.

**Fix:** Eliminate ALL `"` characters from the string that reaches the native executable:
1. Use a **PowerShell double-quoted** outer string (for variable interpolation via `` `$ `` escaping)
2. Use **sh single-quotes** for inner quoting (awk programs, format strings)
3. Leave simple arguments **unquoted** at the sh level when safe (e.g., `stat -c %s` — no sh metacharacters in `%s`)
4. Use `print` instead of `printf "%d\n"` in awk to avoid needing format-string quotes

**Note:** This does **not** affect Bash. On Linux/macOS, Bash passes arguments via `execvp` as a pre-parsed array — there is no intermediate command-line string for a C runtime to reinterpret.

**Severity:** High. The failure is completely silent — the command may exit 0 but produce truncated output. Any PowerShell script passing complex `sh -c` commands to Docker (or any native executable) on Windows is potentially affected.

---

### Expression Context Breaks Interactive Native Commands (TTY Loss)

**The problem:** When a function containing an interactive native command (like `docker compose exec`) is called inside a PowerShell expression -- `if (-not (FunctionCall))`, `$result = FunctionCall`, `FunctionCall | ...` -- PowerShell captures the function's stdout through an internal pipe. Native commands that check both stdin AND stdout for TTY (e.g., Docker, ssh, interactive CLIs) see stdout as a pipe and refuse to allocate a TTY. The interactive program silently enters non-interactive/pipe mode:

```powershell
# BAD: expression context captures stdout through a pipe -- Docker sees non-TTY stdout
function Resolve-Conflict {
    docker compose exec daaf-docker claude   # Claude Code enters --print mode (3s timeout)
    return $true
}
if (-not (Resolve-Conflict)) { ... }     # Expression context!
$result = Resolve-Conflict                # Also expression context!

# GOOD: call as a statement -- stdout flows to the console
function Resolve-Conflict {
    docker compose exec daaf-docker claude   # Claude Code starts interactively
    $script:ConflictResolved = $true
}
Resolve-Conflict                             # Statement -- no pipe
if (-not $script:ConflictResolved) { ... }   # Check variable separately
```

**Why it happens:** Docker's Go-based TTY detection (`golang.org/x/term.IsTerminal`) calls `GetConsoleMode` on BOTH stdin and stdout file handles. In expression context, PowerShell replaces stdout with a pipe to capture the function's output for evaluation. `GetConsoleMode` fails on the pipe handle, so Docker concludes the environment is non-interactive and skips PTY allocation. The containerized process then sees `isatty(0)` = false on its stdin.

**What makes this insidious:**
- The same function works perfectly when called as a statement (`FunctionCall` on its own line)
- The same Docker command works at the PowerShell prompt and in simple scripts
- No error message points to stdout piping -- the native command just silently enters non-interactive mode
- `cmd /c`, `try/catch` removal, and `$ErrorActionPreference` changes do NOT fix it because the pipe is set up by the expression evaluation, not by any wrapping construct

**This does NOT affect Bash.** In bash, `if ! function_call` evaluates the function's exit code without creating a subshell or capturing stdout. Stdout flows directly to the terminal.

**Severity:** High. The failure is silent and difficult to diagnose. The function appears to run correctly (Docker starts, the program launches), but the interactive program immediately detects non-interactive I/O and falls back to a degraded mode or exits.

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

### UTF-8 BOM Breaks `Invoke-Expression`

**The problem:** A `.ps1` script containing non-ASCII characters (em-dashes, curly quotes) requires a UTF-8 BOM for PowerShell 5.1 to interpret them correctly. When the script is executed via `irm URL | iex`, `Invoke-Expression` does not strip the BOM. The BOM character gets prepended to the first line, making `#` look like a command:

```
The term '﻿#' is not recognized as the name of a cmdlet, function, script file,
or operable program.
```

If the script has a `trap` handler, the `CommandNotFoundException` is caught and the trap fires with a misleading error message, masking the actual root cause entirely.

**Why it happens:** The UTF-8 BOM is three invisible bytes (`EF BB BF`) at the start of the file. When PowerShell reads a BOM-encoded file via `Get-Content` or dot-sourcing, it recognizes and strips the BOM. But `Invoke-Expression` receives the file content as a raw string from `Invoke-RestMethod` -- the BOM bytes decode to the Unicode character U+FEFF, which becomes a visible character prepended to the first token. `﻿#Requires` is not a valid command name.

**Fix:** Use only ASCII characters (code points 0-127) in `.ps1` host scripts. Replace em-dashes (`---`) with `--`, curly quotes with straight quotes. Save files as UTF-8 without BOM. Verify with `file script.ps1` -- it should report "ASCII text", not "UTF-8 Unicode (with BOM)".

**Severity:** High. The `irm | iex` pattern is the standard installation/setup one-liner. Any BOM-encoded script distributed this way will fail on every execution, and the error message gives no hint about encoding.

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
| `exit` in dot-sourced functions | PowerShell | High | — |
| `$?` for native commands | PowerShell | High | — |
| Expression context breaks TTY | PowerShell | High | — |
| `$ErrorActionPreference` scope | PowerShell | High | — |
| Embedded `"` in native args | PowerShell | High | — |
| Implicit return values | PowerShell | High | — |
| UTF-8 BOM breaks `iex` | PowerShell | High | — |
| `$null` in ForEach pipeline | PowerShell | Medium | — |
| `-Version Latest` | PowerShell | Medium | — |
| Parameter validation bypass | PowerShell | Medium | — |
| Env var case sensitivity | Cross-platform | Medium | — |
| Alias removal on Linux | Cross-platform | Medium | PSAvoidUsingCmdletAliases |
| Exit code truncation | Cross-platform | Low | — |
| Path separator differences | Cross-platform | Medium | — |
