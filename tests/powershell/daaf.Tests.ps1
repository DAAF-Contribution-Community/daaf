# ============================================================================
# Pester tests for daaf.ps1 -- DAAF Control Panel (Windows)
# ============================================================================
# daaf.ps1 is the interactive Control Panel: a persistent menu loop that
# delegates to sibling .ps1 scripts. These tests cover the pure-logic units
# that are testable without Docker or an interactive terminal -- syntax,
# structure, the dispatch/quit logic, and helper functions dot-sourced from
# daaf_lib.ps1. Full menu-draw + dashboard behavior is exercised by the
# DAAF_DRY_RUN smoke tests in ci-scripts.yml.
# ============================================================================

Describe "daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "daaf.ps1 parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }

        It "daaf_lib.ps1 parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/daaf_lib.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/daaf.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "enables Set-StrictMode -Version 3.0 AFTER the DAAF_TEST_MODE guard" {
            # Strict mode is dynamically scoped -- it must be placed after the
            # DAAF_TEST_MODE dot-source guard (which sits just above the main loop, past
            # all function definitions) so Pester's dot-sourcing never leaks strict mode
            # into the whole test session, while the real menu loop and every function it
            # calls -- including the dot-sourced daaf_lib.ps1 helpers -- run protected.
            # Assert BOTH presence and ordering.
            $Content | Should -Match 'Set-StrictMode -Version 3\.0'
            $guardIdx  = $Content.LastIndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx  | Should -BeGreaterThan -1
            $strictIdx | Should -BeGreaterThan $guardIdx
        }

        It "dot-sources daaf_lib.ps1" {
            $Content | Should -Match 'daaf_lib\.ps1'
        }

        It "references DAAF_NESTED for nested delegation" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "supports DAAF_TEST_MODE dot-sourcing guard" {
            $Content | Should -Match 'DAAF_TEST_MODE'
        }

        It "supports DAAF_DRY_RUN smoke path" {
            $Content | Should -Match 'DAAF_DRY_RUN'
        }

        It "defines Get-DaafStatus" {
            $Content | Should -Match 'function Get-DaafStatus'
        }

        It "defines Show-DaafMenu" {
            $Content | Should -Match 'function Show-DaafMenu'
        }

        It "defines Invoke-DaafChoice dispatcher" {
            $Content | Should -Match 'function Invoke-DaafChoice'
        }

        It "defines Invoke-DaafDelegate for guarded child calls" {
            $Content | Should -Match 'function Invoke-DaafDelegate\b'
        }

        It "spawns interactive delegates via Start-Process for console inheritance" {
            # The interactive/maintenance delegates must launch the child via
            # Start-Process -NoNewWindow (console handle inheritance) rather than
            # calling it in-process, so docker TTY allocation works. Guard against
            # a revert to `& child.ps1`.
            $Content | Should -Match 'Start-Process'
            $Content | Should -Match '-NoNewWindow'
            $Content | Should -Match '\(Get-Process -Id \$PID\)\.Path'
        }

        It "guards the parent against Ctrl+C while a delegate owns the console" {
            $Content | Should -Match 'TreatControlCAsInput'
        }

        It "drives the main loop off a script-scoped run flag (not return values)" {
            # Quit is signaled by clearing $script:DaafMenuRunning, keeping the
            # handler chain out of a success-stream-capturing context.
            $Content | Should -Match '\$script:DaafMenuRunning'
            $Content | Should -Match 'while\s*\(\s*\$script:DaafMenuRunning\s*\)'
        }

        It "prints Goodbye! on both quit and EOF paths" {
            # CI smoke asserts "Goodbye!"; both Invoke-DaafQuit and the
            # Read-DaafChoice EOF branch must print it.
            ([regex]::Matches($Content, 'Goodbye!')).Count | Should -BeGreaterOrEqual 2
        }

        It "delivers container payloads via base64-as-argument (transport v3)" {
            # PS 5.1 mangles embedded double quotes in native-process args (v1
            # `bash -c <payload>` failure), and piping a PS string to a native
            # process's stdin appends a CRLF and is unreliable on Windows (v2
            # `<payload> | bash -s` failure). v3 base64-encodes the payload and
            # passes the token as an argument: the token is [A-Za-z0-9+/=] only,
            # so PS 5.1 cannot damage it and no stdin is involved.
            #   * base64 decode must be present in the remote wrapper.
            $Content | Should -Match 'base64 -d'
            #   * the payload must NOT be piped into docker on stdin (no `$var | docker`).
            $Content | Should -Not -Match '\$\w+\s*\|\s*docker'
            #   * the remote `-c` literal must be single-quoted (zero double
            #     quotes inside it) -- guard against `bash -c "..."`.
            $Content | Should -Not -Match "bash -c `""
            #   * the payload must be encoded to base64 before dispatch.
            $Content | Should -Match 'ToBase64String'
        }

        It "batches the port probe into a single Get-DaafPortStatus exec" {
            $Content | Should -Match 'function Get-DaafPortStatus'
            $Content | Should -Match 'PORT:\$p'
        }

        It "wraps the main loop in try/catch for unexpected failures" {
            $Content | Should -Match 'catch'
        }

        It "checks for docker-compose.yml in preflight" {
            $Content | Should -Match 'docker-compose\.yml'
        }

        It "displays the Control Panel banner" {
            $Content | Should -Match 'DAAF Control Panel'
        }
    }

    Context "Menu parity with daaf.sh" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/daaf.ps1" -Raw
        }

        It "offers all ten numbered options" {
            foreach ($opt in @(
                "Start Claude Code", "Browse Notebooks", "Browse Files \(VS Code\)",
                "View Session Logs", "Open Container Shell", "Create Backup",
                "Restore from Backup", "Check for Updates", "Rebuild Container",
                "Stop Web Services")) {
                $Content | Should -Match $opt
            }
        }

        It "delegates to the .ps1 siblings (not .sh)" {
            $Content | Should -Match 'run_daaf\.ps1'
            $Content | Should -Match 'backup_daaf\.ps1'
            $Content | Should -Match 'restore_from_backup\.ps1'
            $Content | Should -Match 'update_daaf\.ps1'
            $Content | Should -Match 'rebuild_daaf\.ps1'
        }

        It "mirrors the code-server default password source" {
            $Content | Should -Match 'launch_code_server\.sh'
            $Content | Should -Match '"daaf"'
        }
    }
}

