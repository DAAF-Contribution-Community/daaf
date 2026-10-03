# ============================================================================
# DAAF Shared Function Library (Windows PowerShell)
# ============================================================================
# Reusable functions for the DAAF Control Panel on Windows. Dot-source this
# file -- do not execute it directly:
#
#   $DaafLibDir = Split-Path -Parent $MyInvocation.MyCommand.Path
#   . (Join-Path $DaafLibDir "daaf_lib.ps1")
#
# This is the PowerShell counterpart to daaf_lib.sh. It provides the same
# helpers the Bash Control Panel relies on, adapted to PowerShell idiom:
#   Import-DaafSettingsFile -- export the whitelisted DAAF_* vars (four multi-instance
#                              keys + the DAAF_DEV build flag + the DAAF_BRANCH
#                              updater ref + the DAAF_DATA_VOLUME_NAME data-volume
#                              override) from environment_settings.txt, recording
#                              which keys it adopted from the file (provenance
#                              tracker $script:DaafKeysFromFile); throws if the
#                              file exists but cannot be read
#   Sync-DaafSettingsFile -- re-read environment_settings.txt after it was edited:
#                              drop only the keys the loader adopted from the file,
#                              then import again (user-set values keep winning);
#                              throws on an unreadable file, like the loader
#   Resolve-DaafDataVolumeName -- echo the resolved data-volume name, honoring the
#                              optional DAAF_DATA_VOLUME_NAME full-name override
#   Set-DaafSettingsKey -- insert/update a single KEY=value line in a settings
#                              file (write counterpart to Import-DaafSettingsFile)
#   Read-DaafLine       -- read one input line, working under redirected stdin (CI)
#   Open-DaafUrl        -- open a URL in the default browser (best-effort)
#   Test-DaafPort       -- test whether a port is listening inside the container
#   Confirm-DaafContainer -- start the DAAF container if it is not running
#   ConvertTo-DaafNativeArg -- quote one argument for a Windows-style command line
#                              (Start-Process -ArgumentList); canonical copy of a
#                              helper that standalone scripts carry INLINE
#
# Container-side probe payloads (the /proc/net/tcp + awk strings) are copied
# VERBATIM from daaf_lib.sh: they run inside the Linux container, so they must
# remain Linux shell, not PowerShell. Only the outer invocation wrapper is
# PowerShell here. The payloads are delivered as a base64 TOKEN passed as a
# native argument (transport v3): `bash -c 'echo $1 | base64 -d | bash ...' _ $b64`.
# A base64 token contains only [A-Za-z0-9+/=] -- no quotes, no spaces, no CR --
# so it survives PS 5.1's native-arg marshalling intact and involves no stdin.
# This replaced two earlier transports that both failed on real Windows:
#   v1 `bash -c <payload>` -- PS 5.1 mangles embedded double quotes in native
#      args (the awk `"` patterns); fixed only in PS 7.3+.
#   v2 `<payload> | bash -s` (stdin) -- PS appends CRLF when piping a string to
#      a native process, leaving a stray \r on the last line, and the PS
#      pipeline -> docker.exe npipe stdin wiring is unreliable on Windows.
# See Test-DaafPort for the fully annotated call site.
#
# Supports DAAF_DRY_RUN=1 for CI smoke testing without Docker.
#
# STRICT MODE: this library carries NO `Set-StrictMode` directive of its own, by
# design -- a directive here would impose strict mode on every caller (it is
# dynamically scoped and a dot-sourced library shares the caller's scope). This
# mirrors daaf_lib.sh, which likewise omits a `set` line. The entry points that
# dot-source this file (daaf.ps1, and the standalone scripts that inline the
# settings loader) enable `Set-StrictMode -Version 3.0` themselves, and because
# strict mode is dynamically scoped these functions run UNDER that strict mode at
# runtime. They must therefore stay strict-clean: no reads of never-assigned
# variables, no `.Count`/`.Length`/property access on `$null` or on scalars lacking
# them (wrap collection reads in `@(...)`), and no `$Matches` access after a failed
# `-match`. `$env:` reads are exempt (they never error under strict mode).
# ============================================================================

