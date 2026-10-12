# ============================================================================
# Pester tests: native-command stream-capture idiom ('Continue' bracket)
# ============================================================================
# WHAT FIELD FAILURE THIS IS ABOUT
# --------------------------------
# On a real Windows PowerShell 5.1 host, the backup driver's detached-container
# diagnostic capture --
#
#     $ErrorActionPreference = "SilentlyContinue"
#     $StageLog = (docker logs $StageCid 2>&1 | Out-String)
#
# (backup_daaf.ps1, the staging-failure path; the same idiom recurs at the
# Claude-volume staging path) lost the native command's stderr, and the user
# saw an empty "Details from the staging scan:" block (field failure
# 2026-07-14). The cause was found later (field probe 2026-10-05 on 5.1.26100:
# SILENT_LINES=1, CONTINUE_LINES=2; sourced mechanism in the shell-scripting
# skill's gotchas.md, "Windows PowerShell 5.1 Drops Native stderr Under
# `SilentlyContinue`, Even With `2>&1`"): on Windows PowerShell 5.1 the
# preference still applies to each redirected native stderr line, so
# 'SilentlyContinue' drops it before it reaches the capture. From PowerShell 7.2
# it no longer applies, so pwsh 7 keeps the line under either preference.
#
# The fix (dispatch #63) brackets every capture whose stderr text is SHOWN with
# 'Continue' instead:
#
#     $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
#     $StageLog = (docker logs $StageCid 2>&1 | Out-String)
#     $ErrorActionPreference = $savedEAP
#
# WHAT THIS FILE TESTS (and what it cannot)
# -----------------------------------------
# 1. Behavioral: the 'Continue' idiom, run against a REAL native command that
#    writes to both streams, keeps BOTH lines and raises nothing under a
#    script-wide 'Stop'. This holds on every PowerShell version.
# 2. Behavioral, version-dependent: 'SilentlyContinue' keeps the stderr line on
#    PowerShell 7.2+ and drops it on Windows PowerShell 5.1. On pwsh 7 this
#    documents WHY no behavioral test there can catch a revert to
#    'SilentlyContinue'; the 5.1 branch only runs if this file is ever run under
#    5.1 (CI runs Pester under pwsh only, on ubuntu and windows).
# 3. Structural: backup_daaf.ps1 still uses this exact idiom, under 'Continue',
#    for both staging logs.
#
# The 5.1 drop itself is covered elsewhere: the repo-wide AST guard
# native_stderr_capture.Tests.ps1 (a host script that keeps and uses a docker
# stderr capture must set an explicit literal 'Continue' in the same scope;
# 'SilentlyContinue', 'Ignore', 'Stop' or an inherited preference is flagged),
# and the "Probe native stderr capture" step of the validate-ps-windows job in
# .github/workflows/ci-scripts.yml, which runs under Windows PowerShell 5.1 and
# fails if 5.1 stops dropping the line under SilentlyContinue, or drops it
# under 'Continue'.
#
# PLATFORM: the native command is cmd.exe on Windows and /bin/sh elsewhere.
# The test skips only if neither is resolvable (a genuine "cannot run it").
# ============================================================================

