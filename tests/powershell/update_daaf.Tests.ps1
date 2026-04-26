# ============================================================================
# Pester tests for update_daaf.ps1 -- DAAF Update Script (Windows)
# ============================================================================

Describe "update_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/update_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/update_daaf.ps1" -Raw
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

        It "defines Compose-Git helper function" {
            $Content | Should -Match 'function Compose-Git\b'
        }

        It "defines Compose-Git-Verbose helper function" {
            $Content | Should -Match 'function Compose-Git-Verbose'
        }

        It "defines Compose-Git-Null helper function" {
            $Content | Should -Match 'function Compose-Git-Null'
        }

        It "defines Invoke-Compose helper function" {
            $Content | Should -Match 'function Invoke-Compose'
        }

        It "defines Compose-Exec helper function" {
            $Content | Should -Match 'function Compose-Exec'
        }

        It "defines Prompt-Choice helper function" {
            $Content | Should -Match 'function Prompt-Choice'
        }

        It "defines Handle-Conflict helper function" {
            $Content | Should -Match 'function Handle-Conflict'
        }

        It "defines Sync-HostScripts helper function" {
            $Content | Should -Match 'function Sync-HostScripts'
        }

        It "defines Check-BuildChanges helper function" {
            $Content | Should -Match 'function Check-BuildChanges'
        }

        It "defines Finish-Update helper function" {
            $Content | Should -Match 'function Finish-Update'
        }

        It "has a trap handler for unexpected failures" {
            $Content | Should -Match 'trap \{'
        }

        It "checks for docker-compose.yml" {
            $Content | Should -Match 'docker-compose\.yml'
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "supports DAAF_BRANCH environment variable" {
            $Content | Should -Match 'DAAF_BRANCH'
        }

        It "offers backup before updating" {
            $Content | Should -Match 'Backup recommendation'
        }

        It "creates a git backup branch" {
            $Content | Should -Match 'backup/pre-update'
        }

        It "handles merge and rebase options" {
            $Content | Should -Match 'MERGE \(recommended\)'
            $Content | Should -Match 'REBASE \(cleaner history\)'
        }

        It "handles non-default branch update path" {
            $Content | Should -Match "You are on branch"
        }

        It "handles uncommitted changes (dirty files)" {
            $Content | Should -Match 'uncommitted changes'
        }

        It "detects ahead/behind state" {
            $Content | Should -Match 'rev-list --count'
        }
    }
}
