# Gotchas

Known pitfalls and surprising behaviors in Bash, PowerShell, and cross-platform scripting, plus test-suite pitfalls. Each entry includes the problem, why it happens, and the fix.

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

### `x="$(fn 2>&1 > /dev/null)"` Waits for a Subshell That `fn` Left Running in the Background

**The problem:** Take a command substitution whose call carries its own redirections, such as `said="$(fn 2>&1 > /dev/null)"`, where `fn` is a shell function (or a `{ ...; }` group). If `fn` starts a background subshell (`( ... ) &`), the substitution does not return until that subshell exits, even when the subshell sends its own stdout and stderr to `/dev/null`. The same background job started from a plain `$( ( ... ) & )`, with no redirections on the call, returns at once. A test mock that schedules a delayed signal this way delivers it in the middle of the caller's next step instead of later.

```bash
# BAD: the mock's sleeper is a forked bash subshell -- the caller's $(...) blocks ~1 s
fake_docker() { ( sleep 1; kill -INT "$$" ) > /dev/null 2>&1 < /dev/null & }
said="$(fake_docker volume rm x 2>&1 > /dev/null)"

# GOOD: start the sleeper as an exec'd program -- the substitution returns at once
fake_docker() { sh -c 'sleep 1; kill -INT "$1"' sh "$$" > /dev/null 2>&1 < /dev/null & }
said="$(fake_docker volume rm x 2>&1 > /dev/null)"
```

**Field evidence (this dev container, bash 5.2.21, 2026-10-05):**
- `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/engineer21/comsub_fd_probe.sh` started a 1 s background job from such a function:
  - A forked subshell (`( ls /proc/$BASHPID/fd; sleep 1; : ) ... &`) listed one extra pipe descriptor, `11 -> pipe:[...]`, and the substitution took `forked_elapsed_ms=1003`.
  - With `sleep` as the subshell's last command, which bash execs in place of the subshell, it took `forked_tail_elapsed_ms=2`. The listing, taken before the `sleep`, still showed fd 11.
  - An exec'd `sh -c` listed no pipe descriptor and took `execd_elapsed_ms=1`.
- Fix pass #18's probe (`scratch/engineer18/comsub_probe.sh`, 2 s sleeps) gave `function_subshell_sleeper_elapsed_ms=2002` against `function_exec_sleeper_elapsed_ms=1`, and `comsub_2to1_elapsed_ms=2002` for a braced group `{ ( ... ) & } 2>&1 > /dev/null`. A plain `$( ( ... ) & )` took `comsub_elapsed_ms=1`.

**Why it happens (inference that fits every timing above; bash's source was not read):** to apply the call's redirections, bash first saves a copy of the current stdout, here the write end of the substitution's pipe, on a high descriptor (fd 11 above), and restores it afterwards. A subshell forked meanwhile inherits that copy, and the substitution reads until every write end is closed. The saved copy is close-on-exec, so it disappears as soon as a program is exec'd: an `sh -c`, a real `docker`, or the subshell's own last command.

**Fix:**
1. In mocks and helpers that run inside such a substitution, start background work as an exec'd program (`sh -c '...' sh "$$" ... &`), not as a `( ... ) &` subshell.
2. Production code that calls a real binary is not affected, because the binary is exec'd (inference from the probe: the exec'd child held no pipe descriptor).

**Where it lives in DAAF:** fix pass #18 (2026-10-05) changed `scripts/host/restore_from_backup.sh` to read Docker's text with `said="$(docker volume rm "$1" 2>&1 > /dev/null)"`. The bats `mock_docker` is a shell function whose `volume rm` arm scheduled a delayed SIGINT with `( sleep 1; kill -INT "$$" ) ... &`, so the Ctrl+C-at-the-closing-pause test began to fail: the signal landed during cleanup. The mock's delayed-signal arms in `tests/bash/restore_from_backup.bats` start the sleeper as `sh -c 'sleep 1; kill -INT "$1"' sh "$$"` instead.

**Severity:** Medium. Only test doubles and helpers that fork bash subshells are affected, but the failure moves a signal in time and looks like a script regression.

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

### A Ctrl+C Inside `try`/`finally` Runs the `finally`, Then the Script Exits 0

