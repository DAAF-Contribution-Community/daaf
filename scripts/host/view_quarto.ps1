# ============================================================================
# DAAF Quarto Document Viewer (Windows PowerShell)
# ============================================================================
# Recursively discovers Quarto notebooks (.qmd) under research/, lets you select
# one, renders it to a single self-contained HTML file inside the DAAF container,
# copies the result out to your host machine, and opens it in your default
# browser. This is the R-notebook counterpart to view_notebooks.ps1 (which serves
# marimo for Python projects).
#
# Unlike marimo, Quarto notebooks are not served live -- they render to a static
# HTML file. This script closes that gap so you never have to run
# `quarto render` + `docker cp` by hand.
#
# Usage:
#   cd daaf-docker
#   .\view_quarto.ps1                                       # recursively select a .qmd notebook
#   .\view_quarto.ps1 2026-01-24_My_Project                # render the notebook in that project
#   .\view_quarto.ps1 research/2026-01-24_My_Project/notebook.qmd   # render a specific .qmd
#
# Output:
#   Rendered HTML is copied to .\quarto_html\ under your current directory
#   (created on first use). Output uses the notebook's flat basename, so notebooks
#   with the same basename overwrite one another. Set QUARTO_HTML_DIR to a
#   different directory when both outputs must be retained.
#
# Prerequisites:
#   - Docker Desktop installed and running
#   - An R project with a Quarto notebook (.qmd) under research/
#
# Supports $env:DAAF_TEST_MODE = "1" for Pester test dot-sourcing (see tests/).
# Supports DAAF_DRY_RUN=1 for CI cross-platform smoke testing (see tests/).
# ============================================================================

#Requires -Version 5.1
$ErrorActionPreference = "Stop"

function Wait-AndExit {
    param([int]$Code = 0)
    if ((-not $env:DAAF_NESTED) -and ($env:DAAF_DRY_RUN -ne "1")) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    exit $Code
}

# Read one picker line without assuming stdin is attached to a console. Read-Host
# provides the normal interactive prompt; redirected input uses Console.In and
# returns $null at EOF. This works on Windows PowerShell 5.1 and pwsh 7.
function Read-QuartoSelection {
    param([string]$Prompt)

    $inputRedirected = $false
    try { $inputRedirected = [Console]::IsInputRedirected }
    catch { $inputRedirected = $true }

    if (-not $inputRedirected) {
        return (Read-Host $Prompt)
    }

    Write-Host ($Prompt + ": ") -NoNewline
    return [Console]::In.ReadLine()
}

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# process environment so `docker compose` interpolation resolves the project name
# and published host ports. Canonical shared pattern (kept in sync with
# Import-DaafSettingsFile in daaf_lib.ps1); standalone scripts that do NOT
# dot-source daaf_lib.ps1 inline it. Parse only these whitelisted keys (never dot-source
# -- the file holds API keys); process env wins; absent file = no-op; CR stripped;
# PS 5.1 safe.
function Import-DaafSettingsInline {
    param([string]$SettingsFile = "./environment_settings.txt")
    if (-not (Test-Path -LiteralPath $SettingsFile)) { return }
    $known = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV', 'DAAF_BRANCH')
    # -Encoding UTF8: PS 5.1's bare Get-Content misreads BOM-less UTF-8 as ANSI
    # (cp1252); the settings writer is BOM-less UTF-8, so reads are pinned to match.
    foreach ($rawLine in (Get-Content -LiteralPath $SettingsFile -Encoding UTF8)) {
        $line = $rawLine -replace "`r", ""
        $trimmed = $line.Trim()
        if ($trimmed -eq "" -or $trimmed.StartsWith("#")) { continue }
        $eq = $line.IndexOf("=")
        if ($eq -lt 1) { continue }
        $key = $line.Substring(0, $eq).Trim()
        if ($known -notcontains $key) { continue }
        $val = $line.Substring($eq + 1)
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            if ($val.Length -ge 2) { $val = $val.Substring(1, $val.Length - 2) }
        }
        $current = [Environment]::GetEnvironmentVariable($key, "Process")
        if ([string]::IsNullOrEmpty($current)) {
            Set-Item -Path ("Env:" + $key) -Value $val
        }
    }
}
Import-DaafSettingsInline

# Host directory the rendered HTML is copied into (created on first use).
# Relative to the invoking directory so the user finds output right where they
# launched the script (their daaf-docker folder, next to docker-compose.yml).
if ([string]::IsNullOrEmpty($env:QUARTO_HTML_DIR)) {
    $QuartoHtmlDir = "./quarto_html"
} else {
    $QuartoHtmlDir = $env:QUARTO_HTML_DIR
}

