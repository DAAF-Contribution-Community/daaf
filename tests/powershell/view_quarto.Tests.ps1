# ============================================================================
# Pester tests for view_quarto.ps1 -- DAAF Quarto Document Viewer (Windows)
# ============================================================================
# Tests cover syntax validation, script structure, dry-run behavior (discovery
# and render), and structural markers. Mirrors view_quarto.bats for
# cross-platform parity.
# ============================================================================

Describe "view_quarto.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    # =====================================================================
    # Tier 1 -- Syntax
    # =====================================================================

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/view_quarto.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    # =====================================================================
    # Tier 3 -- Script structure
    # =====================================================================

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/view_quarto.ps1" -Raw
        }

        It "declares #Requires -Version 5.1" {
            $Content | Should -Match '#Requires\s+-Version\s+5\.1'
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "enables Set-StrictMode -Version 3.0" {
            $Content | Should -Match 'Set-StrictMode\s+-Version\s+3\.0'
        }

        It "places Set-StrictMode after the test-mode guard" {
            # Strict mode is dynamically scoped: placing it before the guard would
            # leak into Pester's dot-sourced test session. It must come after.
            $guardIdx = $Content.IndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx | Should -BeGreaterThan -1
            $strictIdx | Should -BeGreaterThan $guardIdx
        }

        It "defines Wait-AndExit function" {
            $Content | Should -Match 'function Wait-AndExit'
        }

        It "checks DAAF_NESTED in Wait-AndExit" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "suppresses its standalone pause during dry-run" {
            $Content | Should -Match '\(-not \$env:DAAF_NESTED\).*DAAF_DRY_RUN -ne "1"'
        }

        It "checks for docker-compose.yml" {
            $Content | Should -Match 'docker-compose\.yml'
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "checks Docker daemon with docker info" {
            $Content | Should -Match 'docker info'
        }

        It "starts container if not running" {
            $Content | Should -Match 'Starting DAAF container'
        }

        It "invokes quarto render" {
            $Content | Should -Match 'quarto render'
        }

        It "forces embed-resources for a self-contained HTML" {
            $Content | Should -Match 'embed-resources:true'
        }

        It "copies the rendered HTML out with docker compose cp" {
            $Content | Should -Match 'compose cp'
        }

        It "supports DAAF_TEST_MODE guard" {
            $Content | Should -Match 'DAAF_TEST_MODE'
        }

        It "supports DAAF_DRY_RUN" {
            $Content | Should -Match 'DAAF_DRY_RUN'
        }

        It "handles quarto render failure" {
            $Content | Should -Match 'quarto render failed'
        }

        It "reports container already running" {
            $Content | Should -Match 'DAAF container is running'
        }

        It "extracts the settings key column-0 strict (no .Trim(), rejects padded keys like bash)" {
            # Import-DaafSettingsInline must extract the key WITHOUT .Trim() so a
            # whitespace-padded "  DAAF_PROJECT_NAME=..." line falls through as
            # unrecognized -- matching the bash loaders' column-0 `case` glob. The
            # pre-fix `.Substring(0, $eq).Trim()` accepted padded keys, diverging from
            # bash across the PS loader copies.
            $Content | Should -Match '\$key = \$line\.Substring\(0, \$eq\)'
            $Content | Should -Not -Match '\$key = \$line\.Substring\(0, \$eq\)\.Trim\(\)'
        }
    }
}

# ============================================================================
# Tier 5 -- Dry-run mode
# ============================================================================