# Guard against redundant dot-sourcing. daaf.ps1 dot-sources this file, and a
# helper that dot-sources it again would merely redefine identical functions.
#
# The guard probes for one of THIS library's own functions rather than a module
# variable. A variable-based flag ($script:DaafLibLoaded) is unsafe under Pester:
# when the lib is first sourced inside a short-lived Pester scope, the function
# definitions vanish when that scope is discarded, but a flag set in a
# longer-lived parent scope can survive -- so a later dot-source (e.g. via
# daaf.ps1) would skip redefinition and the functions would be MISSING, causing
# CommandNotFoundException. Keying the guard on the presence of an actual
# function ties the "already loaded" signal to the same lifetime as the
# definitions themselves: if the functions were discarded, the probe misses and
# the lib re-defines them. Re-defining is safe -- this file only declares
# functions and has no non-idempotent load-time side effects.
if (Get-Command Read-DaafLine -ErrorAction SilentlyContinue) { return }

# --- Multi-Instance / Build-Flag Settings Loader ---
# PowerShell counterpart to daaf_lib.sh load_daaf_settings. Bridges
# environment_settings.txt -> process environment for the seven whitelisted
# DAAF_* variables: the four multi-instance keys so `docker compose`
# interpolation in docker-compose.yml (${DAAF_PROJECT_NAME:-daaf},
# ${DAAF_PORT_*:-27xx}) resolves them, plus DAAF_DEV, the opt-in
# BUILD flag consumed as `--build-arg DAAF_DEV=${DAAF_DEV:-0}`, plus DAAF_BRANCH,
# the updater's target ref (read env-only today; whitelisting it here lets a
# value persisted in environment_settings.txt reach update_daaf.ps1), plus
# DAAF_DATA_VOLUME_NAME, the optional full-name override for the research-workspace
# data volume (consumed by Resolve-DaafDataVolumeName below and by the backup /
# restore tools).
#
# WHY: environment_settings.txt is a compose `env_file` (feeds the CONTAINER
# env only). Compose *interpolation* (and build args) read the host/process
# environment and the project .env file, never env_file -- so these keys must be
# lifted into the process environment here for the project name / published
# ports / build flag to take effect.
#
# PARSING SAFETY: we never dot-source the file (it holds API keys with arbitrary
# characters). We extract only the seven known DAAF_* keys via a line scan and a
# regex on KEY=VALUE. CR is stripped for CRLF tolerance.
#
# PRECEDENCE: an already-set process env var WINS over the file value (matches
# Docker Compose precedence: shell env > .env file). Absent file = no-op. A file
# that exists but cannot be read (permissions, or locked by another program) =
# a terminating error, nothing adopted: the read uses -ErrorAction Stop, so it
# throws whatever the caller's $ErrorActionPreference is. Without that, a caller
# running under 'Continue' would get a non-terminating error and the function
# would carry on as if the file were empty. This is the twin of daaf_lib.sh's
# non-zero return.
#
# PROVENANCE: every key this function adopts from the file is added (once) to the
# script-scoped $script:DaafKeysFromFile list -- the PowerShell twin of daaf_lib.sh's
# _DAAF_KEYS_FROM_FILE. Keys that were already set when the loader ran (a user's
# own $env: value, or one adopted by an earlier call) are not re-adopted and so are
# not re-recorded. Sync-DaafSettingsFile (below) uses that record to re-read an
# edited file without a second hardcoded key list, so $known stays the single
# source of truth. The tracker is read through Get-Variable so a first call under
# the caller's Set-StrictMode never touches a never-assigned variable.
function Import-DaafSettingsFile {
    [CmdletBinding()]
    param(
        [string]$SettingsFile = "./environment_settings.txt"
    )

    if (-not (Test-Path -LiteralPath $SettingsFile)) {
        return
    }

    $known = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV', 'DAAF_BRANCH', 'DAAF_DATA_VOLUME_NAME')

    $tracked = @()
    $trackerVar = Get-Variable -Name 'DaafKeysFromFile' -Scope Script -ErrorAction SilentlyContinue
    if ($null -ne $trackerVar -and $null -ne $trackerVar.Value) { $tracked = @($trackerVar.Value) }

    # -Encoding UTF8 pins BOM-less UTF-8 decoding: a bare Get-Content on Windows
    # PowerShell 5.1 misreads BOM-less UTF-8 as legacy ANSI (cp1252), corrupting
    # any non-ASCII value. The write side (Set-DaafSettingsKey) is BOM-less UTF-8,
    # so reads must be pinned to match. Harmless on PS 7 (UTF-8 by default).
    # -ErrorAction Stop: an unreadable file throws here, before anything is
    # adopted and before the tracker below is written (see PRECEDENCE above).
    foreach ($rawLine in (Get-Content -LiteralPath $SettingsFile -Encoding UTF8 -ErrorAction Stop)) {
        $line = $rawLine -replace "`r", ""
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }

        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        # Extract the key WITHOUT trimming: a leading or trailing space means the
        # line is not flush at column 0, so it must fall through as unrecognized --
        # matching the bash loaders' column-0 `case` glob so a padded key like
        # "  DAAF_PROJECT_NAME=..." is rejected identically on both platforms.
        $key = $line.Substring(0, $eq)
        if ($known -notcontains $key) { continue }

        $val = $line.Substring($eq + 1)
        # Strip one layer of surrounding quotes if present.
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            if ($val.Length -ge 2) { $val = $val.Substring(1, $val.Length - 2) }
        }

        # Precedence: process env var wins. Only adopt the file value when the
        # variable is currently unset or empty.
        $current = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrEmpty($current)) {
            Set-Item -Path ("Env:" + $key) -Value $val
            # Record the adoption once (a duplicate KEY= line whose first value
            # was empty is adopted again but never listed twice).
            if ($tracked -notcontains $key) { $tracked += $key }
        }
    }

    $script:DaafKeysFromFile = $tracked
}

