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

        It "checks container exists (running or stopped) with docker compose ps -aq" {
            $Content | Should -Match 'docker compose ps -aq daaf-docker'
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

        It "extracts the settings key column-0 strict (no .Trim(), rejects padded keys like bash)" {
            # Import-DaafSettingsInline must extract the key WITHOUT .Trim() so a
            # whitespace-padded "  DAAF_PROJECT_NAME=..." line falls through as
            # unrecognized -- matching the bash loaders' column-0 `case` glob. The
            # pre-fix `.Substring(0, $eq).Trim()` accepted padded keys, diverging from
            # bash across all ten PS loader copies.
            $Content | Should -Match '\$key = \$line\.Substring\(0, \$eq\)'
            $Content | Should -Not -Match '\$key = \$line\.Substring\(0, \$eq\)\.Trim\(\)'
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

    It "creates the diagnostic builder under DAAF_DIAG_BUILD=1 (dry-run mock: inspect miss -> create)" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $env:DAAF_DIAG_BUILD = "1"
        $output = & "$RepoRoot/scripts/host/rebuild_daaf.ps1" *>&1
        $env:DAAF_DIAG_BUILD = $null
        ($output | Out-String) | Should -BeLike "*Created diagnostic buildx builder*"
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
        It "outputs error when no container exists (running or stopped)" {
            $Content | Should -Match "No daaf-docker container found \(running or stopped\)"
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

    Context "Diagnostic builder (DAAF_DIAG_BUILD)" {
        It "gates the diagnostic builder behind DAAF_DIAG_BUILD=1" {
            $Content | Should -Match 'DAAF_DIAG_BUILD -eq "1"'
        }

        It "creates a docker-container buildx builder with raised size AND speed step-log limits" {
            $Content | Should -Match 'buildx create --name daaf-diag-builder'
            $Content | Should -Match 'BUILDKIT_STEP_LOG_MAX_SIZE=16777216'
            $Content | Should -Match 'BUILDKIT_STEP_LOG_MAX_SPEED=10485760'
        }

        It "selects the builder via BUILDX_BUILDER and RESTORES the prior value after the build (non-destructive)" {
            # Regression: the pre-fix code cleared the var unconditionally with
            # `if ($UseDiagBuilder) { $env:BUILDX_BUILDER = $null }`, which REMOVES the
            # variable and clobbers a user's own pre-exported BUILDX_BUILDER. The fix
            # saves the prior value first and restores it (removing only when the user had
            # none). Assert the save + conditional restore, and that the destructive
            # single-line unconditional clear is gone. (`$env:BUILDX_BUILDER = $null` still
            # appears in the else-branch and in the hazard comment, so we negative-match
            # the specific one-line `if ($UseDiagBuilder) { ... = $null }` form instead.)
            $Content | Should -Match '\$env:BUILDX_BUILDER = "daaf-diag-builder"'
            $Content | Should -Match '\$priorBuildxBuilder = \$env:BUILDX_BUILDER'
            $Content | Should -Match 'if \(\$null -ne \$priorBuildxBuilder\) \{ \$env:BUILDX_BUILDER = \$priorBuildxBuilder \}'
            $Content | Should -Not -Match 'if \(\$UseDiagBuilder\) \{ \$env:BUILDX_BUILDER = \$null \}'
        }

        It "falls open to the default builder when the builder cannot be created" {
            # Parity with the bash fail-open test: when both inspect and create
            # fail, UseDiagBuilder stays $false so the build runs on the default
            # builder (BUILDX_BUILDER is only set when UseDiagBuilder is $true).
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
            $Content | Should -Match 'DAAF_DIAG_BUILD'
        }
    }

    Context "Diagnostic builder: fail-open behavior (dry-run: create fails)" {
        BeforeAll {
            $script:OrigDryRun2 = $env:DAAF_DRY_RUN
            $script:OrigNested2 = $env:DAAF_NESTED
            $script:OrigDiag2 = $env:DAAF_DIAG_BUILD
            $script:TestDir2 = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-rebuild-failopen-$(Get-Random)")
            Push-Location $script:TestDir2
            New-FakeComposeFile -Directory $script:TestDir2.FullName
        }
        AfterAll {
            $env:DAAF_DRY_RUN = $script:OrigDryRun2
            $env:DAAF_NESTED = $script:OrigNested2
            $env:DAAF_DIAG_BUILD = $script:OrigDiag2
            if ((Get-Location).Path -eq $script:TestDir2.FullName) { Pop-Location }
            Remove-Item -Recurse -Force $script:TestDir2 -ErrorAction SilentlyContinue
        }

        It "runs the build and does not create the builder when DAAF_DIAG_BUILD_TEST_CREATE_FAIL=1" {
            # The script's dry-run docker mock honors DAAF_DIAG_BUILD_TEST_CREATE_FAIL
            # to simulate a `buildx create` failure, exercising the fail-open path
            # end-to-end (parity with the bash fail-open test).
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_NESTED = "1"
            $env:DAAF_DIAG_BUILD = "1"
            $env:DAAF_DIAG_BUILD_TEST_CREATE_FAIL = "1"
            $output = & "$RepoRoot/scripts/host/rebuild_daaf.ps1" *>&1
            $env:DAAF_DIAG_BUILD_TEST_CREATE_FAIL = $null
            ($output | Out-String) | Should -BeLike "*could not be*"
            ($output | Out-String) | Should -Not -BeLike "*Created diagnostic buildx builder*"
        }
    }
}

# ============================================================================
# Native stderr reaches the user (dispatch #63: G2 readiness, G6 preference)
# ============================================================================
# Windows PowerShell 5.1 drops a native command's stderr from a 2>&1 capture when
# $ErrorActionPreference is 'SilentlyContinue' (shell-scripting gotchas), and (CI-observed
# 2026-10-12) from a `2>> file` redirect too. The readiness errors ("Docker
# reported:") are kept in memory under 'Continue' instead. pwsh 7 keeps the lines
# either way, so the behavioral test cannot catch a revert on its own.

Describe "rebuild_daaf.ps1 native stderr reaches the user (dispatch #63)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:ScriptPath = "$RepoRoot/scripts/host/rebuild_daaf.ps1"
        $tokens = $null
        $parseErrors = $null
        $script:Ast = [System.Management.Automation.Language.Parser]::ParseFile($script:ScriptPath, [ref]$tokens, [ref]$parseErrors)
        $script:ParseErrorCount = @($parseErrors).Count
    }

    It "G6: sets `$PSNativeCommandUseErrorActionPreference = `$false at top level, right after `$ErrorActionPreference = 'Stop' and before the first docker call" {
        $ParseErrorCount | Should -Be 0
        $assign = @($Ast.FindAll({
            param($n) ($n -is [System.Management.Automation.Language.AssignmentStatementAst]) -and ($n.Left.Extent.Text -eq '$PSNativeCommandUseErrorActionPreference')
        }, $true))
        $assign.Count | Should -Be 1
        $assign[0].Right.Extent.Text | Should -BeExactly '$false'
        $assign[0].Parent | Should -Be $Ast.EndBlock
        $stmts = @($Ast.EndBlock.Statements)
        $at = [array]::IndexOf($stmts, $assign[0])
        $stmts[$at - 1].Extent.Text | Should -BeExactly '$ErrorActionPreference = "Stop"'
        $dockerCalls = @($Ast.FindAll({
            param($n) ($n -is [System.Management.Automation.Language.CommandAst]) -and ($n.GetCommandName() -eq 'docker')
        }, $true) | Sort-Object { $_.Extent.StartOffset })
        $assign[0].Extent.StartOffset | Should -BeLessThan $dockerCalls[0].Extent.StartOffset
    }

    It "G2: the readiness capture merges stderr (2>&1) inside a 'Continue' bracket, with no temp file or 2>> redirect" {
        $eap = @($Ast.FindAll({
            param($n) ($n -is [System.Management.Automation.Language.AssignmentStatementAst]) -and ($n.Left.Extent.Text -eq '$ErrorActionPreference')
        }, $true) | Sort-Object { $_.Extent.StartOffset })
        $caps = @($Ast.FindAll({
            param($n) ($n -is [System.Management.Automation.Language.AssignmentStatementAst]) -and ($n.Left.Extent.Text -eq '$readyOut')
        }, $true))
        $caps.Count | Should -Be 1
        $caps[0].Right.Extent.Text | Should -BeExactly '@(docker compose exec -T daaf-docker true 2>&1)'
        $open = @($eap | Where-Object { $_.Extent.EndOffset -le $caps[0].Extent.StartOffset }) | Select-Object -Last 1
        $close = @($eap | Where-Object { $_.Extent.StartOffset -ge $caps[0].Extent.EndOffset }) | Select-Object -First 1
        $open.Right.Extent.Text | Should -BeExactly '"Continue"'
        $close.Right.Extent.Text | Should -BeExactly '$savedEAP'
        $code = @((Get-Content -LiteralPath $ScriptPath) | Where-Object { $_ -notmatch '^\s*#' })
        @($code | Where-Object { $_ -match '2>>' -or $_ -match 'readyLog' }).Count | Should -Be 0
    }

    It "G2: a readiness timeout shows the last five of a native docker's stderr lines under 'Docker reported:'" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
        # The real script against a bash fake docker on PATH. Every readiness poll
        # writes a numbered stderr line and exits 1; Start-Sleep is shadowed below
        # (dynamic scoping) so the 30 polls do not take a minute.
        $work = Join-Path $TestDrive ("g2-" + [guid]::NewGuid().ToString('N'))
        $bin = Join-Path $work 'bin'
        $null = New-Item -ItemType Directory -Force -Path $bin
        New-FakeComposeFile -Directory $work
        $count = Join-Path $TestDrive 'g2-count'
        $fake = @(
            '#!/usr/bin/env bash'
            'case "$*" in'
            '    info) exit 0 ;;'
            "    'compose ps -aq daaf-docker') echo cid123; exit 0 ;;"
            "    'compose exec -T daaf-docker true')"
            "        n=`$(( `$(cat '$count' 2>/dev/null || echo 0) + 1 )); echo `"`$n`" > '$count'"
            '        echo "Error response from daemon: container fake is restarting (attempt $n)" >&2; exit 1 ;;'
            '    *) exit 0 ;;'
            'esac'
        ) -join "`n"
        [System.IO.File]::WriteAllText((Join-Path $bin 'docker'), $fake + "`n")
        & chmod +x (Join-Path $bin 'docker')
        function Start-Sleep {
            [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseShouldProcessForStateChangingFunctions', '')]
            param([int]$Seconds)
            $null = $Seconds
        }
        $saved = @{}
        foreach ($k in @('PATH', 'DAAF_DRY_RUN', 'DAAF_TEST_MODE', 'DAAF_NESTED', 'DAAF_DIAG_BUILD')) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process') }
        Push-Location -LiteralPath $work
        try {
            $env:PATH = $bin + [System.IO.Path]::PathSeparator + $saved['PATH']
            Remove-Item Env:DAAF_DRY_RUN, Env:DAAF_TEST_MODE, Env:DAAF_DIAG_BUILD -ErrorAction SilentlyContinue
            $env:DAAF_NESTED = "1"
            $out = & $ScriptPath *>&1 | Out-String
            $code = $LASTEXITCODE
        } finally {
            Pop-Location
            foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') }
        }
        $code | Should -Be 1
        $lines = @($out -split '\r?\n')
        $i = [array]::IndexOf($lines, '  Docker reported:')
        $i | Should -BeGreaterThan 0 -Because "the output was: $out"
        $lines[$i - 1] | Should -Be 'ERROR: Container did not become ready within 60 seconds.'
        $lines[($i + 1)..($i + 7)] | Should -Be @(
            '    Error response from daemon: container fake is restarting (attempt 26)'
            '    Error response from daemon: container fake is restarting (attempt 27)'
            '    Error response from daemon: container fake is restarting (attempt 28)'
            '    Error response from daemon: container fake is restarting (attempt 29)'
            '    Error response from daemon: container fake is restarting (attempt 30)'
            ''
            'Check Docker Desktop for errors.')
    }
}
