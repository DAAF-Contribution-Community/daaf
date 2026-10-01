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

# ALSO BAD: truthiness "guard" -- reads an UNKNOWN ($null) status as success
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Command failed"   # never fires for $null, so an unknown status passes silently
}

# GOOD: decide what $null means explicitly, as its own outcome. Read it via
# Get-Variable: under Set-StrictMode -Version 3.0 a never-set $LASTEXITCODE THROWS
# on a direct read ("The variable '$LASTEXITCODE' cannot be retrieved because it
# has not been set"), so even `$null -eq $LASTEXITCODE` would fail.
$ec = Get-Variable -Name LASTEXITCODE -ValueOnly -ErrorAction SilentlyContinue
if ($null -eq $ec) {
    throw "Exit status unknown -- no native command set it"   # or warn; never assume success
} elseif ($ec -ne 0) {
    throw "Command failed (exit code: $ec)"
}
```

(StrictMode behavior observed on pwsh 7.6 / Linux on 2026-09-29: in a fresh `-File` process with `Set-StrictMode -Version 3.0`, the direct read threw and the `Get-Variable` form returned `$null`, then `3` after a native `exit 3`. Right after a native command you just ran, the variable is always set, so a plain `$LASTEXITCODE -ne 0` read is safe there.)

**Why it happens:** PowerShell only sets `$LASTEXITCODE` when a native executable actually runs. Functions, cmdlets, and mock overrides of native commands (e.g., defining a `docker` function for dry-run testing) do not update `$LASTEXITCODE`. If your script overrides `docker` with a PowerShell function, `$LASTEXITCODE` stays at whatever it was before — often `$null`.

**Unknown is not success.** `$null` means "no exit status was recorded", not "exit 0". The truthiness forms `$x -and $x -ne 0` and `-not $x -or $x -eq 0` both coerce `$null` to the success branch (`[int]$null` is `0`; `$null -and ...` is `$false`), which is exactly how a failed or unreadable child exit gets reported as clean. The same rule applies to any exit code that can be `$null` — above all a `Start-Process -PassThru` object's `ExitCode` (see "`Start-Process -PassThru` `ExitCode` Reads `$null`" below). The best fix is structural: read `$LASTEXITCODE` only immediately after the native command whose status you want, so it cannot be `$null` or stale; where it still can be, give `$null` its own branch.

**When this bites:** CI smoke tests, dry-run modes, or any scenario where native commands are mocked with PowerShell functions. The mock function must explicitly set `$global:LASTEXITCODE = 0` if downstream code checks the exit code.

**Severity:** Medium. With the bare `-ne 0` form the failure is loud (a thrown exception with no real command failure); with a truthiness "guard" it is silent (an unknown status passes as success) — prefer the loud mistake.

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

### `Start-Process -ArgumentList` Joins an Array With Bare Spaces (No Quoting)

**The problem:** Passing `-ArgumentList` an array looks like "one element per argument", but it is not. Start-Process joins the elements with single spaces and quotes nothing; the child then re-splits that one string with the Windows argv rules. Any element containing a space becomes several arguments, and an embedded `"` is silently stripped:

```powershell
# BAD: $childPath = "C:\Users\John Smith\daaf-docker\backup_daaf.ps1"
Start-Process -FilePath $hostExe -ArgumentList @('-NoProfile', '-File', $childPath) -NoNewWindow -PassThru
# The child sees: -NoProfile -File C:\Users\John Smith\daaf-docker\backup_daaf.ps1
# -> "The argument 'C:\Users\John' is not recognized as the name of a script file"
#    (pwsh 7 wording; Windows PowerShell 5.1 reports the missing -File path differently)

# BAD: hand-rolled quoting -- misses trailing backslashes, backslashes before quotes,
# and quote-bearing tokens without whitespace
if ($a -match '\s') { $argList += ('"' + ($a -replace '"', '\"') + '"') }
# 'C:\x y\' becomes "C:\x y\" -- the final \" escapes the closing quote and the
# NEXT argument is swallowed into this one

# GOOD: ONE pre-joined string, every element quoted by the canonical helper
$argString = (@('-NoProfile', '-File', $childPath) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '
Start-Process -FilePath $hostExe -ArgumentList $argString -NoNewWindow -PassThru
```

The canonical helper (defined in `scripts/host/daaf_lib.ps1`; standalone scripts carry a byte-identical INLINE COPY, pinned by `tests/powershell/native_arg_quoting.Tests.ps1`):

```powershell
function ConvertTo-DaafNativeArg {
    [CmdletBinding()]
    param([string]$Value = '')
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    return '"' + (($Value -replace '(\\*)"', '$1$1\"') -replace '(\\+)\z', '$1$1') + '"'
}
```

