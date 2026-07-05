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

        It "defines Wait-ForUser function" {
            $Content | Should -Match 'function Wait-ForUser'
        }

        It "checks DAAF_NESTED in Wait-ForUser" {
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
    # Wait-ForUser (the only function exposed)
    # -----------------------------------------------------------------
    Context "Wait-ForUser function" {
        It "is callable after dot-sourcing" {
            # Verify the function is defined in the current scope
            Get-Command Wait-ForUser -ErrorAction SilentlyContinue |
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
            # Detection is project-name-aware (DAAF_PROJECT_NAME), not hardcoded
            $Content | Should -Match 'docker volume inspect \$DataVolumeName'
        }

        It "derives the volume name from the project name with daaf default" {
            $Content | Should -Match '\$DataVolumeName = "\$\{InstallProjectName\}_daaf-data"'
            $Content | Should -Match '\$InstallProjectName = "daaf"'
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

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "install.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
    }

    It "completes successfully with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $null = & "$RepoRoot/scripts/host/install.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
        # Clean up the daaf-docker directory created by install.ps1
        $installDir = Join-Path (Get-Location).Path "daaf-docker"
        if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir -ErrorAction SilentlyContinue }
    }

    It "completes full installation flow" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/install.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Installation complete*"
        # Clean up the daaf-docker directory created by install.ps1
        $installDir = Join-Path (Get-Location).Path "daaf-docker"
        if (Test-Path $installDir) { Remove-Item -Recurse -Force $installDir -ErrorAction SilentlyContinue }
    }
}

# ============================================================================
# Error paths
# ============================================================================

Describe "install.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:Content = Get-Content "$RepoRoot/scripts/host/install.ps1" -Raw
    }

    Context "Build failure" {
        It "outputs error when docker compose build fails" {
            # Verify the script contains the build-failure error path
            $Content | Should -Match 'Docker image build failed'
            $Content | Should -Match 'LASTEXITCODE -ne 0'
        }

        It "suggests re-running installer on build failure" {
            $Content | Should -Match 'DAAF_FORCE_REINSTALL'
            $Content | Should -Match 're-run this installer'
        }
    }

    Context "Container start failure" {
        It "outputs error when docker compose up -d fails" {
            $Content | Should -Match 'Failed to start the Docker container after build'
        }
    }

    Context "Container readiness timeout" {
        It "reports timeout when container does not become ready" {
            $Content | Should -Match 'did not become ready within 60 seconds'
            $Content | Should -Match '\$maxRetries = 30'
        }

        It "shows Docker error output on timeout" {
            $Content | Should -Match 'Docker reported'
        }
    }

    Context "Download failure" {
        It "outputs error when Invoke-WebRequest fails" {
            $Content | Should -Match "Failed to download installation files from branch"
        }

        It "suggests verifying branch name on download failure" {
            $Content | Should -Match 'verify that the branch name is correct'
        }
    }

    Context "Git clone failure" {
        It "outputs error when git clone into container fails" {
            $Content | Should -Match 'Failed to clone the DAAF repository'
        }

        It "outputs error when copy repo files fails" {
            $Content | Should -Match 'Failed to copy repository files into the container'
        }
    }

    Context "CLAUDE.md verification failure" {
        It "warns when CLAUDE.md is not found post-install" {
            $Content | Should -Match 'CLAUDE\.md was not found in the container'
        }
    }

    Context "Force reinstall with existing volume" {
        It "proceeds when DAAF_FORCE_REINSTALL is set" {
            $Content | Should -Match 'Proceeding with re-install \(DAAF_FORCE_REINSTALL=1\)'
        }
    }

    Context "Existing installation without force flag" {
        It "blocks and warns about existing installation" {
            $Content | Should -Match 'existing DAAF installation was detected'
        }

        It "suggests update_daaf.ps1 as alternative" {
            $Content | Should -Match 'update_daaf\.ps1'
        }
    }
}
