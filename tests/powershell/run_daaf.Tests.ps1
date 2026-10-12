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

        It "declares #Requires -Version 5.1" {
            $Content | Should -Match '#Requires\s+-Version\s+5\.1'
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "enables Set-StrictMode -Version 3.0 AFTER the DAAF_TEST_MODE guard" {
            # Strict mode is dynamically scoped -- it must be placed after the
            # DAAF_TEST_MODE dot-source guard so Pester's dot-sourcing (which returns
            # at the guard) never leaks strict mode into the whole test session, while
            # real executions run fully protected. Assert BOTH presence and ordering.
            $Content | Should -Match 'Set-StrictMode -Version 3\.0'
            $guardIdx  = $Content.IndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx  | Should -BeGreaterThan -1
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

        It "extracts the settings key column-0 strict (no .Trim(), rejects padded keys like bash)" {
            # Import-DaafSettingsInline must extract the key WITHOUT .Trim() so a
            # whitespace-padded "  DAAF_PROJECT_NAME=..." line falls through as
            # unrecognized -- matching the bash loaders' column-0 `case` glob. The
            # pre-fix `.Substring(0, $eq).Trim()` accepted padded keys, diverging from
            # bash across the PS loader copies.
            $Content | Should -Match '\$key = \$line\.Substring\(0, \$eq\)'
            $Content | Should -Not -Match '\$key = \$line\.Substring\(0, \$eq\)\.Trim\(\)'
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

# ============================================================================
# Native stderr handling (dispatch #63: G3 running check, G6 preference)
# ============================================================================
# G3: the running check, the container ID passed to `docker inspect`, and the
# inspect date are stdout only (2>$null). A 2>&1 merge let a stderr-only line
# (such as a Compose warning) count as a container ID on pwsh 7, and put stderr
# text into the inspect arguments and the date; Windows PowerShell 5.1 drops those
# lines under SilentlyContinue, so the bug showed only on pwsh 7.

Describe "run_daaf.ps1 native stderr handling (dispatch #63)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:ScriptPath = "$RepoRoot/scripts/host/run_daaf.ps1"
        $tokens = $null
        $parseErrors = $null
        $script:Ast = [System.Management.Automation.Language.Parser]::ParseFile($script:ScriptPath, [ref]$tokens, [ref]$parseErrors)
        $script:ParseErrorCount = @($parseErrors).Count

        # Run the real script against a native fake docker (a bash script on PATH, so
        # stderr crosses the real native-command path). $FakeBody is the body of the
        # fake's `case "$*" in ... esac`; every call is logged to $TestDrive/<tag>.log.
        function Invoke-RunDaafUnderFake {
            param([string]$Tag, [string]$FakeBody, [switch]$WithSettings)
            $work = Join-Path $TestDrive ("$Tag-" + [guid]::NewGuid().ToString('N'))
            $bin = Join-Path $work 'bin'
            $null = New-Item -ItemType Directory -Force -Path $bin
            New-FakeComposeFile -Directory $work
            if ($WithSettings) { [System.IO.File]::WriteAllText((Join-Path $work 'environment_settings.txt'), "# test`n") }
            $callLog = Join-Path $TestDrive "$Tag.log"
            $fake = "#!/usr/bin/env bash`nprintf '%s\n' `"`$*`" >> '$callLog'`ncase `"`$*`" in`n$FakeBody`n    *) exit 0 ;;`nesac`n"
            [System.IO.File]::WriteAllText((Join-Path $bin 'docker'), $fake)
            & chmod +x (Join-Path $bin 'docker')
            $saved = @{}
            foreach ($k in @('PATH', 'DAAF_DRY_RUN', 'DAAF_TEST_MODE', 'DAAF_NESTED')) { $saved[$k] = [Environment]::GetEnvironmentVariable($k, 'Process') }
            Push-Location -LiteralPath $work
            try {
                $env:PATH = $bin + [System.IO.Path]::PathSeparator + $saved['PATH']
                Remove-Item Env:DAAF_DRY_RUN, Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
                $env:DAAF_NESTED = "1"
                $out = & $script:ScriptPath *>&1 | Out-String
                $code = $LASTEXITCODE
            } finally {
                Pop-Location
                foreach ($k in $saved.Keys) { [Environment]::SetEnvironmentVariable($k, $saved[$k], 'Process') }
            }
            $calls = @()
            if (Test-Path -LiteralPath $callLog) { $calls = @(Get-Content -LiteralPath $callLog) }
            [pscustomobject]@{ Output = $out; ExitCode = $code; Calls = $calls }
        }
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

    It "G3: the running check, the container ID and the inspect date read stdout only (2>`$null, not a 2>&1 merge)" {
        $expected = @{
            '$CidOutput' = 'docker compose ps -q daaf-docker 2>$null'
            '$_cid'      = 'docker compose ps -q daaf-docker 2>$null'
            '$_created'  = "docker inspect --format '{{.Created}}' `$_cid 2>`$null"
        }
        foreach ($var in $expected.Keys) {
            $cap = @($Ast.FindAll({
                param($n) ($n -is [System.Management.Automation.Language.AssignmentStatementAst]) -and ($n.Left.Extent.Text -eq $var) -and ($n.Right.Extent.Text -match '^docker\s')
            }, $true))
            $cap.Count | Should -Be 1 -Because "$var is captured once"
            $cap[0].Right.Extent.Text | Should -BeExactly $expected[$var]
        }
    }

    It "G3: a stderr-only 'compose ps -q' (no container ID) is treated as NOT running" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
        # `compose up -d` fails, which ends the run right after the decision under test.
        $body = "    info) exit 0 ;;`n    'compose ps -q daaf-docker') echo 'WARN[0000] fake compose warning on stderr' >&2; exit 0 ;;`n    'compose up -d') exit 1 ;;"
        $r = Invoke-RunDaafUnderFake -Tag 'g3-stopped' -FakeBody $body
        $r.Output | Should -BeLike "*Starting DAAF container...*"
        $r.Output | Should -BeLike "*ERROR: Failed to start the container.*"
        $r.Output | Should -Not -BeLike "*DAAF container is already running.*"
        $r.ExitCode | Should -Be 1
        $r.Calls | Should -Contain 'compose up -d'
    }

    It "G3: a stderr line next to the container ID reaches neither the inspect arguments nor the date (the settings hint still shows)" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
        # The container was created in 2000, so the new environment_settings.txt is
        # newer and the hint must show. The fake answers the inspect only when its
        # arguments are exactly the ID (a stray stderr argument gets no date).
        $body = @(
            "    info) exit 0 ;;"
            "    'compose ps -q daaf-docker') echo abc123; echo 'WARN[0000] fake compose warning on stderr' >&2; exit 0 ;;"
            "    'inspect --format {{.Created}} abc123') echo '2000-01-01T00:00:00.000000000Z'; echo 'WARN[0000] fake inspect warning on stderr' >&2; exit 0 ;;"
            "    inspect*) exit 1 ;;"
        ) -join "`n"
        $r = Invoke-RunDaafUnderFake -Tag 'g3-running' -FakeBody $body -WithSettings
        $r.Output | Should -BeLike "*DAAF container is already running.*"
        $r.Calls | Should -Contain 'inspect --format {{.Created}} abc123'
        @($r.Calls | Where-Object { $_ -like 'inspect*' }).Count | Should -Be 1
        $r.Output | Should -BeLike "*NOTE: Your environment_settings.txt file has been modified since this container was started.*"
        $r.ExitCode | Should -Be 0
    }
}
