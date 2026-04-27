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

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "rebuild_daaf.ps1 dry-run mode" {
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
        $output = & "$RepoRoot/scripts/host/rebuild_daaf.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "completes full rebuild flow" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/rebuild_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Rebuild complete*"
    }
}
