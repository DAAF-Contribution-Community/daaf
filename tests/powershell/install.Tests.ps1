# ============================================================================
# Pester tests for install.ps1 -- DAAF One-Line Installer (Windows)
# ============================================================================

Describe "install.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/install.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/install.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "defines Pause-For-User function" {
            $Content | Should -Match 'function Pause-For-User'
        }

        It "checks DAAF_NESTED in Pause-For-User" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "uses numbered progress steps [1/4] through [4/4]" {
            ($Content | Select-String -Pattern '\[1/4\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
            ($Content | Select-String -Pattern '\[2/4\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
            ($Content | Select-String -Pattern '\[3/4\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
            ($Content | Select-String -Pattern '\[4/4\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "checks Docker daemon with docker info" {
            $Content | Should -Match 'docker info'
        }

        It "checks for existing installation" {
            $Content | Should -Match 'existing DAAF installation'
        }

        It "supports DAAF_BRANCH environment variable" {
            $Content | Should -Match 'DAAF_BRANCH'
        }

        It "supports DAAF_FORCE_REINSTALL environment variable" {
            $Content | Should -Match 'DAAF_FORCE_REINSTALL'
        }

        It "downloads required utility scripts" {
            $Content | Should -Match 'run_daaf\.ps1'
            $Content | Should -Match 'backup_daaf\.ps1'
            $Content | Should -Match 'rebuild_daaf\.ps1'
            $Content | Should -Match 'update_daaf\.ps1'
            $Content | Should -Match 'view_logs\.ps1'
        }

        It "verifies CLAUDE.md exists in container" {
            $Content | Should -Match 'CLAUDE\.md'
        }

        It "sets TLS 1.2 for GitHub downloads" {
            $Content | Should -Match 'Tls12'
        }
    }
}

# ============================================================================
# Behavioral tests -- dot-source to verify functions + source analysis
# ============================================================================

Describe "install.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/install.ps1"

        $script:Content = Get-Content "$RepoRoot/scripts/host/install.ps1" -Raw
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    # -----------------------------------------------------------------
    # Pause-For-User (the only function exposed)
    # -----------------------------------------------------------------
    Context "Pause-For-User function" {
        It "is callable after dot-sourcing" {
            # Verify the function is defined in the current scope
            Get-Command Pause-For-User -ErrorAction SilentlyContinue |
                Should -Not -BeNullOrEmpty
        }
    }

    # -----------------------------------------------------------------
    # URL construction and branch defaults
    # -----------------------------------------------------------------
    Context "URL construction" {
        It "default branch is 'main'" {
            # When DAAF_BRANCH is not set, $Branch defaults to "main"
            $Content | Should -Match '\$Branch = if \(\$env:DAAF_BRANCH\) \{ \$env:DAAF_BRANCH \} else \{ "main" \}'
        }

        It "DAAF_BRANCH overrides default branch" {
            $Content | Should -Match '\$env:DAAF_BRANCH'
            # The config section uses $Branch throughout for URL construction
            $Content | Should -Match '\$RawBase = "https://raw\.githubusercontent\.com/\$Repo/\$Branch"'
        }

        It "download URLs use scripts/host/ prefix" {
            $Content | Should -Match '\$RawBase/scripts/host/'
            # Verify specific script downloads reference scripts/host/
            $Content | Should -Match 'scripts/host/run_daaf\.ps1'
            $Content | Should -Match 'scripts/host/backup_daaf\.ps1'
            $Content | Should -Match 'scripts/host/update_daaf\.ps1'
        }
    }

    # -----------------------------------------------------------------
    # Installation detection
    # -----------------------------------------------------------------
    Context "Installation detection" {
        It "checks for existing docker-compose.yml" {
            $Content | Should -Match 'Test-Path "\$InstallDir\\docker-compose\.yml"'
        }

        It "checks for existing Docker volume" {
            $Content | Should -Match 'docker volume inspect daaf_daaf-data'
        }

        It "DAAF_FORCE_REINSTALL bypasses existing check" {
            $Content | Should -Match '\$env:DAAF_FORCE_REINSTALL -eq "1"'
            $Content | Should -Match 'Proceeding with re-install'
        }
    }

    # -----------------------------------------------------------------
    # Readiness verification
    # -----------------------------------------------------------------
    Context "Readiness verification" {
        It "readiness check looks for CLAUDE.md" {
            $Content | Should -Match 'test -f /daaf/CLAUDE\.md'
        }

        It "readiness check has retry logic for container startup" {
            # The container readiness check uses a retry loop
            $Content | Should -Match '\$maxRetries = 30'
            $Content | Should -Match 'Start-Sleep -Seconds 2'
        }
    }
}
