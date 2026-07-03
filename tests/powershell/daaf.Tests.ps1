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
    }

    AfterEach {
        Remove-Item -Recurse -Force $script:TmpDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PROJECT_NAME  -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_MARIMO   -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_LOGVIEWER -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PORT_VSCODE   -ErrorAction SilentlyContinue
    }

    It "picks up a DAAF_* value from the settings file" {
        Set-Content -Path $script:SettingsFile -Value "DAAF_PROJECT_NAME=myinstance`nDAAF_PORT_MARIMO=3001"
        Import-DaafSettingsFile -SettingsFile $script:SettingsFile
        $env:DAAF_PROJECT_NAME | Should -Be "myinstance"
        $env:DAAF_PORT_MARIMO  | Should -Be "3001"
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

    Context "Invoke-DaafChoice dispatch" {
        It "returns true (redraw) for an empty choice" {
            Invoke-DaafChoice "" | Should -BeTrue
        }

        It "returns true (redraw) for an invalid choice" {
            $result = Invoke-DaafChoice "zzz" 6>$null
            $result | Should -BeTrue
        }

        It "returns false (stop loop) for quit" {
            $result = Invoke-DaafChoice "q" 6>$null
            $result | Should -BeFalse
        }

        It "returns false (stop loop) for uppercase quit" {
            $result = Invoke-DaafChoice "Q" 6>$null
            $result | Should -BeFalse
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