It is the inverse of the Windows argv parser: bare when the value has no whitespace and no `"`; otherwise wrapped in quotes, with each backslash run before an embedded `"` doubled plus the quote escaped, and a trailing backslash run doubled. `''` becomes `""`. The trailing-run anchor is `\z`, not `$`: in .NET, `$` also matches just before a final newline, so `'(\\+)$'` would double backslashes that sit before a trailing LF (`"trail\<LF>"` came out as `"trail\\<LF>"`). Verified values that round-trip exactly through a real child process (on the Linux Pester runner): `''`, `q"z`, `back\"slash`, `trail\`, `C:\Users\John Smith\OneDrive - Org\`.

**Why it happens:** Microsoft's Start-Process reference states it plainly: "The cmdlet joins the array into a single string with each element of the array separated by a single space." Windows processes receive one command-line string, not an argv array, so the join is lossy. PowerShell#5576 ("Start-Process doesn't pass arguments with embedded whitespace and double quotes correctly") lists Windows PowerShell 5.1 as affected and concludes that "the best workaround is to pass a single string containing all arguments to -ArgumentList and use embedded quoting and escaping as necessary". On Linux/macOS, .NET splits the joined string with the same Windows-style rules, so the bug and the fix both reproduce on a Linux Pester runner (observed on pwsh 7.6).

**Prefer direct invocation when you can:** `& $exe @argArray` makes PowerShell quote each whitespace-bearing element for you. Use Start-Process only when you need what it uniquely gives — console inheritance for an interactive child (`-NoNewWindow` from a capturing context; see "Expression Context Breaks Interactive Native Commands" below) or a Process object to poll while showing progress. (Windows PowerShell 5.1's direct-call path is reported to still mishandle an embedded `"` — see "Embedded Double-Quotes" above — or a trailing backslash inside a spaced argument; native argument passing was reworked in PowerShell 7.3. Not reproducible on Linux, which passes argv directly.)

**When this bites:** any path under the user's profile or install folder — `C:\Users\First Last\...`, `OneDrive - Org\...`. In DAAF (fixed 2026-09-29) it broke every Control Panel hand-off to a child script (`daaf.ps1`, Claude Code / shell / Quarto / backup / restore / update / rebuild) and the backup `docker cp` for spaced install folders; `tests/powershell/native_arg_quoting.Tests.ps1` now fails on any array-form or unquoted `-ArgumentList` in `scripts/host/*.ps1`.

**Severity:** High. The splitting is deterministic for affected users (every run fails) and invisible to anyone whose paths have no spaces — including most developers and CI.

---

### `Start-Process -PassThru` `ExitCode` Reads `$null` Unless `.Handle` Is Cached

**The problem:** On Windows — Windows PowerShell 5.1 and PowerShell 6.0 through 7.4.0 — the Process object returned by `Start-Process -PassThru` together with `-NoNewWindow` and/or any `-RedirectStandard*` parameter does not hold an open OS handle. If nothing opens one before the child exits, `$proc.ExitCode` reads `$null` after `WaitForExit()` — the exit status is gone. PowerShell 7.4.1 fixed it. Code that then coerces `$null` reports an unknown (possibly failed) child as a clean success:

```powershell
# BAD: no handle cached; $null then coerced to success
$proc = Start-Process -FilePath $exe -ArgumentList $argString -NoNewWindow -PassThru
$proc.WaitForExit()
$ec = $proc.ExitCode                 # $null on Windows PowerShell 5.1 / pwsh 6.0-7.4.0 (Windows)
if ($ec -and $ec -ne 0) { ... }      # $null -> "no error": failure never reported
if (-not $ec -or $ec -eq 0) { ... }  # $null -> "clean return": same bug, other spelling

# GOOD: cache the handle immediately, read defensively, treat $null as UNKNOWN
$proc = Start-Process -FilePath $exe -ArgumentList $argString -NoNewWindow -PassThru
try { $null = $proc.Handle } catch { Write-Verbose "Could not cache the process handle: $_" }  # while the child is alive
$proc.WaitForExit()
$ec = $null
try { $ec = $proc.ExitCode } catch { $ec = $null }
if ($null -eq $ec) {
    # UNKNOWN: warn (or fail closed) -- never report success
} elseif ($ec -ne 0) {
    # FAILURE
}
```

