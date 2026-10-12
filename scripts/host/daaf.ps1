# ============================================================================
# DAAF Control Panel (Windows PowerShell)
# ============================================================================
# Interactive menu wrapper for all DAAF operations. Presents a status
# dashboard and numbered options for launching services, managing backups,
# and performing maintenance.
#
# Usage:
#   cd daaf-docker
#   .\daaf.ps1
#
# This is the top-level entry point on Windows -- it runs a persistent menu
# loop and delegates to individual .ps1 scripts via DAAF_NESTED=1 to suppress
# their pause-on-exit prompts. It is the PowerShell counterpart to daaf.sh
# (macOS/Linux) and mirrors its menu, dashboard, and behavior.
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"
# pwsh 7.4+ only (an ordinary, unused variable on Windows PowerShell 5.1): never turn a
# native command's nonzero exit into an error record or a throw. The native calls here
# read $LASTEXITCODE themselves (same line as backup_daaf.ps1 and restore_from_backup.ps1;
# audit 04: under 'Stop' with this set to $true, pwsh 7.6 threw NativeCommandExitException).
# daaf_lib.ps1, dot-sourced below, runs in this script's scope and so inherits it.
$PSNativeCommandUseErrorActionPreference = $false

# --- Source shared library ---
# Resolve this script's directory from MyInvocation so the library resolves
# whether the panel is executed directly or dot-sourced by Pester (where
# $PSCommandPath may point at the test runner).
$DaafScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $DaafScriptDir "daaf_lib.ps1")

# --- Multi-instance settings ---
# Bridge environment_settings.txt's DAAF_* keys into the process environment so
# `docker compose` interpolation resolves the project name and published host
# ports. See Import-DaafSettingsFile in daaf_lib.ps1 for the full rationale.
# An existing but unreadable file makes the loader throw. This runs before the
# main loop's try/catch, so say what to fix (the same two lines daaf.sh prints)
# instead of ending on a raw exception. The pause follows the main loop catch's
# rule: not nested, not a dry run, and only in an interactive console.
try {
    Import-DaafSettingsFile
} catch {
    Write-Host "ERROR: Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it." -ForegroundColor Red
    Write-Host "Fix that (or move the file aside), then start the DAAF Control Panel again."
    try { $startupPauseOk = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) }
    catch { $startupPauseOk = $false }
    if ((-not $env:DAAF_NESTED) -and ($env:DAAF_DRY_RUN -ne "1") -and $startupPauseOk) {
        $null = Read-DaafLine "Press Enter to close"
    }
    exit 1
}

# Host-facing ports for browser URLs and status display (default to the fixed
# container ports so existing single-instance installs behave identically).
# A function so the Restart Container handler can recompute them after reloading
# environment_settings.txt; it assigns $script: variables so a call from inside a
# handler updates the values the menu and URL builders read. (Like daaf.sh's
# PANEL_PORT_* values from set_panel_ports, these are separate variables from the
# $env:DAAF_PORT_* values the loader fills, so a display default can never mask a
# reloaded file value -- no defaults record needed.)
function Initialize-DaafPortDisplay {
    $script:DaafPortMarimo = if ($env:DAAF_PORT_MARIMO) { $env:DAAF_PORT_MARIMO } else { "2718" }
    $script:DaafPortLogViewer = if ($env:DAAF_PORT_LOGVIEWER) { $env:DAAF_PORT_LOGVIEWER } else { "2719" }
    $script:DaafPortVscode = if ($env:DAAF_PORT_VSCODE) { $env:DAAF_PORT_VSCODE } else { "2720" }
}
Initialize-DaafPortDisplay

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate Docker for CI cross-platform smoke testing
# without a Docker daemon. Mirrors daaf.sh's docker() dry-run shim: the status
# probes return empty (no services listening), git metadata returns canned
# values, and every other invocation is a no-op that echoes a [DRY-RUN] marker.
#
# NOTE: the port-status probes (Get-DaafPortStatus, Test-DaafPort) short-circuit
# to DAAF_MOCK_PORTS in their OWN dry-run branches before ever reaching docker,
# so this shim never has to interpret their payloads. Under real (non-dry-run)
# operation those probes use the base64-as-argument transport (v3): the b64
# token and the `echo $1 | base64 -d | bash ...` remote wrapper show up in $args,
# but that is irrelevant here because the dry-run branch returns first. Any other
# `docker compose exec` payload that does reach this shim (e.g. the stop-services
# base64 call) falls through the generic `*compose exec*` arm as a no-op, which
# is the intended dry-run behavior.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*compose ps -q daaf-docker*" { Write-Output "abc123" }
            "*compose ps --status running*--format*" { Write-Output "daaf-docker" }
            "*compose exec*git*describe*" { Write-Output "v2.0.0" }
            "*compose exec*git*log*" { Write-Output "2026-06-21" }
            "*compose exec*git*branch*" { Write-Output "main" }
            "*compose exec*git*rev-list*" { Write-Output "0" }
            "*compose exec -d*" { return }
            "*compose exec*" { return }
            default { Write-Host "[DRY-RUN] docker $argStr"; return }
        }
    }
}

# --- Preflight ---
# Skipped under DAAF_TEST_MODE so the Pester harness can dot-source this file
# (to load the function definitions further below) without a real Docker daemon.
if ($env:DAAF_TEST_MODE -ne "1") {
    if (-not (Test-Path "docker-compose.yml")) {
        Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
        Write-Host "Please run this script from your daaf-docker folder."
        if (-not $env:DAAF_NESTED) { $null = Read-DaafLine "Press Enter to close" }
        exit 1
    }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from PowerShell." -ForegroundColor Red
        Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
        if (-not $env:DAAF_NESTED) { $null = Read-DaafLine "Press Enter to close" }
        exit 1
    }

    $savedEAP = $ErrorActionPreference
    try { $ErrorActionPreference = "SilentlyContinue"; $null = docker info 2>&1 } finally { $ErrorActionPreference = $savedEAP }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker Desktop does not seem to be running. Please start it and try again." -ForegroundColor Red
        if (-not $env:DAAF_NESTED) { $null = Read-DaafLine "Press Enter to close" }
        exit 1
    }
}

# ============================================================================
# Status Gathering
# ============================================================================