# --- Settings Reload (after environment_settings.txt was edited) ---
# PowerShell counterpart to daaf_lib.sh reload_daaf_settings. Re-read
# environment_settings.txt in a long-running session (the Control Panel) so edited
# DAAF_* values take effect. Calling Import-DaafSettingsFile a second time is NOT
# enough: its "already-set env wins" rule would keep every value it adopted on the
# first call, so a changed DAAF_PORT_MARIMO would be ignored by compose
# interpolation while env_file handed the container the new value.
#
# Design (no second key list): remove exactly the keys recorded in
# $script:DaafKeysFromFile, clear the record, and import again. Values the user set
# before launching were never recorded, so they still win. A key deleted from the
# file ends up unset, so the docker-compose.yml default applies again. Any key
# added to $known later takes part automatically. Only DAAF_* names are ever
# removed (defense in depth; the tracker is only written by the whitelist path).
#
# Throws what Import-DaafSettingsFile throws: a terminating error when the file
# exists but cannot be read. The tracked keys are removed BEFORE the read, so on
# that failure they stay unset and the tracker stays empty. A caller that must
# keep its settings (the Control Panel's Restart Container) snapshots them first
# and restores them on failure.
#
# Named Sync- (an approved verb outside PSScriptAnalyzer's
# PSUseShouldProcessForStateChangingFunctions list) rather than Update-/Reset-,
# which would demand SupportsShouldProcess ceremony for an in-process env refresh.
# Strict-clean: the tracker is read through Get-Variable, never as a bare variable.
function Sync-DaafSettingsFile {
    [CmdletBinding()]
    param(
        [string]$SettingsFile = "./environment_settings.txt"
    )

    $trackerVar = Get-Variable -Name 'DaafKeysFromFile' -Scope Script -ErrorAction SilentlyContinue
    if ($null -ne $trackerVar -and $null -ne $trackerVar.Value) {
        foreach ($key in @($trackerVar.Value)) {
            if ($key -like 'DAAF_*') {
                Remove-Item -Path ("Env:" + $key) -ErrorAction SilentlyContinue
            }
        }
    }
    $script:DaafKeysFromFile = @()
    Import-DaafSettingsFile -SettingsFile $SettingsFile
}

