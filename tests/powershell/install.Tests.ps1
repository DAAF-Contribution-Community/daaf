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