# ============================================================================
# daaf_lib.ps1 structure
# ============================================================================

Describe "daaf_lib.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:LibContent = Get-Content "$RepoRoot/scripts/host/daaf_lib.ps1" -Raw
    }

    It "carries NO Set-StrictMode directive (Library Rule)" {
        # A dot-sourced library shares the caller's scope, so a Set-StrictMode
        # directive here would impose strict mode on every caller. Entry points
        # enable strict mode themselves; the library must stay strict-clean and
        # directive-free, mirroring daaf_lib.sh's deliberate lack of a `set` line.
        # Match only an actual directive LINE -- one that begins with Set-StrictMode
        # after leading whitespace -- so the cmdlet name appearing in the header's
        # explanatory prose (each such line starts with `#`) does not trip the guard.
        $directiveLines = @(
            $LibContent -split "`n" | Where-Object { $_ -match '^\s*Set-StrictMode\b' }
        )
        $directiveLines.Count | Should -Be 0
    }

    It "defines Open-DaafUrl" {
        $LibContent | Should -Match 'function Open-DaafUrl'
    }

    It "defines Test-DaafPort" {
        $LibContent | Should -Match 'function Test-DaafPort'
    }

    It "defines Confirm-DaafContainer" {
        $LibContent | Should -Match 'function Confirm-DaafContainer'
    }

    It "carries the container-side /proc/net/tcp probe verbatim" {
        $LibContent | Should -Match '/proc/net/tcp'
        $LibContent | Should -Match '0A'
    }

    It "delivers the probe payload via base64-as-argument (transport v3)" {
        # Test-DaafPort must base64-encode its payload and pass the token as a
        # native arg, decoding it container-side. The embedded double quotes in
        # the awk pattern rule out v1 `bash -c <payload>` (PS 5.1 native-arg
        # quoting bug), and PS-string-to-native-stdin CRLF contamination ruled
        # out v2 `<payload> | bash -s`. Guard against a revert to either.
        #   * base64 decode present in the remote wrapper.
        $LibContent | Should -Match 'base64 -d'
        #   * payload encoded before dispatch.
        $LibContent | Should -Match 'ToBase64String'
        #   * payload NOT piped into docker on stdin.
        $LibContent | Should -Not -Match '\$\w+\s*\|\s*docker'
        #   * remote `-c` literal is single-quoted (no double quotes inside it).
        $LibContent | Should -Not -Match "bash -c `""
    }

    It "guards against redundant dot-sourcing via a function-existence probe" {
        $LibContent | Should -Match 'Get-Command Read-DaafLine'
    }

    It "defines Import-DaafSettingsFile" {
        $LibContent | Should -Match 'function Import-DaafSettingsFile'
    }
}