# --- Dry-Run Support ---
# When DAAF_DRY_RUN=1, simulate Docker for CI cross-platform smoke testing. The
# recursive find returns a deep fixture. Later branches skip every host write,
# copy, output-directory resolution, and browser launch rather than merely
# replacing those operations with no-ops.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*compose ps -q daaf-docker*" { Write-Output "abc123" }
            "*compose up*" { return }
            "*base64 -d*bash -o pipefail*" { Write-Output "research/2026-07-15_Project/output/analysis/deep.qmd" }
            "*quarto render*" { return }
            "*compose exec*" { return }
            default {
                Write-Host "[DRY-RUN] docker $argStr"
                return
            }
        }
    }
}

# --- Test Mode Guard ---
# When dot-sourced for testing, define functions but skip execution.
# Usage: $env:DAAF_TEST_MODE = "1"; . ./scripts/host/view_quarto.ps1
if ($env:DAAF_TEST_MODE -eq "1") {
    return
}

# Enable strict mode AFTER the test-mode guard. Set-StrictMode is dynamically
# scoped, so placing it here keeps Pester's dot-sourcing (which returns above)
# from leaking strict mode into the whole test session, while real executions
# run fully protected from this point on.
Set-StrictMode -Version 3.0

# --- Parse arguments ---
# Optional single positional argument: a project folder name (under research/)
# or a direct path to a .qmd file. No argument => recursive discovery picker.
$TargetArg = ""
foreach ($a in $args) {
    if ($a -eq "-h" -or $a -eq "--help" -or $a -eq "-Help") {
        Write-Host "Usage: .\view_quarto.ps1                         # recursively discover and select a .qmd"
        Write-Host "       .\view_quarto.ps1 <project-folder>        # render the single .qmd in that project"
        Write-Host "       .\view_quarto.ps1 <path/to/notebook.qmd>  # render a specific .qmd file"
        Write-Host ""
        Write-Host "The picker accepts a number; 0, blank, q/Q, or EOF cancels cleanly."
        Write-Host "Rendered HTML is written to $QuartoHtmlDir\ and opened in your browser."
        Write-Host "Flat basenames overwrite on collision; set QUARTO_HTML_DIR to retain both."
        exit 0
    }
    if ($TargetArg -ne "") {
        Write-Host "ERROR: Too many arguments. Provide at most one project folder or .qmd path." -ForegroundColor Red
        Write-Host "  Try: .\view_quarto.ps1 --help"
        exit 1
    }
    $TargetArg = $a
}

# --- Preflight ---
if (-not (Test-Path "docker-compose.yml")) {
    Write-Host "ERROR: docker-compose.yml not found in the current directory." -ForegroundColor Red
    Write-Host "Please run this script from your daaf-docker folder."
    Wait-AndExit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Docker is either not installed or not configured properly in your system PATH to allow it to be used from Terminal." -ForegroundColor Red
    Write-Host "Please install Docker Desktop: https://www.docker.com/products/docker-desktop/"
    Wait-AndExit 1
}

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$null = docker info 2>&1
$ErrorActionPreference = $savedEAP
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker Desktop is not running. Please start it and try again." -ForegroundColor Red
    Wait-AndExit 1
}

# --- Start container if not running ---
# `docker compose ps -q daaf-docker` prints the running container's ID (empty
# when stopped), derived from the compose project rather than a hardcoded name.
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
$CidOutput = docker compose ps -q daaf-docker 2>&1
$ErrorActionPreference = $savedEAP
$Running = if ([string]::IsNullOrWhiteSpace(($CidOutput | Out-String))) { 0 } else { 1 }

if ($Running -eq 0) {
    Write-Host "Starting DAAF container..."
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose up -d
    $ErrorActionPreference = $savedEAP
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to start the container." -ForegroundColor Red
        Write-Host "  Try: docker compose logs daaf-docker" -ForegroundColor Yellow
        Wait-AndExit 1
    }
    Write-Host "Container started."
} else {
    Write-Host "DAAF container is running."
}

# --- Resolve the .qmd to render ---
# Three input shapes are accepted:
#   1. No argument              -> recursively discover and select under research/.
#   2. A project folder name    -> recursively find its single .qmd.
#   3. A direct .qmd path       -> use it verbatim (normalized to container-relative).
# Discovery is newline-delimited, so literal-newline filenames are unsupported.
# Spaces and ordinary shell metacharacters are preserved as literal path data.
# The final path handed to `quarto render` is relative to /daaf, the container's
# working_dir. Discovery programs and project values cross the Windows native
# process boundary as base64 tokens: the tokens contain no quotes or whitespace,
# avoiding Windows PowerShell 5.1 argument reconstruction of embedded quotes.
$GlobalDiscoveryScript = 'cd /daaf && find research -type f -name "*.qmd" -print | LC_ALL=C sort'
$ProjectDiscoveryScript = 'proj=$(printf "%s" "$1" | base64 -d) && cd /daaf && find "research/$proj" -type f -name "*.qmd" -print | LC_ALL=C sort'
$GlobalDiscoveryB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($GlobalDiscoveryScript))
$ProjectDiscoveryB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($ProjectDiscoveryScript))
$QmdRel = ""

