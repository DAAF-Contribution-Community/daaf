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

        It "declares #Requires -Version 5.1" {
            $Content | Should -Match '#Requires\s+-Version\s+5\.1'
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

        It "saves and restores DAAF_NESTED around each nested delegate (no unconditional clobber)" {
            # Regression guard for the DAAF_NESTED clobber bug: each delegate must
            # capture the parent's DAAF_NESTED before setting it to "1" and restore
            # it in finally, so a value inherited when the panel itself runs nested
            # survives instead of being unconditionally removed (which re-enabled
            # child pause prompts for the rest of the panel session).
            $setCount     = ([regex]::Matches($Content, '\$env:DAAF_NESTED = "1"')).Count
            $saveCount    = ([regex]::Matches($Content, '\$savedNested = \$env:DAAF_NESTED')).Count
            $restoreCount = ([regex]::Matches($Content, 'if \(\$null -ne \$savedNested\) \{ \$env:DAAF_NESTED = \$savedNested \} else \{ Remove-Item Env:\\DAAF_NESTED')).Count
            $removeCount  = ([regex]::Matches($Content, 'Remove-Item Env:\\DAAF_NESTED')).Count
            $setCount     | Should -BeGreaterOrEqual 2
            $saveCount    | Should -Be $setCount
            $restoreCount | Should -Be $setCount
            # Every Remove-Item Env:\DAAF_NESTED must live inside a conditional restore.
            $removeCount  | Should -Be $restoreCount
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

        It "renders the exact numbered launch order and unchanged management choices" {
            $expectedLaunchLines = @(
                '    Write-Host "  LAUNCH"',
                '    Write-Host "    1) Start Claude Code"',
                '    Write-Host "    2) Browse Files (VS Code)"',
                '    Write-Host "    3) View Session Logs"',
                '    Write-Host "    4) View Marimo Notebooks (Python)"',
                '    Write-Host "    5) View Quarto Notebooks (R)"',
                '    Write-Host "    6) Open Terminal in Container"'
            )
            $launchPattern = ($expectedLaunchLines | ForEach-Object { [regex]::Escape($_) }) -join '\r?\n'
            $Content | Should -Match $launchPattern

            $expectedManageLines = @(
                '    Write-Host "  MANAGE"',
                '    Write-Host "    7) Create Backup"',
                '    Write-Host "    8) Restore from Backup"',
                '    Write-Host "    9) Check for Updates"',
                '    Write-Host "   10) Rebuild Container"',
                '    Write-Host "   11) Restart Container"',
                '    Write-Host "   12) Stop Web Services"'
            )
            $managePattern = ($expectedManageLines | ForEach-Object { [regex]::Escape($_) }) -join '\r?\n'
            $Content | Should -Match $managePattern
        }

        It "maps manage choices 10-12 to Rebuild, Restart, and Stop Web Services" {
            $expectedDispatchLines = @(
                '        "10" { Invoke-DaafRebuild }',
                '        "11" { Invoke-DaafRestart }',
                '        "12" { Invoke-DaafServiceStop }'
            )
            $dispatchPattern = ($expectedDispatchLines | ForEach-Object { [regex]::Escape($_) }) -join '\r?\n'
            $Content | Should -Match $dispatchPattern
            $Content | Should -Match ([regex]::Escape('Please enter a number (1-12), h, or q.'))
        }

        It "documents Restart Container (11) and Stop Web Services (12) in Show-DaafHelp" {
            $helpStart = $Content.IndexOf('function Show-DaafHelp')
            $helpEnd = $Content.IndexOf('function Invoke-DaafQuit', $helpStart)
            $helpBody = $Content.Substring($helpStart, $helpEnd - $helpStart)
            $helpBody | Should -Match ([regex]::Escape('Write-Host "  11) Restart Container" -ForegroundColor Cyan'))
            $helpBody | Should -Match ([regex]::Escape('Write-Host "  12) Stop Web Services" -ForegroundColor Cyan'))
            $helpBody | Should -Match 'environment_settings\.txt'
            $helpBody | Should -Match 'no image build'
        }

        It "says 'rebuild required' in the Restart help entry and indents items 11/12 descriptions by 5 spaces" {
            $helpStart = $Content.IndexOf('function Show-DaafHelp')
            $helpEnd = $Content.IndexOf('function Invoke-DaafQuit', $helpStart)
            $helpLines = @($Content.Substring($helpStart, $helpEnd - $helpStart) -split '\r?\n')

            # Description block = the Write-Host lines after an item heading, up to
            # the blank `Write-Host ""` separator.
            $descByItem = @{}
            foreach ($heading in @('11) Restart Container', '12) Stop Web Services')) {
                $headIdx = -1
                for ($i = 0; $i -lt $helpLines.Count; $i++) {
                    if ($helpLines[$i] -match ('^\s*Write-Host "  ' + [regex]::Escape($heading) + '"')) { $headIdx = $i; break }
                }
                $headIdx | Should -BeGreaterThan -1
                $desc = New-Object System.Collections.Generic.List[string]
                for ($i = $headIdx + 1; $i -lt $helpLines.Count; $i++) {
                    if ($helpLines[$i] -match '^\s*Write-Host ""\s*$') { break }
                    $desc.Add($helpLines[$i])
                }
                $desc.Count | Should -BeGreaterThan 0
                foreach ($line in $desc) {
                    # Exactly five spaces inside the literal, then text.
                    $line | Should -Match '^\s*Write-Host "     [^ ]'
                }
                $descByItem[$heading] = $desc
            }

            # The phrase is wrapped across two lines, so join the string literals
            # (unescaping `" to ") and collapse whitespace before comparing.
            $flat = (@($descByItem['11) Restart Container'] | ForEach-Object {
                [regex]::Match($_, '^\s*Write-Host "(.*)"\s*$').Groups[1].Value -replace '`"', '"'
            }) -join ' ') -replace '\s+', ' '
            $flat | Should -BeLike '*Settings marked "rebuild required" there*'
            # Same examples and Rebuild list as the handler's intro text.
            $flat | Should -BeLike '*there (such as DAAF_DEV, or turning on the provider shim for the first time), and changes to the Dockerfile, packages, or docker-compose.yml, need Rebuild Container instead.*'
            $flat | Should -BeLike '*no image build. It ends any open Claude Code session or web service. Settings marked*'
            $flat | Should -Not -BeLike '*web service first.*'
        }

        It "renders the exact ordered launch headings in Show-DaafHelp" {
            $helpStart = $Content.IndexOf('function Show-DaafHelp')
            $helpEnd = $Content.IndexOf('function Invoke-DaafQuit', $helpStart)
            $helpStart | Should -BeGreaterThan -1
            $helpEnd | Should -BeGreaterThan $helpStart
            $helpBody = $Content.Substring($helpStart, $helpEnd - $helpStart)

            $actualHelpHeadings = @(
                $helpBody -split '\r?\n' |
                    Where-Object { $_ -match '^\s*Write-Host "  [1-6][)] ' } |
                    ForEach-Object { $_.Trim() }
            ) -join "`n"
            $expectedHelpHeadings = @(
                'Write-Host "  1) Start Claude Code" -ForegroundColor Cyan',
                'Write-Host "  2) Browse Files (VS Code)" -ForegroundColor Cyan',
                'Write-Host "  3) View Session Logs" -ForegroundColor Cyan',
                'Write-Host "  4) View Marimo Notebooks (Python)" -ForegroundColor Cyan',
                'Write-Host "  5) View Quarto Notebooks (R)" -ForegroundColor Cyan',
                'Write-Host "  6) Open Terminal in Container" -ForegroundColor Cyan'
            ) -join "`n"
            $actualHelpHeadings | Should -BeExactly $expectedHelpHeadings
        }

        It "maps launch choices 1-6 to the matching handlers" {
            $expectedDispatchLines = @(
                '        "1"  { Invoke-DaafClaudeCode }',
                '        "2"  { Invoke-DaafVSCode }',
                '        "3"  { Invoke-DaafLogViewer }',
                '        "4"  { Invoke-DaafNotebookBrowser }',
                '        "5"  { Invoke-DaafQuartoViewer }',
                '        "6"  { Invoke-DaafShell }'
            )
            $dispatchPattern = ($expectedDispatchLines | ForEach-Object { [regex]::Escape($_) }) -join '\r?\n'
            $Content | Should -Match $dispatchPattern
        }

        It "uses terminal wording for option 6 and its handler messages" {
            ([regex]::Matches($Content, 'Open Terminal in Container')).Count | Should -BeGreaterOrEqual 2
            $Content | Should -Match 'Opening terminal in container'
            $Content | Should -Match 'Container terminal ended with an error'
            $Content | Should -Not -Match 'Open Container Shell'
        }

        It "delegates to the .ps1 siblings (not .sh)" {
            $Content | Should -Match 'run_daaf\.ps1'
            $Content | Should -Match 'backup_daaf\.ps1'
            $Content | Should -Match 'restore_from_backup\.ps1'
            $Content | Should -Match 'update_daaf\.ps1'
            $Content | Should -Match 'rebuild_daaf\.ps1'
            $Content | Should -Match 'view_quarto\.ps1'
        }

        It "invokes the Quarto viewer with no target through the console-inheriting nested delegate" {
            $Content | Should -Match 'function Invoke-DaafQuartoViewer\s*\{\s*Invoke-DaafDelegate "view_quarto\.ps1"\s*\}'
            $Content | Should -Match '\$env:DAAF_NESTED = "1"'
            # DAAF_NESTED is saved before the set and conditionally restored (not
            # unconditionally removed), so a parent-inherited value survives the
            # nested delegate. See the save/restore regression test above.
            $Content | Should -Match '\$savedNested = \$env:DAAF_NESTED'
            $Content | Should -Match 'if \(\$null -ne \$savedNested\) \{ \$env:DAAF_NESTED = \$savedNested \} else \{ Remove-Item Env:\\DAAF_NESTED'
            $Content | Should -Match 'Start-Process.*-FilePath'
        }

        It "explains recursive Quarto selection and cancellation in option 5 help" {
            $helpStart = $Content.IndexOf('function Show-DaafHelp')
            $helpEnd = $Content.IndexOf('function Invoke-DaafQuit', $helpStart)
            $helpBody = $Content.Substring($helpStart, $helpEnd - $helpStart)
            $helpBody | Should -Match 'recursiv'
            $helpBody | Should -Match 'select'
            $helpBody | Should -Match 'cancel'
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

    It "defines Sync-DaafSettingsFile (provenance-tracked reload)" {
        $LibContent | Should -Match 'function Sync-DaafSettingsFile'
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

    Context "Sync-DaafSettingsFile (provenance-tracked reload)" {
        # Import-DaafSettingsFile records the keys it adopted FROM THE FILE in
        # $script:DaafKeysFromFile; Sync-DaafSettingsFile removes exactly those and
        # imports again, so an edited file takes effect while user-set values win.
        BeforeEach {
            $script:DaafKeysFromFile = @()
        }

        It "picks up a value changed in the file after the first import" {
            Set-Content -Path $script:SettingsFile -Value "DAAF_PORT_MARIMO=3001"
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            Set-Content -Path $script:SettingsFile -Value "DAAF_PORT_MARIMO=3002"
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            # A plain second import keeps the first value (already-set wins).
            $env:DAAF_PORT_MARIMO | Should -Be "3001"
            Sync-DaafSettingsFile -SettingsFile $script:SettingsFile
            $env:DAAF_PORT_MARIMO | Should -Be "3002"
        }

        It "keeps a user-set value winning over the file after a reload" {
            Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=fromfile"
            $env:DAAF_PROJECT_NAME = "fromshell"
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=edited"
            Sync-DaafSettingsFile -SettingsFile $script:SettingsFile
            $env:DAAF_PROJECT_NAME | Should -Be "fromshell"
            @($script:DaafKeysFromFile).Count | Should -Be 0
        }

        It "unsets a key that was removed from the file" {
            Set-Content -Path $script:SettingsFile -Value "DAAF_PORT_VSCODE=3020"
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            Set-Content -Path $script:SettingsFile -Value "# DAAF_PORT_VSCODE removed"
            Sync-DaafSettingsFile -SettingsFile $script:SettingsFile
            $env:DAAF_PORT_VSCODE | Should -BeNullOrEmpty
        }

        It "tracks only file-adopted keys, without duplicates across repeated loads" {
            Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=inst`nDAAF_PORT_MARIMO=`nDAAF_PORT_MARIMO=3001`nDAAF_DEV=1"
            $env:DAAF_DEV = "0"
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            Sync-DaafSettingsFile -SettingsFile $script:SettingsFile
            Import-DaafSettingsFile -SettingsFile $script:SettingsFile
            (@($script:DaafKeysFromFile) -join ' ') | Should -BeExactly "DAAF_PROJECT_NAME DAAF_PORT_MARIMO"
            $env:DAAF_PORT_MARIMO | Should -Be "3001"
            $env:DAAF_DEV | Should -Be "0"
        }

        It "only ever removes DAAF_* names (tampered tracker)" {
            $script:DaafKeysFromFile = @('PATH', 'DAAF_PORT_MARIMO')
            $env:DAAF_PORT_MARIMO = "1234"
            $absentPath = Join-Path $script:TmpDir "nonexistent.txt"
            Sync-DaafSettingsFile -SettingsFile $absentPath
            $env:PATH | Should -Not -BeNullOrEmpty
            $env:DAAF_PORT_MARIMO | Should -BeNullOrEmpty
        }
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

    Context "Invoke-DaafChoice routes 11 to Restart and 12 to Stop Web Services" {
        It "routes 11 to Invoke-DaafRestart" {
            Mock Invoke-DaafRestart { }
            Mock Invoke-DaafServiceStop { }
            Invoke-DaafChoice "11"
            Should -Invoke Invoke-DaafRestart -Times 1 -Exactly
            Should -Invoke Invoke-DaafServiceStop -Times 0 -Exactly
        }

        It "routes 12 to Invoke-DaafServiceStop" {
            Mock Invoke-DaafRestart { }
            Mock Invoke-DaafServiceStop { }
            Invoke-DaafChoice "12"
            Should -Invoke Invoke-DaafServiceStop -Times 1 -Exactly
            Should -Invoke Invoke-DaafRestart -Times 0 -Exactly
        }
    }

    Context "Invoke-DaafRestart (Restart Container)" {
        # Each test starts like a fresh panel in a folder holding (optionally) an
        # environment_settings.txt: whitelisted DAAF_* env vars cleared, settings
        # imported, display ports computed. Docker is mocked to record each call
        # ("compose down", "compose up -d", ...) with exit codes driven by
        # $script:MockDownExit / $script:MockUpExit / $script:MockReadyExit (the
        # `exec -T daaf-docker true` readiness probe, which also writes the
        # $script:MockReadyErrLines lines -- by default one Docker-style line -- to
        # the error stream when failing) / $script:MockVerifyExit
        # (the `test -f /daaf/CLAUDE.md` check); Read-DaafLine answers the
        # confirmation prompt with $script:MockAnswer. Two `compose down` knobs
        # model a file change WHILE `down` runs: $script:MockDownSettings is written
        # to ./environment_settings.txt ("__DELETE__" removes it), and
        # $script:MockDownBreaksSync arms a one-shot Sync-DaafSettingsFile mock that
        # fails the way the real function does on an unreadable file (removes the
        # tracked keys and clears the tracker, THEN throws). Unarmed, the real
        # Sync-DaafSettingsFile runs (the mock's -ParameterFilter does not match).
        #
        # STRICT MODE: the real panel runs its handlers under Set-StrictMode 3.0
        # (set after the DAAF_TEST_MODE guard, so dot-sourcing for tests never
        # turns it on). This Context turns it on itself so the handler and the
        # daaf_lib.ps1 loaders it calls are exercised the way a real run executes
        # them; AfterAll switches it off again so the rest of the file is unaffected.
        # Every $script: variable the mocks read is initialized in BeforeEach.
        BeforeAll {
            Set-StrictMode -Version 3.0

            $script:RestartKeys = @('DAAF_PROJECT_NAME', 'DAAF_PORT_MARIMO', 'DAAF_PORT_LOGVIEWER', 'DAAF_PORT_VSCODE', 'DAAF_DEV', 'DAAF_BRANCH', 'DAAF_DATA_VOLUME_NAME')
            $script:SavedRestartEnv = @{}
            foreach ($k in $script:RestartKeys) { $script:SavedRestartEnv[$k] = [Environment]::GetEnvironmentVariable($k, "Process") }

            # Simulate the panel's startup in the current folder. (Test helper: the
            # Start- verb's ShouldProcess rule does not apply, as for TestHelper's
            # New-FakeComposeFile.)
            function Start-TestPanel {
                [Diagnostics.CodeAnalysis.SuppressMessageAttribute('PSUseShouldProcessForStateChangingFunctions', '')]
                param()
                $script:DaafKeysFromFile = @()
                Import-DaafSettingsFile
                Initialize-DaafPortDisplay
            }

            # Every DAAF_* process variable as sorted "NAME=value" lines, for
            # before/after comparisons of the panel's environment.
            function Get-TestDaafEnv {
                @(Get-ChildItem -Path Env: | Where-Object { $_.Name -like 'DAAF_*' } |
                    Sort-Object Name | ForEach-Object { $_.Name + "=" + $_.Value }) -join "`n"
            }
        }
        AfterAll {
            foreach ($k in $script:RestartKeys) { [Environment]::SetEnvironmentVariable($k, $script:SavedRestartEnv[$k], "Process") }
            Set-StrictMode -Off
        }
        BeforeEach {
            foreach ($k in $script:RestartKeys) { Remove-Item -Path ("Env:" + $k) -ErrorAction SilentlyContinue }
            $script:RestartDir = Join-Path $TestDrive ("restart-" + [guid]::NewGuid().ToString('N'))
            $null = New-Item -ItemType Directory -Path $script:RestartDir
            Push-Location $script:RestartDir
            $script:DockerCalls = New-Object System.Collections.Generic.List[string]
            $script:MockDownExit = 0
            $script:MockUpExit = 0
            $script:MockReadyExit = 0
            $script:MockReadyErrLines = @("Error response from daemon: container mock123 is restarting")
            $script:MockVerifyExit = 0
            $script:SyncCalls = 0
            $script:MockAnswer = "y"
            $script:MockDownSettings = $null
            $script:MockDownBreaksSync = $false
            $script:SyncArmed = $false
            Mock docker {
                $call = $args -join ' '
                $script:DockerCalls.Add($call)
                $global:LASTEXITCODE = 0
                if ($call -like "compose down*") {
                    if ($script:MockDownSettings -eq "__DELETE__") {
                        Remove-Item -LiteralPath "./environment_settings.txt" -ErrorAction SilentlyContinue
                    } elseif ($null -ne $script:MockDownSettings) {
                        Set-Content -Path "./environment_settings.txt" -Value $script:MockDownSettings
                    }
                    if ($script:MockDownBreaksSync) { $script:SyncArmed = $true }
                    $global:LASTEXITCODE = $script:MockDownExit
                }
                if ($call -like "compose up*") { $global:LASTEXITCODE = $script:MockUpExit }
                if ($call -eq "compose exec -T daaf-docker true") {
                    if ($script:MockReadyExit -ne 0) {
                        foreach ($errText in @($script:MockReadyErrLines)) {
                            Write-Error -Message $errText -ErrorAction Continue
                        }
                    }
                    $global:LASTEXITCODE = $script:MockReadyExit
                }
                if ($call -like "compose exec -T daaf-docker test -f*") { $global:LASTEXITCODE = $script:MockVerifyExit }
            }
            Mock Read-DaafLine { $script:MockAnswer }
            Mock Start-Sleep { }
            # Realistic unreadable-file failure, armed by `compose down` (above).
            Mock Sync-DaafSettingsFile -ParameterFilter { $script:SyncArmed } {
                $script:SyncArmed = $false
                foreach ($key in @($script:DaafKeysFromFile)) {
                    Remove-Item -Path ("Env:" + $key) -ErrorAction SilentlyContinue
                }
                $script:DaafKeysFromFile = @()
                throw "Access to the path './environment_settings.txt' is denied."
            }
        }
        AfterEach {
            Pop-Location
        }

        It "answering n cancels without any docker down/up" {
            Start-TestPanel
            $script:MockAnswer = "n"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*Restart cancelled*"
            @($script:DockerCalls | Where-Object { $_ -like "compose down*" -or $_ -like "compose up*" }).Count | Should -Be 0
        }

        It "an empty answer (default No) cancels without any docker down/up" {
            Start-TestPanel
            $script:MockAnswer = ""
            $null = Invoke-DaafRestart 6>&1
            @($script:DockerCalls | Where-Object { $_ -like "compose down*" -or $_ -like "compose up*" }).Count | Should -Be 0
        }

        It "confirming runs compose down BEFORE compose up -d, never -v, then reports success" {
            Start-TestPanel
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $calls = @($script:DockerCalls)
            $downIdx = [array]::IndexOf($calls, "compose down")
            $upIdx = [array]::IndexOf($calls, "compose up -d")
            $downIdx | Should -BeGreaterThan -1
            $upIdx | Should -BeGreaterThan $downIdx
            @($calls | Where-Object { $_ -match '^compose down.*(\s-v(\s|$)|--volumes)' }).Count | Should -Be 0
            $calls | Should -Contain "compose exec -T daaf-docker true"
            $calls | Should -Contain "compose exec -T daaf-docker test -f /daaf/CLAUDE.md"
            $out | Should -BeLike "*Container restarted*"
            Should -Invoke Start-Sleep -Times 0 -Exactly
        }

        It "a changed DAAF_PROJECT_NAME aborts before any docker command and leaves the env untouched" {
            Start-TestPanel
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=otherinstall"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*Restart stopped*"
            $out | Should -BeLike "*otherinstall*"
            $script:DockerCalls.Count | Should -Be 0
            $env:DAAF_PROJECT_NAME | Should -BeNullOrEmpty
            @($script:DaafKeysFromFile).Count | Should -Be 0
        }

        It "a port changed in the file after startup is reflected in the panel's port variable" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PORT_MARIMO=3001"
            Start-TestPanel
            $script:DaafPortMarimo | Should -Be "3001"
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PORT_MARIMO=3002"
            $null = Invoke-DaafRestart 6>&1
            $env:DAAF_PORT_MARIMO | Should -Be "3002"
            $script:DaafPortMarimo | Should -Be "3002"
        }

        It "a port added to the file after startup is reflected in the panel's port variable" {
            Start-TestPanel
            $script:DaafPortMarimo | Should -Be "2718"
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PORT_MARIMO=3001"
            $null = Invoke-DaafRestart 6>&1
            $script:DaafPortMarimo | Should -Be "3001"
        }

        It "a failed compose down returns without compose up" {
            Start-TestPanel
            $script:MockDownExit = 1
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*Could not stop the container*"
            @($script:DockerCalls | Where-Object { $_ -like "compose up*" }).Count | Should -Be 0
            $out | Should -Not -BeLike "*Container restarted*"
        }

        It "a failed compose up returns with guidance" {
            Start-TestPanel
            $script:MockUpExit = 1
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*could not be started again*"
            $out | Should -Not -BeLike "*Container restarted*"
        }

        It "runs under Set-StrictMode 3.0 (reading an undefined variable throws)" {
            # Guards the Context's own premise: if strict mode did not reach the
            # tests, every other test here would silently run non-strict.
            $threw = $false
            try { $null = $strictProbeNeverDefinedVariable } catch { $threw = $true }
            $threw | Should -BeTrue
        }

        It "EOF at the confirmation prompt (null answer) cancels without any docker call" {
            Start-TestPanel
            Mock Read-DaafLine { $null }
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*Restart cancelled*"
            $script:DockerCalls.Count | Should -Be 0
        }

        It "answer <Label> confirms the restart (any case, ends trimmed)" -ForEach @(
            @{ Label = "'YES'"; Answer = "YES" }
            @{ Label = "' Yes '"; Answer = " Yes " }
            @{ Label = "'yes<CR>'"; Answer = "yes`r" }
        ) {
            Start-TestPanel
            $script:MockAnswer = $Answer
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose down"
            $script:DockerCalls | Should -Contain "compose up -d"
            $out | Should -BeLike "*Container restarted*"
        }

        It "answer <Label> cancels (only the ends are trimmed)" -ForEach @(
            @{ Label = "'no'"; Answer = "no" }
            @{ Label = "'nope'"; Answer = "nope" }
            @{ Label = "'y es'"; Answer = "y es" }
        ) {
            Start-TestPanel
            $script:MockAnswer = $Answer
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*Restart cancelled*"
            $script:DockerCalls.Count | Should -Be 0
        }

        It "a readiness timeout reports 60 seconds and Docker's error text, then returns" {
            Start-TestPanel
            $script:MockReadyExit = 1
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*did not become ready within 60 seconds*"
            $out | Should -BeLike "*Docker reported:*"
            $out | Should -BeLike "*    Error response from daemon: container mock123 is restarting*"
            $out | Should -Not -BeLikeExactly "*Container restarted*"
            # 30 polls plus the one error-capturing attempt; a 2s sleep between polls.
            @($script:DockerCalls | Where-Object { $_ -eq "compose exec -T daaf-docker true" }).Count | Should -Be 31
            Should -Invoke Start-Sleep -Times 29 -Exactly -ParameterFilter { $Seconds -eq 2 }
            @($script:DockerCalls | Where-Object { $_ -like "compose exec -T daaf-docker test -f*" }).Count | Should -Be 0
        }

        It "'Docker reported:' skips whitespace-only lines in Docker's errors, and is omitted when all are blank" {
            # Parity with daaf.sh, which drops blank lines before the last five.
            Start-TestPanel
            $script:MockReadyExit = 1
            $script:MockReadyErrLines = @(" ", "Error response from daemon: container mock123 is restarting", "`t")
            $lines = @((Invoke-DaafRestart 6>&1 | Out-String) -split '\r?\n')
            $head = [array]::IndexOf($lines, "  Docker reported:")
            $head | Should -BeGreaterThan -1
            $tail = [array]::IndexOf($lines, "  Check Docker Desktop for errors.")
            ($lines[($head + 1)..($tail - 1)] -join '|') | Should -BeExactly "    Error response from daemon: container mock123 is restarting"

            $script:DockerCalls.Clear()
            $script:MockReadyErrLines = @(" ", "`t")
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -BeLike "*did not become ready within 60 seconds*"
            $out | Should -Not -BeLike "*Docker reported:*"
            $out | Should -BeLike "*Check Docker Desktop for errors.*"
        }

        It "a failed DAAF-files check warns 'may not be intact' and returns" {
            Start-TestPanel
            $script:MockVerifyExit = 1
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose exec -T daaf-docker test -f /daaf/CLAUDE.md"
            $out | Should -BeLike "*DAAF's files may not be intact*"
            # Case-sensitive: the warning itself reads "The container restarted, but".
            $out | Should -Not -BeLikeExactly "*Container restarted*"
        }

        It "the guard proceeds when a user-set DAAF_PROJECT_NAME outranks the file's value" {
            # Set before launch (user env wins over the file on load AND reload),
            # so the project does not change and the restart must go ahead.
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=bar"
            $env:DAAF_PROJECT_NAME = "foo"
            Start-TestPanel
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -Not -BeLike "*Restart stopped*"
            $script:DockerCalls | Should -Contain "compose down"
            $script:DockerCalls | Should -Contain "compose up -d"
            $out | Should -BeLike "*Container restarted*"
            $env:DAAF_PROJECT_NAME | Should -Be "foo"
        }

        It "the guard proceeds when the file adds DAAF_PROJECT_NAME=daaf (the default)" {
            Start-TestPanel
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=daaf"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -Not -BeLike "*Restart stopped*"
            $script:DockerCalls | Should -Contain "compose down"
            $script:DockerCalls | Should -Contain "compose up -d"
            $out | Should -BeLike "*Container restarted*"
        }

        # Review 51q SUGGESTION-1: the guard compares the names Docker Compose USES
        # (Resolve-DaafProjectName). `My.Proj` -> `myproj` is the row a raw
        # comparison refuses even with PowerShell's case-insensitive -ne.
        It "the guard proceeds when the edit normalizes to the same project (<From> -> <To>)" -ForEach @(
            @{ From = "Work"; To = "work" }
            @{ From = "My.Proj"; To = "myproj" }
        ) {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=$From"
            Start-TestPanel
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=$To"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -Not -BeLike "*Restart stopped*"
            $out | Should -Not -BeLike "*DIFFERENT*"
            $script:DockerCalls | Should -Contain "compose down"
            $script:DockerCalls | Should -Contain "compose up -d"
            $out | Should -BeLike "*Container restarted*"
            $env:DAAF_PROJECT_NAME | Should -BeExactly $To
        }

        It "the guard still refuses work -> play before any docker command" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=work"
            Start-TestPanel
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=play"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $flat = $out -replace '\s+', ' '
            $flat | Should -BeLike "*Restart stopped -- nothing was changed.*"
            $flat | Should -BeLike '*the project name "play" (the default is "daaf" when the file does not set one) instead of "work".*'
            $flat | Should -BeLike "*start a DIFFERENT one in its place*"
            $script:DockerCalls.Count | Should -Be 0
            $env:DAAF_PROJECT_NAME | Should -BeExactly "work"
        }

        It "default path unchanged: no file, and the file adding daaf, pass with no refusal text" {
            Start-TestPanel
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -Not -BeLike "*Restart stopped*"
            $out | Should -Not -BeLike "*cannot use*"
            $out | Should -BeLike "*Container restarted*"
            $script:DockerCalls.Clear()
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=daaf"
            $out2 = Invoke-DaafRestart 6>&1 | Out-String
            $out2 | Should -Not -BeLike "*Restart stopped*"
            $out2 | Should -Not -BeLike "*cannot use*"
            $out2 | Should -BeLike "*Container restarted*"
        }

        It "a file name that normalizes to nothing is refused before any docker command" {
            Start-TestPanel
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=___"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $flat = $out -replace '\s+', ' '
            $flat | Should -BeLike "*Restart stopped -- nothing was changed.*"
            $flat | Should -BeLike "*With your current environment_settings.txt, the project name would be `"___`", which Docker Compose cannot use. A project name may use lowercase letters, digits, '-' and '_', and must start with a letter or digit.*"
            $flat | Should -BeLike '*make environment_settings.txt use the project name "daaf" again*'
            $out | Should -Not -BeLike "*DIFFERENT*"
            $script:DockerCalls.Count | Should -Be 0
            $env:DAAF_PROJECT_NAME | Should -BeNullOrEmpty
        }

        It "the post-down re-check also compares normalized names (Work -> WORK proceeds, -> ___ stops before up)" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=Work"
            Start-TestPanel
            $script:MockDownSettings = "DAAF_PROJECT_NAME=WORK"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $out | Should -Not -BeLike "*now names a different project*"
            $script:DockerCalls | Should -Contain "compose up -d"
            $out | Should -BeLike "*Container restarted*"

            # A fresh panel on `Work` again (clear the env the first restart adopted).
            foreach ($k in $script:RestartKeys) { Remove-Item -Path ("Env:" + $k) -ErrorAction SilentlyContinue }
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=Work"
            Start-TestPanel
            $script:DockerCalls.Clear()
            $script:MockDownSettings = "DAAF_PROJECT_NAME=___"
            $out2 = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose down"
            @($script:DockerCalls | Where-Object { $_ -like "compose up*" }).Count | Should -Be 0
            $flat2 = $out2 -replace '\s+', ' '
            $flat2 | Should -BeLike "*environment_settings.txt now names a different project.*"
            $flat2 | Should -BeLike '*now gives the project name "___", which Docker Compose cannot use.*'
            $out2 | Should -Not -BeLike "*Container restarted*"
            $env:DAAF_PROJECT_NAME | Should -BeExactly "Work"
        }

        It "an unreadable settings file stops before any docker call and restores the environment" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PORT_MARIMO=3001"
            Start-TestPanel
            $envBefore = Get-TestDaafEnv
            $trackerBefore = @($script:DaafKeysFromFile) -join ' '
            # Fail part-way, after changing values, so the restore is what is tested.
            Mock Sync-DaafSettingsFile {
                $env:DAAF_PORT_MARIMO = "9999"
                $env:DAAF_PROJECT_NAME = "partial"
                $script:DaafKeysFromFile = @('DAAF_PROJECT_NAME')
                throw "denied"
            }
            $out = Invoke-DaafRestart 6>&1 | Out-String
            ($out -replace '\s+', ' ') | Should -BeLike "*Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it. Nothing was changed.*"
            # Only the panel's message, not the exception text.
            $out | Should -Not -BeLike "*denied*"
            $script:DockerCalls.Count | Should -Be 0
            Get-TestDaafEnv | Should -BeExactly $envBefore
            (@($script:DaafKeysFromFile) -join ' ') | Should -BeExactly $trackerBefore
            $script:DaafPortMarimo | Should -Be "3001"
        }

        It "a settings file that becomes unreadable after down stops before up" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PORT_MARIMO=3001"
            Start-TestPanel
            # First call (the guard probe) succeeds without changes; the second
            # (the reload after `down`) fails.
            Mock Sync-DaafSettingsFile {
                $script:SyncCalls++
                if ($script:SyncCalls -ge 2) { throw "denied" }
            }
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $script:SyncCalls | Should -Be 2
            $script:DockerCalls | Should -Contain "compose down"
            ($out -replace '\s+', ' ') | Should -BeLike "*The container is stopped, but environment_settings.txt can no longer be read. Make sure it is not open in another program and that you have permission to read it, then choose Restart Container again (or Start Claude Code, which starts the container).*"
            @($script:DockerCalls | Where-Object { $_ -like "compose up*" }).Count | Should -Be 0
            $out | Should -Not -BeLike "*Container restarted*"
            $script:DaafPortMarimo | Should -Be "3001"
        }

        It "a reload that fails after down (keys already removed) restores the pre-down settings, and a retry proceeds" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=myproj`nDAAF_PORT_MARIMO=3001"
            Start-TestPanel
            $envBefore = Get-TestDaafEnv
            $trackerBefore = @($script:DaafKeysFromFile) -join ' '
            $script:MockDownBreaksSync = $true
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose down"
            $out | Should -BeLike "*The container is stopped, but environment_settings.txt can no longer*"
            $out | Should -Not -BeLike "*is denied*"
            @($script:DockerCalls | Where-Object { $_ -like "compose up*" }).Count | Should -Be 0
            # Exactly as before `down`: env, tracker, and the panel's port display.
            Get-TestDaafEnv | Should -BeExactly $envBefore
            (@($script:DaafKeysFromFile) -join ' ') | Should -BeExactly $trackerBefore
            $env:DAAF_PROJECT_NAME | Should -Be "myproj"
            $env:DAAF_PORT_MARIMO | Should -Be "3001"
            $script:DaafPortMarimo | Should -Be "3001"

            # The user fixes the file and chooses Restart Container again: the
            # guard must NOT refuse it (same project), and the restart completes.
            $script:MockDownBreaksSync = $false
            $script:DockerCalls.Clear()
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=myproj`nDAAF_PORT_MARIMO=3003"
            $out2 = Invoke-DaafRestart 6>&1 | Out-String
            $out2 | Should -Not -BeLike "*Restart stopped*"
            $script:DockerCalls | Should -Contain "compose down"
            $script:DockerCalls | Should -Contain "compose up -d"
            $out2 | Should -BeLike "*Container restarted*"
            $env:DAAF_PROJECT_NAME | Should -Be "myproj"
            $script:DaafPortMarimo | Should -Be "3003"
        }

        It "a project name edited during down stops before up, keeps the original settings, and a retry proceeds" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=myproj`nDAAF_PORT_MARIMO=3001"
            Start-TestPanel
            $envBefore = Get-TestDaafEnv
            $trackerBefore = @($script:DaafKeysFromFile) -join ' '
            # The mid-down edit also ADDS a key the panel never had (DAAF_PORT_VSCODE),
            # so the restore must remove what the reload adopted, not only put back
            # the old values.
            $script:MockDownSettings = "DAAF_PROJECT_NAME=other`nDAAF_PORT_MARIMO=3002`nDAAF_PORT_VSCODE=3999"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose down"
            @($script:DockerCalls | Where-Object { $_ -like "compose up*" }).Count | Should -Be 0
            $flat = $out -replace '\s+', ' '
            $flat | Should -BeLike "*The container is stopped, but it was not started again -- environment_settings.txt now names a different project.*"
            $flat | Should -BeLike '*name "other" (the default is "daaf"*'
            $flat | Should -BeLike '*name "myproj" again, then choose Restart Container again.*'
            $out | Should -Not -BeLike "*Container restarted*"
            Get-TestDaafEnv | Should -BeExactly $envBefore
            (@($script:DaafKeysFromFile) -join ' ') | Should -BeExactly $trackerBefore
            $env:DAAF_PORT_VSCODE | Should -BeNullOrEmpty
            $script:DaafPortMarimo | Should -Be "3001"
            $script:DaafPortVscode | Should -Be "2720"

            $script:MockDownSettings = $null
            $script:DockerCalls.Clear()
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=myproj`nDAAF_PORT_MARIMO=3003"
            $out2 = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose up -d"
            $out2 | Should -BeLike "*Container restarted*"
            $env:DAAF_PROJECT_NAME | Should -Be "myproj"
            $script:DaafPortMarimo | Should -Be "3003"
        }

        It "a settings file deleted during down stops before up (the default project would differ)" {
            Set-Content -Path "./environment_settings.txt" -Value "DAAF_PROJECT_NAME=myproj"
            Start-TestPanel
            $script:MockDownSettings = "__DELETE__"
            $out = Invoke-DaafRestart 6>&1 | Out-String
            $script:DockerCalls | Should -Contain "compose down"
            @($script:DockerCalls | Where-Object { $_ -like "compose up*" }).Count | Should -Be 0
            ($out -replace '\s+', ' ') | Should -BeLike '*now names a different project.*name "daaf" (the default is "daaf"*'
            $out | Should -Not -BeLike "*Container restarted*"
            $env:DAAF_PROJECT_NAME | Should -Be "myproj"
            (@($script:DaafKeysFromFile) -join ' ') | Should -BeExactly "DAAF_PROJECT_NAME"
        }

        It "the intro names DAAF_DEV, the first-time shim, and the Dockerfile/packages/docker-compose.yml list" {
            Start-TestPanel
            $script:MockAnswer = "n"
            $flat = (Invoke-DaafRestart 6>&1 | Out-String) -replace '\s+', ' '
            $flat | Should -BeLike '*Settings marked "rebuild required" in environment_settings.txt (such as DAAF_DEV, or turning on the provider shim for the first time), and changes to the Dockerfile, packages, or docker-compose.yml, need Rebuild Container instead.*'
            $flat | Should -Not -BeLike "*Alternative Providers*"
        }
    }

    Context "Web-service URLs use the HOST-published port" {
        # Non-default host ports, so a URL hardcoded to the container port
        # (2718/2719/2720) fails. The container-side probes stay on those ports.
        BeforeAll {
            $script:SavedPortDisplay = @($script:DaafPortMarimo, $script:DaafPortLogViewer, $script:DaafPortVscode)
        }
        AfterAll {
            $script:DaafPortMarimo = $script:SavedPortDisplay[0]
            $script:DaafPortLogViewer = $script:SavedPortDisplay[1]
            $script:DaafPortVscode = $script:SavedPortDisplay[2]
        }
        BeforeEach {
            $script:DaafPortMarimo = "3718"
            $script:DaafPortLogViewer = "3719"
            $script:DaafPortVscode = "3720"
            Mock Confirm-DaafContainer { $true }
            Mock Test-DaafPort { $true }
            Mock Open-DaafUrl { }
            Mock docker {
                $global:LASTEXITCODE = 0
                if (($args -join ' ') -like "*discover_log_sources.sh*") { "ARCHIVE|3" }
            }
            Mock Read-DaafLine { "1" }
        }

        It "Invoke-DaafNotebookBrowser opens the notebook URL on the DaafPortMarimo host port" {
            Invoke-DaafNotebookBrowser 6>$null
            Should -Invoke Open-DaafUrl -Times 1 -Exactly -ParameterFilter { $Url -eq "http://localhost:3718" }
        }

        It "Invoke-DaafVSCode opens the VS Code URL on the DaafPortVscode host port" {
            Invoke-DaafVSCode 6>$null
            Should -Invoke Open-DaafUrl -Times 1 -Exactly -ParameterFilter { $Url -eq "http://localhost:3720" }
        }

        It "Invoke-DaafLogViewer opens the viewer URL on the DaafPortLogViewer host port" {
            Invoke-DaafLogViewer 6>$null
            Should -Invoke Open-DaafUrl -Times 1 -Exactly -ParameterFilter { $Url -eq "http://localhost:3719/scripts/log_viewer.html?manifest=.claude/logs/sessions/session_manifest.json" }
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

    Context "Invoke-DaafDelegate restores parent-inherited DAAF_NESTED" {
        # Behavioral guard for the DAAF_NESTED clobber bug. Start-Process is mocked
        # to a no-op child (ExitCode 0) so the delegate's save/restore logic runs
        # without spawning a real host process or Docker. Ensure the delegate can
        # resolve the child path regardless of dot-source scope.
        BeforeAll {
            $script:OrigNested = $env:DAAF_NESTED
            $script:DaafScriptDir = "$RepoRoot/scripts/host"
        }
        AfterAll {
            if ($null -ne $script:OrigNested) { $env:DAAF_NESTED = $script:OrigNested }
            else { Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue }
        }

        It "restores DAAF_NESTED to the parent's value after the delegate returns" {
            Mock Start-Process {
                [pscustomobject]@{ ExitCode = 0 } |
                    Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { } -PassThru
            }
            $env:DAAF_NESTED = "outer"
            Invoke-DaafDelegate "backup_daaf.ps1" 6>$null
            $env:DAAF_NESTED | Should -Be "outer"
        }

        It "clears DAAF_NESTED when the parent had none set" {
            Mock Start-Process {
                [pscustomobject]@{ ExitCode = 0 } |
                    Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { } -PassThru
            }
            Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
            Invoke-DaafDelegate "backup_daaf.ps1" 6>$null
            $env:DAAF_NESTED | Should -BeNullOrEmpty
        }
    }

    Context "Delegates quote a spaced child path and report UNKNOWN / error / success distinctly" {
        # F1: Start-Process joins an -ArgumentList ARRAY with bare spaces, so a
        # child path under a spaced install folder ("C:\Users\John Smith\...") used
        # to split into several argv entries. The delegates must hand Start-Process
        # ONE pre-joined string with the -File path quoted as a single token.
        # F2/F3: on Windows (PS 5.1 and pwsh 6.0-7.4.0) ExitCode can read $null (handle not
        # cached); that is UNKNOWN and must get its own message -- never the bare
        # "Returned to DAAF Control Panel." success path or silence.
        # Start-Process is mocked; the mock records -ArgumentList and returns a
        # Process-like object whose ExitCode is driven by $script:MockExitCode.
        BeforeAll {
            $script:OrigNested = $env:DAAF_NESTED
            $script:OrigScriptDir = $script:DaafScriptDir
            $script:DaafScriptDir = Join-Path $TestDrive 'John Smith dir'
        }
        AfterAll {
            $script:DaafScriptDir = $script:OrigScriptDir
            if ($null -ne $script:OrigNested) { $env:DAAF_NESTED = $script:OrigNested }
            else { Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue }
        }
        BeforeEach {
            $script:CapturedArgumentList = $null
            Mock Start-Process {
                $script:CapturedArgumentList = $ArgumentList
                [pscustomobject]@{ ExitCode = $script:MockExitCode } |
                    Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { } -PassThru
            }
        }

        It "Invoke-DaafDelegate passes one string with the spaced -File path as one quoted token" {
            $script:MockExitCode = 0
            $null = Invoke-DaafDelegate "backup_daaf.ps1" 6>&1
            $expectedPath = Join-Path $script:DaafScriptDir 'backup_daaf.ps1'
            @($script:CapturedArgumentList).Count | Should -Be 1
            @($script:CapturedArgumentList)[0] | Should -BeExactly ('-NoProfile -File "' + $expectedPath + '"')
        }

        It "Invoke-DaafDelegateInteractive passes one string: quoted spaced -File path, then the script args" {
            $script:MockExitCode = 0
            $null = Invoke-DaafDelegateInteractive "run_daaf.ps1" @("bash") "Container terminal ended with an error." 6>&1
            $expectedPath = Join-Path $script:DaafScriptDir 'run_daaf.ps1'
            @($script:CapturedArgumentList).Count | Should -Be 1
            @($script:CapturedArgumentList)[0] | Should -BeExactly ('-NoProfile -File "' + $expectedPath + '" bash')
        }

        It "Invoke-DaafDelegateInteractive: a `$null ScriptArgs adds no trailing empty `"`" argument" {
            # A $null [string[]] binds as ONE $null element; unfiltered, the helper
            # turned it into an explicit "" argument for the child script.
            $script:MockExitCode = 0
            $null = Invoke-DaafDelegateInteractive "run_daaf.ps1" $null "Claude Code session ended with an error." 6>&1
            $expectedPath = Join-Path $script:DaafScriptDir 'run_daaf.ps1'
            @($script:CapturedArgumentList).Count | Should -Be 1
            @($script:CapturedArgumentList)[0] | Should -BeExactly ('-NoProfile -File "' + $expectedPath + '"')
        }

        It "Invoke-DaafDelegateInteractive: a `$null element is dropped, real script args are kept" {
            $script:MockExitCode = 0
            $null = Invoke-DaafDelegateInteractive "run_daaf.ps1" @("bash", $null) "Container terminal ended with an error." 6>&1
            $expectedPath = Join-Path $script:DaafScriptDir 'run_daaf.ps1'
            @($script:CapturedArgumentList)[0] | Should -BeExactly ('-NoProfile -File "' + $expectedPath + '" bash')
        }

        It "Invoke-DaafDelegate: a null ExitCode reports UNKNOWN, not a clean return" {
            $script:MockExitCode = $null
            $out = Invoke-DaafDelegate "backup_daaf.ps1" 6>&1 | Out-String
            $out | Should -BeLike "*Could not read the exit status of backup_daaf.ps1*"
            $out | Should -Not -BeLike "*exited without completing*"
        }

        It "Invoke-DaafDelegate: ExitCode 1 reports the failure with its code" {
            $script:MockExitCode = 1
            $out = Invoke-DaafDelegate "backup_daaf.ps1" 6>&1 | Out-String
            $out | Should -BeLike "*backup_daaf.ps1 exited without completing (code 1).*"
            $out | Should -Not -BeLike "*Could not read the exit status*"
        }

        It "Invoke-DaafDelegate: ExitCode 0 is a plain clean return" {
            $script:MockExitCode = 0
            $out = Invoke-DaafDelegate "backup_daaf.ps1" 6>&1 | Out-String
            $out | Should -BeLike "*Returned to DAAF Control Panel.*"
            $out | Should -Not -BeLike "*Could not read the exit status*"
            $out | Should -Not -BeLike "*exited without completing*"
        }

        It "Invoke-DaafDelegateInteractive: a null ExitCode reports UNKNOWN (not silence, not the failure text)" {
            $script:MockExitCode = $null
            $out = Invoke-DaafDelegateInteractive "run_daaf.ps1" @() "Claude Code session ended with an error." 6>&1 | Out-String
            $out | Should -BeLike "*Could not read the exit status of run_daaf.ps1*"
            $out | Should -Not -BeLike "*Claude Code session ended with an error.*"
        }

        It "Invoke-DaafDelegateInteractive: ExitCode 1 prints the caller's failure message" {
            $script:MockExitCode = 1
            $out = Invoke-DaafDelegateInteractive "run_daaf.ps1" @() "Claude Code session ended with an error." 6>&1 | Out-String
            $out | Should -BeLike "*Claude Code session ended with an error.*"
            $out | Should -Not -BeLike "*Could not read the exit status*"
        }

        It "Invoke-DaafDelegateInteractive: ExitCode 0 prints neither the failure nor the UNKNOWN message" {
            $script:MockExitCode = 0
            $out = Invoke-DaafDelegateInteractive "run_daaf.ps1" @() "Claude Code session ended with an error." 6>&1 | Out-String
            $out | Should -Not -BeLike "*Claude Code session ended with an error.*"
            $out | Should -Not -BeLike "*Could not read the exit status*"
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

    It "runs Restart Container (11) end to end, issuing down then up -d, and writes nothing" {
        # Child process for the same stdin reason as above. Every docker call hits
        # the dry-run shim, so the readiness poll succeeds on its first try.
        $env:DAAF_DRY_RUN = "1"
        Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
        $before = @(Get-ChildItem -Force -Path $script:TestDir | ForEach-Object { $_.Name } | Sort-Object)
        $psExe = (Get-Process -Id $PID).Path
        $output = @("11", "y", "q") | & $psExe -NoProfile -File "$RepoRoot/scripts/host/daaf.ps1" 2>&1 | Out-String
        $output | Should -BeLike "*[[]DRY-RUN] docker compose down*"
        $output | Should -BeLike "*[[]DRY-RUN] docker compose up -d*"
        $output.IndexOf("docker compose down") | Should -BeLessThan $output.IndexOf("docker compose up -d")
        $output | Should -BeLike "*Container restarted*"
        $output | Should -BeLike "*Goodbye!*"
        # HSM5: the dry-run restart path creates nothing in the working folder.
        $after = @(Get-ChildItem -Force -Path $script:TestDir | ForEach-Object { $_.Name } | Sort-Object)
        ($after -join '|') | Should -BeExactly ($before -join '|')
    }

    It "exits 1 with the same two-line message as daaf.sh when environment_settings.txt is unreadable at startup" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows -or ((& id -u) -eq '0')) {
        # Child process for the same stdin reason as above (the startup load runs
        # before the menu loop). `chmod 000` stages a real read failure, so this is
        # skipped where chmod cannot block reads: Windows, and running as root.
        $startDir = Join-Path $TestDrive ("startup-" + [guid]::NewGuid().ToString('N'))
        $null = New-Item -ItemType Directory -Path $startDir
        $settings = Join-Path $startDir "environment_settings.txt"
        New-FakeComposeFile -Directory $startDir
        Set-Content -LiteralPath $settings -Value "DAAF_PORT_MARIMO=3001"
        & chmod 000 $settings
        Push-Location $startDir
        try {
            $env:DAAF_DRY_RUN = "1"
            Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
            $psExe = (Get-Process -Id $PID).Path
            $output = "q" | & $psExe -NoProfile -File "$RepoRoot/scripts/host/daaf.ps1" 2>&1 | Out-String
            $LASTEXITCODE | Should -Be 1
            $output | Should -BeLike "*ERROR: Cannot read environment_settings.txt -- make sure it is not open in another program and that you have permission to read it.*"
            $output | Should -BeLike "*Fix that (or move the file aside), then start the DAAF Control Panel again.*"
            $output | Should -Not -BeLike "*unexpected failure*"
            $output | Should -Not -BeLike "*denied*"
            # The panel stopped before drawing the menu.
            $output | Should -Not -BeLike "*Enter choice*"
        } finally {
            Pop-Location
            & chmod 644 $settings
        }
    }

    It "daaf_lib.ps1 defines Read-DaafLine" {
        $libContent = Get-Content "$RepoRoot/scripts/host/daaf_lib.ps1" -Raw
        $libContent | Should -Match 'function Read-DaafLine'
    }
}