Never pre-set `$ec = 0`, cast `[int]$ec` (`[int]$null` is `0`), or use the `$ec -and ...` / `-not $ec` truthiness forms — each turns "unknown" into "success". Whether unknown should warn or fail closed depends on the caller: `test_migration.ps1` (`Invoke-HardenedScript`) fails closed (returns 1); `backup_daaf.ps1` keeps a separate `$CopyExitKnown` flag, never reads the copy as clean on the exit code's say-so, latches the WITH WARNINGS banner, and leans on the file-count check; `daaf.ps1`'s delegates print a distinct "Could not read the exit status" message.

**Why it happens:** the widely cited Stack Overflow answer to "Obtaining ExitCode using Start-Process and WaitForExit instead of -Wait" (question 10262231, answer 23797762) reports: "All I had to do was cache the process handle. As soon as I did that, $process.ExitCode worked correctly. If I didn't cache the process handle, $process.ExitCode was null." The version scope comes from upstream: PowerShell#5421 ("Process objects created with Start-Process -NoNewWindow and/or -RedirectStandard* never report their exit code on Windows") reproduces it on "PowerShell Core v6.0.0-beta.9" and "Windows PowerShell v5.1.15063.674", notes "The problem only surfaces on Windows", and gives the same workaround ("cache the process handle before calling Wait-Process / .WaitForExit()"); PowerShell#20400 reports it again on 7.4.0-preview.5; the PowerShell v7.4.1 release notes list "Fix Start-Process -PassThru to make sure the ExitCode property is accessible for the returned Process object (Fix #20400 ...)". That fix shipped in PowerShell 7.4.1; Windows PowerShell 5.1 is a separate product that is not expected to receive it (inference, not verified against 5.1 servicing notes), so the `.Handle` cache stays mandatory for DAAF host scripts, which must work on 5.1. DAAF hit it in the field: `test_migration.ps1` scored a SUCCESSFUL child as failed ("exited with code .") until the handle was cached. The quirk does not reproduce on Linux/macOS pwsh (ExitCode is always populated there), so a Linux-only test cannot prove the fix — structural guards do instead (`tests/powershell/native_arg_quoting.Tests.ps1` parses `scripts/host/*.ps1` and requires that the first use of every `Start-Process -PassThru` result variable is a `.Handle` read, so a comment cannot satisfy it).

**Related trap:** `Start-Process -Wait` without `-PassThru` leaves `$LASTEXITCODE` untouched (observed in the 2026-09-29 host sweep on pwsh/Linux: it stayed `0` after a child that exited 5) — never read `$LASTEXITCODE` after Start-Process.

**Severity:** Medium-High. Silent on the affected platforms (Windows PowerShell 5.1 and PowerShell 6.0–7.4.0 on Windows), invisible on the platform most tests run on, and it converts failures into successes.

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

### Octal `printf` Escapes Are Eaten by the Host Shell Before `sh` Sees Them

**The problem:** When a host driver (bash or PowerShell) builds a program string that will be handed to `sh` and that program uses an octal `printf` escape like `\357` (a UTF-8 byte) or `\011` (a tab), the **host shell consumes one layer of backslash escaping first**. A naive single backslash reaches `sh` with the backslash already eaten, so `sh`'s `printf` never sees the octal escape — it emits the literal digits instead of the byte. This bit DAAF twice on 2026-07-14.

The rule: `sh -c` itself performs quote removal on the program text it executes, so an **unquoted** `printf` argument loses one backslash at the final `sh` layer — on top of whatever the host embedding context consumed. Two ways to arrive correct: the resolved program string carries a **doubled** backslash (`printf \\357`, which `sh` collapses to `\357`), or the octal is **quoted at the `sh` level** (`printf '\357'`, which quote removal leaves intact).

