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

        It "starts container if not running" {
            $Content | Should -Match 'Starting DAAF container'
        }

        It "references generate_log_viewer.sh" {
            $Content | Should -Match 'generate_log_viewer\.sh'
        }

        It "mentions the Log Explorer in output" {
            $Content | Should -Match 'Log Explorer'
        }
    }
}