# ============================================================================
# Import-DaafSettingsFile unit tests (daaf_lib.ps1)
# ============================================================================

Describe "daaf_lib.ps1 Import-DaafSettingsFile" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        # Dot-source the library in a clean scope
        . "$RepoRoot/scripts/host/daaf_lib.ps1"
    }

    BeforeEach {
        $script:TmpDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-lib-test-$(Get-Random)")
        $script:SettingsFile = Join-Path $script:TmpDir "environment_settings.txt"
        # Clear any leftover env vars from prior tests
        Remove-Item Env:DAAF_PROJECT_NAME  -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_MARIMO   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_LOGVIEWER -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_VSCODE   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_DEV           -ErrorAction SilentlyContinue
    }

    AfterEach {
        Remove-Item -Recurse -Force $script:TmpDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PROJECT_NAME  -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_MARIMO   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_LOGVIEWER -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_VSCODE   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_DEV           -ErrorAction SilentlyContinue
    }

    It "picks up a DAAF_* value from the settings file" {
        Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=myinstance`nDAAF_PORT_MARIMO=3001"
        Import-DaafSettingsFile -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "myinstance"
        $env:DAAF_PORT_MARIMO  | Should -Be "3001"
    }

    It "picks up the DAAF_DEV build flag from the settings file" {
        # DAAF_DEV rides the same whitelist bridge as the four multi-instance keys
        # so it can reach `docker compose build` as --build-arg DAAF_DEV=${DAAF_DEV:-0}.
        Set-Content -Path $script:SettingsFile -Value "DAAF_DEV=1"
        Import-DaafSettingsFile -SettingsFile $script:SettingsFile
        $env:DAAF_DEV | Should -Be "1"
    }

    It "lets an already-set process env var win over the file value" {
        Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=fromfile"
        $env:DAAF_PROJECT_NAME = "fromshell"
        Import-DaafSettingsFile -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "fromshell"
    }

    It "is a no-op when the settings file is absent" {
        $absentPath = Join-Path $script:TmpDir "nonexistent.txt"
        Import-DaafSettingsFile -SettingsFile $absentPath
        $env:DAAF_PROJECT_NAME | Should -BeNullOrEmpty
    }

    It "tolerates CRLF line endings" {
        [System.IO.File]::WriteAllBytes($script:SettingsFile, [System.Text.Encoding]::ASCII.GetBytes("DAAF_PORT_VSCODE=3020`r`n"))
        Import-DaafSettingsFile -SettingsFile $script:SettingsFile
        $env:DAAF_PORT_VSCODE | Should -Be "3020"
    }

    It "ignores non-DAAF keys (does not inject arbitrary variables)" {
        Set-Content -Path $script:SettingsFile -Value "ANTHROPIC_API_KEY=sk-secret`nDAAF_PROJECT_NAME=safe"
        Import-DaafSettingsFile -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME   | Should -Be "safe"
        $env:ANTHROPIC_API_KEY   | Should -BeNullOrEmpty
    }
}

# ============================================================================
# Behavioral tests -- dot-source the script and call functions directly
# ============================================================================

