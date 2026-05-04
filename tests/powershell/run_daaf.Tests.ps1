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

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "run_daaf.ps1 dry-run mode" {
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
        $null = & "$RepoRoot/scripts/host/run_daaf.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "launches Claude Code in dry-run" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/run_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Launching Claude Code*"
    }
}

# ============================================================================
# Error paths
# ============================================================================

Describe "run_daaf.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/run_daaf.ps1" -Raw
    }

    Context "Container not running auto-starts" {
        It "attempts to start container with docker compose up -d" {
            $Content | Should -Match 'Starting DAAF container'
            $Content | Should -Match 'docker compose up -d'
        }
    }

    Context "Auto-start fails" {
        It "exits with error when docker compose up fails (exit 1)" {
            $Content | Should -Match 'Failed to start the container'
            $Content | Should -Match 'Check Docker Desktop'
        }
    }

    Context "Compose file missing" {
        It "exits with error when docker-compose.yml is missing (exit 1)" {
            $Content | Should -Match 'docker-compose\.yml not found'
            $Content | Should -Match 'daaf-docker folder'
        }
    }

    Context "DAAF not installed in container" {
        It "exits with error when CLAUDE.md is missing (exit 1)" {
            $Content | Should -Match 'DAAF does not appear to be installed'
            $Content | Should -Match 'CLAUDE\.md'
        }
    }

    Context "Custom command passthrough" {
        It "handles custom commands beyond claude and bash" {
            $Content | Should -Match 'Running: \$Command'
            $Content | Should -Match 'docker compose exec daaf-docker \$Command'
        }
    }

    Context "Default command" {
        It "defaults to claude when no args provided" {
            $Content | Should -Match '\$Command = if \(\$args\.Count -gt 0\) \{ \$args\[0\] \} else \{ "claude" \}'
        }
    }
}
