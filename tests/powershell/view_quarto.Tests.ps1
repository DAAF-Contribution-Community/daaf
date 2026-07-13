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

    It "discovery mode lists notebooks with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_quarto.ps1" *>&1
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