| Host embedding context | Source you write | Resolved program handed to `sh -c` | Correct? |
|------------------------|------------------|------------------------------------|----------|
| PowerShell single-quoted here-string (`@'…'@`) — the DAAF production pattern | `printf \\357` | `printf \\357` — `sh` collapses `\\`→`\`, printf sees the octal | Correct — emits the byte |
| PowerShell (any string form) with a lone backslash | `printf \357` | `printf \357` — `sh` quote removal eats the lone `\`, printf sees `357` | Wrong — emits digits (the 2026-07-14 field bug) |
| Bash **single-quoted** string | `'printf \\357'` | `printf \\357` — `sh` collapses `\\`→`\` | Correct — emits the byte |
| Bash **single-quoted** string | `'printf \357'` | `printf \357` — `sh` quote removal eats the lone `\` | Wrong — emits digits |
| Bash **double-quoted** string | `"printf \\357"` | `printf \357` — bash eats one, then `sh` eats the survivor | Wrong — avoid double-quoted embedding for these programs |
| Any context, octal quoted at the `sh` level | resolved string contains `printf '\357'` | printf receives `\357` intact (the `sh`-level quotes protect it) | Correct — no doubling needed |

The same applies to `\011` (tab) and every other octal escape: in the DAAF production patterns (bash single-quoted program strings and PowerShell single-quoted here-strings, both literal) write the doubled form `\\011`, or quote the escape at the `sh` level.

**Why it happens:** every layer that *parses* the string can consume backslashes — and the final `sh -c` is itself such a layer: its quote removal strips a lone backslash from any unquoted argument before `printf` ever runs. Bash single quotes and PS single-quoted here-strings pass source text through literally (zero host consumption); bash/PS double-quoted contexts and native-argument passing may each consume one more. The number of backslashes you must write is a function of **how many parsing layers sit between your source and `printf` itself — counting the final `sh`**.

**Fix — test the resolved string, don't reason about layers:** counting backslash layers by hand is error-prone (the two 2026-07-14 failures were both miscounts). Empirically resolve the program string as the host will produce it, then feed *that exact string* to a real `sh` and check the bytes:

```bash
# Capture what the host actually produces, then test it against real sh
resolved='printf \357'          # <- the post-host-parsing program string
printf '%s' "$resolved" | od -c # inspect: is it one backslash or zero?
sh -c "$resolved" | od -An -tx1 # does sh emit the byte (ef) or the digits (33 35 37)?
```

If `sh -c "$resolved"` emits `ef` (the byte) you have the right number of backslashes; if it emits `33 35 37` (ASCII `357`) the backslash was eaten upstream and you need one more layer. Always validate the **resolved** program string against real `sh` rather than trusting a hand count.

---

### Windows `docker cp` (Container to Host) Aborts at the First FIFO, Device Node, Uncreatable Symlink, or Uncreatable Name

**The problem:** On a Windows host, `docker cp CONTAINER:/path HOSTDIR` stops extracting at the first named pipe (FIFO) or block/char device node in the archive stream — at the first symlink it cannot create (symlink creation needs admin or Developer Mode) — and at the first file or folder NAME Windows cannot create (a control byte such as a newline, one of `< > " | ? *`, a device name such as `CON` or `NUL.txt`), or a file and a folder whose names differ only in upper/lower case. Every entry that sorts after it is silently dropped. The CLI still prints "Successfully copied ...", and the exit code alone is not a trustworthy completeness signal (DAAF's own Windows backup reported a truncation with a zero exit — most likely a since-fixed `$null`-to-0 ExitCode coercion, see the `Start-Process -PassThru` entry above).

```powershell
# BAD: copy a live volume/tree straight out and trust the success line or $LASTEXITCODE
docker cp "${cid}:/source/." $HostPath     # stops at e.g. logs/shim.stream.x/output.fifo

# GOOD (DAAF backup pattern): stage into a throwaway container, strip what Windows
# cannot extract, then copy the stripped tree -- and verify by COUNTING files
$StageProgram = @'
set -e
cp -a /source /staging
cd /staging
find . -type l > /tmp/link_paths
find . -type l -exec readlink {} \; > /tmp/link_targets
paste /tmp/link_paths /tmp/link_targets > /staging/.daaf-symlinks
find /staging -type l -exec rm -f {} +
find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +
'@
# (abridged -- the production program also gates tab/newline symlink names, and,
# before the symlink manifest, removes and lists names Windows cannot create and
# case-only clashes when launched with `-e DAAF_STAGE_NAMES=win`; see
# scripts/host/backup_daaf.{sh,ps1})
```

**Why it happens (verified from upstream source, 2026-09-29):** moby/go-archive's Windows `handleTarTypeBlockCharFifo` (`archive_windows.go`) is a no-op that returns nil — no file is created for the FIFO/device entry. `createTarFile` (`archive.go`) then falls through to its timestamp step, `chtimes` on the path that was never created fails, and `Unpack` returns on the first `createTarFile` error — the rest of the archive is never read. docker/cli's `cp.go` prints "Successfully copied" unconditionally after the copy call, before that call's error is returned. Sockets were stripped defensively in DAAF's fix: how Docker archives a socket on this path was not verified.

