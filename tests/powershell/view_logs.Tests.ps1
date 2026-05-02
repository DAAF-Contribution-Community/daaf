# ============================================================================
# Pester tests for view_logs.ps1 -- DAAF Log Explorer (Windows)
# ============================================================================

Describe "view_logs.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/view_logs.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/view_logs.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
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

        It "references generate_log_viewer.sh" {
            $Content | Should -Match 'generate_log_viewer\.sh'
        }

        It "mentions the Log Explorer in output" {
            $Content | Should -Match 'Log Explorer'
        }

        It "includes recovery step" {
            $Content | Should -Match 'recover-session-logs'
        }

        It "includes menu selection prompt" {
            $Content | Should -Match 'Select a log source'
        }

        It "handles --archive argument" {
            $Content | Should -Match '"--archive"'
        }

        It "handles --help argument" {
            $Content | Should -Match '"--help"'
        }

        It "skips menu in non-interactive contexts" {
            $Content | Should -Match 'DAAF_DRY_RUN'
            $Content | Should -Match 'DAAF_NESTED'
            $Content | Should -Match '\$SkipMenu'
        }
    }
}

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "view_logs.ps1 dry-run mode" {
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
        $null = & "$RepoRoot/scripts/host/view_logs.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "opens log explorer in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_logs.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Log Explorer*"
    }

    It "skips menu in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_logs.ps1" *>&1
        ($output | Out-String) | Should -Not -BeLike "*Select a log source*"
    }

    It "includes recovery step in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_logs.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*orphaned session logs*"
    }

    It "skips sleep in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        $null = & "$RepoRoot/scripts/host/view_logs.ps1" *>&1
        $sw.Stop()
        $sw.Elapsed.TotalSeconds | Should -BeLessThan 2
    }

    It "accepts --archive flag" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/view_logs.ps1" --archive *>&1
        ($output | Out-String) | Should -BeLike "*Log Explorer*"
    }
}