# Populates the script-scoped STATUS_* variables the menu reads. Mirrors
# daaf.sh gather_status: checks container state first, then (if running)
# gathers version/date/branch/updates and probes ports 2718/2719/2720; finally
# finds the most recent local *_daaf_backup folder.
function Get-DaafStatus {
    # Container running? `docker compose ps -q daaf-docker` prints the running
    # container's ID (empty when stopped), derived from the compose project
    # rather than matching a hardcoded container name.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $cidRaw = docker compose ps -q daaf-docker 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    $running = -not [string]::IsNullOrWhiteSpace(($cidRaw | Out-String))

    if (-not $running) {
        $script:STATUS_CONTAINER = "Stopped"
        $script:STATUS_VERSION = "--"
        $script:STATUS_DATE = ""
        $script:STATUS_BRANCH = "--"
        $script:STATUS_UPDATES = ""
        $script:STATUS_PORT_2718 = $false
        $script:STATUS_PORT_2719 = $false
        $script:STATUS_PORT_2720 = $false
    } else {
        $script:STATUS_CONTAINER = "Running"

        # Container-side git metadata. PowerShell has no cheap parallel-exec
        # idiom that is PS-5.1-safe, so these run sequentially (a handful of
        # fast exec calls). Each strips carriage returns and falls back to a
        # sensible default, matching daaf.sh's `|| echo` fallbacks.
        $script:STATUS_VERSION = (Invoke-DaafGit "describe" "--tags" "--always")
        if (-not $script:STATUS_VERSION) { $script:STATUS_VERSION = "unknown" }
        $script:STATUS_DATE    = (Invoke-DaafGit "log" "-1" "--format=%cd" "--date=short")
        $script:STATUS_BRANCH  = (Invoke-DaafGit "branch" "--show-current")
        if (-not $script:STATUS_BRANCH) { $script:STATUS_BRANCH = "detached" }
        $script:STATUS_UPDATES = (Invoke-DaafGit "rev-list" "--count" "HEAD..origin/main")

        # Port probes: ONE batched exec for all three ports instead of three
        # separate Test-DaafPort execs. On Windows Docker Desktop each
        # `docker compose exec` costs ~0.5-2s, so three per menu redraw made the
        # dashboard visibly slow. This mirrors daaf.sh gather_status's single
        # ports_probe: the container-side payload loops over 2718/2719/2720 and
        # emits one "PORT:<n>" line per LISTENing port, which we parse per port.
        # Test-DaafPort is retained for single-port readiness polls elsewhere.
        $portStatus = Get-DaafPortStatus
        $script:STATUS_PORT_2718 = $portStatus["2718"]
        $script:STATUS_PORT_2719 = $portStatus["2719"]
        $script:STATUS_PORT_2720 = $portStatus["2720"]
    }

    # Local backup check (no Docker needed). Timestamp-prefixed names sort
    # lexicographically, so the last match is the newest backup. Mirrors
    # daaf.sh's glob-array last-element lookup (the very line that was fatal
    # under Bash 3.2 -- PowerShell has no such subscript hazard).
    $backupDirs = @(Get-ChildItem -Path "." -Directory -Filter "*_daaf_backup" -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($backupDirs.Count -gt 0) {
        $lastBackup = $backupDirs[$backupDirs.Count - 1].Name
        $script:STATUS_LAST_BACKUP = ($lastBackup -replace "_daaf_backup", "")
    } else {
        $script:STATUS_LAST_BACKUP = ""
    }
}

# Probe all three service ports (2718/2719/2720) in ONE container exec and
# return a hashtable of "<port>" -> $true/$false. Batches what used to be three
# separate Test-DaafPort execs (each ~0.5-2s on Windows Docker Desktop) into a
# single call to keep the menu redraw responsive.
#
# The container-side payload is mirrored VERBATIM from daaf.sh gather_status's
# ports_probe: it loops the three ports and echoes "PORT:<n>" for each LISTENing
# one (column 2 = HEXIP:HEXPORT, column 4 = 0A = LISTEN, matched on the
# uppercase 4-hex-digit port). We parse the emitted lines back into booleans.
#
# TRANSPORT v3 -- base64-as-argument (do NOT revert): the payload is base64-
# encoded and the TOKEN is passed as a native argument; the container decodes it
# and runs it, and we capture its "PORT:<n>" stdout lines. This payload takes no
# positional args (the three ports are hardcoded), so the remote wrapper is the
# arg-less `echo $1 | base64 -d | bash`. Two earlier transports both failed on
# real Windows: v1 `bash -c <payload>` mangled the awk `"` patterns (PS 5.1
# native-arg quoting bug, fixed only in 7.3+); v2 `<payload> | bash -s` (stdin)
# left a stray CR on the last line (PS appends CRLF piping to a native process)
# and the PS-pipeline -> docker.exe npipe stdin wiring is unreliable. See the
# fully annotated Test-DaafPort transport note in daaf_lib.ps1.
function Get-DaafPortStatus {
    $result = @{ "2718" = $false; "2719" = $false; "2720" = $false }

    # In dry-run mode, consult DAAF_MOCK_PORTS directly (parity with
    # Test-DaafPort's dry-run branch and daaf.sh's check_port mock) rather than
    # routing through the docker shim -- the payload is on stdin and so is
    # invisible to a $args-matching shim.
    if ($env:DAAF_DRY_RUN -eq "1") {
        foreach ($p in @("2718", "2719", "2720")) {
            if ($env:DAAF_MOCK_PORTS -and ($env:DAAF_MOCK_PORTS -like "*${p}:yes*")) {
                $result[$p] = $true
            }
        }
        return $result
    }

    $portsProbe = @'
        for p in 2718 2719 2720; do
            ph=$(printf "%04X" "$p")
            if awk -v ph="$ph" '$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}' \
                /proc/net/tcp /proc/net/tcp6 2>/dev/null; then
                echo "PORT:$p"
            fi
        done
'@

    # Encode the payload and pass the b64 token as a native arg. The single-
    # quoted PS literal 'echo $1 | base64 -d | bash' has spaces but ZERO double
    # quotes, so PS 5.1 wraps it in "..." on the CommandLine intact; $1 stays
    # literal and is the container bash's positional param (`_` is $0, the token
    # is $1). `echo $1` is unquoted deliberately (base64 alphabet has no
    # whitespace/glob chars) -- quoting it would reintroduce double quotes and
    # revert to the v1 failure. We capture stdout (the PORT:<n> lines) here, not
    # Out-Null, so the per-port parse below is preserved.
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($portsProbe))
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $probeRaw = (docker compose exec -T daaf-docker bash -c 'echo $1 | base64 -d | bash' _ $b64 2>$null)
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    $probeOut = ($probeRaw | Out-String) -replace "`r", ""

    if ($probeOut -match "PORT:2718") { $result["2718"] = $true }
    if ($probeOut -match "PORT:2719") { $result["2719"] = $true }
    if ($probeOut -match "PORT:2720") { $result["2720"] = $true }

    return $result
}

# Run `docker compose exec ... git -C /daaf <args>` and return trimmed,
# CR-stripped stdout (empty string on failure). Uses SilentlyContinue so PS 5.1
# does not promote Docker/git stderr to a terminating error under EAP = Stop.
function Invoke-DaafGit {
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $raw = @(docker compose exec -T daaf-docker git -C /daaf @args 2>$null)
        $result = ($raw | Out-String)
        return ($result -replace "`r", "").Trim()
    } finally {
        $ErrorActionPreference = $savedEAP
    }
}

# ============================================================================
# Menu Display
# ============================================================================

function Show-DaafMenu {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  DAAF Control Panel"
    Write-Host "=========================================="
    Write-Host ""

    # --- Status dashboard ---
    if ($script:STATUS_CONTAINER -eq "Running") {
        Write-Host "  Container:  " -NoNewline; Write-Host "* Running" -ForegroundColor Green
    } else {
        Write-Host "  Container:  " -NoNewline; Write-Host "o Stopped" -ForegroundColor DarkGray
    }

    # Version line
    $versionLine = "  Version:    $($script:STATUS_VERSION)"
    if ($script:STATUS_DATE) {
        $versionLine = "$versionLine ($($script:STATUS_DATE))"
    }
    Write-Host $versionLine

    # Branch line
    $branchLine = "  Branch:     $($script:STATUS_BRANCH)"
    if ($script:STATUS_UPDATES -and $script:STATUS_UPDATES -ne "0") {
        $branchLine = "$branchLine ($($script:STATUS_UPDATES) updates available)"
    } elseif ($script:STATUS_UPDATES) {
        $branchLine = "$branchLine (up to date)"
    }
    Write-Host $branchLine

    # Last backup
    if ($script:STATUS_LAST_BACKUP) {
        Write-Host "  Last backup: $($script:STATUS_LAST_BACKUP)"
    } else {
        Write-Host "  Last backup: never"
    }

    Write-Host ""

    # --- Services ---
    Write-Host "  Services:"
    if ($script:STATUS_PORT_2718) {
        Write-Host "    " -NoNewline; Write-Host "* Notebooks    localhost:$DaafPortMarimo" -ForegroundColor Green
    } else {
        Write-Host "    o Notebooks    (not running)" -ForegroundColor DarkGray
    }
    if ($script:STATUS_PORT_2719) {
        Write-Host "    " -NoNewline; Write-Host "* Log Viewer   localhost:$DaafPortLogViewer" -ForegroundColor Green
    } else {
        Write-Host "    o Log Viewer   (not running)" -ForegroundColor DarkGray
    }
    if ($script:STATUS_PORT_2720) {
        Write-Host "    " -NoNewline; Write-Host "* VS Code      localhost:$DaafPortVscode" -ForegroundColor Green
    } else {
        Write-Host "    o VS Code      (not running)" -ForegroundColor DarkGray
    }

    Write-Host ""

    # --- Menu options ---
    Write-Host "  LAUNCH"
    Write-Host "    1) Start Claude Code"
    Write-Host "    2) Browse Files (VS Code)"
    Write-Host "    3) View Session Logs"
    Write-Host "    4) View Marimo Notebooks (Python)"
    Write-Host "    5) View Quarto Notebooks (R)"
    Write-Host "    6) Open Terminal in Container"

    Write-Host ""

    Write-Host "  MANAGE"
    Write-Host "    7) Create Backup"
    Write-Host "    8) Restore from Backup"
    Write-Host "    9) Check for Updates"
    Write-Host "   10) Rebuild Container"
    Write-Host "   11) Restart Container"
    Write-Host "   12) Stop Web Services"

    Write-Host ""

    Write-Host "  OTHER"
    Write-Host "    h) Help"
    Write-Host "    q) Quit"

    Write-Host ""
}

# ============================================================================
# Input
# ============================================================================