# --- Data Volume Name Resolver ---
# PowerShell counterpart to daaf_lib.sh resolve_data_volume_name. Return the
# Docker volume name that holds the DAAF research workspace (/daaf), honoring the
# optional DAAF_DATA_VOLUME_NAME full-name override.
#
# PRECEDENCE (returned to the caller):
#   1. DAAF_DATA_VOLUME_NAME, when set non-empty -> used VERBATIM as the full
#      volume name (no project prefix is added). This is the escape hatch for
#      pointing two installs at ONE shared workspace volume; it must match the
#      `name:` under the external `daaf-data` block in docker-compose.yml.
#   2. Otherwise "<project>_daaf-data", where <project> is DAAF_PROJECT_NAME or
#      the "daaf" default -- the Compose-prefixed default. So an UNSET
#      DAAF_DATA_VOLUME_NAME is byte-for-byte identical to the historical
#      hardcoded derivation, and a second instance with DAAF_PROJECT_NAME=daaf2
#      still owns "daaf2_daaf-data".
# A set-but-EMPTY DAAF_DATA_VOLUME_NAME falls through to the derived default: an
# empty string is falsy in PowerShell, so the `if ($env:DAAF_DATA_VOLUME_NAME)`
# guard treats empty and unset alike, matching the bash `:-` semantics and the
# way Import-DaafSettingsFile adopts a whitelisted key only when it is non-empty.
#
# The claude-config volume is deliberately NOT resolved here: per-install auth
# isolation is by design, so it keeps its project-prefixed default everywhere and
# has no analogous override.
#
# Callers that need a value persisted in environment_settings.txt to win should
# Import-DaafSettingsFile first (which bridges DAAF_DATA_VOLUME_NAME into the
# process env), then call this. Strict-clean: only $env: reads and string ops.
function Resolve-DaafDataVolumeName {
    [CmdletBinding()]
    param()
    if ($env:DAAF_DATA_VOLUME_NAME) {
        return $env:DAAF_DATA_VOLUME_NAME
    }
    $projectName = "daaf"
    if ($env:DAAF_PROJECT_NAME) { $projectName = $env:DAAF_PROJECT_NAME }
    return "${projectName}_daaf-data"
}

# --- Line Input ---
# Read one line of input from the user, compatible with both interactive
# terminals and redirected stdin (CI pipelines). Mirrors the pattern used in
# update_daaf.ps1 Read-UserChoice: probe [Environment]::UserInteractive and
# [Console]::IsInputRedirected so the helper works correctly under Pester
# dry-run (redirected) and a real terminal (interactive).
function Read-DaafLine {
    param([string]$Prompt = "")

    # Probe interactivity. Wrap in try/catch so any unusual host (e.g., a
    # constrained PS runspace) defaults to non-interactive rather than throwing.
    try { $isInteractive = [Environment]::UserInteractive -and (-not [Console]::IsInputRedirected) }
    catch { $isInteractive = $false }

    if ($isInteractive) {
        # Normal interactive terminal: Read-Host handles the prompt and line
        # buffering. Return $null on failure (e.g., Ctrl+Z on Windows).
        try { return Read-Host $Prompt }
        catch { return $null }
    } else {
        # Redirected stdin (CI, Pester dry-run, pipeline): echo the prompt text
        # without a trailing newline so log output is readable, then consume one
        # line from stdin. [Console]::In.ReadLine() returns $null at EOF.
        Write-Host -NoNewline $Prompt
        return [Console]::In.ReadLine()
    }
}

# --- Browser Open ---
# Open a URL in the default browser. Best-effort convenience -- failure to open
# is never fatal, mirroring daaf_lib.sh open_url which always returns 0.
function Open-DaafUrl {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Url
    )

    # Skip the actual open in dry-run mode (parity with daaf_lib.sh open_url).
    if ($env:DAAF_DRY_RUN -eq "1") { return }

    # Start-Process is the native Windows opener; on PowerShell 7 running on
    # macOS/Linux it also resolves the platform default handler. Any failure is
    # swallowed so a missing handler never aborts the caller.
    try {
        Start-Process $Url | Out-Null
    } catch {
        # No handler available (headless, restricted shell) -- silent fallback.
        Write-Verbose "Silenced: $_"
    }
}