if ($TargetArg -eq "") {
    Write-Host ""
    Write-Host "Discovering Quarto notebooks under research/ ..."
    Write-Host "Searching recursively at every depth."
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $QmdsRaw = @(docker compose exec -T daaf-docker bash -c 'echo $1 | base64 -d | bash -o pipefail' _ $GlobalDiscoveryB64 2>$null)
        $discoveryExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($discoveryExit -ne 0) {
        Write-Host "ERROR: Could not discover Quarto notebooks in the DAAF container." -ForegroundColor Red
        Write-Host "  Check Docker/container status, then try again."
        Wait-AndExit 1
    }

    # Remove CR line endings only. Do not Trim(): leading/trailing spaces are
    # meaningful path characters and must survive discovery unchanged.
    $QmdPaths = @()
    foreach ($rawPath in $QmdsRaw) {
        if ($null -eq $rawPath) { continue }
        $pathValue = ([string]$rawPath) -replace "`r", ""
        if ($pathValue -ne "") { $QmdPaths += $pathValue }
    }

    if ($QmdPaths.Count -eq 0) {
        Write-Host ""
        Write-Host "No Quarto notebooks (.qmd) found under research/." -ForegroundColor Yellow
        Write-Host "  Quarto notebooks are produced by R projects. If you expected one here,"
        Write-Host "  confirm the project finished assembling its notebook."
        Wait-AndExit 1
    }

    Write-Host ""
    Write-Host "Available Quarto notebooks:"
    Write-Host ""
    for ($i = 0; $i -lt $QmdPaths.Count; $i++) {
        Write-Host ("  {0}) {1}" -f ($i + 1), $QmdPaths[$i])
    }
    Write-Host "  0) Cancel"
    Write-Host ""

    if ($env:DAAF_DRY_RUN -eq "1") {
        $QmdRel = $QmdPaths[0]
        Write-Host "[DRY-RUN] Auto-selected 1) $QmdRel"
    } else {
        while ($true) {
            $selection = Read-QuartoSelection "Select a notebook (1-$($QmdPaths.Count), 0 to cancel)"
            if ($null -eq $selection -or $selection -eq "" -or $selection -eq "0" -or $selection -eq "q" -or $selection -eq "Q") {
                Write-Host "Quarto notebook selection cancelled."
                Wait-AndExit 0
            }

            if ($selection -notmatch '^[1-9][0-9]*$' -or $selection.Length -gt 9) {
                Write-Host "Invalid selection. Enter a number from 1 to $($QmdPaths.Count), or 0 to cancel." -ForegroundColor Yellow
                continue
            }

            $selectionNumber = 0
            if (-not [int]::TryParse($selection, [ref]$selectionNumber)) {
                Write-Host "Invalid selection. Enter a number from 1 to $($QmdPaths.Count), or 0 to cancel." -ForegroundColor Yellow
                continue
            }
            if ($selectionNumber -lt 1 -or $selectionNumber -gt $QmdPaths.Count) {
                Write-Host "Invalid selection. Enter a number from 1 to $($QmdPaths.Count), or 0 to cancel." -ForegroundColor Yellow
                continue
            }

            $QmdRel = $QmdPaths[$selectionNumber - 1]
            break
        }
    }
} elseif ($TargetArg -like "*.qmd") {
    # Direct .qmd path. Strip a leading ./ and /daaf/ so the value is relative
    # to the container working_dir (/daaf).
    $QmdRel = $TargetArg -replace "^\./", "" -replace "^/daaf/", ""
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        docker compose exec -T daaf-docker test -f "/daaf/$QmdRel" 2>$null
        $testExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($testExit -ne 0) {
        Write-Host "ERROR: Quarto notebook not found in the container: $QmdRel" -ForegroundColor Red
        Write-Host "  Run '.\view_quarto.ps1' with no arguments to select an available notebook."
        Wait-AndExit 1
    }
} else {
    # Keep the project value as a positional argument to container bash; never
    # interpolate host-provided text into the command source.
    $proj = ($TargetArg -replace "^research/", "").TrimEnd("/")
    $ProjectB64 = [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($proj))
    $savedEAP = $ErrorActionPreference
    try {
        $ErrorActionPreference = "SilentlyContinue"
        $FoundRaw = @(docker compose exec -T daaf-docker bash -c 'echo $1 | base64 -d | bash -o pipefail -s -- $2' _ $ProjectDiscoveryB64 $ProjectB64 2>$null)
        $projectDiscoveryExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedEAP
    }
    if ($projectDiscoveryExit -ne 0) {
        Write-Host "ERROR: Could not search project '$proj' for Quarto notebooks." -ForegroundColor Red
        Write-Host "  Check Docker/container status and the project name, then try again."
        Wait-AndExit 1
    }

    $FoundList = @()
    foreach ($rawFound in $FoundRaw) {
        if ($null -eq $rawFound) { continue }
        $foundValue = ([string]$rawFound) -replace "`r", ""
        if ($foundValue -ne "") { $FoundList += $foundValue }
    }

    if ($FoundList.Count -eq 0) {
        Write-Host "ERROR: No Quarto notebook (.qmd) found in project: $proj" -ForegroundColor Red
        Write-Host "  Run '.\view_quarto.ps1' with no arguments to select an available notebook."
        Wait-AndExit 1
    }

    if ($FoundList.Count -gt 1) {
        Write-Host "ERROR: Multiple Quarto notebooks found in project '$proj':" -ForegroundColor Red
        foreach ($f in $FoundList) { Write-Host "    $f" }
        Write-Host "  Re-run with the full .qmd path to pick one."
        Wait-AndExit 1
    }

    $QmdRel = $FoundList[0]
}

