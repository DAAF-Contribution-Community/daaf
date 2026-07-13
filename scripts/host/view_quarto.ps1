# ============================================================================
# DAAF Quarto Document Viewer (Windows PowerShell)
# ============================================================================
# Renders a Quarto notebook (.qmd) to a single self-contained HTML file inside
# the DAAF container, copies the result out to your host machine, and opens it
# in your default browser. This is the R-notebook counterpart to
# view_notebooks.ps1 (which serves marimo for Python projects).
#
# Unlike marimo, Quarto notebooks are not served live -- they render to a static
# HTML file. This script closes that gap so you never have to run
# `quarto render` + `docker cp` by hand.
#
# Usage:
#   cd daaf-docker
#   .\view_quarto.ps1                                       # list available .qmd notebooks
#   .\view_quarto.ps1 2026-01-24_My_Project                # render the notebook in that project
#   .\view_quarto.ps1 research/2026-01-24_My_Project/notebook.qmd   # render a specific .qmd
#
# Output:
#   Rendered HTML is copied to .\quarto_html\ under your current directory
#   (created on first use). Each render overwrites the file of the same name.
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
    if (-not $env:DAAF_NESTED) {
        Write-Host ""
        Read-Host "Press Enter to continue"
    }
    exit $Code
}

# --- Multi-instance settings (shared pattern) ---
# Bridge environment_settings.txt's four DAAF_* multi-instance keys into the
# process environment so `docker compose` interpolation resolves the project name
# and published host ports. Canonical shared pattern (kept in sync with
# Import-DaafSettingsFile in daaf_lib.ps1); standalone scripts that do NOT
# dot-source daaf_lib.ps1 inline it. Parse only these four keys (never dot-source
# -- the file holds API keys); process env wins; absent file = no-op; CR stripped;
# PS 5.1 safe.
function Import-DaafSettingsInline {
    param([string]$SettingsFile = "./environment_settings.txt")
    if (-not (Test-Path -LiteralPath $SettingsFile)) { return }
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
# When DAAF_DRY_RUN=1, simulate external commands (Docker) for CI cross-platform
# smoke testing without a Docker daemon. The find arm echoes a fake .qmd path so
# discovery listing has content; render and cp are no-ops.
if ($env:DAAF_DRY_RUN -eq "1") {
    function docker {
        $argStr = $args -join ' '
        $global:LASTEXITCODE = 0
        switch -Wildcard ($argStr) {
            "*info*" { return }
            "*compose ps -q daaf-docker*" { Write-Output "abc123" }
            "*compose up*" { return }
            "*find research*" { Write-Output "research/2026-01-24_Sample_R_Project/2026-01-24_Sample_R_Project.qmd" }
            "*find `"research*" { Write-Output "research/2026-01-24_Sample_R_Project/2026-01-24_Sample_R_Project.qmd" }
            "*quarto render*" { return }
            "*compose cp*" { return }
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
# or a direct path to a .qmd file. No argument => discovery-listing mode.
$TargetArg = ""
foreach ($a in $args) {
    if ($a -eq "-h" -or $a -eq "--help" -or $a -eq "-Help") {
        Write-Host "Usage: .\view_quarto.ps1                         # list available .qmd notebooks"
        Write-Host "       .\view_quarto.ps1 <project-folder>        # render the .qmd in that research project"
        Write-Host "       .\view_quarto.ps1 <path/to/notebook.qmd>  # render a specific .qmd file"
        Write-Host ""
        Write-Host "Rendered HTML is written to $QuartoHtmlDir\ and opened in your browser."
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
#   1. No argument              -> list all .qmd files under research/ and exit.
#   2. A project folder name    -> find the .qmd inside research/<name>/.
#   3. A direct .qmd path       -> use it verbatim (normalized to container-relative).
# The .qmd path handed to `quarto render` is expressed relative to /daaf inside
# the container, because the container's working_dir is /daaf.
$QmdRel = ""

if ($TargetArg -eq "") {
    # --- Discovery mode: list available notebooks ---
    Write-Host ""
    Write-Host "Discovering Quarto notebooks under research/ ..."
    # `find` runs inside the container (its GNU userland is guaranteed); results
    # are paths relative to /daaf. -maxdepth keeps this to project-level notebooks.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $QmdsRaw = docker compose exec -T daaf-docker bash -c 'cd /daaf && find research -maxdepth 3 -name "*.qmd" -type f 2>/dev/null | sort' 2>$null
    $ErrorActionPreference = $savedEAP
    $QmdsText = (($QmdsRaw | Out-String) -replace "`r", "").Trim()

    if ([string]::IsNullOrWhiteSpace($QmdsText)) {
        Write-Host ""
        Write-Host "No Quarto notebooks (.qmd) found under research/." -ForegroundColor Yellow
        Write-Host "  Quarto notebooks are produced by R projects. If you expected one here,"
        Write-Host "  confirm the project finished assembling its notebook."
        Wait-AndExit 1
    }

    Write-Host ""
    Write-Host "Available Quarto notebooks:"
    Write-Host ""
    foreach ($qmdPath in ($QmdsText -split "`n")) {
        $trimmedPath = $qmdPath.Trim()
        if ($trimmedPath -ne "") {
            Write-Host "  $trimmedPath"
        }
    }
    Write-Host ""
    Write-Host "To render one, re-run with its project folder or path, e.g.:"
    Write-Host "  .\view_quarto.ps1 <project-folder>"
    Write-Host "  .\view_quarto.ps1 <path/to/notebook.qmd>"
    Wait-AndExit 0
}

if ($TargetArg -like "*.qmd") {
    # Direct .qmd path. Strip a leading ./ and a leading /daaf/ so the value is
    # expressed relative to the container working_dir (/daaf).
    $QmdRel = $TargetArg -replace "^\./", "" -replace "^/daaf/", ""
    # Confirm it exists inside the container before attempting a render.
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    docker compose exec -T daaf-docker test -f "/daaf/$QmdRel" 2>$null
    $testExit = $LASTEXITCODE
    $ErrorActionPreference = $savedEAP
    if ($testExit -ne 0) {
        Write-Host "ERROR: Quarto notebook not found in the container: $QmdRel" -ForegroundColor Red
        Write-Host "  Run '.\view_quarto.ps1' with no arguments to list available notebooks."
        Wait-AndExit 1
    }
} else {
    # Treat the argument as a project folder name (with or without a leading
    # research/). Find the single .qmd inside it.
    $proj = ($TargetArg -replace "^research/", "").TrimEnd("/")
    $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
    $FoundRaw = docker compose exec -T daaf-docker bash -c 'cd /daaf && find "research/$1" -maxdepth 2 -name "*.qmd" -type f 2>/dev/null | sort' _ $proj 2>$null
    $ErrorActionPreference = $savedEAP
    $FoundText = (($FoundRaw | Out-String) -replace "`r", "").Trim()

    if ([string]::IsNullOrWhiteSpace($FoundText)) {
        Write-Host "ERROR: No Quarto notebook (.qmd) found in project: $proj" -ForegroundColor Red
        Write-Host "  Run '.\view_quarto.ps1' with no arguments to list available notebooks."
        Wait-AndExit 1
    }

    $FoundList = @($FoundText -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
    # If multiple .qmd files exist in the project, ask the user to be specific
    # rather than guessing which one they meant.
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
# `docker compose cp` copies from the container to the host without needing a
# raw container name (it resolves the service from the compose project, so it
# tracks DAAF_PROJECT_NAME just like the ps/exec calls above).
$null = New-Item -ItemType Directory -Path $QuartoHtmlDir -Force
$HostHtml = Join-Path $QuartoHtmlDir $HtmlBasename

$savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
docker compose cp "daaf-docker:/daaf/$HtmlRel" $HostHtml
$cpExit = $LASTEXITCODE
$ErrorActionPreference = $savedEAP
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
# handler on PS 7 (macOS/Linux) too. In dry-run mode we skip the actual open so
# CI never launches a browser. Any failure is swallowed -- the path is printed
# above regardless, so the user can always open it by hand.
#
# Build the absolute path from the (existing) output DIRECTORY plus the file
# basename rather than Resolve-Path on the file itself: under DAAF_DRY_RUN the
# `docker compose cp` above is a no-op, so the HTML file does not exist and a
# LiteralPath resolve of it would throw. The directory always exists (New-Item
# -Force created it), so resolving that and joining the basename is safe in both
# real and dry-run runs. Mirrors the Bash twin's `cd $(dirname) && pwd` pattern.
$AbsHtmlDir = (Resolve-Path -LiteralPath $QuartoHtmlDir).Path
$AbsHtml = Join-Path $AbsHtmlDir $HtmlBasename
if ($env:DAAF_DRY_RUN -ne "1") {
    try {
        Start-Process $AbsHtml | Out-Null
        Write-Host "Opening in your default browser..."
    } catch {
        Write-Host "Open it in your browser to view:"
        Write-Host "  $AbsHtml"
    }
} else {
    Write-Host "Open it in your browser to view:"
    Write-Host "  $AbsHtml"
}

Wait-AndExit 0