# Read a menu choice into the script-scoped $script:CHOICE. On EOF (CI piping a
# single `q`, or the terminal closing) it clears $script:DaafMenuRunning so the
# main loop exits cleanly, mirroring daaf.sh read_choice's EOF-to-quit behavior.
#
# This function deliberately does NOT return a value the loop consumes in a
# conditional: quit is signaled purely through the script-scoped flag. Routing
# control flow through a captured return value would put the whole handler chain
# in a success-stream-capturing context, which strips console handles from the
# interactive delegates (see Invoke-DaafDelegateInteractive). $script:CHOICE is
# set to "" on EOF so a stray value from a prior iteration is never re-dispatched.
function Read-DaafChoice {
    $line = Read-DaafLine "  Enter choice"
    if ($null -eq $line) {
        # EOF on stdin (CI piped a finite input, or terminal closed). Treat as
        # explicit quit so the main loop exits cleanly and CI assertions hold.
        Write-Host ""
        Write-Host "Goodbye!"
        $script:CHOICE = ""
        $script:DaafMenuRunning = $false
        return
    }
    $script:CHOICE = $line
}

# ============================================================================
# Dispatch
# ============================================================================

# Dispatch a menu choice. Quit is signaled by clearing $script:DaafMenuRunning,
# NOT by a return value the main loop consumes in a conditional. This keeps every
# handler out of a success-stream-capturing context so the interactive delegates
# (Claude Code, container shell) inherit real console handles for TTY allocation
# -- routing quit through a captured `return $false` was what pipe-attached their
# stdio and broke TTY detection. Handlers are invoked as bare statements here and
# in the main loop; any incidental output they emit is theirs to print, not a
# control signal. Empty input and invalid input simply fall through to a redraw.
function Invoke-DaafChoice {
    param([string]$Choice)

    switch ($Choice) {
        "1"  { Invoke-DaafClaudeCode }
        "2"  { Invoke-DaafVSCode }
        "3"  { Invoke-DaafLogViewer }
        "4"  { Invoke-DaafNotebookBrowser }
        "5"  { Invoke-DaafQuartoViewer }
        "6"  { Invoke-DaafShell }
        "7"  { Invoke-DaafBackup }
        "8"  { Invoke-DaafRestore }
        "9"  { Invoke-DaafUpdate }
        "10" { Invoke-DaafRebuild }
        "11" { Invoke-DaafRestart }
        "12" { Invoke-DaafServiceStop }
        { $_ -in @("h", "H") } { Show-DaafHelp }
        { $_ -in @("q", "Q") } { Invoke-DaafQuit; $script:DaafMenuRunning = $false }
        "" { }  # Empty input -- just redraw
        default {
            Write-Host "  Invalid choice. Please enter a number (1-12), h, or q."
        }
    }
}

# ============================================================================
# Handlers: Interactive (options 1, 6)
# ============================================================================