# --- Render inside the container ---
# `-M embed-resources:true` forces a SINGLE self-contained HTML regardless of
# whether the source .qmd's YAML sets it, so the copied-out file is fully
# portable (all CSS/JS/images inlined -- no sidecar _files/ directory to copy).
# Verified against Quarto 1.7.29: `-M embed-resources:true` produces one .html
# with no _files/ dir even when the .qmd YAML omits the setting.
$HtmlRel = $QmdRel -replace "\.qmd$", ".html"
$HtmlBasename = Split-Path -Leaf $HtmlRel

Write-Host ""
Write-Host "Rendering $QmdRel to a self-contained HTML file..."
Write-Host ""
$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose exec -T daaf-docker quarto render "/daaf/$QmdRel" --to html -M embed-resources:true
$renderExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
if ($renderExit -ne 0) {
    Write-Host ""
    Write-Host "ERROR: quarto render failed for $QmdRel." -ForegroundColor Red
    Write-Host "  The Quarto error output above shows what went wrong (a code chunk error," -ForegroundColor Yellow
    Write-Host "  a missing package, or malformed YAML frontmatter are the usual causes)." -ForegroundColor Yellow
    Wait-AndExit 1
}

# --- Copy the rendered HTML out to the host ---
# Preserve the existing flat-basename destination. Two notebooks with the same
# basename therefore share a destination and the later copy overwrites the
# earlier one; set QUARTO_HTML_DIR differently when both must be retained.
$HostHtml = Join-Path $QuartoHtmlDir $HtmlBasename

if ($env:DAAF_DRY_RUN -eq "1") {
    Write-Host ""
    Write-Host "[DRY-RUN] Render simulated for: $QmdRel"
    Write-Host "[DRY-RUN] Rendered document would be copied to: $HostHtml"
    Write-Host "[DRY-RUN] Skipping output-directory creation, copy, path resolution, and browser launch."
    Wait-AndExit 0
}

# `docker compose cp` resolves the service from the compose project, so it
# tracks DAAF_PROJECT_NAME just like the ps/exec calls above.
$null = New-Item -ItemType Directory -Path $QuartoHtmlDir -Force
$savedEAP = $ErrorActionPreference
try {
    $ErrorActionPreference = "SilentlyContinue"
    docker compose cp "daaf-docker:/daaf/$HtmlRel" $HostHtml
    $cpExit = $LASTEXITCODE
} finally {
    $ErrorActionPreference = $savedEAP
}
if ($cpExit -ne 0) {
    Write-Host ""
    Write-Host "ERROR: Failed to copy the rendered HTML out of the container." -ForegroundColor Red
    Write-Host "  The render succeeded, so the file exists at /daaf/$HtmlRel inside" -ForegroundColor Yellow
    Write-Host "  the container. You can copy it manually with:" -ForegroundColor Yellow
    Write-Host "    docker compose cp daaf-docker:/daaf/$HtmlRel $HostHtml" -ForegroundColor Yellow
    Wait-AndExit 1
}

Write-Host ""
Write-Host "Rendered document copied to: $HostHtml"

# --- Open in the default browser ---
# Start-Process is the native Windows opener and resolves the platform default
# handler on PS 7 (macOS/Linux) too. Any failure is swallowed -- the path is
# printed above regardless, so the user can always open it by hand.
$AbsHtmlDir = (Resolve-Path -LiteralPath $QuartoHtmlDir).Path
$AbsHtml = Join-Path $AbsHtmlDir $HtmlBasename
try {
    $null = Start-Process $AbsHtml
    Write-Host "Opening in your default browser..."
} catch {
    Write-Host "Open it in your browser to view:"
    Write-Host "  $AbsHtml"
}

Wait-AndExit 0
