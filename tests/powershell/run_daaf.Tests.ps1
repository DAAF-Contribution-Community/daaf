# ============================================================================
# Pester tests for run_daaf.ps1 -- DAAF Launcher (Windows)
# ============================================================================

Describe "run_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/run_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/run_daaf.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "defines Pause-And-Exit function" {
            $Content | Should -Match 'function Pause-And-Exit'
        }

        It "checks DAAF_NESTED in Pause-And-Exit" {
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

        It "defaults command to claude" {
            $Content | Should -Match '"claude"'
        }

        It "handles bash command argument" {
            $Content | Should -Match '"bash"'
        }

        It "verifies CLAUDE.md exists in container" {
            $Content | Should -Match 'CLAUDE\.md'
        }

        It "starts container if not running" {
            $Content | Should -Match 'Starting DAAF container'
        }
    }
}
