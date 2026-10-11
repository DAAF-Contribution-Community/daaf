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
            # Detection is project-name-aware (DAAF_PROJECT_NAME), not hardcoded.
            # With a compose file in the folder the derived $DataVolumeName is
            # checked; the probe itself is Get-DaafVolumeState.
            $Content | Should -Match '\$CheckVolumeName = \$DataVolumeName'
            $Content | Should -Match 'docker volume inspect \$Name'
        }

        It "checks the volume even when the folder has no docker-compose.yml (B-1)" {
            # The probe runs outside any Test-Path of the compose file, against the
            # volume this run would write when the folder has no compose file.
            $Content | Should -Match '\$CheckVolumeName = "\$\{InstallTargetProject\}_daaf-data"'
            $Content | Should -Match '\$CheckVolumeState = Get-DaafVolumeState -Name \$CheckVolumeName'
            $Content | Should -Not -Match '(?s)if \(Test-Path "\$InstallDir\\docker-compose\.yml"\) \{\s*\$savedEAP'
        }

        It "classifies the volume by exit code and stdout only (no stderr text, PS 5.1 safe)" {
            # Windows PowerShell 5.1 drops native stderr under SilentlyContinue, so
            # Docker's "no such volume" text is never matched; the fallback list is
            # read from stdout only. pwsh 7 cannot reproduce the 5.1 drop, so this
            # is guarded structurally (shell-scripting gotchas).
            $Content | Should -Match 'docker volume ls -q 2>\$null'
            $Content | Should -Not -Match '(?i)no such volume'
            $Content | Should -Match '-ccontains \$Name'
        }

        It "derives the volume name from the project name with daaf default" {
            $Content | Should -Match '\$DataVolumeName = "\$\{InstallTargetProject\}_daaf-data"'
            $Content | Should -Match '\$InstallTargetProject = if \(\[string\]::IsNullOrEmpty\(\$env:DAAF_PROJECT_NAME\)\) \{ "daaf" \}'
        }

        It "derives the target project ONCE, after bridging the settings file into the process environment (F-a)" {
            # One project-name source: the bridge sets the whitelisted keys in the
            # process environment (so Compose sees them), and only then is the
            # project derived, exactly once, from that environment.
            ([regex]::Matches($Content, '(?m)^\$InstallTargetProject = ')).Count | Should -Be 1
            $bridgeIdx = $Content.IndexOf('Set-Item -Path ("Env:" + $key) -Value $val')
            $deriveIdx = $Content.IndexOf('$InstallTargetProject = if')
            $checkIdx = $Content.IndexOf('$CheckVolumeState = Get-DaafVolumeState')
            $bridgeIdx | Should -BeGreaterThan -1
            $deriveIdx | Should -BeGreaterThan $bridgeIdx
            $checkIdx | Should -BeGreaterThan $deriveIdx
            $Content | Should -Match "\`$bridgeKeys = @\('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV'\)"
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

    # -----------------------------------------------------------------
    # Settings seeding (environment_settings.txt from process-env DAAF_*)
    # -----------------------------------------------------------------
    # Parity twin of the bash install.bats seeder tests. The Pester suite verifies
    # the seeder by source-analysis (its harness has no docker function-mock), plus
    # a dry-run behavioral zero-write assertion in the dry-run Describe below.
    Context "Settings seeding" {
        It "defines the Set-DaafSettingsKey upsert helper inline" {
            $Content | Should -Match 'function Set-DaafSettingsKey'
        }

        It "seeds environment_settings.txt from the example template" {
            $Content | Should -Match '\$SeedSrc = Join-Path \$InstallDir "environment_settings_example\.txt"'
            $Content | Should -Match '\$SeedDst = Join-Path \$InstallDir "environment_settings\.txt"'
        }

        It "never overwrites an existing environment_settings.txt" {
            $Content | Should -Match 'left untouched'
        }

        It "skips DAAF_BRANCH when it resolves to a version tag (symbolic-ref probe)" {
            $Content | Should -Match 'symbolic-ref -q HEAD'
            $Content | Should -Match '\$SeedBranchSkipTag'
            $Content | Should -Match 'is a version tag'
        }

        It "runs a health probe first so an exec failure is 'could not verify', not a false tag claim" {
            # A cheap `git rev-parse HEAD` health probe must precede the symbolic-ref
            # branch/tag classification, gating it behind $probeOk, so a stopped
            # container / transient exec error reports UNVERIFIED rather than "tag".
            $Content | Should -Match 'rev-parse HEAD'
            $Content | Should -Match '\$probeOk'
            $Content | Should -Match '\$SeedBranchUnverified'
            $Content | Should -Match 'could not verify whether'
        }

        It "degrades to a manual-fallback note when seeding fails (install still completes)" {
            $Content | Should -Match 'did not fully complete'
        }

        It "is DAAF_DRY_RUN gated (prints intent, writes nothing)" {
            $Content | Should -Match '\[DRY-RUN\] Would seed'
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

    # --- Regression: non-writing dry-run (2026-07-14 root-stub incident) ---
    # Root cause: the dry-run Invoke-WebRequest mock wrote an empty file for every
    # -OutFile target under $InstallDir (=<CWD>/daaf-docker), leaking zero-byte
    # stubs on disk. A dry-run install must now create NOTHING -- no daaf-docker/
    # directory, no stub files. See:
    # research/2026-07-15_FrameworkDev_CwdLeakRootStubs/SESSION_NOTES.md
    It "dry-run creates no daaf-docker directory or files" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $before = (Get-ChildItem -Force $script:TestDir | Select-Object -ExpandProperty Name | Sort-Object) -join "`n"
        $null = & "$RepoRoot/scripts/host/install.ps1" *>&1
        # The daaf-docker/ install target must not have been created.
        (Test-Path (Join-Path $script:TestDir "daaf-docker")) | Should -Be $false
        $after = (Get-ChildItem -Force $script:TestDir | Select-Object -ExpandProperty Name | Sort-Object) -join "`n"
        $after | Should -Be $before
    }

    It "creates the diagnostic builder under DAAF_DIAG_BUILD=1 (dry-run mock: inspect miss -> create)" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $env:DAAF_DIAG_BUILD = "1"
        $output = & "$RepoRoot/scripts/host/install.ps1" *>&1
        $env:DAAF_DIAG_BUILD = $null
        ($output | Out-String) | Should -BeLike "*Created diagnostic buildx builder*"
    }

    It "dry-run does not create environment_settings.txt (seeder zero-write)" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $env:DAAF_PROJECT_NAME = "myproj"
        $output = & "$RepoRoot/scripts/host/install.ps1" *>&1
        $env:DAAF_PROJECT_NAME = $null
        ($output | Out-String) | Should -BeLike "*Would seed*"
        (Test-Path (Join-Path $script:TestDir "daaf-docker/environment_settings.txt")) | Should -Be $false
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

# ============================================================================
# Existing-install guard does not depend on the install folder (B-1)
# ============================================================================
# Parity twin of the install.bats section of the same name. Before 2026-10-06 the
# data-volume check ran only when THIS folder held a docker-compose.yml, so the
# installer run from another folder with the same project name took over that
# install. Cases: 1 volume + compose here (WARNING, stop); 2 volume, no compose
# (refuse before any download/build); 3 no volume + compose ("incomplete" NOTE);
# 4 neither (fresh install). These run the REAL script (no DAAF_DRY_RUN) with
# docker and Invoke-WebRequest shadowed by functions defined in the calling scope
# (PowerShell's dynamic scoping makes them visible to the script), so "nothing was
# downloaded or built" is observed, not inferred. A run that proceeds is stopped
# at the image build (the mock fails it). install.ps1's refusals end in
# `Wait-ForUser; return` (exit 0), so they are asserted by output, not exit code.

Describe "install.ps1 existing-install guard (folder-independent)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-install-guard-$(Get-Random)")

        # Run install.ps1 in a fresh folder under $script:TestDir with mocked docker /
        # Invoke-WebRequest. -Volumes: the Docker volumes that exist. -VolumeLsExit:
        # exit code of `docker volume ls` (nonzero = the fallback list fails too).
        # -WithCompose: put a docker-compose.yml in <folder>/daaf-docker first.
        # -SettingsText: write this text (verbatim) to <folder>/daaf-docker/
        # environment_settings.txt first. -InDir: run in this existing folder instead
        # of a fresh one. -BuildOk: every docker call succeeds, so the run goes on to
        # the end (otherwise the mock fails the image build and the run stops there).
        # -EnvVars: DAAF_* values for this run only (every DAAF_* the guard or the
        # settings bridge reads is cleared first and restored after, so the dev
        # container's own values cannot steer it and the script's bridge cannot leak).
        # ComposeLog: one line per `docker compose -f <file> <args>` call,
        # "compose <args> | P=.. M=.. L=.. V=.. D=..", the DAAF_PROJECT_NAME /
        # DAAF_PORT_MARIMO / _LOGVIEWER / _VSCODE / DAAF_DEV process values at that call.
        # -FailOn: a literal substring; a `docker compose ...` call whose argument
        # string contains it exits 1 (flag-anchored strings such as ' up -d',
        # 'git clone', 'cp -a /tmp/daaf-clone', '--force-recreate'). Start-Sleep is
        # shadowed so the readiness loop's 30 retries do not take a minute.
        # -WithTemplate: put an environment_settings_example.txt in <folder>/daaf-docker
        # first (the mock download writes nothing), so the seeder can run.
        function Invoke-InstallUnderMock {
            param(
                [string[]]$Volumes = @(),
                [int]$VolumeLsExit = 0,
                [switch]$WithCompose,
                [string]$SettingsText = $null,
                [string]$InDir = $null,
                [switch]$BuildOk,
                [hashtable]$EnvVars = @{},
                [string]$FailOn = $null,
                [switch]$WithTemplate
            )
            if ([string]::IsNullOrEmpty($InDir)) {
                $runDir = Join-Path $script:TestDir ("run-" + [guid]::NewGuid().ToString('N'))
                $null = New-Item -ItemType Directory -Path $runDir
            } else {
                $runDir = $InDir
            }
            $composeDir = Join-Path $runDir 'daaf-docker'
            if ($WithCompose -or $WithTemplate -or -not [string]::IsNullOrEmpty($SettingsText)) {
                $null = New-Item -ItemType Directory -Path $composeDir -Force
            }
            if ($WithCompose) {
                New-FakeComposeFile -Directory $composeDir
            }
            if ($WithTemplate) {
                [System.IO.File]::WriteAllText((Join-Path $composeDir 'environment_settings_example.txt'), "# template`n#DAAF_PROJECT_NAME=daaf2`n")
            }
            if (-not [string]::IsNullOrEmpty($SettingsText)) {
                [System.IO.File]::WriteAllText((Join-Path $composeDir 'environment_settings.txt'), $SettingsText)
            }
            $dockerCalls = [System.Collections.Generic.List[string]]::new()
            $composeLog = [System.Collections.Generic.List[string]]::new()
            $webRequests = [System.Collections.Generic.List[string]]::new()
            # Read by the docker mock below through dynamic scoping.
            $mockVolumes = @($Volumes)
            $mockVolumeLsExit = $VolumeLsExit
            $mockBuildOk = [bool]$BuildOk
            $mockFailOn = $FailOn
            function Start-Sleep {
                param([int]$Seconds)
                $null = $Seconds
            }
            function docker {
                $argStr = $args -join ' '
                $dockerCalls.Add($argStr)
                $global:LASTEXITCODE = 0
                if ($args.Count -ge 4 -and [string]$args[0] -eq 'compose') {
                    # Empty reads as <unset>: Compose's ${VAR:-default} treats both alike,
                    # and this harness's own clearing (SetEnvironmentVariable with $null,
                    # which PowerShell binds as "") can leave a variable set but empty.
                    $seen = foreach ($en in @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV')) {
                        $ev = [Environment]::GetEnvironmentVariable($en, 'Process')
                        if ([string]::IsNullOrEmpty($ev)) { '<unset>' } else { $ev }
                    }
                    $composeLog.Add(('compose {0} | P={1} M={2} L={3} V={4} D={5}' -f (@($args | Select-Object -Skip 3) -join ' '), $seen[0], $seen[1], $seen[2], $seen[3], $seen[4]))
                }
                if ($argStr -like 'volume inspect *') {
                    if (-not ($mockVolumes -ccontains [string]$args[2])) { $global:LASTEXITCODE = 1 }
                    return
                }
                if ($argStr -like 'volume ls*') {
                    if ($mockVolumeLsExit -ne 0) { $global:LASTEXITCODE = $mockVolumeLsExit; return }
                    foreach ($v in $mockVolumes) { $v }
                    return
                }
                if ($argStr -like '* build --progress*' -and -not $mockBuildOk) { $global:LASTEXITCODE = 1 }
                if (-not [string]::IsNullOrEmpty($mockFailOn) -and [string]$args[0] -eq 'compose' -and $argStr.Contains($mockFailOn)) { $global:LASTEXITCODE = 1 }
            }
            function Invoke-WebRequest {
                param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
                $null = $UseBasicParsing, $OutFile
                $webRequests.Add($Uri)
            }
            $names = @('DAAF_PROJECT_NAME', 'DAAF_DATA_VOLUME_NAME', 'DAAF_FORCE_REINSTALL', 'DAAF_DRY_RUN', 'DAAF_TEST_MODE', 'DAAF_NESTED', 'DAAF_DIAG_BUILD',
                'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV')
            $saved = @{}
            foreach ($n in $names) {
                $saved[$n] = [Environment]::GetEnvironmentVariable($n, 'Process')
                [Environment]::SetEnvironmentVariable($n, $null, 'Process')
            }
            [Environment]::SetEnvironmentVariable('DAAF_NESTED', '1', 'Process')
            foreach ($k in $EnvVars.Keys) { [Environment]::SetEnvironmentVariable($k, $EnvVars[$k], 'Process') }
            Push-Location $runDir
            try {
                $output = & "$RepoRoot/scripts/host/install.ps1" *>&1 | Out-String
            } finally {
                Pop-Location
                foreach ($n in $names) { [Environment]::SetEnvironmentVariable($n, $saved[$n], 'Process') }
            }
            [pscustomobject]@{
                Output = $output
                DockerCalls = @($dockerCalls)
                ComposeLog = @($composeLog)
                WebRequests = @($webRequests)
                Dir = $runDir
            }
        }

        # A named instance's settings file: project x, ports 3101-3103, one comment.
        $script:NamedSettings = "# my real API keys`nDAAF_PROJECT_NAME=x`nDAAF_PORT_MARIMO=3101`nDAAF_PORT_LOGVIEWER=3102`nDAAF_PORT_VSCODE=3103`n"
    }

    AfterAll {
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "case 2: volume exists, no compose file here -- refuses before any download or build" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data')
        $r.Output | Should -BeLike "*A DAAF installation using Docker volume 'daaf_daaf-data' (project 'daaf')*"
        $r.Output | Should -BeLike "*already exists, probably installed from another folder, or its daaf-docker*"
        $r.Output | Should -BeLike "*folder was moved or deleted.*"
        $r.Output | Should -BeLike "*Nothing has been downloaded or changed.*"
        # Default project: the FORCE hint needs no DAAF_PROJECT_NAME.
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_FORCE_REINSTALL = "1"'
        $r.Output | Should -Not -BeLike '*$env:DAAF_PROJECT_NAME = "daaf";*'
        $r.Output | Should -Not -BeLike "*[[]1/4]*"
        $r.WebRequests.Count | Should -Be 0
        @($r.DockerCalls | Where-Object { $_ -like '*compose*' }).Count | Should -Be 0
        (Test-Path (Join-Path $r.Dir 'daaf-docker')) | Should -Be $false
    }

    It "case 2: the refusal names the update, second-instance, and force escapes" {
        $r = Invoke-InstallUnderMock -Volumes @('myproj_daaf-data') -EnvVars @{ DAAF_PROJECT_NAME = 'myproj' }
        $r.Output | Should -BeLike "*Docker volume 'myproj_daaf-data'*"
        $r.Output | Should -BeLike "*(project 'myproj')*"
        $r.Output | Should -BeLike "*.\update_daaf.ps1*"
        $r.Output | Should -BeLike '*$env:DAAF_PROJECT_NAME = *'
        $r.Output | Should -BeLike '*$env:DAAF_PORT_MARIMO = *'
        $r.Output | Should -BeLike '*$env:DAAF_PORT_LOGVIEWER = *'
        $r.Output | Should -BeLike '*$env:DAAF_PORT_VSCODE = *'
        $r.Output | Should -BeLike "*Running multiple DAAF instances*"
        $r.Output | Should -BeLike "*01_installation_and_quickstart.md#running-multiple-daaf-instances*"
        $r.Output | Should -BeLike '*$env:DAAF_FORCE_REINSTALL = "1"*'
        $r.Output | Should -Not -BeLike "*An existing DAAF installation was detected.*"
        $r.WebRequests.Count | Should -Be 0
    }

    It "case 2: the FORCE hint for a non-default project sets DAAF_PROJECT_NAME on the same line (42q I-1)" {
        # The refusal ends the PowerShell session under irm | iex, and its $env:
        # values with it; a FORCE line without the project would re-run as 'daaf'.
        $r = Invoke-InstallUnderMock -Volumes @('myproj_daaf-data') -EnvVars @{ DAAF_PROJECT_NAME = 'myproj' }
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_PROJECT_NAME = "myproj"; $env:DAAF_FORCE_REINSTALL = "1"'
        @($r.Output -split '\r?\n') | Should -Not -Contain '  $env:DAAF_FORCE_REINSTALL = "1"'
        # The second-copy example is a different project from the refused one, and
        # (refused project not 'daaf') avoids the guide's example ports 2818-2820.
        $r.Output | Should -BeLike '*  $env:DAAF_PROJECT_NAME = "daaf-work"*'
        $r.Output | Should -BeLike '*  $env:DAAF_PORT_MARIMO = "2918"*'
    }

    It "case 2: following the printed FORCE hint in a new window re-targets the same project" {
        # A new window: only the variables the hint line sets (nothing else carried
        # over). The forced run must check and name myproj's volume, never daaf's
        # (which also exists).
        $r = Invoke-InstallUnderMock -Volumes @('myproj_daaf-data', 'daaf_daaf-data') -EnvVars @{ DAAF_PROJECT_NAME = 'myproj' }
        $hint = @($r.Output -split '\r?\n') | Where-Object { $_ -like '*$env:DAAF_FORCE_REINSTALL = "1"*' }
        @($hint).Count | Should -Be 1
        $hintVars = @{}
        foreach ($m in [regex]::Matches([string]$hint, '\$env:(\w+) = "([^"]*)"')) { $hintVars[$m.Groups[1].Value] = $m.Groups[2].Value }
        $r2 = Invoke-InstallUnderMock -Volumes @('myproj_daaf-data', 'daaf_daaf-data') -EnvVars $hintVars
        $r2.Output | Should -BeLike "*NOTE: An existing DAAF installation using Docker volume 'myproj_daaf-data' (project 'myproj')*"
        $r2.Output | Should -Not -BeLike "*'daaf_daaf-data'*"
        $r2.Output | Should -BeLike "*Downloading installation files*"
    }

    It "case 2: refusing project daaf-personal gives a different second-copy example (name and ports)" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf-personal_daaf-data') -EnvVars @{ DAAF_PROJECT_NAME = 'daaf-personal' }
        $r.Output | Should -BeLike "*(project 'daaf-personal')*"
        $r.Output | Should -BeLike '*  $env:DAAF_PROJECT_NAME = "daaf-work"*'
        $r.Output | Should -BeLike '*  $env:DAAF_PORT_MARIMO = "2918"*'
        $r.Output | Should -BeLike '*  $env:DAAF_PORT_LOGVIEWER = "2919"*'
        $r.Output | Should -BeLike '*  $env:DAAF_PORT_VSCODE = "2920"*'
        @($r.Output -split '\r?\n') | Should -Not -Contain '  $env:DAAF_PROJECT_NAME = "daaf-personal"'
        $r.Output | Should -Not -BeLike '*$env:DAAF_PORT_MARIMO = "2818"*'
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_PROJECT_NAME = "daaf-personal"; $env:DAAF_FORCE_REINSTALL = "1"'
    }

    It "case 2 with DAAF_FORCE_REINSTALL=1 proceeds with a NOTE" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -EnvVars @{ DAAF_FORCE_REINSTALL = '1' }
        $r.Output | Should -BeLike "*NOTE: An existing DAAF installation using Docker volume 'daaf_daaf-data'*"
        $r.Output | Should -BeLike "*re-install from this folder (DAAF_FORCE_REINSTALL=1).*"
        $r.Output | Should -BeLike "*Downloading installation files*"
        $r.WebRequests.Count | Should -BeGreaterThan 0
    }

    It "case 2 ignores DAAF_DATA_VOLUME_NAME (shared-workspace Step 3 still installs)" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -EnvVars @{ DAAF_PROJECT_NAME = 'daaf-gpt'; DAAF_DATA_VOLUME_NAME = 'daaf_daaf-data' }
        $r.Output | Should -Not -BeLike "*already exists, probably installed from*"
        $r.Output | Should -BeLike "*Downloading installation files*"
    }

    It "case 2 refuses when only DAAF_DATA_VOLUME_NAME is set (default project volume exists)" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -EnvVars @{ DAAF_DATA_VOLUME_NAME = 'daaf_daaf-data' }
        $r.Output | Should -BeLike "*Docker volume 'daaf_daaf-data' (project 'daaf')*"
        $r.Output | Should -BeLike "*already exists, probably installed from another folder, or its daaf-docker*"
        $r.WebRequests.Count | Should -Be 0
    }

    It "case 1: volume + compose here -- the unchanged WARNING, nothing downloaded" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose
        $r.Output | Should -BeLike "*An existing DAAF installation was detected.*"
        $r.Output | Should -Not -BeLike "*probably installed from*"
        $r.WebRequests.Count | Should -Be 0
    }

    It "case 1 with DAAF_FORCE_REINSTALL=1 proceeds (unchanged NOTE)" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose -EnvVars @{ DAAF_FORCE_REINSTALL = '1' }
        $r.Output | Should -BeLike "*Proceeding with re-install (DAAF_FORCE_REINSTALL=1)*"
        $r.Output | Should -BeLike "*Downloading installation files*"
    }

    It "case 3: compose here, no volume -- the unchanged 'incomplete' NOTE, then proceeds" {
        $r = Invoke-InstallUnderMock -WithCompose
        $r.Output | Should -BeLike "*previous install attempt was detected but appears incomplete*"
        $r.Output | Should -BeLike "*Downloading installation files*"
    }

    It "case 4: another project's volume does not block a fresh install" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -EnvVars @{ DAAF_PROJECT_NAME = 'daaf-personal' }
        $r.Output | Should -Not -BeLike "*already exists*"
        $r.Output | Should -Not -BeLike "*Could not check*"
        $r.Output | Should -BeLike "*Downloading installation files*"
        $r.WebRequests.Count | Should -BeGreaterThan 0
    }

    It "a volume check that cannot run (inspect AND list fail) refuses, never reads as absent" {
        $r = Invoke-InstallUnderMock -VolumeLsExit 1
        $r.Output | Should -BeLike "*Could not check whether a DAAF installation already exists*"
        $r.Output | Should -BeLike "*'daaf_daaf-data'*"
        $r.WebRequests.Count | Should -Be 0
        # Default project: the FORCE hint needs no DAAF_PROJECT_NAME.
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_FORCE_REINSTALL = "1"'
        $r.Output | Should -Not -BeLike '*$env:DAAF_PROJECT_NAME*'
    }

    It "the 'could not check' FORCE hint for a non-default project sets DAAF_PROJECT_NAME on the same line (42q I-1)" {
        $r = Invoke-InstallUnderMock -VolumeLsExit 1 -EnvVars @{ DAAF_PROJECT_NAME = 'myproj' }
        $r.Output | Should -BeLike "*looking for 'myproj_daaf-data'*"
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_PROJECT_NAME = "myproj"; $env:DAAF_FORCE_REINSTALL = "1"'
        @($r.Output -split '\r?\n') | Should -Not -Contain '  $env:DAAF_FORCE_REINSTALL = "1"'
        $r.WebRequests.Count | Should -Be 0
    }

    It "an unknown volume state with compose here also refuses (not the 'incomplete' NOTE)" {
        $r = Invoke-InstallUnderMock -VolumeLsExit 1 -WithCompose
        $r.Output | Should -BeLike "*Could not check whether a DAAF installation already exists*"
        $r.Output | Should -Not -BeLike "*appears incomplete*"
    }

    It "an unknown volume state with DAAF_FORCE_REINSTALL=1 proceeds with a NOTE" {
        $r = Invoke-InstallUnderMock -VolumeLsExit 1 -EnvVars @{ DAAF_FORCE_REINSTALL = '1' }
        $r.Output | Should -BeLike "*NOTE: Could not check whether Docker volume 'daaf_daaf-data' already exists.*"
        $r.Output | Should -BeLike "*Downloading installation files*"
    }

    # --- One project-name source (F-a) and the second-copy example (F-c) ---
    # Parity twin of the install.bats section of the same name: the settings file's
    # DAAF_PROJECT_NAME / DAAF_PORT_* / DAAF_DEV are set in the process environment
    # (process value wins) and the project is derived once; the volume checked, every
    # compose call (ComposeLog) and every hint use it.

    It "F-a: a re-install from a named instance's own folder builds, starts and execs the settings-file project and ports" {
        $r = Invoke-InstallUnderMock -Volumes @('x_daaf-data', 'daaf_daaf-data') -WithCompose -SettingsText $script:NamedSettings -BuildOk -EnvVars @{ DAAF_FORCE_REINSTALL = '1' }
        $r.Output | Should -BeLike "*NOTE: Existing installation detected. Proceeding with re-install (DAAF_FORCE_REINSTALL=1).*"
        $r.Output | Should -BeLike "*Installation complete*"
        $r.DockerCalls | Should -Contain 'volume inspect x_daaf-data'
        @($r.DockerCalls | Where-Object { $_ -like '*daaf_daaf-data*' }).Count | Should -Be 0
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=x M=3101 L=3102 V=3103 D=<unset>'
        $r.ComposeLog | Should -Contain 'compose up -d | P=x M=3101 L=3102 V=3103 D=<unset>'
        $r.ComposeLog.Count | Should -BeGreaterOrEqual 4
        @($r.ComposeLog | Where-Object { $_ -notlike '* | P=x M=3101 L=3102 V=3103 D=<unset>' }).Count | Should -Be 0
    }

    It "F-a: a process value wins over the settings file, key by key" {
        $r = Invoke-InstallUnderMock -Volumes @('y_daaf-data', 'x_daaf-data') -WithCompose -SettingsText $script:NamedSettings -EnvVars @{ DAAF_FORCE_REINSTALL = '1'; DAAF_PROJECT_NAME = 'y'; DAAF_PORT_MARIMO = '4001' }
        $r.DockerCalls | Should -Contain 'volume inspect y_daaf-data'
        @($r.DockerCalls | Where-Object { $_ -like '*x_daaf-data*' }).Count | Should -Be 0
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=y M=4001 L=3102 V=3103 D=<unset>'
    }

    It "F-a: settings-file parsing follows Import-DaafSettingsFile (column 0, quotes, CR, comments, repeated empty key)" {
        $text = "# DAAF_PROJECT_NAME=commented`r`n  DAAF_PORT_MARIMO=9999`r`nDAAF_PROJECT_NAME=`"x`"`r`nDAAF_PORT_MARIMO='3101'`r`nDAAF_PORT_LOGVIEWER=`r`nDAAF_PORT_LOGVIEWER=3102`r`nDAAF_DEV=1`r`n"
        $r = Invoke-InstallUnderMock -WithCompose -SettingsText $text
        $r.Output | Should -BeLike "*previous install attempt was detected but appears incomplete*"
        $r.DockerCalls | Should -Contain 'volume inspect x_daaf-data'
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=x M=3101 L=3102 V=<unset> D=1'
    }

    It "F-a: the case-1 WARNING names the settings-file project, and following its FORCE hint targets that project" {
        $r = Invoke-InstallUnderMock -Volumes @('x_daaf-data', 'daaf_daaf-data') -WithCompose -SettingsText $script:NamedSettings
        $r.Output | Should -BeLike "*WARNING: An existing DAAF installation was detected.*"
        @($r.Output -split '\r?\n') | Should -Contain "         (Docker volume 'x_daaf-data', project 'x')"
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_PROJECT_NAME = "x"; $env:DAAF_FORCE_REINSTALL = "1"'
        $r.ComposeLog.Count | Should -Be 0
        # Follow it in a NEW folder with only the variables the hint line sets: the
        # hint alone carries the project, so x is checked and built, never daaf.
        $hint = @($r.Output -split '\r?\n') | Where-Object { $_ -like '*$env:DAAF_FORCE_REINSTALL = "1"*' }
        @($hint).Count | Should -Be 1
        $hintVars = @{}
        foreach ($m in [regex]::Matches([string]$hint, '\$env:(\w+) = "([^"]*)"')) { $hintVars[$m.Groups[1].Value] = $m.Groups[2].Value }
        $r2 = Invoke-InstallUnderMock -Volumes @('x_daaf-data', 'daaf_daaf-data') -EnvVars $hintVars
        $r2.Output | Should -BeLike "*NOTE: An existing DAAF installation using Docker volume 'x_daaf-data' (project 'x')*"
        $r2.Output | Should -Not -BeLike "*'daaf_daaf-data'*"
        $r2.ComposeLog | Should -Contain 'compose build --progress plain | P=x M=<unset> L=<unset> V=<unset> D=<unset>'
    }

    It "F-a: the 'could not check' hint carries the settings-file project, and following it builds that project (43d ISSUE-1)" {
        $r = Invoke-InstallUnderMock -VolumeLsExit 1 -WithCompose -SettingsText $script:NamedSettings
        $r.Output | Should -BeLike "*looking for 'x_daaf-data'*"
        @($r.Output -split '\r?\n') | Should -Contain '  $env:DAAF_PROJECT_NAME = "x"; $env:DAAF_FORCE_REINSTALL = "1"'
        $hint = @($r.Output -split '\r?\n') | Where-Object { $_ -like '*$env:DAAF_FORCE_REINSTALL = "1"*' }
        $hintVars = @{}
        foreach ($m in [regex]::Matches([string]$hint, '\$env:(\w+) = "([^"]*)"')) { $hintVars[$m.Groups[1].Value] = $m.Groups[2].Value }
        # Same folder, Docker still cannot answer.
        $r2 = Invoke-InstallUnderMock -VolumeLsExit 1 -InDir $r.Dir -EnvVars $hintVars
        $r2.Output | Should -BeLike "*NOTE: Could not check whether Docker volume 'x_daaf-data' already exists.*"
        $r2.ComposeLog | Should -Contain 'compose build --progress plain | P=x M=3101 L=3102 V=3103 D=<unset>'
        @($r2.ComposeLog | Where-Object { $_ -like '*P=<unset>*' }).Count | Should -Be 0
    }

    It "F-a: a shared-workspace install's own folder -- the file's DAAF_DATA_VOLUME_NAME is not checked, and Compose never targets project daaf" {
        $text = "DAAF_PROJECT_NAME=daaf-gpt`nDAAF_PORT_MARIMO=2818`nDAAF_PORT_LOGVIEWER=2819`nDAAF_PORT_VSCODE=2820`nDAAF_DATA_VOLUME_NAME=daaf_daaf-data`n"
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose -SettingsText $text
        $r.Output | Should -BeLike "*previous install attempt was detected but appears incomplete*"
        $r.DockerCalls | Should -Contain 'volume inspect daaf-gpt_daaf-data'
        $r.DockerCalls | Should -Not -Contain 'volume inspect daaf_daaf-data'
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=daaf-gpt M=2818 L=2819 V=2820 D=<unset>'
        $r2 = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data', 'daaf-gpt_daaf-data') -WithCompose -SettingsText $text
        @($r2.Output -split '\r?\n') | Should -Contain "         (Docker volume 'daaf-gpt_daaf-data', project 'daaf-gpt')"
    }

    It "F-a: shared-workspace Step 3 from a new folder still installs, as daaf-gpt on its own ports" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -BuildOk -EnvVars @{ DAAF_PROJECT_NAME = 'daaf-gpt'; DAAF_PORT_MARIMO = '2818'; DAAF_PORT_LOGVIEWER = '2819'; DAAF_PORT_VSCODE = '2820'; DAAF_DATA_VOLUME_NAME = 'daaf_daaf-data' }
        $r.Output | Should -Not -BeLike "*already exists, probably installed from*"
        $r.Output | Should -BeLike "*Installation complete*"
        $r.DockerCalls | Should -Contain 'volume inspect daaf-gpt_daaf-data'
        $r.ComposeLog | Should -Contain 'compose up -d | P=daaf-gpt M=2818 L=2819 V=2820 D=<unset>'
    }

    It "F-a: a fresh install is unchanged -- no settings file, nothing bridged, project left to Compose's default" {
        $r = Invoke-InstallUnderMock -BuildOk
        $r.Output | Should -BeLike "*Installation complete*"
        $r.DockerCalls | Should -Contain 'volume inspect daaf_daaf-data'
        $r.ComposeLog.Count | Should -BeGreaterOrEqual 4
        @($r.ComposeLog | Where-Object { $_ -notlike '* | P=<unset> M=<unset> L=<unset> V=<unset> D=<unset>' }).Count | Should -Be 0
    }

    It "F-a: values adopted from an existing settings file are never written back (seeding leaves the file byte-identical)" {
        $text = $script:NamedSettings + "DAAF_DEV=1`n"
        $r = Invoke-InstallUnderMock -Volumes @('x_daaf-data') -WithCompose -SettingsText $text -BuildOk -EnvVars @{ DAAF_FORCE_REINSTALL = '1' }
        $r.Output | Should -BeLike "*An existing environment_settings.txt was found and left untouched.*"
        $r.Output | Should -Not -BeLike "*seeded these values*"
        $r.Output | Should -Not -BeLike "*Restarting the container*"
        [System.IO.File]::ReadAllText((Join-Path $r.Dir 'daaf-docker/environment_settings.txt')) | Should -BeExactly $text
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=x M=3101 L=3102 V=3103 D=1'
        @($r.ComposeLog | Where-Object { $_ -like '*--force-recreate*' }).Count | Should -Be 0
    }

    It "F-c: the second-copy example never repeats the refused project and avoids 2818-2820 for any non-default project" {
        # Same table as install.sh: daaf -> daaf-personal 2818-2820; daaf-work ->
        # daaf-lab 3018-3020; any other project -> daaf-work 2918-2920.
        foreach ($refused in @('daaf', 'daaf-personal', 'daaf-gpt', 'daafmac', 'daaf-work', 'daaf-lab', 'myproj')) {
            $want = switch -CaseSensitive ($refused) {
                'daaf' { 'daaf-personal 2818 2819 2820' }
                'daaf-work' { 'daaf-lab 3018 3019 3020' }
                default { 'daaf-work 2918 2919 2920' }
            }
            $envVars = @{}
            if ($refused -cne 'daaf') { $envVars['DAAF_PROJECT_NAME'] = $refused }
            $r = Invoke-InstallUnderMock -Volumes @("${refused}_daaf-data") -EnvVars $envVars
            $lines = @($r.Output -split '\r?\n')
            $got = foreach ($k in @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE')) {
                $hit = @($lines | Where-Object { $_ -match ('^  \$env:' + $k + ' = "([^"]*)"$') })
                @($hit).Count | Should -Be 1 -Because "refused=$refused key=$k"
                ([regex]::Match([string]$hit[0], '"([^"]*)"')).Groups[1].Value
            }
            ($got -join ' ') | Should -BeExactly $want -Because "refused=$refused"
            $got[0] | Should -Not -Be $refused
            if ($refused -cne 'daaf') {
                @($got[1..3] | Where-Object { $_ -in @('2818', '2819', '2820') }).Count | Should -Be 0 -Because "refused=$refused"
            }
        }
    }

    It "F-a (44q ISSUE-3, twin of bats 'no compose file here'): a settings file's project is checked AND built, and a present volume is refused by that name" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -SettingsText "DAAF_PROJECT_NAME=other`n"
        $r.Output | Should -Not -BeLike "*already exists, probably installed from*"
        $r.Output | Should -BeLike "*Downloading installation files*"
        $r.DockerCalls | Should -Contain 'volume inspect other_daaf-data'
        @($r.DockerCalls | Where-Object { $_ -like '*daaf_daaf-data*' }).Count | Should -Be 0
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=other M=<unset> L=<unset> V=<unset> D=<unset>'
        # Same folder (still no compose file: the mock download writes nothing), but
        # 'other' already has a volume: refused, naming 'other', FORCE hint carries it.
        $r2 = Invoke-InstallUnderMock -Volumes @('other_daaf-data', 'daaf_daaf-data') -InDir $r.Dir
        $r2.Output | Should -BeLike "*Docker volume 'other_daaf-data' (project 'other')*"
        @($r2.Output -split '\r?\n') | Should -Contain '  $env:DAAF_PROJECT_NAME = "other"; $env:DAAF_FORCE_REINSTALL = "1"'
        $r2.WebRequests.Count | Should -Be 0
        $r2.ComposeLog.Count | Should -Be 0
    }

    # --- Round #45 (parity twin of the install.bats section of the same name) ---

    It "#45 ISSUE-1: a settings-file project name is normalized as Compose does -- check, Compose and NOTE (no compose file, and with one)" {
        foreach ($pair in @(@('Work', 'work'), @('work ', 'work'), @('x # mine', 'xmine'), @('"x', 'x'), @('_x', 'x'))) {
            $raw = $pair[0]; $norm = $pair[1]
            foreach ($withCompose in @($false, $true)) {
                $r = Invoke-InstallUnderMock -WithCompose:$withCompose -SettingsText "DAAF_PROJECT_NAME=$raw`n"
                $lines = @($r.Output -split '\r?\n')
                $because = "raw=[$raw] compose=$withCompose"
                $lines | Should -Contain 'NOTE: Using these settings from daaf-docker\environment_settings.txt:' -Because $because
                $lines | Should -Contain "        DAAF_PROJECT_NAME=$raw" -Because $because
                $lines | Should -Contain "      Docker Compose uses the project name '$norm' for '$raw'." -Because $because
                $r.Output | Should -BeLike "*Downloading installation files*" -Because $because
                # Case-sensitive (-BeExactly / -ccontains): Pester's -Be / -Contain
                # ignore case, which would accept the raw 'Work_daaf-data'.
                @($r.DockerCalls | Where-Object { $_ -like 'volume inspect *' }) | Should -BeExactly @("volume inspect ${norm}_daaf-data") -Because $because
                ($r.ComposeLog -ccontains "compose build --progress plain | P=$norm M=<unset> L=<unset> V=<unset> D=<unset>") | Should -BeTrue -Because $because
            }
        }
    }

    It "#45 ISSUE-1: the case-2 refusal holds again for 'x ', '`"x', 'x # mine' and 'Work' (review 44q rows 45/49/53), and case 1 warns for them" {
        $vols = @('daaf_daaf-data', 'x_daaf-data', 'xmine_daaf-data', 'work_daaf-data')
        foreach ($pair in @(@('x ', 'x'), @('"x', 'x'), @('x # mine', 'xmine'), @('Work', 'work'))) {
            $raw = $pair[0]; $norm = $pair[1]
            $because = "raw=[$raw]"
            $r = Invoke-InstallUnderMock -Volumes $vols -SettingsText "DAAF_PROJECT_NAME=$raw`n"
            $r.Output | Should -BeLikeExactly "*WARNING: A DAAF installation using Docker volume '${norm}_daaf-data' (project '$norm')*" -Because $because
            (@($r.Output -split '\r?\n') -ccontains "  `$env:DAAF_PROJECT_NAME = `"$norm`"; `$env:DAAF_FORCE_REINSTALL = `"1`"") | Should -BeTrue -Because $because
            $r.WebRequests.Count | Should -Be 0 -Because $because
            $r1 = Invoke-InstallUnderMock -Volumes $vols -WithCompose -SettingsText "DAAF_PROJECT_NAME=$raw`n"
            (@($r1.Output -split '\r?\n') -ccontains "         (Docker volume '${norm}_daaf-data', project '$norm')") | Should -BeTrue -Because $because
            (@($r1.Output -split '\r?\n') -ccontains "  `$env:DAAF_PROJECT_NAME = `"$norm`"; `$env:DAAF_FORCE_REINSTALL = `"1`"") | Should -BeTrue -Because $because
            $r1.WebRequests.Count | Should -Be 0 -Because $because
        }
        # The reviewer's exact volume set: 'x # mine' is project xmine (absent), a
        # fresh install that touches neither existing install.
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data', 'x_daaf-data') -SettingsText "DAAF_PROJECT_NAME=x # mine`n"
        $r.Output | Should -Not -BeLike "*already exists, probably installed from*"
        $r.DockerCalls | Should -Contain 'volume inspect xmine_daaf-data'
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=xmine M=<unset> L=<unset> V=<unset> D=<unset>'
    }

    It "#45 ISSUE-1: a process project name is normalized too, the NOTE says so, and a new settings file is seeded with the normalized name" {
        $r = Invoke-InstallUnderMock -BuildOk -WithTemplate -EnvVars @{ DAAF_PROJECT_NAME = 'Work' }
        $r.Output | Should -BeLike "*Installation complete*"
        @($r.Output -split '\r?\n') | Should -Contain "NOTE: Docker Compose uses the project name 'work' for 'Work'."
        $r.Output | Should -Not -BeLike "*Using these settings from*"
        ($r.DockerCalls -ccontains 'volume inspect work_daaf-data') | Should -BeTrue
        $r.ComposeLog.Count | Should -BeGreaterOrEqual 4
        @($r.ComposeLog | Where-Object { $_ -cnotlike '* | P=work M=<unset> L=<unset> V=<unset> D=<unset>' }).Count | Should -Be 0
        $seeded = @(Get-Content -LiteralPath (Join-Path $r.Dir 'daaf-docker/environment_settings.txt') | Where-Object { $_ -cmatch '^DAAF_PROJECT_NAME=' })
        $seeded | Should -BeExactly @('DAAF_PROJECT_NAME=work')
    }

    It "#45 ISSUE-1: a name that normalizes to nothing is refused before anything is downloaded (file and process, with and without a compose file)" {
        foreach ($src in @('file', 'process')) {
            foreach ($withCompose in @($false, $true)) {
                $because = "src=$src compose=$withCompose"
                if ($src -eq 'file') {
                    $val = '___'
                    $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose:$withCompose -SettingsText "DAAF_PROJECT_NAME=$val`n"
                } else {
                    $val = '@@'
                    $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose:$withCompose -EnvVars @{ DAAF_PROJECT_NAME = $val }
                }
                $lines = @($r.Output -split '\r?\n')
                $lines | Should -Contain "ERROR: DAAF_PROJECT_NAME='$val' cannot be used as a Docker Compose" -Because $because
                $lines | Should -Contain "       project name. A project name may use lowercase letters, digits, '-'" -Because $because
                $lines | Should -Contain "       and '_', and must start with a letter or digit." -Because $because
                $lines | Should -Contain "       Nothing has been downloaded or changed." -Because $because
                if ($src -eq 'file') {
                    $lines | Should -Contain '       (This value was read from daaf-docker\environment_settings.txt.)' -Because $because
                } else {
                    $r.Output | Should -Not -BeLike '*(This value was read from*' -Because $because
                }
                $r.Output | Should -Not -BeLike "*[[]1/4]*" -Because $because
                $r.WebRequests.Count | Should -Be 0 -Because $because
                $r.DockerCalls | Should -Not -Contain 'volume inspect daaf_daaf-data' -Because $because
                @($r.DockerCalls | Where-Object { $_ -like 'volume *' -or $_ -like 'compose *' }).Count | Should -Be 0 -Because $because
            }
        }
    }

    It "#45 ISSUE-2: with a settings-file project, every failure-path command carries -p and every re-run text names the project" {
        $retry = '(set DAAF_PROJECT_NAME=x, and DAAF_FORCE_REINSTALL=1 if prompted).'
        foreach ($fail in @(' build --progress', ' up -d', 'exec -T daaf-docker true', 'git clone', 'cp -a /tmp/daaf-clone', 'test -f /daaf/CLAUDE.md')) {
            $r = Invoke-InstallUnderMock -WithCompose -SettingsText $script:NamedSettings -BuildOk -FailOn $fail
            $lines = @($r.Output -split '\r?\n')
            $composeF = (Join-Path $r.Dir 'daaf-docker') + '\docker-compose.yml'
            $execLine = '  docker compose -p x -f ' + $composeF + ' exec -T daaf-docker `'
            $because = "fail=[$fail]"
            switch ($fail) {
                ' build --progress' {
                    $lines | Should -Contain "You can safely re-run this installer to retry $retry" -Because $because
                    $lines | Should -Contain '  $env:DAAF_PROJECT_NAME = "x"; $env:DAAF_DIAG_BUILD = "1"' -Because $because
                }
                ' up -d' {
                    $lines | Should -Contain "You can safely re-run this installer to retry $retry" -Because $because
                }
                'exec -T daaf-docker true' {
                    $i = [array]::IndexOf($lines, "  docker compose -p x -f $composeF up -d")
                    $i | Should -BeGreaterThan 2 -Because $because
                    $lines[($i - 3)..($i - 1)] | Should -Be @('  $env:DAAF_PORT_MARIMO = "3101"', '  $env:DAAF_PORT_LOGVIEWER = "3102"', '  $env:DAAF_PORT_VSCODE = "3103"') -Because $because
                }
                'git clone' {
                    @($lines | Where-Object { $_ -ceq $execLine }).Count | Should -Be 2 -Because $because
                    $lines | Should -Contain "You can also safely re-run this installer to retry from scratch $retry" -Because $because
                }
                'cp -a /tmp/daaf-clone' {
                    @($lines | Where-Object { $_ -ceq $execLine }).Count | Should -Be 1 -Because $because
                    $lines | Should -Contain "You can also safely re-run this installer to retry from scratch $retry" -Because $because
                }
                'test -f /daaf/CLAUDE.md' {
                    $lines | Should -Contain '  docker compose -p x exec daaf-docker bash' -Because $because
                }
            }
            $r.Output | Should -Not -Match 'docker compose (-f|exec|down|up)' -Because $because
            $r.Output | Should -Not -BeLike '*(set DAAF_FORCE_REINSTALL=1 if prompted)*' -Because $because
        }
    }

    It "#45 ISSUE-2: a process project that is seeded -- the recreate-failure and final-summary commands carry -p" {
        $r = Invoke-InstallUnderMock -BuildOk -WithTemplate -FailOn '--force-recreate' -EnvVars @{ DAAF_PROJECT_NAME = 'x' }
        $lines = @($r.Output -split '\r?\n')
        $r.Output | Should -BeLike "*Could not restart the container to apply the seeded settings*"
        $lines | Should -Contain '        docker compose -p x down'
        $lines | Should -Contain '  docker compose -p x exec daaf-docker bash   # enter the container'
        $r.Output | Should -Not -Match 'docker compose (-f|exec|down|up)'
    }

    It "#45 ISSUE-2: for the default project every printed command and re-run text is unchanged (no -p)" {
        $retry = '(set DAAF_FORCE_REINSTALL=1 if prompted).'
        foreach ($fail in @(' build --progress', ' up -d', 'exec -T daaf-docker true', 'git clone', 'cp -a /tmp/daaf-clone', 'test -f /daaf/CLAUDE.md', '--force-recreate')) {
            $r = Invoke-InstallUnderMock -BuildOk -WithTemplate -FailOn $fail
            $lines = @($r.Output -split '\r?\n')
            $composeF = (Join-Path $r.Dir 'daaf-docker') + '\docker-compose.yml'
            $execLine = '  docker compose -f ' + $composeF + ' exec -T daaf-docker `'
            $because = "fail=[$fail]"
            switch ($fail) {
                ' build --progress' {
                    $lines | Should -Contain "You can safely re-run this installer to retry $retry" -Because $because
                    $lines | Should -Contain '  $env:DAAF_DIAG_BUILD = "1"' -Because $because
                }
                ' up -d' { $lines | Should -Contain "You can safely re-run this installer to retry $retry" -Because $because }
                'exec -T daaf-docker true' {
                    $i = [array]::IndexOf($lines, "  docker compose -f $composeF up -d")
                    $i | Should -BeGreaterThan 0 -Because $because
                    $lines[$i - 1] | Should -Be 'Check Docker Desktop for errors, then retry with:' -Because $because
                }
                'git clone' {
                    @($lines | Where-Object { $_ -ceq $execLine }).Count | Should -Be 2 -Because $because
                    $lines | Should -Contain "You can also safely re-run this installer to retry from scratch $retry" -Because $because
                }
                'cp -a /tmp/daaf-clone' {
                    @($lines | Where-Object { $_ -ceq $execLine }).Count | Should -Be 1 -Because $because
                    $lines | Should -Contain "You can also safely re-run this installer to retry from scratch $retry" -Because $because
                }
                'test -f /daaf/CLAUDE.md' { $lines | Should -Contain '  docker compose exec daaf-docker bash' -Because $because }
                '--force-recreate' {
                    $lines | Should -Contain '        docker compose down' -Because $because
                    $lines | Should -Contain '  docker compose exec daaf-docker bash   # enter the container' -Because $because
                }
            }
            $r.Output | Should -Not -BeLike '*docker compose -p*' -Because $because
            $r.Output | Should -Not -BeLike '*DAAF_PROJECT_NAME =*' -Because $because
            $r.Output | Should -Not -BeLike '*NOTE: Using these settings*' -Because $because
        }
    }

    It "#45 ISSUE-2: ports set for the default project ride on the printed up -d command (no -p)" {
        $r = Invoke-InstallUnderMock -BuildOk -FailOn 'exec -T daaf-docker true' -EnvVars @{ DAAF_PORT_MARIMO = '3101' }
        $lines = @($r.Output -split '\r?\n')
        $composeF = (Join-Path $r.Dir 'daaf-docker') + '\docker-compose.yml'
        $i = [array]::IndexOf($lines, "  docker compose -f $composeF up -d")
        $i | Should -BeGreaterThan 0
        $lines[$i - 1] | Should -Be '  $env:DAAF_PORT_MARIMO = "3101"'
    }

    It "#45 SUGGESTION-1: a process value wins over the settings file for ALL FIVE keys" {
        $text = $script:NamedSettings + "DAAF_DEV=1`n"
        $r = Invoke-InstallUnderMock -Volumes @('y_daaf-data', 'x_daaf-data') -WithCompose -SettingsText $text -EnvVars @{ DAAF_FORCE_REINSTALL = '1'; DAAF_PROJECT_NAME = 'y'; DAAF_PORT_MARIMO = '4001'; DAAF_PORT_LOGVIEWER = '4002'; DAAF_PORT_VSCODE = '4003'; DAAF_DEV = '0' }
        $r.Output | Should -Not -BeLike "*NOTE: Using these settings*"
        $r.DockerCalls | Should -Contain 'volume inspect y_daaf-data'
        @($r.DockerCalls | Where-Object { $_ -like '*x_daaf-data*' }).Count | Should -Be 0
        $r.ComposeLog | Should -Contain 'compose build --progress plain | P=y M=4001 L=4002 V=4003 D=0'
        @($r.ComposeLog | Where-Object { $_ -notlike '* | P=y M=4001 L=4002 V=4003 D=0' }).Count | Should -Be 0
    }

    It "#45 SUGGESTION-2: the case-1 WARNING says when the folder has no environment_settings.txt (first line unchanged)" {
        $r = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose
        $lines = @($r.Output -split '\r?\n')
        $i = [array]::IndexOf($lines, 'WARNING: An existing DAAF installation was detected.')
        $i | Should -BeGreaterThan -1
        $lines[($i + 1)..($i + 4)] | Should -Be @(
            "         (Docker volume 'daaf_daaf-data', project 'daaf')",
            "         This folder has no environment_settings.txt, so the project name comes",
            "         from your shell (default 'daaf'). If you meant to install a separate",
            "         copy here, set DAAF_PROJECT_NAME (and its ports) again first.")
        $r2 = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -InDir $r.Dir -SettingsText "# my real API keys`n"
        $r2.Output | Should -BeLike "*WARNING: An existing DAAF installation was detected.*"
        $r2.Output | Should -Not -BeLike "*This folder has no environment_settings.txt*"
    }

    It "#45 SUGGESTION-3: one NOTE lists the adopted settings before the decision; none for a template-seeded file or when nothing is adopted" {
        $text = "# keys`nDAAF_PROJECT_NAME=x`nDAAF_PORT_MARIMO=3101`nDAAF_PORT_LOGVIEWER=`nDAAF_DEV=1`n"
        $r = Invoke-InstallUnderMock -Volumes @('x_daaf-data') -WithCompose -SettingsText $text
        $lines = @($r.Output -split '\r?\n')
        $i = [array]::IndexOf($lines, 'NOTE: Using these settings from daaf-docker\environment_settings.txt:')
        $i | Should -BeGreaterThan -1
        $lines[($i + 1)..($i + 4)] | Should -Be @('        DAAF_PROJECT_NAME=x', '        DAAF_PORT_MARIMO=3101', '        DAAF_DEV=1', '')
        @($lines | Where-Object { $_ -like 'NOTE: Using these settings*' }).Count | Should -Be 1
        $r.Output | Should -Not -BeLike "*Docker Compose uses the project name*"
        [array]::IndexOf($lines, 'WARNING: An existing DAAF installation was detected.') | Should -BeGreaterThan $i
        # CI-shaped: the shipped template (bridged keys commented out) plus an active
        # DAAF_BRANCH: nothing adopted, no NOTE.
        $template = [System.IO.File]::ReadAllText("$RepoRoot/scripts/host/environment_settings_example.txt") + "DAAF_BRANCH=main`n"
        $r2 = Invoke-InstallUnderMock -Volumes @('daaf_daaf-data') -WithCompose -SettingsText $template
        $r2.Output | Should -Not -BeLike "*NOTE: Using these settings*"
        $r2.Output | Should -Not -BeLike "*This folder has no environment_settings.txt*"
        @($r2.Output -split '\r?\n') | Should -Contain "         (Docker volume 'daaf_daaf-data', project 'daaf')"
    }

    It "#45 NIT-1: a settings file that cannot be read stops with a plain ERROR before anything is downloaded, even when the process supplies every key" {
        $runDir = Join-Path $script:TestDir ("unread-" + [guid]::NewGuid().ToString('N'))
        $settings = Join-Path $runDir 'daaf-docker/environment_settings.txt'
        $null = New-Item -ItemType Directory -Path (Join-Path $runDir 'daaf-docker') -Force
        [System.IO.File]::WriteAllText($settings, "DAAF_PROJECT_NAME=x`n")
        $lock = $null
        if ($IsLinux -or $IsMacOS) {
            if ((& id -u) -eq '0') { Set-ItResult -Skipped -Because 'root can open a mode-000 file'; return }
            & chmod 000 $settings
        } else {
            # Windows: hold the file open with no sharing, as another program might.
            $lock = [System.IO.File]::Open($settings, 'Open', 'Read', 'None')
        }
        try {
            $r = Invoke-InstallUnderMock -InDir $runDir -EnvVars @{ DAAF_PROJECT_NAME = 'y'; DAAF_PORT_MARIMO = '4001'; DAAF_PORT_LOGVIEWER = '4002'; DAAF_PORT_VSCODE = '4003'; DAAF_DEV = '0' }
        } finally {
            if ($null -ne $lock) { $lock.Dispose() } else { & chmod 600 $settings }
        }
        $lines = @($r.Output -split '\r?\n')
        $i = [array]::IndexOf($lines, 'ERROR: Could not read daaf-docker\environment_settings.txt. Check its')
        $i | Should -BeGreaterThan -1
        $lines[($i + 1)..($i + 2)] | Should -Be @(
            '       permissions, and close any program that has it open, then run the',
            '       installer again. Nothing has been downloaded or changed.')
        $r.Output | Should -Not -BeLike "*[[]1/4]*"
        $r.WebRequests.Count | Should -Be 0
        @($r.DockerCalls | Where-Object { $_ -like 'volume *' -or $_ -like 'compose *' }).Count | Should -Be 0
    }

    Context "Get-DaafVolumeState" {
        BeforeAll {
            $script:SavedTestMode = $env:DAAF_TEST_MODE
            $script:SavedDryRun = $env:DAAF_DRY_RUN
            $env:DAAF_DRY_RUN = $null
            $env:DAAF_TEST_MODE = "1"
            . "$RepoRoot/scripts/host/install.ps1"
        }
        AfterAll {
            $env:DAAF_TEST_MODE = $script:SavedTestMode
            $env:DAAF_DRY_RUN = $script:SavedDryRun
        }

        It "a failed inspect falls back to an exact, case-sensitive name list" {
            # inspect always fails; the list holds a longer name, a case variant, and
            # one exact name (with a trailing CR, as a Windows console may add).
            function docker {
                $argStr = $args -join ' '
                $global:LASTEXITCODE = 0
                if ($argStr -like 'volume inspect *') { $global:LASTEXITCODE = 1; return }
                if ($argStr -eq 'volume ls -q') { 'daaf_daaf-data-restore-tmp'; 'DAAF_DAAF-DATA'; "listed_vol`r" }
            }
            Get-DaafVolumeState -Name 'listed_vol' | Should -BeExactly 'present'
            Get-DaafVolumeState -Name 'daaf_daaf-data' | Should -BeExactly 'absent'
        }

        It "inspect success is present; a failed list is unknown" {
            function docker {
                $argStr = $args -join ' '
                $global:LASTEXITCODE = 0
                if ($argStr -eq 'volume inspect here') { return }
                if ($argStr -like 'volume inspect *') { $global:LASTEXITCODE = 1; return }
                if ($argStr -eq 'volume ls -q') { $global:LASTEXITCODE = 1 }
            }
            Get-DaafVolumeState -Name 'here' | Should -BeExactly 'present'
            Get-DaafVolumeState -Name 'gone' | Should -BeExactly 'unknown'
        }
    }
}