**Fix:**
1. Stage the source into a throwaway container (`docker run -d ... sh -c "$STAGE_PROGRAM"` + `docker wait`), freeze it with `cp -a`, record symlinks in a manifest for restore to replay, and delete symlinks plus `-type p`/`-type s`/`-type b`/`-type c` special files — they are runtime rendezvous objects with no content (e.g. stale provider-shim `output.fifo` stream files).
2. `docker cp` the staged tree, never the live volume.
3. Verify completeness independently: have the staging program print the frozen snapshot's own counts (`STAGED_FILES=`/`STAGED_KB=` to stdout, read back with `docker logs` before `docker rm -f`), then count the host copy with the same predicates, container-side on Windows (see the next entry). Treat the success line as noise and the exit code as one signal among several — a nonzero exit with a full count still latches the WITH WARNINGS banner; a nonzero exit with a short count is fatal only when that count is exact. A short **lower-bound** count (the host count hit read errors, see the next entry) is not a second signal, since the "missing" files may only be unreadable, so it is downgraded to a latched WARNING; a lower-bound count of 0 exits 1 as "could not be verified" (an unverifiable backup must stop an update or migration, but is never reported as empty or truncated).
4. Compare at ZERO tolerance against the snapshot, with the SAME `find` predicate on both sides (a root file excluded on one side only, such as a stray `.daaf-permissions`, is a false mismatch). A 1% tolerance hid real gaps: a probe of the maintainer volume projected 714 of 71,820 files dropped after its first FIFO (under the 718-file tolerance), and the 2026-09-29 Windows run below was 197 files short of 73,031 (187 hidden by the PowerShell 5.1 long-path skip, plus 10 most likely from live-volume drift between the scan and the snapshot, an inference from the field evidence below). A live-volume scan taken before the snapshot can drift from it, which is why the snapshot, not the scan, is the target; the 1% tolerance survives only as the fallback when the markers cannot be read.

**Uncreatable names (field evidence, 2026-09-30):** a Windows backup with Docker Client 29.1.3 (Docker Desktop 4.55.0) stopped at a file named `name<LF>nl` with `The filename, directory name, or volume label syntax is incorrect.` after 72,386 of 73,785 files; DAAF's zero-tolerance count check failed the run (exit 1), so nothing passed silently, but the backup was unusable. Behavior by name class, from upstream source review (moby/go-archive; Microsoft's "Naming Files, Paths, and Namespaces"; not executed on a Windows host): control bytes 0x01-0x1F, `< > " | ? *`, and the device names `CON PRN AUX NUL COM1-9 LPT1-9` (also with the superscript digits ¹²³, `CONIN$`, `CONOUT$`, and with any extension) abort the extraction; `:` aborts in the newer code and is unverified in the older (strip it anyway); `\` is skipped or misplaced; a trailing dot or space is silently renamed (which can then collide). Case-only clashes on case-insensitive NTFS (`docker cp` extracts with no-overwrite-dir-with-non-dir): file+file silently keeps one (count short, exit 0); folder+folder merges; file+folder fails with "cannot overwrite" and aborts. **Version dependence:** Docker CLI 29.7 moved to go-archive v0.3 (`os.Root`-based extraction), which changes some of these outcomes (per specialist source review, not executed); the field host ran the older path, so do not rely on the exact per-class behavior — strip the whole class. DAAF's fix: the staging program, launched with `-e DAAF_STAGE_NAMES=win` by `backup_daaf.ps1` only (the names are legal on macOS/Linux), removes every non-symlink entry with such a name (`-prune` + `rm -rf`, so a folder takes its subtree, before the symlink manifest), removes all but the first (C-locale byte order) of each case-insensitive full-path clash involving a file, lists folder+folder clashes, and prints the list and a `STAGED_STRIPPED_FILES=` count before the final markers; the host prints a WARNING and latches WITH WARNINGS. That list is printed right after the final count line, before either fatal exit, so a run that still stops early names what it left out; and on Windows a staging log that lacks the `STAGED_STRIPPED_NAMES=` marker (the list could not be read) gets its own latched WARNING, because names may then have been removed unannounced. On macOS (`casewarn`) the same step only lists case clashes. Two busybox differences are designed around from source: the busybox `find -iname` fallback upcases the name but not the pattern when libc lacks `FNM_CASEFOLD`, so keep `-iname` patterns upper case; and busybox never runs the last batch of an `-exec ... {} +` inside `\( \)` (see the busybox entry below), so the case listing uses top-level `-o` branches. The test suite runs the step under dash + GNU find; a one-shot host probe ran it under real busybox on Windows (2026-10-01) and matched the expected output exactly (see the busybox entry below).

**Where it lives in DAAF:** `scripts/host/backup_daaf.sh` / `backup_daaf.ps1` staging program (byte-identical across twins, pinned by `tests/bash/backup_twin_parity.bats`); restore replays `.daaf-symlinks`. Linux/macOS hosts are unaffected by the abort (they can create FIFOs, symlinks and these names), but the twins share the staging program so behavior stays aligned; the name step runs only when a twin switches it on.

**Severity:** High. Silent data loss in a backup, with a success message, on the platform least visible to developers.

---

### Windows PowerShell 5.1 `Get-ChildItem -Recurse` Silently Skips Long Paths

**The problem:** With the Windows default `LongPathsEnabled = 0`, Windows PowerShell 5.1's `Get-ChildItem -Recurse` cannot descend into a folder whose full path is 248 characters or longer, and cannot list a file whose path is 260 or longer. Each failure is a non-terminating error. With `-ErrorAction SilentlyContinue`, the idiom most scripts use to "just count the files", those errors vanish and the count comes back short, with no warning:

```powershell
# BAD: an authoritative count that silently undercounts deep trees
$n = @(Get-ChildItem -Path $dir -Recurse -File -Force -ErrorAction SilentlyContinue).Count