# --- Native Argument Quoting ---
# Quote ONE argument so it survives the round trip through a Windows command
# line: Start-Process -ArgumentList string -> child process argv. CANONICAL
# definition; backup_daaf.ps1 and test_migration.ps1 are standalone (they do not
# dot-source this library) and carry an INLINE COPY of the function that must stay
# byte-identical to this one (pinned by tests/powershell/native_arg_quoting.Tests.ps1).
#
# WHY: Start-Process does NOT quote array elements. Its docs say it "joins the
# array into a single string with each element of the array separated by a single
# space", and the child then re-splits that string with the Windows argv rules
# (CommandLineToArgvW; .NET on Linux/macOS applies the same rules). So an element
# such as "C:\Users\John Smith\daaf-docker\backup_daaf.ps1" arrives as TWO argv
# entries, and an embedded double quote is silently stripped (PowerShell#5576,
# which lists Windows PowerShell 5.1 as affected). The issue's recommended
# workaround is ONE pre-joined string with the quoting done by the caller -- this
# helper does that quoting, and callers join its results with single spaces:
#
#   $argString = (@('-NoProfile', '-File', $childPath) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '
#   Start-Process -FilePath $exe -ArgumentList $argString ...
#
# RULES (the inverse of the Windows argv parser):
#   * A non-empty value with no whitespace and no double quote is returned bare.
#   * Otherwise the value is wrapped in double quotes, every run of backslashes
#     that precedes an embedded double quote is doubled and the quote escaped
#     (\"), and a trailing run of backslashes is doubled so it cannot escape the
#     closing quote. Backslashes elsewhere stay literal (C:\x y\z is unchanged
#     inside the quotes). The empty string becomes "" so it survives as an
#     explicit empty argument instead of vanishing. The trailing-run anchor is
#     \z, not $: in .NET, $ also matches just before a final newline, which
#     would double backslashes that are NOT at the end of the value.
# Verified round-trip values (tests): '', 'plain', 'with space', 'q"z',
# 'back\"slash', 'trail\', 'C:\Users\John Smith\OneDrive - Org\'.
#
# USAGE LIMITS:
#   * Pass ONE value per call, as an argument -- not an array and not piped
#     input. An array argument fails parameter binding ("Cannot convert value to
#     type System.String"); piped input is not accepted (binding error) and the
#     call still emits the default "" (both observed on pwsh 7). Map a list element
#     by element: `$parts | ForEach-Object { ConvertTo-DaafNativeArg $_ }`, then
#     -join ' '.
#     Filter $null elements out first (`Where-Object { $null -ne $_ }`): $null
#     binds as '' and becomes an explicit "" argument.
#   * Quoting protects whitespace, quotes, and backslashes -- it does NOT stop a
#     value with a leading '-' from binding as a PARAMETER NAME of a PowerShell
#     child launched with `-File` (the argv parser removes the quotes before the
#     child binds its parameters; observed on pwsh 7: a quoted "-Name" still
#     bound -Name). Never forward untrusted values after `-File <script>`.
#
# Prefer direct invocation (`& $exe @argArray`) when the call needs neither
# console inheritance nor a Process object to poll; PowerShell quotes each
# whitespace-bearing element itself on that path (Windows PowerShell 5.1 is
# reported to still mishandle an embedded double quote or a trailing backslash
# there; native argument passing was reworked in 7.3).
# Strict-clean (a [string] parameter never reads as $null).
function ConvertTo-DaafNativeArg {
    [CmdletBinding()]
    param([string]$Value = '')
    if ($Value.Length -gt 0 -and $Value -notmatch '[\s"]') { return $Value }
    return '"' + (($Value -replace '(\\*)"', '$1$1\"') -replace '(\\+)\z', '$1$1') + '"'
}

# --- Port Check ---
# Check if a service is listening on a port inside the DAAF container.
# Returns $true if listening, $false otherwise.
#
# The probe reads /proc/net/tcp{,6} directly INSIDE THE CONTAINER rather than
# shelling out to `ss` (not installed in the DAAF image). The probe string is
# copied verbatim from daaf_lib.sh check_port: column 2 is HEXIP:HEXPORT and
# column 4 is the socket state (0A = LISTEN); the target port is matched by its
# uppercase 4-hex-digit form. The awk END{exit !found} idiom sets the exec exit
# code, which surfaces as $LASTEXITCODE here. Only the PowerShell invocation
# wrapper differs from the Bash version.
function Test-DaafPort {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [ValidateNotNullOrEmpty()]
        [string]$Port
    )

    # In dry-run mode, consult DAAF_MOCK_PORTS instead of Docker. The value is a
    # space/comma-tolerant list of "<port>:yes" tokens (same variable name as
    # the daaf_lib.sh check_port mock).
    if ($env:DAAF_DRY_RUN -eq "1") {
        if ($env:DAAF_MOCK_PORTS -and ($env:DAAF_MOCK_PORTS -like "*${Port}:yes*")) {
            return $true
        }
        return $false
    }

    # Container-side probe payload -- VERBATIM from daaf_lib.sh check_port. It
    # still reads its target port from $1, so the container-side bash sees the
    # port as its own positional $1 (see the base64 transport below, which passes
    # the port as $2 to the outer `-c` wrapper and forwards it as $1 to the
    # decoded payload via `bash -s -- $2`).
    $probe = @'
        port="$1"
        ph=$(printf "%04X" "$port")
        awk -v ph="$ph" '$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}' \
            /proc/net/tcp /proc/net/tcp6 2>/dev/null
