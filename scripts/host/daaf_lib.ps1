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
#   Import-DaafSettings -- export DAAF_* multi-instance vars from environment_settings.txt
#   Read-DaafLine       -- read one input line, working under redirected stdin (CI)
#   Open-DaafUrl        -- open a URL in the default browser (best-effort)
#   Test-DaafPort       -- test whether a port is listening inside the container
#   Confirm-DaafContainer -- start the DAAF container if it is not running
#
# Container-side probe payloads (the /proc/net/tcp + awk strings) are copied
# VERBATIM from daaf_lib.sh: they run inside the Linux container via
# `docker compose exec ... bash -c '<payload>'`, so they must remain Linux
# shell, not PowerShell. Only the outer invocation wrapper is PowerShell here.
#
# Supports DAAF_DRY_RUN=1 for CI smoke testing without Docker.
# ============================================================================

# Guard against double dot-sourcing. daaf.ps1 dot-sources this file, and a
# helper that dot-sources it again would redefine functions harmlessly, but the
# guard keeps behavior explicit and cheap.
if ($script:DaafLibLoaded) { return }
$script:DaafLibLoaded = $true

# --- Multi-Instance Settings Loader ---
# PowerShell counterpart to daaf_lib.sh load_daaf_settings. Bridges
# environment_settings.txt -> process environment for the four multi-instance
# DAAF_* variables so `docker compose` interpolation in docker-compose.yml
# (${DAAF_PROJECT_NAME:-daaf}, ${DAAF_PORT_*:-27xx}) resolves them.
#
# WHY: environment_settings.txt is a compose `env_file` (feeds the CONTAINER
# env only). Compose *interpolation* reads the host/process environment and the
# project .env file, never env_file -- so these four keys must be lifted into the
# process environment here for the project name / published ports to change.
#
# PARSING SAFETY: we never dot-source the file (it holds API keys with arbitrary
# characters). We extract only the four known DAAF_* keys via a line scan and a
# regex on KEY=VALUE. CR is stripped for CRLF tolerance.
#
# PRECEDENCE: an already-set process env var WINS over the file value (matches
# Docker Compose precedence: shell env > .env file). Absent file = no-op.
function Import-DaafSettings {
    [CmdletBinding()]
    param(
        [string]$SettingsFile = "./environment_settings.txt"
    )

    if (-not (Test-Path -LiteralPath $SettingsFile)) {
        return
    }

    $known = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE')

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

    # Container-side probe payload -- VERBATIM from daaf_lib.sh check_port. The
    # port is passed as a positional argument after the `bash -c '...' _ <port>`
    # sentinel so awk internals and $1 stay literal in the container shell.
    $probe = @'
        port="$1"
        ph=$(printf "%04X" "$port")
        awk -v ph="$ph" '$2 ~ ":"ph"$" && $4 == "0A" {found=1} END {exit !found}' \
            /proc/net/tcp /proc/net/tcp6 2>/dev/null
'@

    # EAP = SilentlyContinue prevents PS 5.1 from promoting Docker's stderr to a
    # terminating error under the caller's global EAP = Stop. Fail-safe: any
    # non-zero exit (including "not listening") returns $false.
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose exec -T daaf-docker bash -c $probe _ $Port 2>$null | Out-Null
        $exit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }

    return ($exit -eq 0)
}

# --- Container Check ---
# Ensure the DAAF container is running, starting it if necessary.
# Returns $true on success, $false on failure. Mirrors daaf_lib.sh
# ensure_container (which set CONTAINER_RUNNING); here the boolean return is the
# single source of truth so callers use `if (Confirm-DaafContainer) { ... }`.
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
