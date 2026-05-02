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
        $null = & "$RepoRoot/scripts/host/rebuild_daaf.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "completes full rebuild flow" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/rebuild_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Rebuild complete*"
    }
}

# ============================================================================
# Error paths
# ============================================================================

Describe "rebuild_daaf.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/rebuild_daaf.ps1" -Raw
    }

    Context "Container not found" {
        It "outputs error when container inspect fails" {
            $Content | Should -Match "Container.*not found"
        }

        It "suggests running the installer first" {
            $Content | Should -Match 'Have you run the DAAF installer'
        }
    }

    Context "Dockerfile copy failure" {
        It "outputs error when Dockerfile copy from container fails" {
            $Content | Should -Match 'Failed to copy Dockerfile from container'
        }

        It "suggests running the installer on copy failure" {
            $Content | Should -Match 'Make sure DAAF is installed in the container'
        }
    }

    Context "docker-compose.yml copy failure" {
        It "outputs error when docker-compose.yml copy fails" {
            $Content | Should -Match 'Failed to copy docker-compose\.yml from container'
        }
    }

    Context "Build failure" {
        It "outputs error when docker compose build fails" {
            $Content | Should -Match 'Rebuild failed'
        }

        It "preserves pre-rebuild backup on build failure" {
            $Content | Should -Match 'Dockerfile\.pre-rebuild'
        }
    }

    Context "Container start failure after build" {
        It "outputs error when docker compose up -d fails after build" {
            $Content | Should -Match 'Failed to start the container after rebuild'
        }
    }

    Context "Container readiness timeout after rebuild" {
        It "reports timeout when container does not become ready" {
            $Content | Should -Match 'did not become ready within 60 seconds'
        }

        It "shows Docker error output on readiness timeout" {
            $Content | Should -Match 'Docker reported'
        }
    }

    Context "CLAUDE.md missing after rebuild" {
        It "warns when DAAF files may not be intact" {
            $Content | Should -Match 'DAAF files may not be intact'
        }
    }

    Context "Hash comparison: Dockerfile changed" {
        It "reports UPDATED when Dockerfile hash differs" {
            $Content | Should -Match 'Dockerfile: UPDATED'
        }

        It "uses Get-FileHash for comparison" {
            $Content | Should -Match 'Get-FileHash'
        }
    }

    Context "Hash comparison: no changes" {
        It "reports no changes when hashes match" {
            $Content | Should -Match 'no changes detected'
        }

        It "rebuilds anyway when no changes detected" {
            $Content | Should -Match 'Rebuilding anyway to make sure the image is up to date'
        }
    }

    Context "Hash comparison: compose file changed" {
        It "reports UPDATED when docker-compose.yml hash differs" {
            $Content | Should -Match 'docker-compose\.yml: UPDATED'
        }
    }
}