'@

    # TRANSPORT v3 -- base64-as-argument (do NOT revert to either prior form):
    #
    #   v1 (`bash -c $probe _ $Port`): FAILED. Windows PowerShell 5.1 does not
    #   correctly escape embedded double quotes when marshalling a string into a
    #   native process's argument vector (fixed only in PS 7.3+). This payload
    #   contains embedded `"` (the awk field patterns), so passing it via `-c`
    #   under PS 5.1 delivered a mangled script and the probe read "not
    #   listening" forever.
    #
    #   v2 (pipe the $probe string into `docker compose exec -T ... bash -s
    #   $Port` on stdin): FAILED in the field. Piping a PS string into a native
    #   process's stdin is unreliable on
    #   Windows: PowerShell appends a Windows CRLF, so the payload's last line
    #   carried a stray `\r` that broke the trailing awk redirect; and the
    #   PS-object-pipeline -> docker.exe (npipe) stdin wiring is itself flaky.
    #   Services worked but the probe never saw them.
    #
    #   v3 (this): encode the payload as base64 and pass the TOKEN as a native
    #   argument. A base64 token is drawn from [A-Za-z0-9+/=] only -- no quotes,
    #   no spaces, no CR -- so PS 5.1's arg marshalling cannot damage it, and
    #   stdin is not involved at all. The container decodes and runs it.
    #
    # Why this exact remote shape:
    #   * The single-quoted PS literal below contains spaces but ZERO double
    #     quotes, so PS 5.1 wraps it in "..." on the Win32 CommandLine and nothing
    #     inside needs escaping -- it arrives byte-intact. In PS single quotes,
    #     $1/$2 stay literal and become the CONTAINER bash's positional params
    #     (`_` is $0, the b64 token is $1, the port is $2).
    #   * `echo $1` is UNQUOTED deliberately: the base64 alphabet has no
    #     whitespace or glob characters, so word-splitting/globbing cannot harm
    #     it. Do NOT "fix" it to "$1" -- that would reintroduce double quotes into
    #     the single-quoted literal and put us back on the v1 failure path.
    #   * `bash -s -- $2` forwards the port to the decoded probe as its $1 (the
    #     `--` stops option parsing so a numeric port is never read as a flag).
    #   * ASCII encoding is correct: these host files are enforced-ASCII, and the
    #     here-string is byte-identical to the daaf_lib.sh payload.
    #
    # EAP = SilentlyContinue prevents PS 5.1 from promoting Docker's stderr to a
    # terminating error under the caller's global EAP = Stop. Fail-safe: any
    # non-zero exit (including "not listening") returns $false. Out-Null does not
    # touch $LASTEXITCODE, so it still reflects docker's exit.
    $b64 = [Convert]::ToBase64String([System.Text.Encoding]::ASCII.GetBytes($probe))
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose exec -T daaf-docker bash -c 'echo $1 | base64 -d | bash -s -- $2' _ $b64 $Port 2>$null | Out-Null
        $exit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }

    return ($exit -eq 0)
}

# --- Container Check ---
# Ensure the DAAF container is running, starting it if necessary.
# Returns $true on success, $false on failure. Mirrors daaf_lib.sh
# ensure_container; both use their return value as the single source of truth
# (no exported status variable), so callers use `if (Confirm-DaafContainer) { ... }`.
function Confirm-DaafContainer {
    [CmdletBinding()]
    param()

    # In dry-run mode, pretend the container is running (parity with daaf_lib.sh).
    if ($env:DAAF_DRY_RUN -eq "1") { return $true }

    # `docker compose ps -q daaf-docker` prints the RUNNING container's ID
    # (compose v2 lists running containers by default); empty = not running.
    # Derived from the compose project, so it tracks DAAF_PROJECT_NAME rather
    # than matching a hardcoded container name.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $cidRaw = docker compose ps -q daaf-docker 2>$null
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if (-not [string]::IsNullOrWhiteSpace(($cidRaw | Out-String))) {
        return $true
    }

    # Attempt to start the container.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose up -d 2>$null | Out-Null
        $exit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }

    return ($exit -eq 0)
}