**The problem:** A Ctrl+C (SIGINT on Linux/macOS) stops the running pipeline. PowerShell runs the enclosing `finally` blocks and then ends the script: no `catch` runs, nothing after the `finally` runs (including an `exit N` placed there), and a `pwsh -File` process exits **0**. A parent that reads only the exit code (a launcher, a CI step, DAAF's Control Panel) sees a clean return, even though the `finally` printed "interrupted". A script with no `try` at all also exits 0 on SIGINT (review round 5 repro, pwsh 7 on Linux), so the fix below covers only the code inside its own `try`/`finally`.

```powershell
$ReachedEnd = $false
try {
    & sleep 20          # Ctrl+C here
    $ReachedEnd = $true
} finally {
    if (-not $ReachedEnd) { Write-Host "Interrupted -- cleaned up." }   # prints
}
exit 1                  # never runs: the process exits 0
```

**Field evidence:** observed with pwsh 7.6.3 on Linux, 2026-10-02 (`research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/engineer17/repro_child.ps1`, driven by `repro_driver.sh` and `repro_repeat.sh` in the same folder). A SIGINT sent to the child `pwsh -NoProfile -File` process while its `try` ran a native `sleep` or `Start-Sleep`:
- No exit in the `finally`: exit 0, all 40 lines of the `finally`'s text printed, the line after the `finally` never printed.
- `[Environment]::Exit(130)` as the `finally`'s last statement: exit 130 in 10 of 10 runs per wait type, each after all 40 lines were printed.
- `exit 130` in the `finally`: exit 130 too.
- The `catch` did not run on the SIGINT; on a `throw` it did, and the process exited 1.
- With a native command running, the process ended only when that command had finished (17-18 s after the SIGINT, for a `sleep 20` started 3 s before it); with `Start-Sleep`, at once.
On Windows (Windows PowerShell 5.1.26100, field test 2026-10-05; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-05_restore_field_test_results.md`, Runs 5a and 7), a real console Ctrl+C (a console control event, not a POSIX signal) during the restore's `try` printed the `finally`'s recovery text as designed. Exit codes were not captured, so whether 5.1 then exits 0 like pwsh 7 is still inference. Started from the Control Panel (`.\daaf.ps1`, which runs the restore as a child process), the same Ctrl+C also ended the Control Panel: the prompt went straight back to PowerShell, with no `exited without completing (code 130)` line. A parent that shares the console can be interrupted by the same Ctrl+C before it reads the child's exit code (inference: Windows delivers a console Ctrl+C to every process attached to that console; not verified here).

**Fix:** Decide "interrupted" from flags (the `try` did not reach its end, a `catch` that rethrows recorded no error, and no outcome flag explains it) and end the process from the `finally`'s LAST statement, after every message. Do it only when a parent reads the exit code: in a script the user started in their own PowerShell window, `[Environment]::Exit` ends that whole session and closes the window the recovery text was just printed in (and, called through `&` in an in-process Pester test, it kills the test host; see the entry above).

```powershell
$ReachedEnd = $false; $Faulted = $false
try {
    # ... every outcome sets a flag and leaves with `break`, never `exit` ...
    $ReachedEnd = $true
} catch {
    $Faulted = $true    # a real error: keep PowerShell's own exit code
    throw
} finally {
    # ... cleanup and messages ...
    if ((-not $ReachedEnd) -and (-not $Faulted) -and $env:DAAF_NESTED) { [Environment]::Exit(130) }
}
```

**Where it lives in DAAF:** `scripts/host/restore_from_backup.ps1` (the copy-then-swap `try`/`finally`; `daaf.ps1`'s `Invoke-DaafDelegate` starts it as a child process with `DAAF_NESTED=1`). Pinned and exercised in `tests/powershell/restore_from_backup.Tests.ps1` (SIGINT sent to the child pwsh while preparing and during the swap, with and without `DAAF_NESTED`, plus an injected error). A standalone run keeps exit 0 (documented known limit).

**Severity:** Medium. The cleanup and the message are right; only the exit code lies, and only callers that read it are misled.

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

**Why it happens:** PowerShell treats native executables as black boxes. Their stderr output and exit codes are outside PowerShell's error handling system (unless `$PSNativeCommandUseErrorActionPreference = $true` in PS 7.4+; see that entry below).

---

### Windows PowerShell 5.1 Drops Native stderr Under `SilentlyContinue`, Even With `2>&1`

**The problem:** A common pattern brackets a native call with `$ErrorActionPreference = 'SilentlyContinue'`, so that its stderr lines (Docker writes errors and progress there) cannot become terminating errors under a script-wide `'Stop'`, and captures the output with `2>&1`. On Windows PowerShell 5.1 the stderr lines never reach that capture. Every `Docker said: ...` message built from it comes out empty, and every match on Docker's error text (`No such container`) silently fails. pwsh 7 keeps the lines, so tests that run on pwsh 7 (Linux CI, the DAAF dev container) cannot catch this.

```powershell
# BAD on Windows PowerShell 5.1: the stderr line is dropped from $out
$saved = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
$out = @(docker container inspect --format x nosuch 2>&1 | ForEach-Object { "$_" })
$ErrorActionPreference = $saved

# GOOD: 'Continue' inside the bracket keeps stderr in the merged capture
$saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
$out = @(docker container inspect --format x nosuch 2>&1 | ForEach-Object { "$_" })
$ErrorActionPreference = $saved
```

**Field evidence (Windows PowerShell 5.1.26100.9444, Docker 29.1.3, 2026-10-05; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-05_restore_field_test_results.md`, section 5):**
- The capture above, run once under each preference, printed `SILENT_LINES=1` and `CONTINUE_LINES=2`.
- Under `Continue` the two lines were an empty stdout line and `Error response from daemon: No such container: daafprobe_none`. So `SilentlyContinue` dropped exactly one line. That it was the stderr line is inference, because the `SilentlyContinue` capture itself was not printed.
- The same day, on the same host, the restore's copy failure printed no `Docker said:` line (Run 3c).
- On pwsh 7.6 / Linux, a raw `2>&1` capture under `SilentlyContinue` kept the line (`lines=2 errorrecords=1`, fix pass #18), so the drop is specific to 5.1.
- The CI probe (below) confirmed it on a stock 5.1 with `cmd.exe` as the native program (CI - Scripts run 38316686493, 5.1.26100.33438, 2026-10-12): `2>&1 under SilentlyContinue: items=1 stdout_lines=1 stderr_lines=0 error_records=0` and `2>&1 under Continue: items=2 stdout_lines=1 stderr_lines=1 error_records=1`. There the dropped line is observed to be the stderr line. The run is recorded in `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-13_ci_ps51_probe_and_windows_recheck2.md`.

**Why it happens (sourced, 2026-10-06):** PowerShell 7.2 changed how redirected native stderr is handled. Microsoft's [about_Preference_Variables](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables) says: "Beginning in PowerShell 7.2, error records redirected from native commands, like when using redirection operators (2>&1), aren't written to the $Error variable and the preference variable $ErrorActionPreference doesn't affect the redirected output." (fetched to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/web/compat/2026-10-06T153036Z_learn-microsoft-com_about-preference-variables-powershell-microsoft-learn_0309d393.md`, lines 212-215). So on Windows PowerShell 5.1 the preference still applies to each redirected stderr record, and `SilentlyContinue` suppresses it before it reaches the capture; from 7.2 on it does not, which is why pwsh 7 keeps the line. The page states the 7.2 change; that 5.1 drops the record *because* the preference applies there is inference from "Beginning in PowerShell 7.2" plus the field probe above. The same page goes on: "PowerShell 7.4 added a feature that allows you to control how messages written to stderr are handled", which is the next entry.

**Fix (choose by what the capture is for; the two fixes are not interchangeable):**
1. **Its text is shown to the user** (`Docker said:`, `Git reported:`, a details block): use `'Continue'`, not `'SilentlyContinue'`, in the bracket, and restore the previous value right after. Under `Continue`, with `2>&1` into a variable, nothing reached the console and nothing was terminating under a top-level `'Stop'` (observed on pwsh 7.6; on 5.1, inferred from the field probe).
2. **It is only tested for emptiness, or parsed for stdout** (a container ID from `docker compose ps -q`, a `NAME=<n>` marker): use `2>$null` and keep `'SilentlyContinue'`. Do **not** switch these to `'Continue'`: here the polarity is inverted. On 5.1 the drop is what made such a check correct, and `Continue` would let a stderr-only line (a Compose warning, say) make the capture non-empty, so a stopped container reads as running. pwsh 7 already had that misread, because 7.2+ keeps the line under any preference. Observed on pwsh 7.6.3: a stderr-only native call captured with `2>&1` under `SilentlyContinue` gave `captured_count=1`, `isNullOrWhiteSpace=False`, and with `2>$null` gave `isNullOrWhiteSpace=True` (scoping audit `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/05_ps1_stderr_audit.md`, section 2). That a Compose warning occurs in practice is inference. A capture whose output is discarded (`$null =`, `| Out-Null`, `[void]`) can keep `SilentlyContinue` with any redirect: it reads nothing.
3. **A stderr file read back for display** (`... 2>> $log`, then `Get-Content -Tail 5`): keep the lines in memory instead, under `'Continue'`:

   ```powershell
   $errLines = New-Object System.Collections.Generic.List[string]
   $saved = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
   $out = @(docker compose exec -T daaf-docker true 2>&1)
   $exit = $LASTEXITCODE
   $ErrorActionPreference = $saved
   foreach ($item in $out) {
       if ($item -is [System.Management.Automation.ErrorRecord]) { $errLines.Add("$item") } else { $item }
   }
   ```

   5.1 empties a `2>>` FILE redirect under `SilentlyContinue` too: **observed** by the CI probe below (CI - Scripts run 38316686493, Windows PowerShell 5.1.26100.33438, 2026-10-12), which printed `2>> file under SilentlyContinue: captured_stdout_items=1 file_exists=True file_lines=0 lines_naming_PROBE_ERR=0`. So the old readiness form's `Docker reported:` block would have come out blank on 5.1 (inference: the probe ran `cmd.exe`, not the readiness loop). That a plain `2>` behaves the same is inference (only `2>>` was probed); pwsh 7.6 was observed to keep the line in the file. Under `Continue` a file redirect is no fix either: the same run printed `2>> file under Continue: captured_stdout_items=1 file_exists=True file_lines=7 lines_naming_PROBE_ERR=2`, and the file held PowerShell's **formatted** error record, not the raw line:

   ```
       | cmd.exe : PROBE_ERR
       |     + CategoryInfo          : NotSpecified: (PROBE_ERR :String) [], RemoteException
   ```

   (lines 1 and 5 of its seven; the others are the `At ...:44 char:14` position, the echoed command and its `~~~` underline, `FullyQualifiedErrorId : NativeCommandError`, and a blank line; in the log the first line ends in one space). A `Get-Content -Tail 5` of that file would show PowerShell's error-record text instead of Docker's message. The in-memory form avoids both: it relies on the `2>&1`-under-`Continue` behavior that is observed, and needs no temp file. That 5.1 hands each merged stderr line over as an `ErrorRecord` is observed in the same run (`2>&1 under Continue: items=2 stdout_lines=1 stderr_lines=1 error_records=1`). That its `"$_"` is the plain message comes from the field probe, whose `ForEach-Object { "$_" }` printed Docker's line with no prefix; the CI probe only checks that the text contains `PROBE_ERR`.
4. **A capture scanned only for anchored stdout markers and never shown** loses nothing that matters, so it can stay as it is. DAAF keeps four of these under `SilentlyContinue` and names them, with reasons, in the guard's allowlist.
5. pwsh 7 cannot reproduce the drop, so a behavioral test on Linux cannot guard against it. Guard it structurally (a test that parses the script), and confirm on a real Windows PowerShell 5.1 host when you can.

**Guards in DAAF:**
- `tests/powershell/native_stderr_capture.Tests.ps1` (dispatch #64) parses every `scripts/host/*.ps1`. It flags a site when all four of these hold:
  - it is a `docker` call, or a call to an in-file wrapper whose body runs docker with stderr not redirected;
  - its effective `$ErrorActionPreference` is not an explicit literal `'Continue'` in the same scope. The guard tracks this in source order within each function. `SilentlyContinue` and `Ignore` are flagged, and so is `Stop`. So is "inherited": no assignment yet in that function, or a `= $saved` restore. That catches a function with no bracket of its own that a `SilentlyContinue` caller calls (dispatch #65);
  - its stderr is merged or sent to a file;
  - its output is kept.

  The failure message carries the fix chooser above. Its self-tests cover known-bad and known-good snippets, plus in-memory reverts of four dispatch #63 fixes (one G1, two G2, one G3), each of which must be flagged. Run against the pre-#63 scripts, it flagged all 24 sites the audit had listed (observed, dispatch #64). Its header lists what it still misses, among them: a `| Tee-Object -Variable t | Out-Null` tail reads as discarded, and a `Set-Variable -Name ErrorActionPreference` after a literal `'Continue'` is not seen.
- `.github/workflows/ci-scripts.yml`, job `validate-ps-windows`, step "Probe native stderr capture (Windows PS 5.1)". Under `shell: powershell` it runs `cmd.exe`, writing one stdout and one stderr line.
  - It **asserts** the two `2>&1` facts: `SilentlyContinue` drops the stderr line and `Continue` keeps it. The step fails if 5.1 stops behaving that way.
  - It **asserts** that a `2>> file` under `SilentlyContinue` gets no lines, after checking that the stdout line arrived. Its first run (CI - Scripts run 38316686493, 5.1.26100.33438, 2026-10-12) observed exactly that, and the assertion was added afterwards; a failure names the direction (`KEPT`) and the docs to correct.
  - It **reports** the `2>> file` result under `Continue` and the merged record type, with a `::warning::` if the file no longer holds a formatted error record naming the line. Not asserted, because no host script sends stderr to a file any more.
- `tests/powershell/stream_capture_idiom.Tests.ps1` runs the `Continue` idiom against a real native command and checks that both lines are kept and nothing is thrown under `'Stop'`. A version-conditional check also asserts that `SilentlyContinue` keeps the line on 7.2+, and drops it on 5.1 if the file is ever run there.
- The per-site pins: the restore suite's D2 pin, and the dispatch #63 pins in the backup, daaf, install, rebuild, update, run_daaf, view_* and run_vscode suites.

**Where it lives in DAAF:**
- **`'Continue'` around captures shown to the user.**
  - `restore_from_backup.ps1`, since fix pass #18 (D2): `Invoke-DaafRestoreDocker`, `Invoke-DaafRestoreDockerSplit`, and `$ScanCountOutput`, `$cpOut`, `$TempVerifyOutput` and `$VerifyOutput`.
  - The helper-image pull `$pullAll` there and in `backup_daaf.ps1`, since follow-up pass #26. The pin also constrains this capture's form: its first shape, `docker pull ... 2>&1 | ForEach-Object` with no assignment, was rejected by the pin, so the pull was reshaped as a `$pullAll = @(...)` capture the pin recognises.
  - Since dispatch #63: `daaf.ps1` (`$launchErr` x2, `$manifestErr` x2, `$serveErr`, `$readyErr`), `update_daaf.ps1` (`$fetchOutput`) and `backup_daaf.ps1` (`$StageLog`, `$ClaudeStageLog`).
- **Readiness lines kept in memory under `'Continue'`, no temp file** (dispatch #63): `$readyOut` / `$readyErrLines` in `install.ps1`, `rebuild_daaf.ps1` and `update_daaf.ps1`. Their `.sh` twins still use a temp file with `2>>` plus `tail -5`; Bash does not have this problem.
- **`2>$null` under `SilentlyContinue` for emptiness and ID checks.** Since dispatch #63: `run_daaf.ps1` (`$CidOutput`, `$_cid`, `$_created`) and `$CidOutput` in `view_notebooks.ps1`, `run_vscode.ps1`, `view_quarto.ps1` and `view_logs.ps1`. This matches the existing checks in `daaf_lib.ps1` (`Confirm-DaafContainer`), `daaf.ps1` and `update_daaf.ps1`.
- **Allowlisted marker-only reads:** `backup_daaf.ps1` (`$StageDoneLog`, `$HostCountOutput`, `$ClaudeStageDoneLog`) and `migrate_daaf.ps1` (`$SearchResultRaw`).

**Severity:** Medium. Data is not at risk, but every diagnostic built from Docker's text is lost on the PowerShell most Windows users run, and logic that matches error text quietly takes its fallback path. The obvious fix, applied to an emptiness check, brings in a different misread (fix 2).

---

### `$PSNativeCommandUseErrorActionPreference` (pwsh 7.4+) Turns a Native Nonzero Exit Into an Error Record

**The problem:** In PowerShell 7.4 and later, when `$PSNativeCommandUseErrorActionPreference` is `$true`, a native command that exits nonzero also raises a PowerShell error, handled by `$ErrorActionPreference`. A script written to read `$LASTEXITCODE` itself (every DAAF host script) then gets an extra line in its `2>&1` captures, or a throw under a script-wide `'Stop'`. It is off by default (observed: `pwsh -NoProfile` 7.6.3 printed `value=[False]`), so the risk is a value set outside the script, for example in a profile or a calling session (inference: not observed in the field). Windows PowerShell 5.1 does not have the feature.

```powershell
# BAD (pwsh 7.4+, if the variable is $true): a script that classifies exit codes itself
$ErrorActionPreference = 'Stop'
docker volume inspect nosuch          # throws NativeCommandExitException before your check runs
if ($LASTEXITCODE -ne 0) { ... }

# GOOD: switch it off once, right after the preamble, in every script that reads $LASTEXITCODE
$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $false   # an ordinary, unused variable on 5.1
```

**Why it happens (sourced, 2026-10-06):** about_Preference_Variables: "When $PSNativeCommandUseErrorActionPreference is $true, native commands with non-zero exit codes issue errors according to $ErrorActionPreference." Its own example disables it for a command that uses nonzero codes for information: "Some native commands, like robocopy use non-zero exit codes to represent information other than errors. In these cases, you can temporarily disable the behavior and prevent non-zero exit codes from issuing errors." (`research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/web/compat/2026-10-06T153036Z_learn-microsoft-com_about-preference-variables-powershell-microsoft-learn_0309d393.md`, lines 586-592.)

**Repro (pwsh 7.6.3 on Linux, compatibility audit 04, `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/04_F1_compat_audit.md`, dependency table):** with the variable set to `$true` and a native `sh` that exits 3:
- Under `Continue`, the `2>&1` capture gained a third line: `Program "sh" ended with non-zero exit code: 3 (0x03).` A script that shows the last captured line as `Docker said:` would have shown that line instead of Docker's message.
- Under `SilentlyContinue`, the capture held 2 lines.
- Under `Stop`, with no preference bracket around the call, it threw `NativeCommandExitException`.

**Fix:**
1. Set `$PSNativeCommandUseErrorActionPreference = $false` right after `$ErrorActionPreference = 'Stop'` in every script that classifies native exit codes itself. It is a plain assignment that a 5.1 script also accepts.
2. Keep reading `$LASTEXITCODE` immediately after each native call; the preference variable only stops PowerShell from adding its own error on top.
3. Where a single command needs the feature on, set it inside a script block (`& { ... }`): the change is local to that block, as the documentation's robocopy example shows.

**Where it lives in DAAF:** every `scripts/host/*.ps1` that runs native commands, right after the `$ErrorActionPreference` line: `restore_from_backup.ps1` and `backup_daaf.ps1` (follow-up pass #26), `migrate_daaf.ps1` (review fix round 9), and since dispatch #63 `install.ps1`, `update_daaf.ps1`, `rebuild_daaf.ps1`, `daaf.ps1`, `run_daaf.ps1`, `view_notebooks.ps1`, `view_quarto.ps1`, `view_logs.ps1`, `run_vscode.ps1` and `test_migration.ps1`. The dot-sourced `daaf_lib.ps1` carries no assignment of its own and inherits `daaf.ps1`'s.

**Severity:** Low-Medium. Low in DAAF (every docker call there sits in a preference bracket, so it could not throw; only the extra line could leak into a `Docker said:` text). Higher for a script that calls native commands under a bare `'Stop'`.

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
2. Count container-side when Docker is at hand: bind-mount the host folder read-only and run `find` (DAAF: `$BackupCountProgram` in `backup_daaf.ps1` / `restore_from_backup.ps1`, byte-identical, pinned by `tests/bash/backup_twin_parity.bats`; one `find -exec stat -c %s {} + | awk` pass yields files and KB, since each walk of a bind mount crosses Docker Desktop's host file sharing). Pass the path by direct invocation as one argument (`"${HostPath}:/b:ro"`); it contains no `"` and never ends in `\`, so PowerShell's quoting of a spaced path is safe. **Prove the mount is visible before trusting a count:** Docker Desktop has been reported to present an EMPTY folder for bind mounts of some locations (a non-C:, USB or network drive; docker/for-win#14271, not reproduced here), and an empty view counts 0 and exits 0. DAAF's program prints `BACKUP_SENTINEL=1` only when it sees a file every backup contains (the root `.daaf-symlinks`); backup treats a missing sentinel as "count unavailable" and falls back, and restore (which must accept older backups without that file) treats a count of 0 the same way. **Prove the count saw everything, too:** a pipeline's exit status is its LAST command's, so in `find ... | awk` a `find` read error (e.g. `Permission denied` through the bind mount) is silent: awk prints a SHORT count and the program exits 0. `set -e` does not help (the pipeline "succeeded"). busybox ash does support `set -o pipefail` (from source: `BASH_PIPEFAIL = ENABLE_ASH_BASH_COMPAT`, and `ASH_BASH_COMPAT` is `default y`; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/02_docker_volume_disk_mechanics.md` § E), but no DAAF program has been executed with it under busybox, and a program that must stay portable to other images should not rely on a build option. DAAF sends the count's stderr to a file inside the throwaway container (`find ... 2>/tmp/count_err | awk ...`) and prints the count markers only when that file is empty, otherwise `BACKUP_COUNT_ERRORS=<n>` (the snapshot count does the same with `STAGED_COUNT_ERRORS`), so an error routes to the fallback instead of being trusted as exact (review round 2 reproduced the silent short count under dash). The post-restore volume count in both restore twins uses the same pattern (`RESTORED_FILES=` only on an empty error file, else `RESTORED_COUNT_ERRORS=`); there an unavailable count is a WARNING with exit 0 that latches restore's WITH WARNINGS banner, because the copy already succeeded and only the check could not run, while a count that was read must equal the checked temporary copy's count exactly (any difference, including 0, fails with the temporary copy kept).
3. When you must use `Get-ChildItem`, capture `-ErrorVariable` and report a non-empty error set as a lower bound (DAAF: `Measure-DaafBackupTree`; `backup_daaf.ps1` shows the count as `N+` and latches the WITH WARNINGS banner, and `restore_from_backup.ps1`'s listing and scan show `N+`, the scan's `N+` also latching restore's WITH WARNINGS banner). Never treat a lower bound as proof of loss: a short lower-bound count does not trigger backup's fatal short-copy branch, and restore's check of its temporary copy only requires at least that many files (its banner still ends WITH WARNINGS, because a lower bound cannot prove the restore complete). `restore_from_backup.ps1` treats every PowerShell-fallback count as such a lower bound, even one without read errors, because PowerShell can miss what `docker cp` streams; only a count made inside Docker is an exact gate. The macOS/Linux twins apply the same lower-bound semantics to a host `find` that hits a read error (`_daaf_tree_count`: `backup_daaf.sh` and the `restore_from_backup.sh` listing show `N+`), with one deliberate difference: `restore_from_backup.sh`'s scan of the selected backup **refuses** to restore (exit 1, before anything is copied) instead of proceeding with `N+`. It also refuses when the backup folder itself cannot be opened, and when any regular file in it is unreadable: `find` opens only folders, so a separate POSIX `[ -r ]` pass over every file catches unreadable files, such as a root-owned 0600 file left by a backup run under sudo. Off Windows there is no path-length limit to explain the error, so it is a real permission or I/O problem that `docker cp`, reading the same files as the same user, would most likely hit too, partway through the copy. **What `docker cp` then does was observed on Windows** (field test 2026-10-05, Docker 29.1.3, one backup file denied with `icacls ... /deny "$(whoami):(RD)"`; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-05_restore_field_test_results.md`, Run 3b). It does not skip the file. It FAILS, with exit 1 (`CP_EXIT=1`), after `Can't add file ...rt_n.txt to tar: open ...: Access is denied.`, `archive/tar: missed writing 7 bytes` and `Error response from daemon: unexpected EOF`. It also leaves a PARTIAL copy behind: 7 of the 8 files arrived, including the denied file as an entry, and the file after it in the stream was missing. (That the denied file arrived as a header with none of its 7 bytes, which broke the stream for the next file, is inference.) So treat any nonzero `docker cp` exit as a failed copy, and never use what arrived. On macOS/Linux the same failure is expected (inference, not run). The general lesson: when an input is known to be unreadable, refuse before any destructive step, and say which file. Until 2026-10-01 DAAF's restore cleared the live volume before copying, so that failure would have hit after the clear. The restore now copies into a temporary volume and checks it before it replaces anything (copy-then-swap; see the Ctrl+C and `docker volume create` entries below), so a failed or short copy no longer touches the live data. The refusal is kept anyway, because it can name the unreadable file and a failed or short copy cannot.
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

**Why it happens (from source, not executed here):** in busybox `findutils/find.c`, `flush_exec_plus()` runs the pending batch of every `func_exec` action it finds by walking `G.actions`, the top-level OR branches and their AND lists; a `\( \)` group is a single `func_paren` action whose own `subexpr` action list it never visits ([busybox find.c, `mirror/busybox` master](https://github.com/mirror/busybox/blob/master/findutils/find.c), read on 2026-09-30). Alpine's downstream patch documents the symptom: `touch a; busybox find a \( -exec echo {} + \)` "didn't output anything but should output a" ([Alpine aports MR !75008](https://gitlab.alpinelinux.org/alpine/aports/-/merge_requests/75008), not yet upstreamed when read). The `busybox` image DAAF uses is the upstream (glibc) build, and it is affected: see the field evidence below. (Since follow-up pass #26 DAAF pins it by digest to `busybox:1.37.0`, whose per-architecture digests equal `1.37.0-glibc`'s on Docker Hub; see "Upstream images re-push and retag" below. Per the compatibility audit the bug was still present in 1.37.0.)

**Field evidence (2026-10-01, Windows host, Docker 29.1.3, the `busybox` image as pulled that day):** a one-shot probe (`research/2026-09-29_FrameworkDev_BackupLongPathCount/2026-09-30_busybox_host_probe.md`) printed `CANARY_PARENS=0` for `find /source -name keep.txt \( -exec echo {} + \) | wc -l` and `CONTROL_TOPLEVEL=1` for the same `-exec` at the top level, with no error line in the output. So the batch inside the parentheses never ran and printed nothing. The probe did not capture `find`'s exit status. The same probe ran the fixed staging program (top-level `-o` branches) under that busybox in both name modes, and its output matched the expected listing exactly.

**Field relevance (review round 7, 2026-09-30):** the Windows backup's case-clash listing (`STAGE_PROGRAM` in `scripts/host/backup_daaf.{sh,ps1}`) first grouped its two `-exec printf ... {} +` branches in `\( \)`. Under busybox it would have listed nothing, so case clashes involving a file would neither have been removed nor reported (the zero-tolerance count would still have caught any file lost to them). Fixed by the top-level form above.

**Fix:**
1. Keep every batched `-exec ... {} +` at the top level: put tests in the parentheses and the action after them, or split the group into `-o` branches that each repeat their tests.
2. Guard it mechanically: `tests/bash/backup_twin_parity.bats` reads the host backup/restore scripts and their extracted container programs as text and fails on any `{} +` inside `\( \)` (continuation lines joined, comment lines skipped), with a self-test that rebuilds the pre-fix line.
3. When busybox itself is not available to the test suite, give the user a one-shot probe to run on the real host (`docker run --rm busybox ...`) with a canary line that proves the probe ran on busybox.

**Severity:** High. A silent no-op in a container program, invisible to GNU-based tests.

---

### A Forwarded Ctrl+C Stops a Container's `sh -c` Between Commands (PID 1 Does Not Protect a Shell)

**The problem:** A multi-step program run with `docker run ... sh -c '<step 1>; <step 2>'` looks safe from Ctrl+C, because the shell is the container's PID 1 and "PID 1 ignores signals". That rule covers only signals with their *default* action, and a shell running `-c` installs its own SIGINT handler. By default, `docker run` forwards the host's Ctrl+C to PID 1 (`--sig-proxy`, default `true`). The shell lets the current command finish, then exits 130 without running the next one. For a destructive pair like clear-then-copy, that leaves the target EMPTY.

```sh
# BAD: a Ctrl+C during rm is forwarded to the shell, which exits 130 after rm -- cp never runs
docker run --rm -v "${TEMP}:/src:ro" -v "${LIVE}:/dest" busybox sh -c 'rm -rf /dest/*; cp -a /src/. /dest/'

# GOOD (DAAF restore swap): forward nothing, and have the shell catch INT/TERM/HUP with a no-op
docker run --rm --sig-proxy=false --name "${LIVE}-restore-swap" -v "${TEMP}:/src:ro" -v "${LIVE}:/dest" busybox \
    sh -c 'trap : INT TERM HUP; test -f /src/.daaf-restore-swap-started || exit 3; rm -rf /dest/* /dest/.[!.]* /dest/..?* && cp -a /src/. /dest/ && rm -f /dest/.daaf-restore-swap-started'
```

(The BAD form's `/dest/*` also misses dotfiles; the three globs in the GOOD form cover them. The `test -f ... || exit 3` marker guard makes the program erase nothing unless its source is the copy the restore just marked, and reports that refusal with an exit code of its own; see the vanished-volume entry below. `trap :` installs a no-op handler and needs no quotes. DAAF's container programs must stay quote-free, because Windows PowerShell 5.1 mangles a `"` in a native argument and the `.sh` twin wraps each program in single quotes. `trap '' INT` would ignore the signal too, but it needs quotes.)

**Why it happens:**
1. **The CLI forwards signals.** `docker run --sig-proxy` defaults to `true`, "Proxy received signals to the process" ([docker container run](https://docs.docker.com/reference/cli/docker/container/run/), options table). docker/cli's `signals.go` calls `gosignal.Notify(sigc)` with no signal list, which catches every signal, and sends each one on with `ContainerKill` ([signals.go](https://raw.githubusercontent.com/docker/cli/master/cli/command/container/signals.go), [run.go](https://raw.githubusercontent.com/docker/cli/master/cli/command/container/run.go); read 2026-10-01).
2. **The PID-1 rule does not cover a shell.** Docker's docs: "A process running as PID 1 inside a container is treated specially by Linux: it ignores any signal with the default action. So, the process doesn't terminate on SIGINT or SIGTERM unless it's coded to do so." A shell given `-c` is coded to. busybox ash (`shell/ash.c`, lines 3718-3720 of [master](https://raw.githubusercontent.com/mirror/busybox/master/shell/ash.c), read 2026-10-01) catches SIGINT whenever `-c` is in use: `case SIGINT: if (iflag || minusc || sflag == 0) new_act = S_CATCH;`. Per the same source, the interrupt is deferred while a child runs and the shell then exits with status 130 (`raise_interrupt()`). Under dash the shell exited 130 after the child finished (observed, below). Whether busybox waits for the child to end or exits before it does is not settled: the host probe accepts either, as long as the next command never runs (probe doc, "Where busybox may legitimately differ", item 4). In both readings the next command never runs (observed under dash, and under busybox 1.37.0 in a real container: see the field evidence below).
3. **Inference, from the same source:** busybox runs the *last* command of a `-c` string in place of the shell when no trap is set. A single-command `sh -c 'cp ...'` therefore makes `cp` PID 1 with default actions, and a forwarded INT is dropped. That only holds for one command, so do not rely on it.

**Field evidence:**
- **Observed under dash, not busybox** (this dev container, 2026-10-01; dash 0.5.12, GNU coreutils 9.4; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/agent2/probe_signals_b.sh` and `probe_trap_noop.sh`). The probes send SIGINT to the `sh -c` process only, as `docker kill` does.
  - `dash -c 'sleep 2; echo B_RAN'` showed `SigCgt: 0000000000010002`, meaning SIGINT (bit 2) is caught, then printed `Q1 exit=130` and never printed `B_RAN`.
  - With `trap '' INT TERM` first, it printed `B_RAN` and `Q2 exit=0`.
  - With `trap : INT TERM HUP` first, and a SIGTERM one second after the INT, it printed `B_RAN`, `C_RAN` and `Q5 exit=0`.
  - That dash was not PID 1. For INT this does not matter: the shell has a handler, so the PID-1 rule never applies.
- **Observed under busybox 1.37.0 in a real container** (Windows host, Docker 29.1.3, 2026-10-05; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-01_restore_busybox_host_probe.md`, Step 7 and "Field result"). The probe hit the swap's trap prefix and a trap-less control with `docker kill -s INT/TERM/HUP`:
  - With the trap prefix (T1: INT, then TERM, then HUP): `docker wait` printed `0`, and the logs showed `SH_PID=1` and `AFTER_SLEEP`.
  - Without the trap, hit with INT (C1): `130`, and `SH_PID=1` only. The next command never ran.
  - Without the trap, hit with TERM (C2): `0`, `SH_PID=1` and `AFTER_SLEEP`. TERM was ignored by the trap-less PID 1, so the trap matters for INT.
  - A real Ctrl+C on the foreground `--sig-proxy=false` form (T2): the prompt came back before the container finished, and the container ran to the end with `0`.
  - Whether busybox waits for the running child before exiting on INT was not timed.

**Fix:**
1. Run every destructive multi-step container program with `--sig-proxy=false`, so the CLI forwards nothing. A Ctrl+C then stops only the CLI that is waiting. The container runs to the end, and with `--rm` Docker removes it when it exits.
2. Put `trap : INT TERM HUP` first in the program as a second layer, in case a signal reaches it some other way (for example `docker kill -s INT`). Only SIGKILL or Docker itself stopping can cut it short then.
3. Give the container a fixed `--name`, so a re-run can see it still running (`docker container inspect --format '{{.State.Running}}' <name>`). Read that state from stdout only, and count any line that is exactly `true` as running: with stderr merged in (`2>&1 | tail -n 1` in bash, or PowerShell's `2>&1` output joined into one string), a Docker warning line on stderr can make a running container look stopped, and a script would then offer to `docker rm -f` it (DAAF review round 2, I-A; found by reading the code, not reproduced against a real daemon). Keep the source copy until the result has been checked, and tell the user the operation keeps running inside Docker.
4. Do not add `--init` for such a program. tini as PID 1 forwards signals to the shell, which is exactly what must not happen here (inference from tini's documented purpose).

**Where it lives in DAAF:** `SWAP_PROGRAM` / `$SwapProgram` in `scripts/host/restore_from_backup.{sh,ps1}` (byte-identical). `tests/bash/backup_twin_parity.bats` pins the trap prefix and `--sig-proxy=false` on every swap call.

**Severity:** High. An ordinary Ctrl+C silently empties the live data.

---

### `docker volume create` Silently Reuses an Existing Volume, and `docker volume ls --filter name=` Is an Unanchored Regex

**The problem:** Two Docker behaviors make "create a scratch volume, find it again later" unsafe:
- `docker volume create NAME` on a name that already exists does not fail. It hands back the existing volume, contents and all, with exit 0. A stale scratch volume from an earlier failed run is silently adopted.
- `docker volume ls --filter name=X` matches any volume whose name *contains* X, as a regular expression. `name=daaf_daaf-data` also matches `daaf_daaf-data-restore-tmp`, `name=_daaf-data` matches every install's data volume, and `.` matches any character.

```bash
# BAD: adopts a stale $TEMP silently; the "exists?" test matches other volumes too
docker volume create "${TEMP}"
if docker volume ls -q --filter "name=${LIVE}" | grep -q .; then echo "live volume exists"; fi

# GOOD: check the EXACT name first, create only when absent, and mark ownership with a label
if docker volume inspect "${TEMP}" > /dev/null 2>&1; then
    echo "A leftover ${TEMP} exists"      # ask, remove or refuse -- never reuse it blindly
    exit 1
fi
docker volume create --label "org.daaf.restore-tmp-for=${LIVE}" "${TEMP}"
docker ps -aq --filter "label=org.daaf.restore-tmp-for=${LIVE}"   # label=key=value matches exactly
```

**Why it happens (from the docs and source, read 2026-10-01):** [docker volume create](https://docs.docker.com/reference/cli/docker/volume/create/): "If you specify a volume name already in use on the current driver, Docker assumes you want to reuse the existing volume and doesn't return an error." [docker volume ls](https://docs.docker.com/reference/cli/docker/volume/ls/): "The name filter matches on all or part of a volume's name." In moby's `daemon/internal/filters/parse.go` ([master](https://raw.githubusercontent.com/moby/moby/master/daemon/internal/filters/parse.go)), `Args.Match` tries an exact match first and then falls back to `regexp.MatchString(name2match, source)`. A `label=key=value` filter is an exact key/value match (same `volume ls` page).

**Related:**
- `docker volume rm` refuses a volume that any container still references, including a stopped one. [docker volume rm](https://docs.docker.com/reference/cli/docker/volume/rm/) says "You can't remove a volume that's in use by a container", and [moby#18250](https://github.com/moby/moby/issues/18250) shows `volume is in use` from a stopped, not-removed container. A container that was created but never started holds it the same way (observed in the 2026-10-05 Windows field test; see the next entry). So remove the helper containers by label before removing the volume, and then any other stopped holder that `docker ps -a --filter volume=<name>` lists (next entry).
- `docker volume inspect` also exits nonzero when the daemon is unreachable, not only when the volume is missing (inference: not reproduced here). So a nonzero exit alone does not mean "absent". Reading every failure as "absent" lets a transient error lead to a `docker volume create` that silently reuses a leftover, and to a cleanup that then removes it (review round 1, I2; inference, not reproduced).

**Fix:**
1. Test existence by exact name (`docker volume inspect` / `docker container inspect`), never with `ls --filter name=`. Treat a "no such volume / container / object" error (case-insensitive) as absent. For any other failure, do not guess from the error text, whose wording is not a stable interface (inference): fall back to an exact whole-line match against Docker's own name list, stdout only (`docker volume ls -q`, or `docker ps -a --format '{{.Names}}'`; `docker ps --format '{{.Names}}'` then tells a running container from a stopped one), and refuse only when that list fails too, because then the check could not be made.
2. Never `docker volume create` a scratch volume without that check. Decide what a leftover means (DAAF's restore asks `Remove it and continue? (y/n)`) instead of reusing it.
3. Still verify right after the create, because a volume can appear between the check and the create: the new volume must be empty (`find /dest -mindepth 1` lists nothing) and carry a label whose value is unique to this run. Labels are fixed at creation, so a reused volume keeps its own. If either fails, refuse and leave the volume alone: it may be another run's.
4. Derive scratch names from the resolved full volume name, not a project prefix. An override such as `DAAF_DATA_VOLUME_NAME` can make the two differ.
5. Put a label on every scratch volume and helper container, and reap them with `--filter label=key=value`. Leave the label off any container that must never be reaped while it runs. DAAF's swap containers carry no label.
6. Never add `com.docker.compose.*` labels to scratch volumes: compose would treat them as its own.

**Where it lives in DAAF:** `scripts/host/restore_from_backup.{sh,ps1}`: `<volume>-restore-tmp` volumes with labels `org.daaf.restore-tmp-for=<live volume>` (reaping) and `org.daaf.restore-run=<per-run token>` (identity); the not-found test is `_restore_is_not_found` / `Test-DaafRestoreNotFound`, the exact-name list fallback `_restore_name_listed` / `Find-DaafRestoreExactName`, the post-create check `_restore_check_new_temp` / `Test-DaafRestoreNewTemp`. `tests/bash/restore_from_backup.bats` checks that a similarly named volume is not taken for a leftover, that a failed inspect refuses, and that a non-empty new temp volume is left alone.

**Severity:** High. Stale data silently reused, or the wrong install's volume matched.

---

### A "Created" Flag Set After the Create Misses a Ctrl+C That Lands During It

**The problem:** An interrupt handler that removes only what a flag says this run created has a gap. The flag is set after the create call (and often after a check of the new resource), so a Ctrl+C during either one runs the cleanup while the flag still says "nothing created". In bash, a trapped SIGINT that arrives while a foreground command runs is handled when that command returns, before the next statement: the handler runs after `docker volume create` has already succeeded. In PowerShell, the `finally` runs instead (see the `try`/`finally` entry above). Either way the new resource is left behind and nothing reports it.

```bash
# BAD: a Ctrl+C during the create or the check runs the cleanup with CREATED=0
docker volume create --label "org.example.run=${RUN_ID}" "${TEMP}"
check_new_volume "${TEMP}"
CREATED=1

# GOOD: record the attempt BEFORE the call, close it only AFTER the created flag
ATTEMPTED=1
docker volume create --label "org.example.run=${RUN_ID}" "${TEMP}"
check_new_volume "${TEMP}"          # its own refusal sets ATTEMPTED=0 before cleaning up
CREATED=1
ATTEMPTED=0
# ...and at the start of the cleanup: adopt an open attempt only on proof of ownership
if [ "${ATTEMPTED}" -eq 1 ] && [ "${CREATED}" -eq 0 ] && volume_has_run_label "${TEMP}" "${RUN_ID}"; then CREATED=1; fi
ATTEMPTED=0
```

**Why ownership proof, not existence:** an open attempt does not show that this run created anything. The client may have been stopped before the create happened (inference: a real Ctrl+C also reaches the docker CLI), and `docker volume create` silently reuses a volume of the same name, perhaps another run's (see the entry above). Labels are fixed at creation, so a label whose value is unique to this run proves the volume is this run's own. A check that fails is "not ours", never "ours" or "absent". A refusal that has decided to leave a volume alone must close the attempt before its cleanup runs, or the cleanup adopts what the refusal just spared.

**Field evidence:**
- **Deferred handler, observed** (this dev container, bash 5.2.21, 2026-10-06; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/engineer40/probe_deferred_trap.sh`): with `trap '...' INT`, a `kill -INT $$` sent 0.3 s into a foreground `sleep 1.5` printed `HANDLER CREATED=0 elapsed_ms=1510`, and neither of the next two statements ran. Not run under bash 3.2.
- **The DAAF restore gap, reproduced** (task #36, `.../engineer_reports/36_engineer36_COMPLETED.md`): a stand-in `docker` sent SIGINT to the script during `volume create` and then finished. The pre-fix `.sh` exited 130 with `Restore interrupted. Your DAAF data has not been changed.` and left `daaf_daaf-data-restore-tmp` behind; the fixed one ran the identity inspect, the holder list and `volume rm`. A reused volume with another run's label, and a failing identity inspect, were left alone. The `.ps1` twin was probed the same way through Pester under pwsh 7 on Linux. Not observed against a real Docker daemon.

**Fix:**
1. Set an "attempted" flag right before every call that creates something the cleanup should remove, and clear it only after the "created" flag is set.
2. In the cleanup, before acting on the "created" flags, adopt an open attempt only when the resource exists and carries this run's unique identity (a per-run label for Docker volumes). Then remove it through the normal removal path, so its holder checks and messages still apply. Always clear the attempt flag afterwards, and make no call when no attempt is open.
3. Close the attempt first in any path that deliberately leaves the resource alone.
4. In bash, run the same adoption from the EXIT handler when no cleanup has run yet, which covers exits other than the trapped signals. A PowerShell `finally` already covers every exit from its `try`.

**Where it lives in DAAF:** `TEMP_CREATE_ATTEMPTED` / `CLAUDE_TEMP_CREATE_ATTEMPTED` and `_restore_adopt_attempted_temps` in `scripts/host/restore_from_backup.sh`, `$TempCreateAttempted` / `$ClaudeTempCreateAttempted` and `Resolve-DaafRestoreAttemptedTemp` in the `.ps1` twin (task #36; review 32q, I-3). The identity test is `_restore_temp_is_ours` / `Test-DaafRestoreTempIdentity`.

**Severity:** Low-Medium. Nothing is lost, but an empty resource is left behind with no message, and the next run has to ask about it.

---

### An Interrupted `docker run --rm` Can Leave a Never-Started Container That Holds Its Volumes

**The problem:** `docker run` creates a container and then starts it. If the client is interrupted between the two (a Ctrl+C, a killed process, a closed window), the container stays in the `Created` state. `--rm` never removes it: it acts when a container exits, and this one never ran. The container keeps referencing its volumes, so `docker volume rm` of any of them fails with `volume is in use`, every time, for as long as Docker keeps running. A label-based reap misses it if it carries no label. It also gets a random name (`bold_clarke` in the field), so a `--filter name=` search misses it too.

```sh
# BAD: assume --rm cleaned up, or search by name
docker volume rm "${TEMP}"                   # volume is in use - [c9be7425...]
docker ps -a --filter "name=myrun"           # misses a randomly named holder

# GOOD: list every container that references the volume (stdout only), remove the
# stopped ones with a PLAIN rm (never -f: Docker refuses a running one), then the volume
docker ps -a --filter "volume=${TEMP}" --format '{{.ID}} {{.State}}'
docker rm <ID>                               # only for created / exited / dead
docker volume rm "${TEMP}"
```

**Field evidence (Windows, Docker 29.1.3, 2026-10-05; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/2026-10-05_restore_field_test_results.md`, section 5):**
- After a Ctrl+C during DAAF's restore swap, the next restore could not remove its leftover temp volume. `docker ps -a --filter volume=restoretest_daaf-data-restore-tmp --format '{{.ID}} | {{.Status}} | {{.Names}} | {{.Command}}'` printed `c9be7425c57c | Created | bold_clarke | "sh -c 'export LC_AL…"`. The same container was listed for the live volume.
- `docker volume rm restoretest_daaf-data-restore-tmp` printed `Error response from daemon: remove restoretest_daaf-data-restore-tmp: volume is in use - [c9be7425c57cdf9986582df00a33e2026ee81d442191780062ad3bbb49f30ec5]`.
- `docker rm c9be7425c57c`, then `docker volume rm`, removed both.
- Inference, consistent with the `docker events` log: the holder was the swap-check `docker run --rm`, and the Ctrl+C fell between its create and start. It was created in the second the swap container unmounted, it runs the only program that starts with `export LC_ALL=C` and mounts both volumes, and no mount event appeared for it, because volume mount events fire at start.

**Why it happens:**
- `Created` is a container state of its own: docker/cli's `container_ls.md` lists `created` among the seven states and defines it as "A container that has never been started."
- Plain `docker rm` refuses a running container (moby `daemon/delete.go`: `container is %s: stop the container before removing or force remove`) and a paused one (`container is paused and must be unpaused first`). It never removes a named volume either: docker/cli's `container_rm.md` says of `--volumes`, "Note that if a volume was specified with a name, it will not be removed".
- The `volume` filter matches a mount's volume name (for a bind mount, its source) or its destination path, exactly, and several `--filter volume=` values are OR'd (moby `daemon/list.go`). So a volume name, which never starts with `/`, cannot match a destination.
- These sources were fetched 2026-10-05 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/engineer18/web/` (`MANIFEST.jsonl`).
- A Docker restart is expected to remove such a container, but that is inference from source: no restart was done in the field test. In moby's `daemon/daemon.go` at tag `docker-v29.1.3`, `restore()` (lines 529-535) adds every container with `HostConfig.AutoRemove` (`--rm`) that is not alive, or every such container when live-restore is off, to `removeContainers`, and lines 644-658 remove those with `ForceRemove: true`. Fetched 2026-10-06 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/engineer23/web/2026-10-06T132542Z_raw-githubusercontent-com_untitled_bc81a3ad.bin` (raw `.go` source; `web_fetch.sh` wrote no extract for `text/plain`). An earlier version of this entry inferred the opposite from moby#46857; that PR is about live-restore and does not decide this case. A container created without `--rm` is not on that path.

**Fix:**
1. Before removing a scratch volume, list its holders from stdout only with `docker ps -a --filter volume=<name> --format '{{.ID}} {{.State}}'`. A stderr line is not an ID.
2. Remove each `created`, `exited` or `dead` holder with a plain `docker rm <ID>`. Treat any other state (`running`, `restarting`, `paused`, `removing`, or one you don't know) as "in use" and remove nothing. A list that fails means "could not check", never "no holders". Use a plain `rm` for a container you remove by name, too: after a wait (a user prompt, say), a name you found stopped may belong to a new container that another run started, and `rm -f` would kill it. A container that is already gone by then counts as removed: a plain `docker rm` of a missing container exits 1 with `No such container` (the docker CLI's `cli/command/container/rm.go` at v29.1.3 ignores not-found only for `-f`; read from source), so match that text, case-insensitive. Any other failure, such as a container that is still running or a removal already in progress (`removal of container ... is already in progress`, moby `daemon/delete.go`, read on master), should stop with nothing removed; running again a little later then works (inference). DAAF's restore does this for its leftover swap containers (fix round 8).
3. When several volumes must go, check all of their holders before removing anything, so a refusal leaves everything in place.
4. When the volume might belong to another run, remove no holder at all.
5. Tell the user the same three commands for a manual cleanup (observed to work in the field test). Prefer them to "restart Docker": they touch only the containers listed, and what a restart does here is inference from source (above) and covers only `--rm` containers.

**Where it lives in DAAF:** `_restore_remove_volume` / `Invoke-DaafRestoreVolumeRemoval` in `scripts/host/restore_from_backup.{sh,ps1}` (fix pass #18, D1). It is used by every temp removal; the careful cleanup skips its holder step. The leftover path uses it for its check pass and its removal pass, and removes a stopped leftover swap container with a plain `docker rm` as well (review round 6, R5). The printed hint is `_restore_remove_hint` / `Write-DaafRestoreRemoveHint`.

**Severity:** Medium. Nothing is lost, but every removal of the volume fails until the holder is removed (or, by inference from source, until Docker restarts).

---

### `docker run -v NAME:/path` Silently Re-Creates a Vanished Named Volume, Empty

**The problem:** Mounting a named volume that does not exist is not an error: Docker creates a new, empty volume under that name and the command succeeds. A script that created a scratch volume, checked it, and later mounts it again by name cannot tell from that mount whether it is still the same volume. If the volume was removed in between (another run of the same script, a user cleaning up in Docker Desktop), the next write that mounts it creates an empty one, and a check that compares two trees can then compare two empty ones and report a match.

```bash
# BAD: the identity check comes after a write that mounts the volume by name
docker run --rm -v "${TEMP}:/dest" busybox touch /dest/.marker   # re-creates ${TEMP} empty if it vanished
check_identity "${TEMP}"                                           # too late: Docker already made a new volume

# GOOD: check identity BEFORE any mount, again right before the destructive step,
# and make the destructive program refuse a source that lacks what this run put there
check_identity "${TEMP}" || exit 1          # e.g. this run's unique label is still on the volume
docker run --rm -v "${TEMP}:/dest" busybox touch /dest/.marker
check_identity "${TEMP}" || exit 1
docker run --rm -v "${TEMP}:/src:ro" -v "${LIVE}:/dest" busybox sh -c 'test -f /src/.marker || exit 3; ...'
```

**Why it happens:** Docker's volumes guide ([Volumes](https://docs.docker.com/engine/storage/volumes/), "Start a container with a volume", fetched 2026-10-01 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/web/2026-10-01T162728Z_docs-docker-com_volumes-docker-docs_ea5bbea4.md`, line 107): "If you start a container with a volume that doesn't yet exist, Docker creates the volume for you." A volume created this way does not carry the per-run label the script set on its own `docker volume create` (inference: nothing on the mount passes one), so that label survives only on the volume the script actually created.

**Field evidence:** review round 1 (2026-10-01) ran DAAF's `SWAP_VERIFY_PROGRAM` under dash on two empty trees and got `SWAP_VERIFY=MATCH` and `SWAP_VERIFY_ENTRIES=0:0`. The re-creation itself was not reproduced against a real Docker daemon; it rests on the documentation quote above. The busybox host probe's Step 8 read the label format back on a real host (Windows, Docker 29.1.3, 2026-10-05; probe doc "Field result"): `docker volume inspect --format '{{.Labels}}'` printed `map[org.daaf.restore-run:probe123 org.daaf.restore-tmp-for:daafprobe_x]`, which is Go's sorted `map[...]` form with no labels added by Docker Desktop, and `map[]` for an unlabelled volume. The identity check read it correctly (`IDENTITY probe123 True`, `IDENTITY probe999 False`).

**Fix:**
1. Give the scratch volume an identity that a re-created volume cannot have: a label whose value is unique to this run (`docker volume create --label org.daaf.restore-run=<token>`). Read it back with `docker volume inspect --format '{{.Labels}}'` (one argument with no space or quote, so Windows PowerShell 5.1 passes it unchanged).
2. Re-check the identity before the first write that mounts the volume after a wait, and again right before each destructive step. Refuse and remove nothing when it fails: the volume under that name may belong to another run.
3. Make the destructive program itself refuse a source that lacks a marker this run wrote (`test -f /src/<marker> || exit 3; ...`), as a second layer for a volume that vanishes between the last check and the program. Give that refusal an exit code that nothing else in the program uses, so the caller can report "nothing was replaced" instead of "the data may be incomplete" (with `test -f ... && rm ...` the refusal exits 1, like a failed `rm` or `cp`). Keep the code out of 125-127, which `docker run` uses for its own failures ([Running containers](https://docs.docker.com/engine/containers/run/), "Exit status", fetched 2026-10-01 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/web/2026-10-01T194739Z_docs-docker-com_running-containers-docker-docs_91e3e7fa.md`, lines 168-191: "Exit code 125 indicates that the error is with Docker daemon itself"). Do not read a 125 as "nothing ran", not even when the named `--rm` container is gone afterwards: an engine that stops or restarts while the program runs can make `docker run` exit 125 after the program had already started, and the engine removes a `--rm` container that exited meanwhile, so "exit 125, container gone" can follow an erase that already happened. This rests on upstream PR discussion, not on a DAAF reproduction: in [moby#34999](https://github.com/moby/moby/pull/34999) (fetched 2026-10-01 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scratch/review3q/web/2026-10-01T205329Z_github-com_containerwait-on-remove-don-39-t-stuck-on-rm-fail-by-kolyshk_d0f5614f.md`, line 67) the author stopped a daemon "while having a few docker run processes stuck in wait" and docker-cli 17.06 printed `error waiting for container: EOF` and exited 125; [moby#46857](https://github.com/moby/moby/pull/46857) (fetched 2026-10-01 to `.../scratch/review3q/web/2026-10-01T205539Z_github-com_liverestore-don-39-t-remove-rm-containers-on-restart-by-vvol_b7fa1494.md`, lines 39-42) stops live-restore from killing `--rm` containers on an engine restart, and says they "still should be removed if they exited while the engine was down". Only the program's own refusal code means nothing was replaced; treat every other nonzero exit, 125 included, as "may have stopped partway" and keep the source copy.
4. Never accept a comparison of two empty trees as proof: require equal, nonzero entry counts where the data cannot legitimately be empty.

**Where it lives in DAAF:** `scripts/host/restore_from_backup.{sh,ps1}`: `_restore_temp_is_ours` / `Test-DaafRestoreTempIdentity` (checked after the create, before the state-marker write, and before each swap), the `test -f /src/.daaf-restore-swap-started || exit 3;` guard in `SWAP_PROGRAM` / `$SwapProgram` with its host-side reading `_restore_fail_swap_not_run` / the `$swapExit -eq 3` branch (only 3 means nothing was replaced; any other nonzero exit, 125 included, keeps the checked copy and takes the after-swap path, review round 3, I-1), and `_restore_swap_checked` / `Test-DaafRestoreSwapChecked` (MATCH plus `SWAP_VERIFY_ENTRIES=n:n`, n > 0 for the data volume).

**Severity:** High. A volume removed while a script waited comes back empty, and an empty-versus-empty comparison passes.

---

### `df` Inside a Docker Desktop Container Reports the VM's Virtual Disk, Not the Computer's Drive

**The problem:** A free-space check run inside a container (`df`, `stat -f`) measures the filesystem that holds Docker's data. On Docker Desktop that is a virtual disk with a fixed maximum size: a WSL2 `.vhdx` on Windows, a disk image on macOS, and most likely a disk image with Docker Desktop for Linux too (see "Other platforms" below). It is not the host drive. The check can pass with hundreds of GB "available" while the computer's drive is nearly full. The virtual disk file then can't grow, and writes fail partway.

```sh
# BAD: treat the in-container figure as the user's free disk space
avail_kb=$(df -Pk /dest | tail -n 1 | awk '{print $4}')   # also: the pipeline hides a df failure

# GOOD: measure Docker's own limit without a pipeline, and say what it is NOT
a=$(stat -f -c %a /dest) && s=$(stat -f -c %S /dest) && echo AVAIL_KB=$((a*s/1024))
# ...then tell the user the host drive needs that room too (the script cannot see it)
```

**Field evidence (observed in this dev container, WSL2 kernel `6.6.87.2-microsoft-standard-WSL2`, `/daaf` a named volume, 2026-10-01):** `df -Pk /daaf` printed `/dev/sde 1055762868 173717588 828341808 18% /daaf` (orchestrator run), and `/dev/sde 1055762868 175276104 826783292 18% /daaf` on a re-run. 1,055,762,868 KB is about 1007 GiB, the WSL2 default 1 TB virtual size, whatever the host drive holds. Microsoft documents the effect ([How to manage WSL disk space](https://learn.microsoft.com/en-us/windows/wsl/disk-space), read 2026-10-01): "The amount of disk space allocated to your VHD by WSL will always show the default maximum amount (1TB in the most recent version of WSL), even if the amount of disk space on your actual Windows device is less than that", and `df`'s "Avail: Amount of space left in the VHD".

**Other platforms (inference, not observed):**
- macOS and Hyper-V Docker Desktop have a configurable "Disk usage limit", and the Mac FAQ notes that "many tools report the maximum file size, not the actual file size", so in-container `df` there most likely reports the image's limit too.
- Docker Desktop for Linux runs a VM as well. Its FAQ says it "stores Linux containers and images in a single, large "disk image" file in the Linux filesystem. This is different from Docker on Linux, which usually stores containers and images in the /var/lib/docker directory on the host's filesystem." ([FAQs for Docker Desktop for Linux](https://docs.docker.com/desktop/troubleshoot-and-support/faqs/linuxfaqs/), fetched 2026-10-01 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/web/2026-10-01T194729Z_docs-docker-com_faqs-for-docker-desktop-for-linux-docker-docs_2a32f60e.md`, line 26.) That volumes live in the same image, and that in-container `df` there reports the image's limit, is inference.
- On Linux Docker Engine, a named volume is a host directory (`/var/lib/docker/volumes/<name>/_data`), so the in-container figure is the host filesystem's.

**Fix:**
1. Treat the in-container figure as Docker's limit only. Make the user-facing message say the computer's drive needs the room too: DAAF's restore messages say "inside Docker", and the docs add the host-drive caveat.
2. Do not try to locate the disk image from a host script unless you accept a heuristic. Docker documents only the default WSL2 data location (`%LOCALAPPDATA%\Docker\wsl`, movable in Settings), and the settings keys that hold a moved location are undocumented (community sources only). DAAF's restore checks inside Docker only (user decision D5, 2026-10-01).
3. Prefer `stat -f -c %a` / `%S` (free blocks for unprivileged users times block size) over `df | tail`, so a failure propagates. If you use `df`, pass `-P`: busybox `df` wraps the line for a device name longer than 20 characters without it (busybox `coreutils/df.c`, from source).
4. Size the margin for real overhead. Apparent sizes undercount allocated blocks (about 1.4% observed on the DAAF volume), so DAAF requires max(10% of the size, 1,048,576 KB) on top of the peak need max(B, 2B - L). Its messages print KB / 1,048,576 labelled "GB" (a binary gigabyte), and the user docs say "about 1 GB".
5. Expect the host-side file to stay large. Space freed inside the virtual disk is most likely not returned to the computer's drive until the image is compacted (inference from the Mac FAQ and WSL docs, not observed).

**Where it lives in DAAF:** `SPACE_PROGRAM` / `$SpaceProgram` in `scripts/host/restore_from_backup.{sh,ps1}`, plus the user-facing caveat in `user_reference/07_faq_technical.md` and `01_installation_and_quickstart.md`.

**Severity:** Medium. A space check that passes and then runs out. DAAF's restore most likely runs out while preparing the temporary copy (nothing replaced); if the swap itself runs out, the checked copy is kept and the restore can be re-run.

---

### Upstream Images Re-Push and Retag: a Tag Is Not the Image You Tested

**The problem:** `docker run busybox` means `busybox:latest`, and a tag is a pointer the publisher can move at any time. Even a version tag such as `busybox:1.37.0` can be rebuilt and re-pushed under the same name. A script that names an image by tag runs whatever the computer has cached, or whatever the registry serves on the day of a fresh pull. Two computers, or one computer before and after `docker image prune`, can run different programs, and "field-tested" stops meaning anything.

```bash
# BAD: whatever `latest` (or a re-pushed version tag) points to today
docker run --rm -v "${VOL}:/source:ro" busybox sh -c '...'

# GOOD: one pinned reference, defined once per script, digest included
BUSYBOX_IMAGE='busybox:1.37.0@sha256:bdf57e528e45e4433820e045b29b4597825a1c9e38353532d90a01445013f82e'
docker run --rm -v "${VOL}:/source:ro" "${BUSYBOX_IMAGE}" sh -c '...'
```

With `name:tag@sha256:...`, Docker uses the digest and the tag is only a label for readers (inference from Docker's reference format; the combined form was not exercised against a real daemon in pass #26, see Fix item 4).

**Field evidence (Docker Hub API, fetched 2026-10-06; compatibility audit 04, `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/scoping/04_F1_compat_audit.md`, section 0; JSON under `.../web/compat/`):**
- `latest`, `1`, `1.38` and `1.38.0` all pointed to index `sha256:fd7dc98638c8…`, pushed `2026-09-23T07:57`-`07:58`. busybox.net lists that release as "13 May 2026 -- BusyBox 1.38.0 (unstable)", and its changelog touches areas DAAF's restore relies on (ash signal handling, `cp`, `cmp`).
- `1.37.0` and `1.37` pointed to index `sha256:bdf57e528e45…` (`application/vnd.oci.image.index.v1+json`), also pushed 2026-09-23 (`tag_last_pushed` `2026-09-23T07:57:44`). So the version tag itself was re-pushed.
- Every DAAF field test ran busybox 1.37.0 under digest `1487d0af…`. A search of all 219 tags, matching index and per-architecture digests, found it on none (`1487d0af hits: []`). That it was an earlier push of `1.37.0`/`latest` is inference: Docker Hub keeps only current digests.
- Consequence: from 2026-09-23 a fresh install that pulled `busybox` got the untested 1.38.0, and even `busybox:1.37.0` was a different artifact from the field-tested one.

**Fix:**
1. Pin by digest: `name:tag@sha256:<index digest>`. Use the multi-architecture index digest (the one the tag points to), not one platform's, so the same string works on amd64 and Apple silicon (`bdf57e52…` lists amd64, arm64/v8 and others).
2. Keep **one** source of truth: a single constant per script (`BUSYBOX_IMAGE` / `$BusyboxImage`), with every `docker run`/`create` going through it, and the same literal in any compose file (`docker-compose.yml`'s `daaf-init` `image:`). Otherwise compose keeps pulling the moving tag into the same image cache the scripts read.
3. Guard the copies with a parity test that extracts every occurrence and asserts exactly one distinct value. Also re-check source-text tests: pins keyed on the bare token (`busybox sh -c`, `'busybox',`) stop matching once calls go through the constant (pass #26 broke 12 bats pins and about 15 Pester pins this way, across the restore, backup and migrate suites).
4. When the pinned image may be missing, check for it before anything changes, and pull it with visible progress (see "The Docker 29 API floor" for the startup check that runs just before). Confirm once on a real host that `docker image inspect <name:tag@digest>` exits 0 after a pull: if it ever failed for an image that is present, every run would pull again and an offline computer would be refused (pass #26 WARNING, inference).
5. A digest pin freezes security fixes too. Re-pin on purpose, re-run the field probes on the new digest, and note the date.

**Where it lives in DAAF:** `BUSYBOX_IMAGE` in `scripts/host/backup_daaf.sh` and `restore_from_backup.sh`, `$BusyboxImage` in their `.ps1` twins, the same constant in `migrate_daaf.{sh,ps1}`, and `daaf-init`'s `image:` in `docker-compose.yml` (follow-up pass #26). The backup and restore scripts check for the image after their Docker version check and before anything is created, and download it when missing (`Downloading the small helper image busybox that the restore needs...`).

**Severity:** High. A silent change of the program that erases and copies the user's data, between a test and a user's run.

---

### The Docker 29 API Floor: a 29.x Client Cannot Talk to an Engine Older Than 25.0

**The problem:** Docker 29 removed support for Engine API versions below 1.44 (Docker 25.0). A Docker 29.x CLI cannot drive an Engine older than 25.0, and a 29.0-29.2 Engine refuses a client older than 25.0. This bites mismatched pairs: a Homebrew `docker` CLI with an older Colima, Rancher Desktop or distro engine, or an old Docker Desktop with a newer CLI on the `PATH`. The symptom can be misleading. In DAAF the first Docker call is `docker info`, so such a pair most likely fails there and the user sees `ERROR: Docker Desktop does not seem to be running. Please start it and try again.`, never reaching the version check (inference from the code path, noted by the pass #26 engineer; not reproduced against a real mismatched pair). Fix item 4 below adds a hint to that message.

```bash
# GOOD: after `docker info` succeeds, read both versions from stdout only and gate on the majors
docker version --format '{{.Client.Version}} {{.Server.Version}}' 2>/dev/null
# 29.1.3 29.1.3   -> continue
# 24.0.7 29.1.3   -> refuse: older than 25.0 on one side
# 30.0.0 30.0.0   -> NOTE: not tested with this version; continue
```

**Why it happens (Docker Engine 29 release notes, fetched 2026-10-06 to `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/web/compat/2026-10-06T152953Z_docs-docker-com_docker-engine-version-29-release-notes-docker-docs_1be52d7c.md`):**
- 29.0.0, line 540: "The daemon now requires API version v1.44 or later (Docker v25.0+)."
- 29.0.0, line 724: "client: remove support for negotiating API version < v1.44 (docker 25.0)."; line 727: "daemon: raise minimum API version to v1.44."; line 849: "Remove API version compatibility for API version < v1.44 (Docker v24.0 and older)."
- 29.3.0, line 372: "Lower minimum API version from v1.44 to v1.40 (Docker 19.03)." That relaxes only the daemon side: a 29.3+ Engine accepts older clients again, but the 29.x client still cannot negotiate below 1.44.
- Docker Desktop 4.27.0 shipped Engine 25.0.0; DAAF names 4.27.1 (Engine 25.0.2, which also carries the CVE-2024-24557 fix) as the minimum. 4.27.1's upgrade line reads "Docker Engine v25.0.2 which contains a fix for CVE-2024-24557, ..." (Docker Desktop release notes, `.../web/compat/2026-10-06T153137Z_docs-docker-com_docker-desktop-release-notes-docker-docs_46c5da5e.md`, line 2185). 4.27.0's "Docker Engine v25.0.0" appears only in the raw HTML (`..._46c5da5e.html`, the `Docker Engine v25.0.0</a>` link under the 4.27.0 Upgrades list); the Markdown extract dropped that list. Per audit 04, 4.26.x shipped 24.0.7.

**Fix:**
1. Run one `docker version --format '{{.Client.Version}} {{.Server.Version}}'` right after the `docker info` check, stdout only, last non-empty line. The `--format` value has no `"`, so Windows PowerShell 5.1 passes it unchanged (observed in the busybox host probe's Step 0, which printed `29.1.3 29.1.3`).
2. Refuse, with nothing changed, when either major is below 25 or does not parse. DAAF requires 25 on **both** sides even though a 29.3+ Engine would accept an older client: one rule is simpler to explain, and it covers older features too (`{{.State}}` in `docker ps` since 20.10, `AutoRemove` since API 1.25).
3. For a major other than the tested one, print a NOTE and continue. Never block newer versions on a guess.
4. Add a hint in the `docker info` failure branch, so a mismatched pair is not reported only as "not running": read the same `docker version --format` line there, and when the client's major parses as 25 or newer while the Engine's version is empty or does not parse, say the Engine may be older than 25.0 and give the minimum. Start the hint with "If Docker is running", because Docker that is simply stopped gives the same reading. Keep the original message and exit code.

**Where it lives in DAAF:** the `Docker version check` block in `scripts/host/backup_daaf.{sh,ps1}` and `restore_from_backup.{sh,ps1}`, identical wording with the script name varied: `ERROR: This Docker version is too old for the restore (...)`, `ERROR: Could not read the Docker version (...)`, `The restore needs Docker 25.0 or newer, for both the Docker client and Docker Engine` / `(Docker Desktop 4.27.1 or newer). Update Docker, then run the restore again.` / `(Docker Desktop or Docker Engine is required; Podman is not supported.)`, and the `NOTE: The restore has not been tested with this Docker version (...; tested: 29). Continuing.` line (follow-up pass #26; the Podman line from review fix round 9). The old-Engine hint (fix item 4) sits in the `docker info` failure branch just above: `If Docker is running, its Docker Engine may be older than 25.0 (Docker client <c>).` / `The restore needs Docker 25.0 or newer (Docker Desktop 4.27.1 or newer).` (review fix round 9; tested with stand-in docker output only, not against a real mismatched pair).

**Severity:** Medium. Nothing is damaged (every call fails), but without the check the error is opaque, and with a mismatched pair it can look like Docker is not running at all.

---

## Testing Gotchas

### A New Startup Docker Call Makes Every Silent Docker Mock Fail Closed

**The problem:** Test suites stub `docker` with a `case` whose default arm succeeds with nothing on stdout (`*) return 0` in bash; in PowerShell a `switch` `default` arm that only returns, or only writes to the host). That is fine for calls whose result is the exit code. A new startup call whose result is its **stdout** (here `docker version --format ...`, which must print two versions) gets the empty default, and a fail-closed script correctly refuses: every end-to-end test then stops at the new check, long before the behavior it tests.

```bash
# BAD: each test file grows its own inline docker() with a silent default, none knows `version`
docker() { case "$1" in info) return 0 ;; *) return 0 ;; esac; }

# GOOD: one shared arm in the shared mock (and in every inline mock that cannot use it)
docker() {
    case "$*" in
        "version --format"*) echo "29.1.3 29.1.3"; return 0 ;;
        ...
        *) return 0 ;;
    esac
}
```

**Field evidence (follow-up pass #26, 2026-10-06; `research/2026-10-01_FrameworkDev_RestoreCopyThenSwap/engineer_reports/26_engineer26_COMPLETED.md`):** after the version and image checks were added, the bats run printed `1..391` with 198 ok and 193 not ok. 181 of the failures were this cause (178 matched on `ERROR: Could not read the Docker version`; 3 inferred). The Pester restore suite had 180 failures, first at the PowerShell edition guard and, with the test-only bypass set, at the version check. The scripts were correct; only the mocks lacked the arm. `backup_daaf.bats` alone has 24 inline `docker()` mocks (`grep -c -E '^\s*docker\(\)'` printed `24` on 2026-10-06).

**Fix:**
1. When a script gains a startup docker call, add its arm to the shared mock (`mock_docker` in `tests/bash/test_helper.bash`) in the same change, and to every inline mock that shadows it. Grep the test tree for `docker()` and for PowerShell `function docker` before calling the script change done.
2. The script's own `DAAF_DRY_RUN` mock needs the arm too (pass #26 added `"version --format"*` and `"image inspect "*` arms there), or the CI dry-run smoke fails the same way.
3. Prefer shared mocks to inline ones: one place to update.
4. Expect a matching edit for each new guard that is not a docker call. Pass #26's PowerShell edition guard needed a test-only environment variable (`DAAF_TEST_ALLOW_CORE_NONWINDOWS=1`) in the Pester harnesses that run the real script under pwsh on Linux.

**Severity:** Medium (test-suite only). It hides nothing, because the run fails loudly, but a large red run invites wholesale "fixes" that could mask a real regression. Classify failures by cause before changing tests.

---

## Quick Lookup

| Gotcha | Language | Severity | ShellCheck/Analyzer |
|--------|----------|----------|---------------------|
| `local var=$(cmd)` masks exit | Bash | High | SC2155 |
| `set -e` in assignments | Bash | Medium | — |
| `2>/dev/null` on probes | Bash | Medium | — |
| `cd` without `\|\| exit` | Bash | Medium | SC2164 |
| Backtick nesting | Bash | Low | SC2006 |
| `x="$(fn 2>&1 > /dev/null)"` waits for a subshell `fn` left in the background (exec the sleeper) | Bash | Medium | — |
| `exit` in dot-sourced functions | PowerShell | High | — |
| Ctrl+C inside `try`/`finally`: the `finally` runs, then exit 0 | PowerShell | Medium | — |
| `$?` for native commands | PowerShell | High | — |
| Expression context breaks TTY | PowerShell | High | — |
| `$ErrorActionPreference` scope | PowerShell | High | — |
| PS 5.1 drops native stderr under `SilentlyContinue`, even with `2>&1` (text shown to the user: bracket with `Continue`; emptiness or ID check: `2>$null`, not `Continue`; 7.2+ no longer applies the preference to redirected native stderr; guard: `native_stderr_capture.Tests.ps1`) | PowerShell | Medium | — |
| `$PSNativeCommandUseErrorActionPreference` (7.4+) adds an error line or throws on a native nonzero exit (set it to `$false`) | PowerShell | Low-Medium | — |
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
| Forwarded Ctrl+C stops a container's `sh -c` between commands (`--sig-proxy=false` + `trap : INT TERM HUP`) | Cross-platform | High | — |
| `docker volume create` reuses an existing name; `volume ls --filter name=` is an unanchored regex | Cross-platform | High | — |
| A "created" flag set after the create misses a Ctrl+C during it (record the attempt first; adopt only with a per-run label) | Cross-platform | Low-Medium | — |
| Interrupted `docker run --rm` leaves a never-started (Created) container holding its volumes (`docker ps -a --filter volume=` + plain `docker rm`) | Cross-platform | Medium | — |
| `docker run -v NAME:/path` silently re-creates a vanished named volume, empty (check identity before any mount) | Cross-platform | High | — |
| In-container `df` on Docker Desktop reports the VM's virtual disk, not the host drive | Cross-platform | Medium | — |
| Upstream images re-push and retag: pin by digest (`name:tag@sha256:...`), one constant per script plus compose, parity test | Cross-platform | High | — |
| Docker 29 API floor: a 29.x client cannot talk to an Engine below 25.0 (startup `docker version` check; can look like "not running") | Cross-platform | Medium | — |
| A new startup docker call fails every mock whose default arm prints nothing (add a shared mock arm) | Testing | Medium | — |
