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

        It "enables Set-StrictMode -Version 3.0" {
            $Content | Should -Match 'Set-StrictMode\s+-Version\s+3\.0'
        }

        It "places Set-StrictMode after the test-mode guard" {
            # Strict mode is dynamically scoped: placing it before the guard would
            # leak into Pester's dot-sourced test session. It must come after.
            $guardIdx = $Content.IndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx | Should -BeGreaterThan -1
            $strictIdx | Should -BeGreaterThan $guardIdx
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
            $Content | Should -Match 'view_notebooks\.ps1'
            $Content | Should -Match 'view_quarto\.ps1'
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
        # Run inside a throwaway temp dir. install.ps1 creates a daaf-docker/
        # tree under the current directory ($InstallDir = <CWD>/daaf-docker).
        # Isolating the CWD keeps those artifacts out of the repo root and makes
        # cleanup independent of the ambient working directory. Push in BeforeAll,
        # Pop crash-proof in AfterAll.
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-install-dry-$(Get-Random)")
        Push-Location $script:TestDir
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        # Pop unconditionally so a mid-block failure cannot leave CWD at the repo
        # root for the next Describe block.
        if ((Get-Location).Path -eq $script:TestDir.FullName) { Pop-Location }
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "completes successfully with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $null = & "$RepoRoot/scripts/host/install.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "completes full installation flow" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/install.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Installation complete*"
    }

    It "creates the diagnostic builder under DAAF_DIAG_BUILD=1 (dry-run mock: inspect miss -> create)" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $env:DAAF_DIAG_BUILD = "1"
        $output = & "$RepoRoot/scripts/host/install.ps1" *>&1
        $env:DAAF_DIAG_BUILD = $null
        ($output | Out-String) | Should -BeLike "*Created diagnostic buildx builder*"
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

    Context "Diagnostic builder (DAAF_DIAG_BUILD)" {
        It "gates the diagnostic builder behind DAAF_DIAG_BUILD=1" {
            $Content | Should -Match 'DAAF_DIAG_BUILD -eq "1"'
        }

        It "creates a docker-container buildx builder with raised size AND speed step-log limits" {
            $Content | Should -Match 'buildx create --name daaf-diag-builder'
            $Content | Should -Match 'BUILDKIT_STEP_LOG_MAX_SIZE=16777216'
            $Content | Should -Match 'BUILDKIT_STEP_LOG_MAX_SPEED=10485760'
        }

        It "selects the builder via BUILDX_BUILDER and clears it after the build" {
            $Content | Should -Match '\$env:BUILDX_BUILDER = "daaf-diag-builder"'
            $Content | Should -Match '\$env:BUILDX_BUILDER = \$null'
        }

        It "falls open to the default builder when the builder cannot be created" {
            $Content | Should -Match 'could not be'
            $Content | Should -Match 'Falling back to the default builder'
        }

        It "prints an arm64 first-build heads-up notice" {
            $Content | Should -Match 'arm64 detected'
        }

        It "uses version-robust wording in the clipped-log hint" {
            $Content | Should -Match 'the exact limit varies by Docker version'
        }

        It "extends the build-failure hint to mention DAAF_DIAG_BUILD" {
            $Content | Should -Match 'DAAF_DIAG_BUILD=1'
        }
    }

    Context "Diagnostic builder: fail-open behavior (dry-run: create fails)" {
        BeforeAll {
            $script:OrigDryRun2 = $env:DAAF_DRY_RUN
            $script:OrigNested2 = $env:DAAF_NESTED
            $script:OrigDiag2 = $env:DAAF_DIAG_BUILD
            $script:TestDir2 = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-install-failopen-$(Get-Random)")
            Push-Location $script:TestDir2
        }
        AfterAll {
            $env:DAAF_DRY_RUN = $script:OrigDryRun2
            $env:DAAF_NESTED = $script:OrigNested2
            $env:DAAF_DIAG_BUILD = $script:OrigDiag2
            if ((Get-Location).Path -eq $script:TestDir2.FullName) { Pop-Location }
            Remove-Item -Recurse -Force $script:TestDir2 -ErrorAction SilentlyContinue
        }

        It "completes the install on the default builder when buildx create fails" {
            # The script's dry-run docker mock honors DAAF_DIAG_BUILD_TEST_CREATE_FAIL
            # to simulate a `buildx create` failure, exercising the fail-open path
            # end-to-end (parity with the bash fail-open test).
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $env:DAAF_DIAG_BUILD = "1"
            $env:DAAF_DIAG_BUILD_TEST_CREATE_FAIL = "1"
            $output = & "$RepoRoot/scripts/host/install.ps1" *>&1
            $env:DAAF_DIAG_BUILD_TEST_CREATE_FAIL = $null
            ($output | Out-String) | Should -BeLike "*could not be*"
            ($output | Out-String) | Should -Not -BeLike "*Created diagnostic buildx builder*"
        }
    }
}
