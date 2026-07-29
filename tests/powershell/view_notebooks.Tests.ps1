# ============================================================================
# Pester tests for view_notebooks.ps1 -- DAAF Notebook Browser (Windows)
# ============================================================================
# Tests cover syntax validation, script structure, dry-run behavior, and
# structural markers. Mirrors view_notebooks.bats for cross-platform parity.
# ============================================================================

Describe "view_notebooks.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    # =====================================================================
    # Tier 1 -- Syntax
    # =====================================================================

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/view_notebooks.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    # =====================================================================
    # Tier 3 -- Script structure
    # =====================================================================

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/view_notebooks.ps1" -Raw
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

        It "references launch_marimo.sh" {
            $Content | Should -Match 'launch_marimo\.sh'
        }

        It "mentions the Notebook Browser in output" {
            $Content | Should -Match 'Notebook Browser'
        }

        It "supports DAAF_TEST_MODE guard" {
            $Content | Should -Match 'DAAF_TEST_MODE'
        }

        It "supports DAAF_DRY_RUN" {
            $Content | Should -Match 'DAAF_DRY_RUN'
        }

        It "handles notebook browser launch failure" {
            $Content | Should -Match 'Failed to start the notebook browser'
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

Describe "view_notebooks.ps1 dry-run mode" {
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

    It "completes successfully with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $null = & "$RepoRoot/scripts/host/view_notebooks.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "shows Notebook Browser message in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_notebooks.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Notebook Browser*"
    }

    It "reports container running in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_notebooks.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*DAAF container is running*"
    }

    It "completes quickly in dry-run (no blocking)" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $null = & "$RepoRoot/scripts/host/view_notebooks.ps1" *>&1
        $sw.Stop()
        $sw.Elapsed.TotalSeconds | Should -BeLessThan 5
    }
}
