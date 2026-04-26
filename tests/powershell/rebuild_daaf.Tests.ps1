# ============================================================================
# Pester tests for rebuild_daaf.ps1 -- DAAF Rebuild Utility (Windows)
# ============================================================================

Describe "rebuild_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/rebuild_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/rebuild_daaf.ps1" -Raw
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

        It "checks container exists with docker inspect" {
            $Content | Should -Match 'docker inspect'
        }

        It "uses numbered progress steps [1/3] [2/3] [3/3]" {
            ($Content | Select-String -Pattern '\[1/3\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
            ($Content | Select-String -Pattern '\[2/3\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
            ($Content | Select-String -Pattern '\[3/3\]' -AllMatches).Matches.Count | Should -BeGreaterOrEqual 1
        }

        It "copies Dockerfile from container" {
            $Content | Should -Match 'docker cp.*Dockerfile'
        }

        It "copies docker-compose.yml from container" {
            $Content | Should -Match 'docker cp.*docker-compose\.yml'
        }

        It "backs up existing files before overwrite" {
            $Content | Should -Match 'pre-rebuild'
        }

        It "compares file hashes to detect changes" {
            $Content | Should -Match 'Get-FileHash'
        }

        It "verifies CLAUDE.md after rebuild" {
            $Content | Should -Match 'CLAUDE\.md'
        }

        It "cleans up pre-rebuild backups on success" {
            $Content | Should -Match 'Remove-Item.*pre-rebuild'
        }

        It "waits for container readiness after rebuild" {
            $Content | Should -Match 'Waiting for container to be ready'
        }
    }
}
