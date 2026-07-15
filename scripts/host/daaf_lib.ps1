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
#                              updater ref) from environment_settings.txt
#   Set-DaafSettingsKey -- insert/update a single KEY=value line in a settings
#                              file (write counterpart to Import-DaafSettingsFile)
#   Read-DaafLine       -- read one input line, working under redirected stdin (CI)
#   Open-DaafUrl        -- open a URL in the default browser (best-effort)
#   Test-DaafPort       -- test whether a port is listening inside the container
#   Confirm-DaafContainer -- start the DAAF container if it is not running
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
# environment_settings.txt -> process environment for the six whitelisted
# DAAF_* variables: the four multi-instance keys so `docker compose`
# interpolation in docker-compose.yml (${DAAF_PROJECT_NAME:-daaf},
# ${DAAF_PORT_*:-27xx}) resolves them, plus DAAF_DEV, the opt-in
# BUILD flag consumed as `--build-arg DAAF_DEV=${DAAF_DEV:-0}`, plus DAAF_BRANCH,
# the updater's target ref (read env-only today; whitelisting it here lets a
# value persisted in environment_settings.txt reach update_daaf.ps1).
#
# WHY: environment_settings.txt is a compose `env_file` (feeds the CONTAINER
# env only). Compose *interpolation* (and build args) read the host/process
# environment and the project .env file, never env_file -- so these keys must be
# lifted into the process environment here for the project name / published
# ports / build flag to take effect.
#
# PARSING SAFETY: we never dot-source the file (it holds API keys with arbitrary
# characters). We extract only the six known DAAF_* keys via a line scan and a
# regex on KEY=VALUE. CR is stripped for CRLF tolerance.
#
# PRECEDENCE: an already-set process env var WINS over the file value (matches
# Docker Compose precedence: shell env > .env file). Absent file = no-op.
function Import-DaafSettingsFile {
    [CmdletBinding()]
    param(
        [string]$SettingsFile = "./environment_settings.txt"
    )

    if (-not (Test-Path -LiteralPath $SettingsFile)) {
        return
    }

    $known = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV', 'DAAF_BRANCH')

    foreach ($rawLine in (Get-Content -LiteralPath $SettingsFile)) {
        $line = $rawLine -replace "`r", ""
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }

        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
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
        }
    }
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
    [CmdletBinding()]
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
    $lines = @(Get-Content -LiteralPath $File | ForEach-Object { $_ -replace "`r", "" })

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

    # One-time backup (only when a suffix was given and no backup exists yet).
    if (-not [string]::IsNullOrEmpty($BackupSuffix)) {
        $backupPath = $File + $BackupSuffix
        if (-not (Test-Path -LiteralPath $backupPath)) {
            Copy-Item -LiteralPath $File -Destination $backupPath
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
        Move-Item -LiteralPath $tmp -Destination $File -Force
    }
    catch {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
        Write-Error "Set-DaafSettingsKey: write failed for ${File}: $_"
        return
    }

    Write-Host "Set-DaafSettingsKey: $Key $action"
}