Describe "Native-command stream-capture idiom (2>&1 | Out-String under a 'Continue' bracket)" {

    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        # A native command that writes a known STDOUT line and a known STDERR
        # line, cross-platform -- like a `docker logs` whose container wrote both.
        $script:OutMarker = "STDOUT_MARKER_A1"
        $script:ErrMarker = "STDERR_MARKER_B2"

        if ($IsWindows -or ($null -eq $IsWindows -and $env:OS -eq "Windows_NT")) {
            # Windows PowerShell 5.1 has no $IsWindows automatic variable, hence
            # the $env:OS fallback. cmd.exe /c: echo -> stdout, echo 1>&2 -> stderr.
            $script:NativeExe  = "cmd.exe"
            $script:NativeArgs = @("/c", "echo $($script:OutMarker)& echo $($script:ErrMarker) 1>&2")
        }
        elseif (Get-Command /bin/sh -ErrorAction SilentlyContinue) {
            # /bin/sh -c: echo to stdout, echo to stderr (>&2).
            $script:NativeExe  = "/bin/sh"
            $script:NativeArgs = @("-c", "echo $($script:OutMarker); echo $($script:ErrMarker) >&2")
        }
        else {
            $script:NativeExe = $null
        }

        $script:IsWindowsPowerShell = ($PSVersionTable.PSEdition -eq 'Desktop')
        $script:IsPwsh72Plus = ($PSVersionTable.PSVersion -ge [version]'7.2')
    }

    It "the 'Continue' idiom keeps BOTH stdout and stderr and raises nothing under a script-wide 'Stop'" {
        if ($null -eq $script:NativeExe) {
            Set-ItResult -Skipped -Because "no native shell (cmd.exe or /bin/sh) is resolvable on this host"
            return
        }

        # EXACT production shape (backup_daaf.ps1 `$StageLog`), inside the
        # script-wide 'Stop' every host script sets in its preamble.
        $ErrorActionPreference = 'Stop'
        $captured = $null
        {
            $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "Continue"
            try {
                $script:Captured = (& $script:NativeExe @($script:NativeArgs) 2>&1 | Out-String)
            }
            finally {
                $ErrorActionPreference = $savedEAP
            }
        } | Should -Not -Throw
        $captured = $script:Captured

        # stdout survives (the leg that never regressed) ...
        $captured | Should -Match ([regex]::Escape($script:OutMarker))
        # ... and so does stderr: this is the line 5.1 dropped under
        # 'SilentlyContinue', so the "Details from the staging scan:" block was empty.
        $captured | Should -Match ([regex]::Escape($script:ErrMarker))
    }

    It "'SilentlyContinue' keeps stderr on PowerShell 7.2+ and drops it on Windows PowerShell 5.1 (why the idiom is 'Continue')" {
        if ($null -eq $script:NativeExe) {
            Set-ItResult -Skipped -Because "no native shell (cmd.exe or /bin/sh) is resolvable on this host"
            return
        }
        if (-not ($script:IsWindowsPowerShell -or $script:IsPwsh72Plus)) {
            Set-ItResult -Skipped -Because "PowerShell $($PSVersionTable.PSVersion) is neither 5.1 nor 7.2+; its behavior here is not established"
            return
        }

        $savedEAP = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"
        try {
            $captured = (& $script:NativeExe @($script:NativeArgs) 2>&1 | Out-String)
        }
        finally {
            $ErrorActionPreference = $savedEAP
        }

        $captured | Should -Match ([regex]::Escape($script:OutMarker))
        if ($script:IsWindowsPowerShell) {
            # Field-observed 2026-10-05 (5.1.26100). If this ever fails, 5.1 kept the
            # line: revisit gotchas.md and the native_stderr_capture guard.
            $captured | Should -Not -Match ([regex]::Escape($script:ErrMarker))
        }
        else {
            # about_Preference_Variables: from 7.2 the preference "doesn't affect the
            # redirected output". So pwsh 7 cannot reproduce the 5.1 drop, and the
            # guard against a revert has to be structural.
            $captured | Should -Match ([regex]::Escape($script:ErrMarker))
        }
    }

    It "backup_daaf.ps1 still uses this idiom, under 'Continue', for both staging-failure logs" {
        # Anchor the behavioral test to the real call sites: the capture text AND
        # the bracket line right above it. If either changes, this test (and the
        # backup suite's own pins) say so.
        $content = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
        $content | Should -Match 'docker logs \$StageCid 2>&1 \| Out-String'
        $content | Should -Match 'docker logs \$ClaudeStageCid 2>&1 \| Out-String'
        $content | Should -Match '\$ErrorActionPreference = "Continue"\r?\n[ \t]*\$StageLog = \(docker logs \$StageCid 2>&1 \| Out-String\)'
        $content | Should -Match '\$ErrorActionPreference = "Continue"\r?\n[ \t]*\$ClaudeStageLog = \(docker logs \$ClaudeStageCid 2>&1 \| Out-String\)'
    }
}