# --- Settings-File Key Upsert ---
# PowerShell counterpart to daaf_lib.sh upsert_settings_key. Insert or update a
# single KEY=value line in a dotenv-style settings file (environment_settings.txt),
# preserving comments, key order, and surrounding layout. WRITE counterpart to
# Import-DaafSettingsFile (which only reads).
#
# Usage:
#   Set-DaafSettingsKey -File <path> -Key <name> -Value <val> [-Mode if-absent|replace] [-BackupSuffix <suffix>]
#     -Mode:         "if-absent" (default) writes only when no active KEY= line
#                    exists; "replace" rewrites an existing active line's value.
#     -BackupSuffix: optional; when given (e.g. ".pre-update") a one-time backup
#                    copy <File><suffix> is made before the first write, and only
#                    if it does not already exist.
#
# Placement rules mirror the Bash twin (git-config-style conservative default):
#   1. Active `KEY=` line -> if-absent leaves it; replace rewrites its value.
#   2. Commented example (`#KEY=` / `# KEY=`, first match) -> insert active line
#      directly below it.
#   3. Key absent entirely -> append under a dated provenance comment.
#
# ATOMICITY / ENCODING: writes to a temp file in the SAME directory then
# Move-Item -Force (rename). The payload is joined with "`n" (LF) and written via
# [System.IO.File]::WriteAllText with a UTF8Encoding($false) encoder so there is
# NO BOM -- Windows PowerShell 5.1's `-Encoding UTF8` writes a BOM, which
# corrupts the first key for the strict bash/Compose parser, so Set-Content /
# Out-File are deliberately NOT used for the payload. CR is stripped on read for
# CRLF-tolerance. $File is resolved to a full path so the .NET WriteAllText call
# (which honors [Environment]::CurrentDirectory, not $PWD) writes where intended.
#
# READ/WRITE ENCODINGS ARE A PAIR: the read below pins `-Encoding UTF8` for the
# same reason the write pins BOM-less UTF-8. This function WRITES BOM-less UTF-8,
# and BOM-less UTF-8 is exactly what Windows PowerShell 5.1's BARE `Get-Content`
# misreads as legacy ANSI (cp1252) -- mojibaking every multibyte character (any
# non-ASCII content, such as user-added comments or values -- the example template
# itself is deliberately pure ASCII, enforced by lint) once per read->rewrite
# cycle, so a single install that seeds N keys compounds the corruption N times. `-Encoding
# UTF8` decodes BOM-less UTF-8 correctly on PS 5.1 (the BOM hazard is write-only)
# and is harmless on PS 7 (UTF-8 by default). Never drop it while the write stays
# BOM-less -- the two are correct only together.
#
# DRY-RUN: when $env:DAAF_DRY_RUN -eq "1", print the intended action and the exact
# line that WOULD be written, and touch nothing on disk -- satisfies
# FRAMEWORK_INTEGRATION_CHECKLIST item HSM5.
#
# Strict-clean: no reads of never-assigned variables, collection reads guarded;
# runs under whatever Set-StrictMode the caller imposes (the library sets none).
#
# DUPLICATE KEYS (replace mode): "replace" updates the FIRST active `KEY=` line
# and assumes a single active occurrence per key. A settings file should never
# hold two active lines for the same key: Docker Compose's env_file ingestion is
# last-wins while DAAF's own loader (Import-DaafSettingsFile) is first-wins, so a
# duplicate already means the container and the host scripts would disagree on the
# value. If a file was hand-edited to contain duplicates, replace mode rewrites
# only the first and leaves later ones stale -- deduplicate the file by hand
# rather than relying on this function to reconcile it.
#
# SYMLINKED TARGET: the same-directory temp + Move-Item -Force REPLACES the
# settings path with a freshly written regular file. If -File is a symlink, the
# rename swaps the symlink itself for a regular file and the original link target
# is left untouched (stale) -- a symlinked environment_settings.txt is therefore
# not supported; point the tools at a real file.
function Set-DaafSettingsKey {
    [CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'Low')]
    param(
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$File,
        [Parameter(Mandatory)][ValidateNotNullOrEmpty()][string]$Key,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Value,
        [ValidateSet('if-absent', 'replace')][string]$Mode = 'if-absent',
        [string]$BackupSuffix = ''
    )

    if (-not (Test-Path -LiteralPath $File)) {
        Write-Error "Set-DaafSettingsKey: file not found: $File"
        return
    }
    # Resolve to a full path so [System.IO.File]::WriteAllText (which uses the
    # .NET current directory, not $PWD) targets the intended file.
    $File = (Resolve-Path -LiteralPath $File).Path

    # Read lines; Get-Content strips EOLs. Strip any stray CR for CRLF tolerance.
    # -Encoding UTF8 is REQUIRED and paired with the BOM-less UTF-8 write below
    # (see ATOMICITY / ENCODING above): a bare read on PS 5.1 would decode this
    # function's own BOM-less UTF-8 output as ANSI and mojibake it.
    $lines = @(Get-Content -LiteralPath $File -Encoding UTF8 | ForEach-Object { $_ -replace "`r", "" })

    $activeIdx = -1
    $commentIdx = -1
    $keyPattern = '^' + [regex]::Escape($Key) + '='
    $commentPattern = '^\s*#\s*' + [regex]::Escape($Key) + '='
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($activeIdx -lt 0 -and $lines[$i] -match $keyPattern) { $activeIdx = $i }
        if ($commentIdx -lt 0 -and $lines[$i] -match $commentPattern) { $commentIdx = $i }
    }

    $newLine = "$Key=$Value"
    $action = ''
    $out = New-Object System.Collections.Generic.List[string]

    if ($activeIdx -ge 0) {
        if ($Mode -ne 'replace') {
            Write-Host "Set-DaafSettingsKey: $Key skipped (exists)"
            return
        }
        if ($lines[$activeIdx] -eq $newLine) {
            Write-Host "Set-DaafSettingsKey: $Key unchanged (value already present)"
            return
        }
        for ($i = 0; $i -lt $lines.Count; $i++) {
            if ($i -eq $activeIdx) { $out.Add($newLine) } else { $out.Add($lines[$i]) }
        }
        $action = 'replaced'
    }
    elseif ($commentIdx -ge 0) {
        for ($i = 0; $i -lt $lines.Count; $i++) {
            $out.Add($lines[$i])
            if ($i -eq $commentIdx) { $out.Add($newLine) }
        }
        $action = 'inserted below commented example'
    }
    else {
        for ($i = 0; $i -lt $lines.Count; $i++) { $out.Add($lines[$i]) }
        if ($out.Count -gt 0 -and -not [string]::IsNullOrEmpty($out[$out.Count - 1])) {
            $out.Add('')
        }
        $out.Add('# Added by DAAF on ' + (Get-Date -Format 'yyyy-MM-dd'))
        $out.Add($newLine)
        $action = 'appended (new)'
    }

    if ($env:DAAF_DRY_RUN -eq '1') {
        Write-Host "[DRY-RUN] Set-DaafSettingsKey would write ${File}: $action"
        Write-Host "[DRY-RUN]   line: $newLine"
        return
    }

    if (-not $PSCmdlet.ShouldProcess($File, "Update settings key $Key ($action)")) {
        return
    }

    # One-time backup (only when a suffix was given and no backup exists yet).
    if (-not [string]::IsNullOrEmpty($BackupSuffix)) {
        $backupPath = $File + $BackupSuffix
        if (-not (Test-Path -LiteralPath $backupPath)) {
            Copy-Item -LiteralPath $File -Destination $backupPath -Confirm:$false
        }
    }

    # LF-joined payload, single trailing LF, UTF-8 NO BOM.
    $payload = ($out -join "`n") + "`n"
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)

    # Atomic write: temp in the SAME directory, then Move-Item -Force (rename).
    $dir = Split-Path -Parent $File
    if ([string]::IsNullOrEmpty($dir)) { $dir = '.' }
    $tmp = Join-Path $dir ('.daaf_upsert.' + [System.IO.Path]::GetRandomFileName())
    try {
        [System.IO.File]::WriteAllText($tmp, $payload, $utf8NoBom)
        Move-Item -LiteralPath $tmp -Destination $File -Force -Confirm:$false
    }
    catch {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -Confirm:$false }
        Write-Error "Set-DaafSettingsKey: write failed for ${File}: $_"
        return
    }

    Write-Host "Set-DaafSettingsKey: $Key $action"
}