Describe "view_quarto.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-test-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "discovery mode offers the recursive picker with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_quarto.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Discovering Quarto notebooks under research/*"
        ($output | Out-String) | Should -BeLike "*Searching recursively at every depth.*"
        ($output | Out-String) | Should -BeLike "*Available Quarto notebooks*"
    }

    It "reports container running in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_quarto.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*DAAF container is running*"
    }

    It "renders a direct .qmd path in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_quarto.ps1" "research/2026-01-24_Sample_R_Project/2026-01-24_Sample_R_Project.qmd" *>&1
        ($output | Out-String) | Should -BeLike "*copied to*"
    }

    It "renders a project folder in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_quarto.ps1" "2026-01-24_Sample_R_Project" *>&1
        ($output | Out-String) | Should -BeLike "*copied to*"
    }

    It "completes quickly in dry-run (no blocking)" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $null = & "$RepoRoot/scripts/host/view_quarto.ps1" *>&1
        $sw.Stop()
        $sw.Elapsed.TotalSeconds | Should -BeLessThan 5
    }
}

# ============================================================================
# Tier 7 -- Recursive discovery and picker behavior
# ============================================================================

Describe "view_quarto.ps1 recursive discovery and picker" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        function Invoke-QuartoViewerProcess {
            param(
                [string[]]$InputLines = @(),
                [string]$Target = ""
            )

            $psExe = (Get-Process -Id $PID).Path
            $wrapperArgs = @('-NoProfile', '-File', $script:ViewerWrapper, $RepoRoot, $Target)
            $captured = @($InputLines | & $psExe @wrapperArgs 2>&1)
            $script:ViewerLastExit = $LASTEXITCODE
            return ($captured | Out-String)
        }
        $script:OrigNested = $env:DAAF_NESTED
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigDiscovery = $env:MOCK_VIEWER_DISCOVERY_OUTPUT
        $script:OrigDiscoveryExit = $env:MOCK_VIEWER_DISCOVERY_EXIT
        $script:OrigFileExit = $env:MOCK_VIEWER_FILE_EXIT
        $script:OrigHtmlDir = $env:QUARTO_HTML_DIR
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-viewer-$(Get-Random)")
        $script:ViewerWrapper = Join-Path $script:TestDir "viewer-wrapper.ps1"
        $script:ViewerLog = Join-Path $script:TestDir "viewer-docker.log"
        $script:ViewerHtmlDir = Join-Path $script:TestDir "viewer-html"
        Push-Location $script:TestDir
        New-FakeComposeFile -Directory $script:TestDir

        $wrapper = @'
param([string]$RepoRoot, [string]$Target)
$env:DAAF_NESTED = "1"
$ErrorActionPreference = "Stop"
function docker {
    $parts = @("docker")
    foreach ($part in $args) { $parts += "<$part>" }
    [System.IO.File]::AppendAllText($env:MOCK_VIEWER_LOG, (($parts -join " ") + [Environment]::NewLine))
    $argText = $args -join " "
    $global:LASTEXITCODE = 0
    if ($argText -eq "info") { return }
    if ($argText -like "compose ps -q daaf-docker*") { Write-Output "abc123"; return }
    if ($argText -like "compose up*") { return }
    if ($argText -like "compose exec*test -f*") {
        $global:LASTEXITCODE = [int]$env:MOCK_VIEWER_FILE_EXIT
        return
    }
    if ($argText -like "compose exec*bash -c*") {
        $global:LASTEXITCODE = [int]$env:MOCK_VIEWER_DISCOVERY_EXIT
        $underscoreIndex = -1
        for ($i = 0; $i -lt $args.Count; $i++) {
            if ([string]$args[$i] -eq "_") { $underscoreIndex = $i; break }
        }
        if ($underscoreIndex -ge 0 -and ($underscoreIndex + 1) -lt $args.Count) {
            $decodedScript = [System.Text.Encoding]::UTF8.GetString(
                [Convert]::FromBase64String([string]$args[$underscoreIndex + 1])
            )
            [System.IO.File]::AppendAllText($env:MOCK_VIEWER_LOG, ("decoded-script <" + $decodedScript + ">" + [Environment]::NewLine))
            if (($underscoreIndex + 2) -lt $args.Count) {
                $decodedProject = [System.Text.Encoding]::UTF8.GetString(
                    [Convert]::FromBase64String([string]$args[$underscoreIndex + 2])
                )
                [System.IO.File]::AppendAllText($env:MOCK_VIEWER_LOG, ("decoded-project <" + $decodedProject + ">" + [Environment]::NewLine))
            }
        }
        if ($global:LASTEXITCODE -eq 0 -and -not [string]::IsNullOrEmpty($env:MOCK_VIEWER_DISCOVERY_OUTPUT)) {
            @($env:MOCK_VIEWER_DISCOVERY_OUTPUT -split "`n") | Sort-Object | ForEach-Object { Write-Output $_ }
        }
        return
    }
    if ($argText -like "compose exec*quarto render*") { return }
    if ($argText -like "compose cp*") { return }
}
function Start-Process {
    param([Parameter(ValueFromRemainingArguments = $true)]$Remaining)
    [System.IO.File]::AppendAllText($env:MOCK_VIEWER_LOG, ("Start-Process <" + ($Remaining -join "><") + ">" + [Environment]::NewLine))
}
if ([string]::IsNullOrEmpty($Target)) {
    & "$RepoRoot/scripts/host/view_quarto.ps1"
    $viewerSuccess = $?
} else {
    & "$RepoRoot/scripts/host/view_quarto.ps1" $Target
    $viewerSuccess = $?
}
if ($viewerSuccess) { exit 0 } else { exit 1 }
'@
        Set-Content -LiteralPath $script:ViewerWrapper -Value $wrapper -Encoding ASCII
    }

    BeforeEach {
        Set-Content -LiteralPath $script:ViewerLog -Value "" -Encoding ASCII
        Remove-Item -LiteralPath $script:ViewerHtmlDir -Recurse -Force -ErrorAction SilentlyContinue
        $env:DAAF_NESTED = "1"
        Remove-Item Env:DAAF_DRY_RUN -ErrorAction SilentlyContinue
        $env:MOCK_VIEWER_LOG = $script:ViewerLog
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = ""
        $env:MOCK_VIEWER_DISCOVERY_EXIT = "0"
        $env:MOCK_VIEWER_FILE_EXIT = "0"
        $env:QUARTO_HTML_DIR = $script:ViewerHtmlDir
    }

    AfterAll {
        $env:DAAF_NESTED = $script:OrigNested
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = $script:OrigDiscovery
        $env:MOCK_VIEWER_DISCOVERY_EXIT = $script:OrigDiscoveryExit
        $env:MOCK_VIEWER_FILE_EXIT = $script:OrigFileExit
        $env:QUARTO_HTML_DIR = $script:OrigHtmlDir
        Remove-Item Env:MOCK_VIEWER_LOG -ErrorAction SilentlyContinue
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "recursively discovers a deep notebook and selects it" {
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = "research/2026-07-15_AdHoc_Quarto_Viewer_Sample/output/analysis/2026-07-15a_Quarto_Viewer_Sample.qmd"
        $output = Invoke-QuartoViewerProcess -InputLines @("1")
        $script:ViewerLastExit | Should -Be 0
        $output | Should -BeLike "*1) research/2026-07-15_AdHoc_Quarto_Viewer_Sample/output/analysis/2026-07-15a_Quarto_Viewer_Sample.qmd*"
        $output | Should -BeLike "*Rendering research/2026-07-15_AdHoc_Quarto_Viewer_Sample/output/analysis/2026-07-15a_Quarto_Viewer_Sample.qmd*"
        $log = Get-Content $script:ViewerLog
        ($log | Out-String) | Should -BeLike '*decoded-script <cd /daaf && find research -type f -name "*.qmd" -print | LC_ALL=C sort>*'
        $nativeLine = @($log | Where-Object { $_ -like 'docker*<bash>*<echo $1 | base64 -d | bash -o pipefail>*' })[0]
        $nativeLine | Should -Not -Match '"'
        @($log | Where-Object { $_ -like "*<quarto> <render>*" }).Count | Should -Be 1
        @($log | Where-Object { $_ -like "*compose> <cp>*" }).Count | Should -Be 1
        @($log | Where-Object { $_ -like "*Start-Process*" }).Count | Should -Be 1
    }

    It "uses C-locale order and selects both first and last" {
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = "research/z/output/analysis/z.qmd`nresearch/a/output/analysis/a.qmd"
        (Invoke-QuartoViewerProcess -InputLines @("1")) | Should -BeLike "*Rendering research/a/output/analysis/a.qmd*"
        (Invoke-QuartoViewerProcess -InputLines @("2")) | Should -BeLike "*Rendering research/z/output/analysis/z.qmd*"
    }

    It "reprompts without rediscovery for malformed huge and out-of-range input" {
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = "research/a.qmd`nresearch/b.qmd"
        $output = Invoke-QuartoViewerProcess -InputLines @("+1", "1.0", "01", "999999999999999999999999999999999999", "3", "2")
        $script:ViewerLastExit | Should -Be 0
        $output | Should -BeLike "*Invalid selection. Enter a number from 1 to 2, or 0 to cancel.*"
        $output | Should -BeLike "*Rendering research/b.qmd*"
        @((Get-Content $script:ViewerLog) | Where-Object { $_ -like "*find research -type f*" }).Count | Should -Be 1
    }

    It "cancels cleanly on zero blank q Q and EOF" -ForEach @(
        @{ Label = "zero"; Lines = @("0") },
        @{ Label = "blank"; Lines = @("") },
        @{ Label = "lower q"; Lines = @("q") },
        @{ Label = "upper Q"; Lines = @("Q") },
        @{ Label = "EOF"; Lines = @() }
    ) {
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = "research/a.qmd"
        $output = Invoke-QuartoViewerProcess -InputLines $Lines
        $script:ViewerLastExit | Should -Be 0
        $output | Should -BeLike "*Quarto notebook selection cancelled.*"
        $log = Get-Content -Raw $script:ViewerLog
        $log | Should -Not -BeLike "*<quarto> <render>*"
        $log | Should -Not -BeLike "*compose> <cp>*"
        $log | Should -Not -BeLike "*Start-Process*"
    }

    It "preserves spaces and metacharacters without executing a command-shaped path" {
        $sentinel = Join-Path $script:TestDir "INJECTION_SENTINEL"
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = 'research/odd project/output/analysis/name $(New-Item INJECTION_SENTINEL); [x].qmd'
        $output = Invoke-QuartoViewerProcess -InputLines @("1")
        $script:ViewerLastExit | Should -Be 0
        $output | Should -Match ([regex]::Escape('Rendering research/odd project/output/analysis/name $(New-Item INJECTION_SENTINEL); [x].qmd'))
        (Get-Content -Raw $script:ViewerLog) | Should -Match ([regex]::Escape('</daaf/research/odd project/output/analysis/name $(New-Item INJECTION_SENTINEL); [x].qmd>'))
        Test-Path -LiteralPath $sentinel | Should -BeFalse
    }

    It "distinguishes empty discovery from Docker discovery failure" {
        $empty = Invoke-QuartoViewerProcess
        $script:ViewerLastExit | Should -Not -Be 0
        $empty | Should -BeLike "*No Quarto notebooks (.qmd) found under research/.*"
        $empty | Should -Not -BeLike "*Could not discover*"

        $env:MOCK_VIEWER_DISCOVERY_EXIT = "17"
        $failed = Invoke-QuartoViewerProcess
        $script:ViewerLastExit | Should -Not -Be 0
        $failed | Should -BeLike "*Could not discover Quarto notebooks*"
        $failed | Should -Not -BeLike "*No Quarto notebooks*"
    }

    It "recursively resolves a deep project with spaces through quote-free native transport" {
        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = "research/odd project [x]/output/analysis/deep.qmd"
        $output = Invoke-QuartoViewerProcess -Target "odd project [x]"
        $script:ViewerLastExit | Should -Be 0
        $output | Should -Match ([regex]::Escape("Rendering research/odd project [x]/output/analysis/deep.qmd"))
        $logLines = @(Get-Content $script:ViewerLog)
        $log = $logLines | Out-String
        $log | Should -BeLike '*decoded-script <proj=$(printf "%s" "$1" | base64 -d) && cd /daaf && find "research/$proj" -type f -name "*.qmd" -print | LC_ALL=C sort>*'
        $log | Should -Match ([regex]::Escape("decoded-project <odd project [x]>"))
        $nativeLine = @($logLines | Where-Object { $_ -like 'docker*<bash>*<echo $1 | base64 -d | bash -o pipefail -s -- $2>*' })[0]
        $nativeLine | Should -Not -Match '"'
        $nativeLine | Should -Not -BeLike "*odd project*"
    }

    It "reports recursive project zero failure and sorted ambiguity" {
        $zero = Invoke-QuartoViewerProcess -Target "project"
        $script:ViewerLastExit | Should -Not -Be 0
        $zero | Should -BeLike "*No Quarto notebook (.qmd) found in project: project*"

        $env:MOCK_VIEWER_DISCOVERY_OUTPUT = "research/project/z/deep-z.qmd`nresearch/project/a/deep-a.qmd"
        $many = Invoke-QuartoViewerProcess -Target "project"
        $script:ViewerLastExit | Should -Not -Be 0
        $many | Should -BeLike "*Multiple Quarto notebooks found*"
        $many.IndexOf("deep-a.qmd") | Should -BeLessThan $many.IndexOf("deep-z.qmd")
        (Get-Content -Raw $script:ViewerLog) | Should -Not -BeLike "*<quarto> <render>*"
    }

    It "reports project discovery command failure separately" {
        $env:MOCK_VIEWER_DISCOVERY_EXIT = "23"
        $output = Invoke-QuartoViewerProcess -Target "project"
        $script:ViewerLastExit | Should -Not -Be 0
        $output | Should -BeLike "*Could not search project 'project' for Quarto notebooks*"
    }

    It "preserves direct-path success and missing-path failure" {
        $direct = "research/odd project/output/analysis/direct [x].qmd"
        $success = Invoke-QuartoViewerProcess -Target $direct
        $script:ViewerLastExit | Should -Be 0
        $success | Should -Match ([regex]::Escape("Rendering $direct"))
        (Get-Content -Raw $script:ViewerLog) | Should -Match ([regex]::Escape("</daaf/$direct>"))

        $env:MOCK_VIEWER_FILE_EXIT = "1"
        $missing = Invoke-QuartoViewerProcess -Target $direct
        $script:ViewerLastExit | Should -Not -Be 0
        $missing | Should -BeLike "*Quarto notebook not found*"
    }
}

Describe "view_quarto.ps1 dry-run no-write contract" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
        $script:OrigHtmlDir = $env:QUARTO_HTML_DIR
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-dry-viewer-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile -Directory $script:TestDir
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        $env:QUARTO_HTML_DIR = $script:OrigHtmlDir
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "auto-selects a deep fixture and writes nothing for no-arg direct and project modes" -ForEach @(
        @{ Target = "" },
        @{ Target = "research/2026-07-15_Project/output/analysis/deep.qmd" },
        @{ Target = "2026-07-15_Project" }
    ) {
        $dryRoot = Join-Path $script:TestDir ("must-not-exist-" + [Guid]::NewGuid().ToString("N"))
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $env:QUARTO_HTML_DIR = $dryRoot
        if ([string]::IsNullOrEmpty($Target)) {
            $output = & "$RepoRoot/scripts/host/view_quarto.ps1" *>&1 | Out-String
        } else {
            $output = & "$RepoRoot/scripts/host/view_quarto.ps1" $Target *>&1 | Out-String
        }
        $output | Should -Match '\[DRY-RUN\]'
        $output | Should -BeLike "*output/analysis*"
        Test-Path -LiteralPath $dryRoot | Should -BeFalse
    }
}