Describe "daaf.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/daaf.ps1"

        # Declare a docker function so Pester can mock it
        function docker {}
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    Context "Invoke-DaafChoice dispatch (flag-based quit)" {
        # The dispatcher signals quit by clearing the script-scoped
        # $script:DaafMenuRunning flag, NOT via a captured return value. Routing
        # quit through a return value consumed in the loop's conditional put the
        # handler chain in a success-stream-capturing context, which stripped
        # console handles from the interactive delegates and broke docker TTY
        # allocation. These tests assert the NEW flag contract: non-quit choices
        # leave the flag set (loop keeps running); quit clears it.

        It "leaves the run flag set for an empty choice (redraw)" {
            $script:DaafMenuRunning = $true
            Invoke-DaafChoice ""
            $script:DaafMenuRunning | Should -BeTrue
        }

        It "leaves the run flag set for an invalid choice (redraw)" {
            $script:DaafMenuRunning = $true
            Invoke-DaafChoice "zzz" 6>$null
            $script:DaafMenuRunning | Should -BeTrue
        }

        It "clears the run flag for quit" {
            $script:DaafMenuRunning = $true
            Invoke-DaafChoice "q" 6>$null
            $script:DaafMenuRunning | Should -BeFalse
        }

        It "clears the run flag for uppercase quit" {
            $script:DaafMenuRunning = $true
            Invoke-DaafChoice "Q" 6>$null
            $script:DaafMenuRunning | Should -BeFalse
        }

        It "does not emit a boolean control value on the success stream for quit" {
            # Guard against a regression to return-value dispatch: capturing the
            # dispatcher's success stream must yield no [bool] control token
            # (any incidental handler output is fine, but not a bare $true/$false).
            $script:DaafMenuRunning = $true
            $captured = Invoke-DaafChoice "q" 6>$null
            @($captured | Where-Object { $_ -is [bool] }).Count | Should -Be 0
        }
    }

    Context "Test-DaafPort dry-run mock" {
        BeforeAll {
            $script:OrigDryRun = $env:DAAF_DRY_RUN
            $script:OrigMockPorts = $env:DAAF_MOCK_PORTS
        }
        AfterAll {
            $env:DAAF_DRY_RUN = $script:OrigDryRun
            $env:DAAF_MOCK_PORTS = $script:OrigMockPorts
        }

        It "returns true when DAAF_MOCK_PORTS lists the port as yes" {
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_MOCK_PORTS = "2718:yes"
            Test-DaafPort 2718 | Should -BeTrue
        }

        It "returns false when the port is not in DAAF_MOCK_PORTS" {
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_MOCK_PORTS = "2718:yes"
            Test-DaafPort 2720 | Should -BeFalse
        }
    }

    Context "Get-DaafPortStatus dry-run mock (batched probe)" {
        BeforeAll {
            $script:OrigDryRun = $env:DAAF_DRY_RUN
            $script:OrigMockPorts = $env:DAAF_MOCK_PORTS
        }
        AfterAll {
            $env:DAAF_DRY_RUN = $script:OrigDryRun
            $env:DAAF_MOCK_PORTS = $script:OrigMockPorts
        }

        It "reports per-port booleans from DAAF_MOCK_PORTS in one call" {
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_MOCK_PORTS = "2718:yes 2720:yes"
            $status = Get-DaafPortStatus
            $status["2718"] | Should -BeTrue
            $status["2719"] | Should -BeFalse
            $status["2720"] | Should -BeTrue
        }

        It "reports all ports false when DAAF_MOCK_PORTS is empty" {
            $env:DAAF_DRY_RUN = "1"
            $env:DAAF_MOCK_PORTS = ""
            $status = Get-DaafPortStatus
            $status["2718"] | Should -BeFalse
            $status["2719"] | Should -BeFalse
            $status["2720"] | Should -BeFalse
        }
    }

    Context "Confirm-DaafContainer dry-run" {
        It "returns true in dry-run mode without Docker" {
            $script:OrigDryRun = $env:DAAF_DRY_RUN
            $env:DAAF_DRY_RUN = "1"
            try {
                Confirm-DaafContainer | Should -BeTrue
            } finally {
                $env:DAAF_DRY_RUN = $script:OrigDryRun
            }
        }
    }
}

# ============================================================================
# Dry-run mode (full menu draw driven with 'q')
# ============================================================================

Describe "daaf.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-panel-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
        # Seed a backup dir so the last-backup dashboard path executes.
        New-Item -ItemType Directory -Path (Join-Path $script:TestDir "2026-06-18_daaf_backup") | Out-Null
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "draws the menu and quits cleanly on 'q'" {
        # CHILD PROCESS REQUIRED: piping `"q"` into an in-process `& script.ps1`
        # call feeds the PowerShell pipeline, not stdin. Read-DaafLine consumes
        # input via [Console]::In.ReadLine(), which only sees real stdin -- so the
        # script would block waiting for terminal input if run in-process.
        # Spawning a child process via -NoProfile -File ensures the pipe connects
        # to the child's stdin and the menu-draw + quit path completes.
        $env:DAAF_DRY_RUN = "1"
        Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
        $psExe = (Get-Process -Id $PID).Path
        $output = "q" | & $psExe -NoProfile -File "$RepoRoot/scripts/host/daaf.ps1" 2>&1 | Out-String
        $output | Should -BeLike "*DAAF Control Panel*"
        $output | Should -BeLike "*Goodbye!*"
    }

    It "daaf_lib.ps1 defines Read-DaafLine" {
        $libContent = Get-Content "$RepoRoot/scripts/host/daaf_lib.ps1" -Raw
        $libContent | Should -Match 'function Read-DaafLine'
    }
}