# run_delegate equivalent for a delegated .ps1 that takes over the terminal
# (Claude Code, container shell). Guards the child exit so a non-zero return
# does not abort the panel -- control always returns to the menu with the
# failure surfaced. DAAF_NESTED=1 suppresses the child's pause-on-exit prompt.
#
# CONSOLE INHERITANCE (do NOT revert to `& child.ps1`): the child runs an
# interactive `docker compose exec` (Claude Code / a container bash shell) that
# needs the real console for TTY allocation. When any ancestor in the PowerShell
# call chain captures the success stream -- and the menu loop does, because a
# handler's return value used to drive the loop's continue/quit decision --
# native child processes get pipe-attached stdio instead of console handles.
# `docker compose exec` then auto-detects a non-terminal and skips `-t`, so
# Claude Code sees non-TTY stdin, flips to `--print` mode, and dies with
# "no stdin data received"; a plain container bash reads its script off the pipe
# and appears frozen. Launching the child via Start-Process with
# -NoNewWindow inherits THIS process's console handles directly, bypassing any
# capturing ancestor. The loop rework below (script-scoped quit flag instead of
# return-value dispatch) is the other half of the fix -- together they keep the
# handler chain out of a capturing context.
function Invoke-DaafDelegateInteractive {
    param(
        [string]$ScriptName,
        [string[]]$ScriptArgs = @(),
        [string]$FailureMessage
    )
    # Save any parent-inherited DAAF_NESTED so the finally restores it rather
    # than unconditionally removing it -- an unconditional Remove-Item would
    # clobber a value inherited when the panel itself runs nested, re-enabling
    # child pause prompts for the rest of the panel session.
    $savedNested = $env:DAAF_NESTED
    $env:DAAF_NESTED = "1"

    # Resolve the current host executable (works for both Windows PowerShell
    # powershell.exe and pwsh) -- same pattern the Pester child-process test and
    # the CI smoke harness use to spawn a child panel.
    $hostExe = (Get-Process -Id $PID).Path
    $childPath = Join-Path $script:DaafScriptDir $ScriptName

    # Build ONE pre-joined, correctly quoted argument string. Start-Process joins an
    # -ArgumentList ARRAY with bare spaces and quotes nothing, so the child path --
    # which lives under the install folder, e.g. "C:\Users\John Smith\daaf-docker"
    # or a "OneDrive - Org" folder -- used to split into several argv entries and the
    # child host failed to find the script (PowerShell#5576). Every element, the
    # -File path included, goes through ConvertTo-DaafNativeArg (daaf_lib.ps1), which
    # also handles embedded quotes and trailing backslashes; current callers pass
    # simple tokens ("bash") or nothing as $ScriptArgs. $null elements are dropped
    # first: a $null $ScriptArgs binds as ONE $null element, which the helper would
    # turn into an explicit empty "" argument for the child.
    $argString = (@(@('-NoProfile', '-File', $childPath) + @($ScriptArgs | Where-Object { $null -ne $_ })) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '

    # Ctrl+C survivability: while the child owns the console, route Ctrl+C to the
    # child (normal claude/bash break behavior) WITHOUT killing the parent panel.
    # Setting [Console]::TreatControlCAsInput = $true stops the parent runspace
    # from treating the break as a PipelineStoppedException. Read the prior value
    # first and restore it exactly in finally. Some hosts throw on this property
    # (e.g. a redirected/non-console host) -- degrade gracefully to prior
    # behavior in that case rather than aborting the delegation.
    $ctrlCGuarded = $false
    $priorTreatCtrlC = $false
    # Pre-init to $null (UNKNOWN), never 0: the post-finally read below stays
    # strict-mode-safe even if Start-Process throws before $ec is assigned (the
    # real exception must surface, not a masking "unset variable $ec" error), and
    # an exit status that was never read can never be mistaken for success.
    $ec = $null
    try {
        $priorTreatCtrlC = [Console]::TreatControlCAsInput
        [Console]::TreatControlCAsInput = $true
        $ctrlCGuarded = $true
    } catch {
        $ctrlCGuarded = $false
    }

    try {
        $proc = Start-Process -FilePath $hostExe -ArgumentList $argString `
            -NoNewWindow -PassThru
        # Cache the process handle NOW, while the child is still running. On
        # Windows -- Windows PowerShell 5.1 and PowerShell 6.0 through 7.4.0 --
        # the Process object Start-Process -PassThru -NoNewWindow (or
        # -RedirectStandard*) returns holds no open OS handle; if none is opened
        # before the child exits, ExitCode later reads as $null (PowerShell#5421,
        # #20400; fixed in 7.4.1; SO 10262231, answer 23797762; in-repo
        # precedents: test_migration.ps1 Invoke-HardenedScript and the
        # backup_daaf.ps1 docker cp copy). Best-effort: a failure here leaves the
        # exit status UNKNOWN below, never success.
        try { $null = $proc.Handle } catch { Write-Verbose "Could not cache the child process handle: $_" }
        $proc.WaitForExit()
        try { $ec = $proc.ExitCode } catch { $ec = $null }
    } finally {
        if ($ctrlCGuarded) {
            try {
                [Console]::TreatControlCAsInput = $priorTreatCtrlC
                # Drain any Ctrl+C keypress records queued while the guard was
                # active so a stray ^C does not land in the next menu prompt.
                # Best-effort: KeyAvailable/ReadKey throw on non-console hosts.
                while ([Console]::KeyAvailable) { [void][Console]::ReadKey($true) }
            } catch {
                # Non-console host or drain unsupported -- a residual keypress
                # landing in the menu prompt is acceptable (documented).
                Write-Verbose "Silenced: $_"
            }
        }
        if ($null -ne $savedNested) { $env:DAAF_NESTED = $savedNested } else { Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue }
    }

    # Three outcomes, never two: an unreadable ($null) exit status is UNKNOWN and
    # gets its own message -- it is not success. (The old `$ec -and $ec -ne 0`
    # test read $null as "no error" and printed nothing.)
    if ($null -eq $ec) {
        Write-Host ""
        Write-Host "  Could not read the exit status of $ScriptName -- check its output above for errors." -ForegroundColor Yellow
    } elseif ($ec -ne 0) {
        Write-Host ""
        Write-Host "  $FailureMessage" -ForegroundColor Yellow
    }
}

function Invoke-DaafClaudeCode {
    Write-Host ""
    Write-Host "Launching Claude Code..."
    Write-Host "(When you're done, type /exit to return to this menu)"
    Write-Host ""
    Invoke-DaafDelegateInteractive "run_daaf.ps1" @() "Claude Code session ended with an error."
    Write-Host ""
    Write-Host "Returned to DAAF Control Panel."
}

function Invoke-DaafShell {
    Write-Host ""
    Write-Host "Opening terminal in container..."
    Write-Host "(Type 'exit' to return to this menu)"
    Write-Host ""
    Invoke-DaafDelegateInteractive "run_daaf.ps1" @("bash") "Container terminal ended with an error."
    Write-Host ""
    Write-Host "Returned to DAAF Control Panel."
}

# ============================================================================
# Handlers: Web services (options 2, 3, 4, 5)
# ============================================================================

function Invoke-DaafNotebookBrowser {
    Write-Host ""
    Write-Host "Starting notebook browser..."

    # Ensure the container is up before attempting docker compose exec, so we
    # give a clear message instead of letting a failed exec surface obscurely.
    if (-not (Confirm-DaafContainer)) {
        Write-Host "  Could not start the DAAF container. Is Docker running?" -ForegroundColor Yellow
        return
    }

    if (Test-DaafPort 2718) {
        Write-Host "  Marimo is already running."
    } else {
        # Capture stderr (do NOT discard) so a container-side launch failure is
        # distinguishable from a slow start. A non-zero exit returns to the menu.
        # 'Continue', not 'SilentlyContinue': Windows PowerShell 5.1 drops native
        # stderr from a 2>&1 capture under SilentlyContinue (shell-scripting gotchas).
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $launchErr = docker compose exec -d daaf-docker bash /daaf/scripts/launch_marimo.sh --background 2>&1
            $launchExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($launchExit -and $launchExit -ne 0) {
            Write-Host "  Failed to start the notebook server:" -ForegroundColor Yellow
            Write-Host "  $launchErr"
            return
        }

        $elapsed = 0
        while ($elapsed -lt 10) {
            if (Test-DaafPort 2718) { break }
            Start-Sleep -Seconds 1
            $elapsed++
        }

        if (-not (Test-DaafPort 2718)) {
            Write-Host "  Server may still be starting. Try the URL in a moment." -ForegroundColor Yellow
        } else {
            Write-Host "  Server started."
        }
    }

    # Browser URL uses the HOST-published port ($DaafPortMarimo); the container
    # port probed above stays fixed at 2718.
    $url = "http://localhost:$DaafPortMarimo"
    Write-Host ""
    Write-Host "  $url" -ForegroundColor Cyan
    Write-Host ""
    Open-DaafUrl $url
}

function Invoke-DaafVSCode {
    Write-Host ""
    Write-Host "Starting VS Code browser..."

    # Ensure the container is up before attempting docker compose exec.
    if (-not (Confirm-DaafContainer)) {
        Write-Host "  Could not start the DAAF container. Is Docker running?" -ForegroundColor Yellow
        return
    }

    # code-server runs with --auth password; the launcher prints the password to
    # its own stdout, which is lost under `exec -d`. Mirror launch_code_server.sh's
    # default here so the menu can display it. Honor a PASSWORD override if the
    # user exported one before launching the panel.
    # Default mirrors launch_code_server.sh (PASSWORD env var overrides both).
    $vscodePassword = if ($env:PASSWORD) { $env:PASSWORD } else { "daaf" }

    if (Test-DaafPort 2720) {
        Write-Host "  VS Code is already running."
    } else {
        # Capture stderr (do NOT discard) so a container-side launch failure --
        # e.g., a stale image without code-server -- is visible rather than
        # masquerading as "still starting". Non-zero exit returns to the menu.
        # 'Continue' keeps that stderr text on Windows PowerShell 5.1 (see above).
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $launchErr = docker compose exec -d daaf-docker bash /daaf/scripts/launch_code_server.sh --background 2>&1
            $launchExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($launchExit -and $launchExit -ne 0) {
            Write-Host "  Failed to start VS Code (code-server):" -ForegroundColor Yellow
            Write-Host "  $launchErr"
            return
        }

        $elapsed = 0
        while ($elapsed -lt 10) {
            if (Test-DaafPort 2720) { break }
            Start-Sleep -Seconds 1
            $elapsed++
        }

        if (-not (Test-DaafPort 2720)) {
            Write-Host "  Server may still be starting. Try the URL in a moment." -ForegroundColor Yellow
        } else {
            Write-Host "  Server started."
        }
    }

    # Browser URL uses the HOST-published port ($DaafPortVscode); the container
    # port probed above stays fixed at 2720.
    $url = "http://localhost:$DaafPortVscode"
    Write-Host ""
    Write-Host "  $url" -ForegroundColor Cyan
    Write-Host "  Password: $vscodePassword"
    Write-Host ""
    Open-DaafUrl $url
}

function Invoke-DaafLogViewer {
    Write-Host ""
    Write-Host "Discovering available log sources..."

    # Ensure the container is up before attempting docker compose exec.
    if (-not (Confirm-DaafContainer)) {
        Write-Host "  Could not start the DAAF container. Is Docker running?" -ForegroundColor Yellow
        return
    }

    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $sourcesRaw = docker compose exec -T daaf-docker bash /daaf/scripts/discover_log_sources.sh 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    $sources = (($sourcesRaw | Out-String) -replace "`r", "").Trim()

    if ([string]::IsNullOrWhiteSpace($sources)) {
        Write-Host "  No session logs found. Run a DAAF session first to generate logs."
        return
    }

    $paths = @()
    $labels = @()

    foreach ($line in ($sources -split "`n")) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '\|'
        $sourceId = $parts[0].Trim()
        $sessionCount = if ($parts.Count -gt 1) { $parts[1].Trim() } else { "" }
        if ([string]::IsNullOrWhiteSpace($sourceId)) { continue }
        if ($sourceId -eq "ARCHIVE") {
            $paths += "ARCHIVE"
            $labels += "Full session archive ($sessionCount sessions)"
        } else {
            $folderName = Split-Path $sourceId -Leaf
            $displayDate = ($folderName -split '_')[0]
            $displayTitle = ($folderName -replace '^[^_]*_', '') -replace '_', ' '
            $paths += $sourceId
            $labels += "$displayDate $displayTitle ($sessionCount sessions)"
        }
    }

    if ($labels.Count -eq 0) {
        Write-Host "  No session logs found. Run a DAAF session first to generate logs."
        return
    }

    Write-Host ""
    Write-Host "  Select a log source:"
    Write-Host ""
    for ($i = 0; $i -lt $labels.Count; $i++) {
        Write-Host ("    {0}) {1}" -f ($i + 1), $labels[$i])
    }
    Write-Host ""
    Write-Host "    0) Back to main menu"
    Write-Host ""

    $choice = Read-DaafLine "  Enter choice"

    if ($choice -eq "0" -or [string]::IsNullOrWhiteSpace($choice)) {
        return
    }

    if (($choice -notmatch '^[0-9]+$') -or ([int]$choice -lt 1) -or ([int]$choice -gt $paths.Count)) {
        Write-Host "  Invalid selection."
        return
    }

    $selected = $paths[[int]$choice - 1]

    # --- Step 1: Generate the manifest for the SELECTED source ---
    # Capture stderr so a generation failure (e.g., empty archive) produces an
    # accurate message instead of a dead URL. A failure here returns to the menu.
    Write-Host ""
    Write-Host "  Generating session manifest..."
    # 'Continue', not 'SilentlyContinue', in both brackets below: Windows PowerShell
    # 5.1 drops native stderr from a 2>&1 capture under SilentlyContinue, and the
    # generator's Python errors go to stderr.
    if ($selected -eq "ARCHIVE") {
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $manifestErr = docker compose exec -T daaf-docker bash /daaf/scripts/generate_log_viewer.sh --archive --no-serve 2>&1
            $manifestExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($manifestExit -and $manifestExit -ne 0) {
            Write-Host "  Manifest generation failed for the full archive." -ForegroundColor Yellow
            Write-Host "  The error was:" -ForegroundColor Yellow
            Write-Host "  $manifestErr"
            Write-Host "  A specific project source may still work -- try selecting" -ForegroundColor Yellow
            Write-Host "  one project instead of the full archive." -ForegroundColor Yellow
            return
        }
        $url = "http://localhost:$DaafPortLogViewer/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json"
    } else {
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $manifestErr = docker compose exec -T daaf-docker bash /daaf/scripts/generate_log_viewer.sh $selected --no-serve 2>&1
            $manifestExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($manifestExit -and $manifestExit -ne 0) {
            Write-Host "  Could not generate the session manifest:" -ForegroundColor Yellow
            Write-Host "  $manifestErr"
            return
        }
        $relPath = $selected -replace '^/daaf/', ''
        $url = "http://localhost:$DaafPortLogViewer/scripts/log_viewer.html?manifest=$relPath/logs/session_manifest.json"
    }

    # --- Step 2: Ensure the log viewer server is running ---
    # Start the server against the SELECTED source, not always --archive, so a
    # valid project selection is not left with a dead URL when the DAAF-wide
    # archive is empty. Serving from the chosen source decouples the two.
    if (-not (Test-DaafPort 2719)) {
        Write-Host "  Starting log viewer server..."
        if ($selected -eq "ARCHIVE") {
            $serveArgs = @("--archive", "--background")
        } else {
            $serveArgs = @($selected, "--background")
        }
        # 'Continue' keeps Docker's stderr text on Windows PowerShell 5.1 (see above).
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "Continue"
            $serveErr = docker compose exec -d daaf-docker bash /daaf/scripts/generate_log_viewer.sh @serveArgs 2>&1
            $serveExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($serveExit -and $serveExit -ne 0) {
            Write-Host "  Could not start the log viewer server:" -ForegroundColor Yellow
            Write-Host "  $serveErr"
            return
        }

        $elapsed = 0
        while ($elapsed -lt 10) {
            if (Test-DaafPort 2719) { break }
            Start-Sleep -Seconds 1
            $elapsed++
        }

        if (-not (Test-DaafPort 2719)) {
            Write-Host "  Server may still be starting. Try the URL in a moment." -ForegroundColor Yellow
        }
    }

    Write-Host ""
    Write-Host "  $url" -ForegroundColor Cyan
    Write-Host ""
    Open-DaafUrl $url
}

# ============================================================================
# Handler: View Quarto Notebooks (option 5)
# ============================================================================

# view_quarto.ps1 is a HOST sibling script (like backup/restore/update), not a
# container-side launcher: with no argument it recursively discovers every .qmd
# under research/, lets the user select or cancel, renders the selection to
# self-contained HTML, copies it out, and opens it in the browser. Delegate via
# Invoke-DaafDelegate (Start-Process child + DAAF_NESTED=1) so it gets real console
# handles and control returns cleanly to the menu -- the guarded-child pattern
# used by the maintenance delegates.
function Invoke-DaafQuartoViewer { Invoke-DaafDelegate "view_quarto.ps1" }

# ============================================================================
# Handlers: Maintenance (options 7-10)
# ============================================================================

# Invoke-DaafDelegate <script-name> -- run a delegated child .ps1 with
# DAAF_NESTED=1. Guards the child's exit code: a non-zero exit (child failure,
# user abort, or the graceful "no backups found" case in
# restore_from_backup.ps1) prints a clear message and returns to the menu
# rather than aborting the panel. Mirrors daaf.sh run_delegate.
#
# CONSOLE INHERITANCE (do NOT revert to `& child.ps1`): these maintenance
# children (backup/restore/update/rebuild) run interactive Read-Host prompts and
# may run interactive docker execs. For the same reason as
# Invoke-DaafDelegateInteractive -- the menu loop no longer captures handler
# return values, but Start-Process with -NoNewWindow guarantees the child gets
# real console handles regardless of any capturing ancestor -- we spawn the
# child as a child process rather than calling it in-process.
function Invoke-DaafDelegate {
    param([string]$ScriptName)
    Write-Host ""
    # Save any parent-inherited DAAF_NESTED so the finally restores it rather
    # than unconditionally removing it -- an unconditional Remove-Item would
    # clobber a value inherited when the panel itself runs nested, re-enabling
    # child pause prompts for the rest of the panel session.
    $savedNested = $env:DAAF_NESTED
    $env:DAAF_NESTED = "1"

    $hostExe = (Get-Process -Id $PID).Path
    $childPath = Join-Path $script:DaafScriptDir $ScriptName
    # ONE pre-joined, quoted argument string -- see Invoke-DaafDelegateInteractive:
    # an array -ArgumentList splits a child path containing spaces.
    $argString = (@('-NoProfile', '-File', $childPath) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '

    # Ctrl+C survivability guard (see Invoke-DaafDelegateInteractive for the full
    # rationale): keep a break from killing the parent panel; degrade gracefully
    # on hosts that do not support the property.
    $ctrlCGuarded = $false
    $priorTreatCtrlC = $false
    # Pre-init to $null (UNKNOWN), never 0: strict-mode-safe for the post-finally
    # read even if Start-Process throws (surface the real exception, not a masking
    # "unset variable $ec" error), and never mistakable for a clean exit.
    $ec = $null
    try {
        $priorTreatCtrlC = [Console]::TreatControlCAsInput
        [Console]::TreatControlCAsInput = $true
        $ctrlCGuarded = $true
    } catch {
        $ctrlCGuarded = $false
    }

    try {
        $proc = Start-Process -FilePath $hostExe -ArgumentList $argString `
            -NoNewWindow -PassThru
        # Cache the handle while the child runs, so ExitCode stays readable on
        # Windows PowerShell 5.1 and PowerShell 6.0-7.4.0 on Windows (see
        # Invoke-DaafDelegateInteractive).
        try { $null = $proc.Handle } catch { Write-Verbose "Could not cache the child process handle: $_" }
        $proc.WaitForExit()
        try { $ec = $proc.ExitCode } catch { $ec = $null }
    } finally {
        if ($ctrlCGuarded) {
            try {
                [Console]::TreatControlCAsInput = $priorTreatCtrlC
                while ([Console]::KeyAvailable) { [void][Console]::ReadKey($true) }
            } catch {
                # Non-console host or drain unsupported -- residual keypress OK.
                Write-Verbose "Silenced: $_"
            }
        }
        if ($null -ne $savedNested) { $env:DAAF_NESTED = $savedNested } else { Remove-Item Env:\DAAF_NESTED -ErrorAction SilentlyContinue }
    }

    # Three outcomes: success, failure, and UNKNOWN. An unreadable ($null) exit
    # status is never summarised as a clean return -- the old `-not $ec` test did
    # exactly that, so a failed backup/restore/update/rebuild could read as success.
    if ($null -eq $ec) {
        Write-Host ""
        Write-Host "  Could not read the exit status of $ScriptName -- check its output above for errors." -ForegroundColor Yellow
        Write-Host "Returned to DAAF Control Panel."
    } elseif ($ec -eq 0) {
        Write-Host ""
        Write-Host "Returned to DAAF Control Panel."
    } else {
        Write-Host ""
        Write-Host "  $ScriptName exited without completing (code $ec)." -ForegroundColor Yellow
        Write-Host "Returned to DAAF Control Panel."
    }
}

function Invoke-DaafBackup  { Invoke-DaafDelegate "backup_daaf.ps1" }
function Invoke-DaafRestore { Invoke-DaafDelegate "restore_from_backup.ps1" }
function Invoke-DaafUpdate  { Invoke-DaafDelegate "update_daaf.ps1" }
function Invoke-DaafRebuild { Invoke-DaafDelegate "rebuild_daaf.ps1" }

# ============================================================================
# Handler: Restart Container (option 11)
# ============================================================================

# PowerShell counterpart to daaf.sh handle_restart -- see that function for the
# full rationale. In short: Docker Compose reads environment_settings.txt (an
# env_file) only when it CREATES the container, so applying an edit takes
# `docker compose down` + `docker compose up -d`; `docker compose restart` would
# keep the old environment. Same order as the bash twin:
#   1. confirm (default No);
#   2. project-name guard before any docker command -- names compared as Docker
#      Compose normalizes them (Resolve-DaafProjectName), so `Work` -> `work`
#      passes and a name that normalizes to nothing is refused; an unreadable
#      settings file is caught by the guard's probe and reported, nothing changed;
#   3. down with the CURRENT settings (never -v);
#   4. Sync-DaafSettingsFile -- if the file can no longer be read, restore the
#      pre-restart settings snapshot and stop (the container stays stopped);
#   5. project re-check -- if the reloaded file now names a different project
#      (edited or deleted while `down` ran), restore the snapshot and stop
#      WITHOUT `up`, which would otherwise start a different install;
#   6. Initialize-DaafPortDisplay -> up -d -> readiness poll (30 x 2s, as
#      rebuild_daaf.ps1) -> verify.
#
# Runs IN-PROCESS (no Start-Process delegation): `docker compose down` / `up -d`
# and the `exec -T` readiness checks are non-interactive, so they need no console
# handle inheritance. Named Invoke- rather than Restart-: PSScriptAnalyzer's
# PSUseShouldProcessForStateChangingFunctions would demand SupportsShouldProcess
# on a Restart-* function, which is wrong ceremony for a menu handler that has its
# own confirmation prompt (same reasoning as Invoke-DaafServiceStop).
#
# PROJECT-NAME GUARD: environment variables are process-wide, so there is no
# subshell to probe in as the bash twin does. Instead the handler takes ONE
# settings snapshot up front (Get-DaafSettingsSnapshot below), the probe runs
# Sync-DaafSettingsFile to see which DAAF_PROJECT_NAME the edited file resolves
# to, and `finally` restores the snapshot, so the panel's environment is unchanged
# whichever way the check goes. The same snapshot is restored after `down` when
# the reload fails or names a different project: Sync-DaafSettingsFile removes
# the file-adopted keys BEFORE it reads the file, so a read that throws part-way
# would otherwise leave DAAF_PROJECT_NAME and the ports unset in the panel, and
# the next Restart would then be refused by the guard with misleading advice.
#
# Every docker call uses the SilentlyContinue + $LASTEXITCODE pattern; a failure
# prints guidance and returns to the menu rather than ending the panel. The
# readiness poll keeps no temp log file, so a dry run writes nothing to disk.

# Get-DaafSettingsSnapshot -- capture the panel's settings state: every DAAF_*
# process variable (by name pattern, not a list of settings keys, so a key added
# to the loader's whitelist later is covered automatically) plus the loader's
# provenance tracker. Restore-DaafSettingsSnapshot puts exactly that state back.
# The tracker is read through Get-Variable so a never-assigned tracker is safe
# under Set-StrictMode. Restore- is not in PSUseShouldProcessForStateChangingFunctions'
# verb list, so the pair needs no ShouldProcess ceremony.
function Get-DaafSettingsSnapshot {
    [CmdletBinding()]
    [OutputType([hashtable])]
    param()
    $envValues = @{}
    foreach ($item in @(Get-ChildItem -Path Env: | Where-Object { $_.Name -like 'DAAF_*' })) {
        $envValues[$item.Name] = $item.Value
    }
    $tracker = @()
    $trackerVar = Get-Variable -Name 'DaafKeysFromFile' -Scope Script -ErrorAction SilentlyContinue
    if ($null -ne $trackerVar -and $null -ne $trackerVar.Value) { $tracker = @($trackerVar.Value) }
    return @{ Env = $envValues; Tracker = $tracker }
}

function Restore-DaafSettingsSnapshot {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable]$Snapshot
    )
    # Drop DAAF_* variables the snapshot did not have, then put back every
    # snapshotted value (empty and unset are equivalent to every DAAF reader).
    foreach ($item in @(Get-ChildItem -Path Env: | Where-Object { $_.Name -like 'DAAF_*' })) {
        if (-not $Snapshot.Env.ContainsKey($item.Name)) {
            Remove-Item -Path ("Env:" + $item.Name) -ErrorAction SilentlyContinue
        }
    }
    foreach ($name in @($Snapshot.Env.Keys)) {
        Set-Item -Path ("Env:" + $name) -Value $Snapshot.Env[$name]
    }
    $script:DaafKeysFromFile = @($Snapshot.Tracker)
}

function Invoke-DaafRestart {
    Write-Host ""
    Write-Host "  Restart Container"
    Write-Host ""
    Write-Host "  This applies the changes you made in environment_settings.txt by"
    Write-Host "  stopping and recreating the DAAF container. It usually takes under a"
    Write-Host "  minute and does not rebuild the image."
    Write-Host ""
    Write-Host "  It ENDS any open Claude Code session, container terminal, or web" -ForegroundColor Yellow
    Write-Host "  service (notebooks, log viewer, VS Code) for this DAAF install --" -ForegroundColor Yellow
    Write-Host "  including ones open in other windows. Save your work and close them" -ForegroundColor Yellow
    Write-Host "  first." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Your research files and your Claude Code login are kept (they live in"
    Write-Host "  Docker volumes)."
    Write-Host ""
    Write-Host "  Settings marked `"rebuild required`" in environment_settings.txt (such as"
    Write-Host "  DAAF_DEV, or turning on the provider shim for the first time), and"
    Write-Host "  changes to the Dockerfile, packages, or docker-compose.yml, need Rebuild"
    Write-Host "  Container instead."
    Write-Host ""

    # Default No: y or yes in any case, surrounding spaces ignored (same rule as
    # daaf.sh; -notin is case-insensitive). EOF ($null) counts as No.
    $answer = Read-DaafLine "  Restart the container now? [y/N]"
    $answer = if ($null -ne $answer) { ([string]$answer).Trim() } else { "" }
    if ($answer -notin @("y", "yes")) {
        Write-Host "  Restart cancelled -- nothing was changed."
        return
    }

    # Path handed to Sync-DaafSettingsFile by the guard probe and the post-down
    # reload (the user-facing messages below name the file literally).
    $settingsFile = "./environment_settings.txt"

    # The panel's settings as they are now, before anything below touches them.
    # Restored by the guard probe's `finally`, and after `down` when the reload
    # fails or names a different project (see the header).
    $preRestart = Get-DaafSettingsSnapshot

    # --- Project-name guard (no docker command has run yet) ---
    # Compare the names Docker Compose USES (Resolve-DaafProjectName, daaf_lib.ps1),
    # case-sensitively with -cne, not the raw values; the raw values are kept for
    # the messages. Same rule as daaf.sh: `Work` -> `work` passes, and a name that
    # normalizes to nothing is refused on the same path, with its own reason.
    $activeProject = if ($env:DAAF_PROJECT_NAME) { $env:DAAF_PROJECT_NAME } else { "daaf" }
    $activeNorm = Resolve-DaafProjectName
    $fileProject = $activeProject
    $fileNorm = $activeNorm
    $readFailed = $false
    try {
        Sync-DaafSettingsFile -SettingsFile $settingsFile
        $fileProject = if ($env:DAAF_PROJECT_NAME) { $env:DAAF_PROJECT_NAME } else { "daaf" }
        $fileNorm = Resolve-DaafProjectName
    } catch {
        # Unreadable file (permissions, locked by an editor): report it here
        # instead of letting it reach the main loop's "This is a bug" catch. The
        # finally below still restores the environment snapshot.
        $readFailed = $true
    } finally {
        Restore-DaafSettingsSnapshot -Snapshot $preRestart
    }
    if ($readFailed) {
        Write-Host ""
        Write-Host "  Cannot read environment_settings.txt -- make sure it is not open in another" -ForegroundColor Yellow
        Write-Host "  program and that you have permission to read it." -ForegroundColor Yellow
        Write-Host "  Nothing was changed." -ForegroundColor Yellow
        return
    }
    if ([string]::IsNullOrEmpty($fileNorm) -or $fileNorm -cne $activeNorm) {
        Write-Host ""
        Write-Host "  Restart stopped -- nothing was changed." -ForegroundColor Yellow
        Write-Host ""
        if ([string]::IsNullOrEmpty($fileNorm)) {
            Write-Host "  With your current environment_settings.txt, the project name would be"
            Write-Host "  `"$fileProject`", which Docker Compose cannot use. A project name may use"
            Write-Host "  lowercase letters, digits, '-' and '_', and must start with a letter or digit."
        } else {
            Write-Host "  With your current environment_settings.txt, this install would now use"
            Write-Host "  the project name `"$fileProject`" (the default is `"daaf`" when the"
            Write-Host "  file does not set one) instead of `"$activeProject`"."
            Write-Host "  The project name decides which install and which research data volume"
            Write-Host "  Docker uses. Restarting under a new name would stop this install and"
            Write-Host "  start a DIFFERENT one in its place, so your current research would"
            Write-Host "  appear to be missing."
        }
        Write-Host ""
        Write-Host "  To keep this install: make environment_settings.txt use the project"
        Write-Host "  name `"$activeProject`" again, then choose Restart Container again."
        Write-Host "  To switch installs on purpose: quit this panel and follow `"Running"
        Write-Host "  multiple DAAF instances`" in the Installation Guide"
        Write-Host "  (user_reference/01_installation_and_quickstart.md)."
        return
    }

    # --- Stop (current settings, so `down` targets the running project) ---
    Write-Host ""
    Write-Host "[1/3] Stopping the DAAF container..."
    $downExit = $null
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose down
        $downExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($downExit -ne 0) {
        Write-Host ""
        Write-Host "  Could not stop the container. Check the Docker message above and" -ForegroundColor Yellow
        Write-Host "  make sure Docker Desktop is running, then try again." -ForegroundColor Yellow
        return
    }

    # --- Reload the edited settings (compose interpolation + panel display) ---
    # The file was readable a moment ago; if that changed, say so and stop
    # rather than starting the container with stale settings. Sync-DaafSettingsFile
    # has already removed the file-adopted keys when its read throws, so put the
    # pre-restart snapshot back: the panel is then exactly as it was before `down`.
    try {
        Sync-DaafSettingsFile -SettingsFile $settingsFile
    } catch {
        Restore-DaafSettingsSnapshot -Snapshot $preRestart
        Write-Host ""
        Write-Host "  The container is stopped, but environment_settings.txt can no longer" -ForegroundColor Yellow
        Write-Host "  be read. Make sure it is not open in another program and that you have" -ForegroundColor Yellow
        Write-Host "  permission to read it, then choose Restart Container again (or Start" -ForegroundColor Yellow
        Write-Host "  Claude Code, which starts the container)." -ForegroundColor Yellow
        return
    }

    # --- Project re-check (the guard ran before `down`) ---
    # If the file was edited or deleted while `down` ran, the reload may have
    # adopted a different project name, and `up` would then start a DIFFERENT
    # install. Restore the pre-restart settings and stop without `up`. Same
    # normalized comparison as the guard above.
    $reloadedProject = if ($env:DAAF_PROJECT_NAME) { $env:DAAF_PROJECT_NAME } else { "daaf" }
    $reloadedNorm = Resolve-DaafProjectName
    if ([string]::IsNullOrEmpty($reloadedNorm) -or $reloadedNorm -cne $activeNorm) {
        Restore-DaafSettingsSnapshot -Snapshot $preRestart
        Write-Host ""
        Write-Host "  The container is stopped, but it was not started again --" -ForegroundColor Yellow
        if ([string]::IsNullOrEmpty($reloadedNorm)) {
            Write-Host "  environment_settings.txt now has a project name that cannot be used." -ForegroundColor Yellow
        } else {
            Write-Host "  environment_settings.txt now names a different project." -ForegroundColor Yellow
        }
        Write-Host ""
        if ([string]::IsNullOrEmpty($reloadedNorm)) {
            Write-Host "  It changed while the container was stopping, and now gives the project"
            Write-Host "  name `"$reloadedProject`", which Docker Compose cannot use. A project name may use"
            Write-Host "  lowercase letters, digits, '-' and '_', and must start with a letter or digit."
        } else {
            Write-Host "  It changed while the container was stopping, and now gives the project"
            Write-Host "  name `"$reloadedProject`" (the default is `"daaf`" when the file does not set one)"
            Write-Host "  instead of `"$activeProject`"."
            Write-Host "  Starting under the new name would start a DIFFERENT install, so your"
            Write-Host "  current research would appear to be missing."
        }
        Write-Host ""
        Write-Host "  To keep this install: make environment_settings.txt use the project"
        Write-Host "  name `"$activeProject`" again, then choose Restart Container again."
        Write-Host "  To switch installs on purpose: quit this panel and follow `"Running"
        Write-Host "  multiple DAAF instances`" in the Installation Guide"
        Write-Host "  (user_reference/01_installation_and_quickstart.md)."
        return
    }
    Initialize-DaafPortDisplay

    # --- Recreate ---
    Write-Host ""
    Write-Host "[2/3] Starting the container with your new settings..."
    $upExit = $null
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose up -d
        $upExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($upExit -ne 0) {
        Write-Host ""
        Write-Host "  The container was stopped but could not be started again. Check" -ForegroundColor Yellow
        Write-Host "  the Docker message above (for example, a port that is already in use)," -ForegroundColor Yellow
        Write-Host "  fix environment_settings.txt if needed, then choose Restart Container" -ForegroundColor Yellow
        Write-Host "  again -- or choose Start Claude Code, which also starts the container." -ForegroundColor Yellow
        return
    }

    # --- Wait for readiness (mirrors rebuild_daaf.ps1) ---
    Write-Host ""
    Write-Host "[3/3] Waiting for the container to be ready..."
    $retries = 0
    $maxRetries = 30
    while ($true) {
        $readyExit = $null
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            docker compose exec -T daaf-docker true 2>$null | Out-Null
            $readyExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($readyExit -eq 0) { break }
        $retries++
        if ($retries -ge $maxRetries) {
            # One more attempt to capture Docker's message for the user (held in
            # memory, not a temp file). "$_" renders a PS 5.1 stderr ErrorRecord
            # as its plain message text. 'Continue', not 'SilentlyContinue': Windows
            # PowerShell 5.1 drops native stderr from a 2>&1 capture under
            # SilentlyContinue, which would leave "Docker reported:" with no lines.
            $savedEAP = $ErrorActionPreference
            try {
                $ErrorActionPreference = "Continue"
                $readyErr = @(docker compose exec -T daaf-docker true 2>&1 | ForEach-Object { "$_" })
            } finally {
                $ErrorActionPreference = $savedEAP
            }
            Write-Host ""
            Write-Host "  The container did not become ready within 60 seconds." -ForegroundColor Yellow
            $errLines = @($readyErr | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -Last 5)
            if ($errLines.Count -gt 0) {
                Write-Host "  Docker reported:"
                foreach ($errLine in $errLines) { Write-Host "    $errLine" }
            }
            Write-Host "  Check Docker Desktop for errors."
            return
        }
        Start-Sleep -Seconds 2
    }

    $verifyExit = $null
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose exec -T daaf-docker test -f /daaf/CLAUDE.md 2>&1 | Out-Null
        $verifyExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($verifyExit -ne 0) {
        Write-Host ""
        Write-Host "  The container restarted, but DAAF's files may not be intact." -ForegroundColor Yellow
        Write-Host "  Choose Open Terminal in Container to take a look." -ForegroundColor Yellow
        return
    }

    Write-Host ""
    Write-Host "  Container restarted -- your environment_settings.txt changes are now in effect" -ForegroundColor Green
    Write-Host "  (settings marked `"rebuild required`" still need Rebuild Container)." -ForegroundColor Green
}

# ============================================================================
# Handler: Stop Services (option 12)
# ============================================================================

# Named with Invoke- (like the other menu handlers) rather than the natural
# Stop- verb: PSSA's PSUseShouldProcessForStateChangingFunctions requires
# SupportsShouldProcess on Stop-* functions, which is wrong ceremony for an
# interactive menu handler that has its own confirmation prompt.
function Invoke-DaafServiceStop {
    Write-Host ""

    $marimoRunning = Test-DaafPort 2718
    $logsRunning   = Test-DaafPort 2719
    $vscodeRunning = Test-DaafPort 2720
    $svcRunning = $marimoRunning -or $logsRunning -or $vscodeRunning

    if (-not $svcRunning) {
        Write-Host "  No web services are currently running."
        return
    }

    Write-Host "  Running services:"
    if ($marimoRunning) {
        Write-Host "    " -NoNewline; Write-Host "* Notebooks    (port 2718)" -ForegroundColor Green
    }
    if ($logsRunning) {
        Write-Host "    " -NoNewline; Write-Host "* Log Viewer   (port 2719)" -ForegroundColor Green
    }
    if ($vscodeRunning) {
        Write-Host "    " -NoNewline; Write-Host "* VS Code      (port 2720)" -ForegroundColor Green
    }
    Write-Host ""
    Write-Host "    1) Stop all"
    Write-Host "    0) Back"
    Write-Host ""

    $choice = Read-DaafLine "  Enter choice"

    if ($choice -eq "1") {
        Write-Host "  Stopping services..."
        # Container-side stop payload -- VERBATIM from daaf.sh handle_stop_services.
        # Maps each listening port to its owning PID via /proc/net/tcp (inode) ->
        # /proc/*/fd (socket symlink) -> PID, then kills it. `ss` is not present
        # in the image, so this reuses the /proc pattern from
        # generate_log_viewer.sh. Surface stderr so failures are visible.
        #
        # TRANSPORT v3 -- base64-as-argument (do NOT revert). This payload
        # contains embedded double quotes (the find/grep/sed patterns) and takes
        # no positional args (ports hardcoded), so it uses the arg-less remote
        # wrapper `echo $1 | base64 -d | bash`, with the b64 token passed as a
        # native argument. Two earlier transports both failed on real Windows:
        # v1 `bash -c <payload>` mangled the embedded `"` (PS 5.1 native-arg
        # quoting bug, fixed only in 7.3+), delivering a broken script so the
        # services were never stopped; v2 `<payload> | bash -s` (stdin) left a
        # stray CR on the last line (PS appends CRLF piping to a native process)
        # and the PS-pipeline -> docker.exe npipe stdin wiring is unreliable. The
        # b64 token is [A-Za-z0-9+/=] only, so PS 5.1's arg marshalling cannot
        # damage it. See the fully annotated Test-DaafPort note in daaf_lib.ps1.
        $stopScript = @'
            for port in 2718 2719 2720; do
                ph=$(printf "%04X" "$port")
                inode=$(awk -v ph="$ph" '$2 ~ ":"ph"$" && $4 == "0A" {print $10}' \
                    /proc/net/tcp /proc/net/tcp6 2>/dev/null | head -1)
                [ -z "$inode" ] && continue
                pid=$(find /proc -maxdepth 3 -path "*/fd/*" -exec ls -la {} + 2>/dev/null \
                    | grep "socket:\[$inode\]" | head -1 \
                    | sed "s|.*/proc/\([0-9]*\)/.*|\1|")
                case "$pid" in
                    ""|*[!0-9]*) continue ;;
                esac
                if kill "$pid" 2>/dev/null; then
                    echo "    Stopped service on port $port (PID $pid)"
                else
                    echo "    Could not stop service on port $port (PID $pid)"
                fi
            done
'@
        # The single-quoted PS literal 'echo $1 | base64 -d | bash' has spaces
        # but ZERO double quotes -> PS 5.1 wraps it in "..." intact; $1 stays
        # literal and is the container bash's positional param (`_` is $0, the
        # token is $1). `echo $1` is unquoted deliberately (base64 alphabet has
        # no whitespace/glob chars); quoting it would reintroduce double quotes
        # and revert to v1. $LASTEXITCODE reflects docker after the call.
        $b64 = [Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($stopScript))
        $savedEAP = $ErrorActionPreference
        try {
            $ErrorActionPreference = "SilentlyContinue"
            docker compose exec -T daaf-docker bash -c 'echo $1 | base64 -d | bash' _ $b64
            $stopExit = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $savedEAP
        }
        if ($stopExit -and $stopExit -ne 0) {
            Write-Host "  Warning: could not reach the container to stop services." -ForegroundColor Yellow
        }
        Write-Host "  Done."
    }
}

# ============================================================================
# Handler: Help (option h)
# ============================================================================

function Show-DaafHelp {
    Write-Host ""
    Write-Host "=========================================="
    Write-Host "  DAAF Control Panel -- Help"
    Write-Host "=========================================="
    Write-Host ""
    Write-Host "  LAUNCH"
    Write-Host ""
    Write-Host "  1) Start Claude Code" -ForegroundColor Cyan
    Write-Host "     Launch an interactive Claude Code session inside the DAAF"
    Write-Host "     container. Type /exit within Claude to return to this menu."
    Write-Host ""
    Write-Host "  2) Browse Files (VS Code)" -ForegroundColor Cyan
    Write-Host "     Open code-server (port 2720) for browser-based file browsing"
    Write-Host "     and editing. Useful for reviewing scripts and data files."
    Write-Host ""
    Write-Host "  3) View Session Logs" -ForegroundColor Cyan
    Write-Host "     Browse session transcripts from previous DAAF sessions."
    Write-Host "     Select a project or the full archive to view logs."
    Write-Host ""
    Write-Host "  4) View Marimo Notebooks (Python)" -ForegroundColor Cyan
    Write-Host "     Open the marimo notebook browser (port 2718). Browse, open,"
    Write-Host "     create, and edit research notebooks across all projects."
    Write-Host ""
    Write-Host "  5) View Quarto Notebooks (R)" -ForegroundColor Cyan
    Write-Host "     Search recursively for every .qmd under research/, select one"
    Write-Host "     to render and open, or cancel to return to this menu."
    Write-Host ""
    Write-Host "  6) Open Terminal in Container" -ForegroundColor Cyan
    Write-Host "     Open a terminal in the DAAF container."
    Write-Host "     Type 'exit' to return to this menu."
    Write-Host ""
    Write-Host "  MANAGE"
    Write-Host ""
    Write-Host "  7) Create Backup" -ForegroundColor Cyan
    Write-Host "     Create a timestamped backup of your DAAF Docker volume."
    Write-Host "     Backups are saved in the current directory."
    Write-Host ""
    Write-Host "  8) Restore from Backup" -ForegroundColor Cyan
    Write-Host "     Restore a previous backup to the DAAF Docker volume."
    Write-Host "     You will be prompted to select which backup to restore."
    Write-Host ""
    Write-Host "  9) Check for Updates" -ForegroundColor Cyan
    Write-Host "     Check for and apply updates to the DAAF framework."
    Write-Host ""
    Write-Host "  10) Rebuild Container" -ForegroundColor Cyan
    Write-Host "     Rebuild the DAAF Docker container from the latest image."
    Write-Host "     Your data volume is preserved during rebuilds."
    Write-Host ""
    Write-Host "  11) Restart Container" -ForegroundColor Cyan
    Write-Host "     Apply changes you made in environment_settings.txt (API keys,"
    Write-Host "     provider settings, ports). Stops and recreates the container,"
    Write-Host "     usually in under a minute -- no image build. It ends any open"
    Write-Host "     Claude Code session or web service. Settings marked"
    Write-Host "     `"rebuild required`" there (such as DAAF_DEV, or turning on the"
    Write-Host "     provider shim for the first time), and changes to the Dockerfile,"
    Write-Host "     packages, or docker-compose.yml, need Rebuild Container instead."
    Write-Host ""
    Write-Host "  12) Stop Web Services" -ForegroundColor Cyan
    Write-Host "     Stop any running web services (notebooks, log viewer,"
    Write-Host "     VS Code) without stopping the container itself."
    Write-Host ""
    Write-Host "  OTHER"
    Write-Host ""
    Write-Host "  h) Help" -ForegroundColor Cyan -NoNewline; Write-Host "  -- Show this help screen"
    Write-Host "  q) Quit" -ForegroundColor Cyan -NoNewline; Write-Host "  -- Exit the control panel"
    Write-Host ""
    $null = Read-DaafLine "  Press Enter to continue"
}

# ============================================================================
# Handler: Quit (option q)
# ============================================================================

function Invoke-DaafQuit {
    Write-Host ""
    Write-Host "Goodbye!"
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip the menu loop.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/daaf.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode for real executions only. Set-StrictMode is dynamically
# scoped, so placing it AFTER the DAAF_TEST_MODE guard keeps Pester's dot-sourcing
# (which returns above) from leaking strict mode into the whole test session. Because
# it is dynamically scoped, every function invoked from the main loop below -- the
# panel's own handlers AND the daaf_lib.ps1 helpers dot-sourced at the top -- runs
# under strict mode, so the library must stay strict-clean (it carries no directive of
# its own; see its header). Real runs are fully protected against uninitialized-variable
# and missing-property reads.
Set-StrictMode -Version 3.0

# ============================================================================
# Main Loop
# ============================================================================
# Wrapped in try/catch/finally so an unexpected failure prints a diagnostic and
# pauses -- a double-clicked window must not vanish before the error can be read
# (parity with daaf.sh's ERR + EXIT traps). Ctrl+C surfaces as a
# PipelineStoppedException, which we treat as a clean "Goodbye!".
#
# The loop is gated on the script-scoped $script:DaafMenuRunning flag rather than
# on captured handler return values. Quit paths (the `q` choice and Read-DaafChoice's
# EOF branch) clear the flag; every step below is a bare statement, so no ancestor
# of a handler captures the success stream. That is what lets the interactive
# delegates (Claude Code, container shell) receive real console handles for TTY
# allocation -- see Invoke-DaafChoice and Invoke-DaafDelegateInteractive.
$script:DaafMenuRunning = $true
# Defensive pre-init (all paths set CHOICE via Read-DaafChoice before the read
# below, but match the pre-init idiom applied elsewhere under strict mode).
$script:CHOICE = ""
try {
    while ($script:DaafMenuRunning) {
        Get-DaafStatus
        Show-DaafMenu
        Read-DaafChoice
        if (-not $script:DaafMenuRunning) { break }
        Invoke-DaafChoice $script:CHOICE
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: DAAF Control Panel hit an unexpected failure." -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  This is a bug -- please report it. The panel will now exit." -ForegroundColor Red
    # Pause so a double-clicked window does not vanish before the diagnostic can
    # be read. Skips the pause in nested/dry-run/non-interactive/redirected-stdin
    # contexts so CI smoke tests never block here.
    try { $pauseOk = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) }
    catch { $pauseOk = $false }
    if ((-not $env:DAAF_NESTED) -and ($env:DAAF_DRY_RUN -ne "1") -and $pauseOk) {
        $null = Read-DaafLine "Press Enter to close"
    }
    exit 1
}
