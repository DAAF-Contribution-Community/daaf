# ============================================================================
# Pester tests for migrate_daaf.ps1 -- DAAF Migration Script (Windows)
# ============================================================================

Describe "migrate_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/migrate_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
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

        It "defines Prompt-Choice helper function" {
            $Content | Should -Match 'function Prompt-Choice'
        }

        It "defines Container-Git helper function" {
            $Content | Should -Match 'function Container-Git\b'
        }

        It "defines Container-Git-Verbose helper function" {
            $Content | Should -Match 'function Container-Git-Verbose'
        }

        It "defines Container-Exec helper function" {
            $Content | Should -Match 'function Container-Exec'
        }

        It "defines Container-Shell helper function" {
            $Content | Should -Match 'function Container-Shell\b'
        }

        It "defines Container-Shell-Verbose helper function" {
            $Content | Should -Match 'function Container-Shell-Verbose'
        }

        It "has a trap handler for unexpected failures" {
            $Content | Should -Match 'trap \{'
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "checks Docker daemon with docker info" {
            $Content | Should -Match 'docker info'
        }

        It "checks volume exists" {
            $Content | Should -Match 'docker volume inspect'
        }

        It "supports DAAF_BRANCH environment variable" {
            $Content | Should -Match 'DAAF_BRANCH'
        }

        It "detects non-interactive mode" {
            $Content | Should -Match 'NonInteractive'
        }

        It "detects Era 1 (clone-based) installations" {
            $Content | Should -Match 'clone-based installation'
        }

        It "detects Era 2 (ZIP-based) installations" {
            $Content | Should -Match 'ZIP-based installation'
        }

        It "performs a backup before migration" {
            $Content | Should -Match 'backup_daaf\.ps1'
        }

        It "handles fork detection" {
            $Content | Should -Match 'IsFork'
        }

        It "performs graft for ERA 2 installations" {
            $Content | Should -Match 'replace --graft'
        }

        It "fixes file permissions for ZIP downloads" {
            $Content | Should -Match 'Fixing file permissions'
        }

        It "sets upstream tracking branch" {
            $Content | Should -Match 'set-upstream-to=origin/main'
        }

        It "offers to run update after migration" {
            $Content | Should -Match 'Run update'
        }

        It "sets TLS 1.2 for GitHub downloads" {
            $Content | Should -Match 'Tls12'
        }

        It "claims idempotency in its header" {
            $Content | Should -Match 'idempotent'
        }
    }
}