# GOOD (DAAF backup): count inside Docker through a read-only bind mount -- Linux
# `find` in the Docker VM has no MAX_PATH limit. Trust the number only when the
# program exited 0, saw the sentinel (the mount is not an empty view), and printed
# BACKUP_FILES at all: it withholds BACKUP_FILES (printing BACKUP_COUNT_ERRORS) when
# its `find` hit any read error. Anything else leaves $n = $null -> fall back.
$out = @(docker run --rm -v "${HostPath}:/b:ro" busybox sh -c $BackupCountProgram 2>&1)
$n = $null
if ($LASTEXITCODE -eq 0 -and (Get-DaafCountMarker -Lines $out -Name 'BACKUP_SENTINEL') -eq 1) {
    $n = Get-DaafCountMarker -Lines $out -Name 'BACKUP_FILES'
}

# ACCEPTABLE fallback: keep the errors and SAY the count is a lower bound
$errs = $null
$n = @(Get-ChildItem -LiteralPath $dir -Recurse -File -Force -ErrorAction SilentlyContinue -ErrorVariable errs).Count
if (@($errs).Count -gt 0) { Write-Host "Could not read $(@($errs).Count) folder(s) -- $n is a LOWER BOUND" }
```

**Field evidence (2026-09-29, Windows 11, Windows PowerShell 5.1.26100, `LongPathsEnabled = 0`):** a DAAF backup into an 85-character folder prefix scanned 73,031 files in the volume. `Get-ChildItem` then counted 72,834 in the host copy, and the 1% tolerance (730) passed that as "Backup complete!". A container-side count of the same folder (`docker run --rm -v "<folder>:/b:ro" busybox sh -c "find /b -type f ... | wc -l"`) found 73,021. So 187 files had been written correctly by `docker cp` (Go handles long paths) but were invisible to PowerShell. An in-container probe put 187-208 files under folders whose Windows path would be 248+ characters, all in deep `research/` trees. The remaining 10 files (73,031 scanned vs 73,021 present) were, by elimination, almost certainly live-volume drift rather than copy loss. A follow-up diff mounted the backup and the live volume side by side and listed every volume file no newer than the backup's last-written `.daaf-permissions` that was absent from the backup (`comm -13` of two sorted `find . -type f` lists). It returned only 3 files, all written at 22:00:23-22:00:48 UTC by a concurrent DAAF session, after the snapshot but before the backup finished. Every pre-existing file still on the volume was in the backup. A diff of surviving files cannot strictly rule out a file that was lost in the copy and later deleted from the volume, so this conclusion is an inference: the 10 most likely existed at scan time and were removed before the staging `cp -a` froze the snapshot. That drift is exactly why verification targets the snapshot, not the scan.

**Why it happens (mechanism is inference from .NET/Win32 documentation, not re-verified on a Windows host):** Windows PowerShell 5.1 runs on .NET Framework, which enforces the Win32 `MAX_PATH` limits (260 for a file path, 248 for a directory) unless the OS-wide `LongPathsEnabled` policy is on *and* the application opts in. `-ErrorAction SilentlyContinue` suppresses display of the resulting per-folder errors but still records them, so `-ErrorVariable` recovers them (observed on pwsh 7.6 / Linux with an unreadable folder standing in: the errors land in the variable, `tests/powershell/backup_daaf.Tests.ps1`). PowerShell 7 (.NET Core) is documented to handle long paths without the policy, and Linux/macOS `find` has no such limit — so the silence is specific to the platform most users have and fewest developers test on.

**Fix:**
1. Never use `Get-ChildItem -Recurse ... -ErrorAction SilentlyContinue` as an **authoritative** count or size. Progress displays are fine: label them as approximate and verify separately.
2. Count container-side when Docker is at hand: bind-mount the host folder read-only and run `find` (DAAF: `$BackupCountProgram` in `backup_daaf.ps1` / `restore_from_backup.ps1`, byte-identical, pinned by `tests/bash/backup_twin_parity.bats`; one `find -exec stat -c %s {} + | awk` pass yields files and KB, since each walk of a bind mount crosses Docker Desktop's host file sharing). Pass the path by direct invocation as one argument (`"${HostPath}:/b:ro"`); it contains no `"` and never ends in `\`, so PowerShell's quoting of a spaced path is safe. **Prove the mount is visible before trusting a count:** Docker Desktop has been reported to present an EMPTY folder for bind mounts of some locations (a non-C:, USB or network drive; docker/for-win#14271, not reproduced here), and an empty view counts 0 and exits 0. DAAF's program prints `BACKUP_SENTINEL=1` only when it sees a file every backup contains (the root `.daaf-symlinks`); backup treats a missing sentinel as "count unavailable" and falls back, and restore (which must accept older backups without that file) treats a count of 0 the same way. **Prove the count saw everything, too:** a pipeline's exit status is its LAST command's, so in `find ... | awk` a `find` read error (e.g. `Permission denied` through the bind mount) is silent: awk prints a SHORT count and the program exits 0. `set -e` does not help (the pipeline "succeeded"), and busybox's `pipefail` build default is unverified. DAAF sends the count's stderr to a file inside the throwaway container (`find ... 2>/tmp/count_err | awk ...`) and prints the count markers only when that file is empty, otherwise `BACKUP_COUNT_ERRORS=<n>` (the snapshot count does the same with `STAGED_COUNT_ERRORS`), so an error routes to the fallback instead of being trusted as exact (review round 2 reproduced the silent short count under dash). The post-restore volume count in both restore twins uses the same pattern (`RESTORED_FILES=` only on an empty error file, else `RESTORED_COUNT_ERRORS=`); there an unavailable count is a WARNING with exit 0 that latches restore's WITH WARNINGS banner, because the copy already succeeded and only the check could not run, while a count actually read as 0 still fails.
3. When you must use `Get-ChildItem`, capture `-ErrorVariable` and report a non-empty error set as a lower bound (DAAF: `Measure-DaafBackupTree`; `backup_daaf.ps1` shows the count as `N+` and latches the WITH WARNINGS banner, and `restore_from_backup.ps1`'s listing and scan show `N+`, the scan's `N+` also latching restore's WITH WARNINGS banner). Never treat a lower bound as proof of loss: a short lower-bound count does not trigger backup's fatal short-copy branch, and restore prints no mismatch warning when the restored volume holds at least that many files (its banner still ends WITH WARNINGS, because a lower bound cannot prove the restore complete). The macOS/Linux twins apply the same lower-bound semantics to a host `find` that hits a read error (`_daaf_tree_count`: `backup_daaf.sh` and the `restore_from_backup.sh` listing show `N+`), with one deliberate difference: `restore_from_backup.sh`'s scan of the selected backup **refuses** to restore (exit 1, before the destructive prompt) instead of proceeding with `N+`. It also refuses when the backup folder itself cannot be opened, and when any regular file in it is unreadable: `find` opens only folders, so a separate POSIX `[ -r ]` pass over every file catches unreadable files, such as a root-owned 0600 file left by a backup run under sudo. Off Windows there is no path-length limit to explain the error, so it is a real permission or I/O problem that `docker cp`, reading the same files as the same user, would most likely hit too, after the volume had already been cleared (inference: whether `docker cp` then skips such a file or fails outright was not verified).
4. Warn users up front when files *will* exceed the limit: other Windows tools (Explorer, zip, cloud-sync clients) share it. DAAF's backup scan counts files whose path in the backup folder would reach 260+ characters and prints a notice suggesting a shorter folder (e.g. `C:\daaf`) or enabling long-path support.

**Severity:** High. A silent undercount on the completeness check of a backup, hidden further by a percentage tolerance.

---

### busybox `find` Never Runs the Last Batch of an `-exec ... {} +` Inside `\( \)`

**The problem:** busybox `find` batches `-exec ... {} +` like GNU `find`, but it runs the final (partial) batch at the end of the walk only for `-exec` actions at the TOP level of the expression. An `-exec ... {} +` inside a parenthesized group collects its paths and then never runs for the last batch, which for a small or medium tree is the only batch: the command prints nothing and no error message (observed on a real host, see the field evidence below); that `find` still exits 0 is inferred from the source, not observed. GNU `find` runs it, so a test suite that runs container programs under GNU `find` (DAAF's dev image has no busybox) passes while the real `docker run ... busybox` does nothing.

```sh
# BAD: the -exec sits inside \( \) -- busybox prints nothing, GNU prints the paths
find . -mindepth 1 \( -type d -exec printf '%s d\n' {} + -o -type f -exec printf '%s f\n' {} + \)

# GOOD: top-level OR branches, each carrying its own tests (identical output under GNU)
find . -mindepth 1 -type d -exec printf '%s d\n' {} + -o -type f -exec printf '%s f\n' {} +

# ALSO GOOD: tests inside the parentheses, the action after them
find /staging \( -type p -o -type s -o -type b -o -type c \) -exec rm -f {} +
```

`-exec ... \;` (one run per path, not batched) is not affected.

**Why it happens (from source, not executed here):** in busybox `findutils/find.c`, `flush_exec_plus()` runs the pending batch of every `func_exec` action it finds by walking `G.actions`, the top-level OR branches and their AND lists; a `\( \)` group is a single `func_paren` action whose own `subexpr` action list it never visits ([busybox find.c, `mirror/busybox` master](https://github.com/mirror/busybox/blob/master/findutils/find.c), read on 2026-09-30). Alpine's downstream patch documents the symptom: `touch a; busybox find a \( -exec echo {} + \)` "didn't output anything but should output a" ([Alpine aports MR !75008](https://gitlab.alpinelinux.org/alpine/aports/-/merge_requests/75008), not yet upstreamed when read). The unpinned `busybox` image DAAF uses is the upstream (glibc) build, and it is affected: see the field evidence below.

**Field evidence (2026-10-01, Windows host, Docker 29.1.3, the `busybox` image as pulled that day):** a one-shot probe (`research/2026-09-29_FrameworkDev_BackupLongPathCount/2026-09-30_busybox_host_probe.md`) printed `CANARY_PARENS=0` for `find /source -name keep.txt \( -exec echo {} + \) | wc -l` and `CONTROL_TOPLEVEL=1` for the same `-exec` at the top level, with no error line in the output. So the batch inside the parentheses never ran and printed nothing. The probe did not capture `find`'s exit status. The same probe ran the fixed staging program (top-level `-o` branches) under that busybox in both name modes, and its output matched the expected listing exactly.

**Field relevance (review round 7, 2026-09-30):** the Windows backup's case-clash listing (`STAGE_PROGRAM` in `scripts/host/backup_daaf.{sh,ps1}`) first grouped its two `-exec printf ... {} +` branches in `\( \)`. Under busybox it would have listed nothing, so case clashes involving a file would neither have been removed nor reported (the zero-tolerance count would still have caught any file lost to them). Fixed by the top-level form above.

**Fix:**
1. Keep every batched `-exec ... {} +` at the top level: put tests in the parentheses and the action after them, or split the group into `-o` branches that each repeat their tests.
2. Guard it mechanically: `tests/bash/backup_twin_parity.bats` reads the host backup/restore scripts and their extracted container programs as text and fails on any `{} +` inside `\( \)` (continuation lines joined, comment lines skipped), with a self-test that rebuilds the pre-fix line.
3. When busybox itself is not available to the test suite, give the user a one-shot probe to run on the real host (`docker run --rm busybox ...`) with a canary line that proves the probe ran on busybox.

**Severity:** High. A silent no-op in a container program, invisible to GNU-based tests.

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
| `Start-Process -ArgumentList` array joined unquoted | PowerShell | High | — |
| `Start-Process -PassThru` `ExitCode` `$null` (no `.Handle`) | PowerShell | Medium-High | — |
| `$LASTEXITCODE` / exit code `$null` read as success | PowerShell | Medium | — |
| Implicit return values | PowerShell | High | — |
| UTF-8 BOM breaks `iex` | PowerShell | High | — |
| `$null` in ForEach pipeline | PowerShell | Medium | — |
| `-Version Latest` | PowerShell | Medium | — |
| Parameter validation bypass | PowerShell | Medium | — |
| Env var case sensitivity | Cross-platform | Medium | — |
| Alias removal on Linux | Cross-platform | Medium | PSAvoidUsingCmdletAliases |
| Exit code truncation | Cross-platform | Low | — |
| Path separator differences | Cross-platform | Medium | — |
| Octal `printf` escapes eaten before `sh` | Cross-platform | High | — |
| Windows `docker cp` aborts at FIFO/device/symlink/name | Cross-platform | High | — |
| PS 5.1 `Get-ChildItem -Recurse` silently skips long paths | PowerShell | High | — |
| busybox `find`: batched `-exec ... {} +` inside `\( \)` never runs its last batch | Cross-platform | High | — |
