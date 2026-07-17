# ============================================================================
# Pester tests: native-command stream-capture idiom (PS 5.1 regression guard)
# ============================================================================
# WHAT FIELD FAILURE THIS GUARDS
# ------------------------------
# Field failure: 2026-07-14 (details block intentionally empty).
#
# On a real Windows PowerShell 5.1 host, the backup driver's detached-container
# diagnostic capture --
#
#     $ErrorActionPreference = "SilentlyContinue"
#     $StageLog = (docker logs $StageCid 2>&1 | Out-String)
#
# (backup_daaf.ps1, the staging-failure path; the same idiom recurs at the
# Claude-volume staging path) -- silently DROPPED the native command's stderr.
# When the container-side staging gate wrote its offender list to a stream that
# ended up on stderr, the merged `2>&1` capture lost it under SilentlyContinue,
# so the user's terminal showed an empty "Details from the staging scan:" block.
# The bug was invisible to our CI because Pester runs on pwsh 7 with a MOCKED
# docker (the mock returns strings, never exercising real native stderr merging).
# It surfaced only in the user's field run against real docker on PS 5.1.
#
# WHY THIS TEST EXISTS
# --------------------
# This is a behavioral (live-execution) regression test for the EXACT capture
# idiom -- `$out = (<native cmd> 2>&1 | Out-String)` under
# `$ErrorActionPreference = "SilentlyContinue"` -- run against a REAL native
# command that writes to BOTH stdout and stderr. It asserts BOTH streams'
# content survives the capture. On PS 5.1 (the Windows CI runner) this is the
# direct regression test for the field failure; on pwsh 7 it must also pass
# (the idiom is expected to be correct there and stay correct).
#
# It lives in its own file (not backup_daaf.Tests.ps1) because it is a
# cross-script *runtime-behavior* guard for a shared idiom, executed live --
# whereas backup_daaf.Tests.ps1 is entirely static regex-on-source structural
# assertions. Mixing a live native-command test into that file would blur the
# static/behavioral boundary and couple the idiom guard to one script's layout.
#
# PLATFORM: the idiom is exercised with a real native command that emits on both
# streams. On Windows we use cmd.exe; on Linux/macOS (where pwsh 7 runs in this
# container and in cross-platform CI) we use /bin/sh. Both are ubiquitous on
# their platforms, so no skip logic is needed. A skip is added ONLY if neither
# native shell is resolvable -- a genuine "cannot run it" condition, not a
# platform-preference skip.
# ============================================================================

Describe "Native-command stream-capture idiom (2>&1 | Out-String under SilentlyContinue)" {

    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        # Resolve a native command that writes a known STDOUT line and a known
        # STDERR line, cross-platform. This mirrors a `docker logs` where the
        # container emitted on both streams.
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
    }

    It "captures BOTH stdout and stderr from a native command under SilentlyContinue" {
        if ($null -eq $script:NativeExe) {
            Set-ItResult -Skipped -Because "no native shell (cmd.exe or /bin/sh) is resolvable on this host"
            return
        }

        # EXACT idiom under test: capture (native 2>&1 | Out-String) with
        # ErrorActionPreference = SilentlyContinue. This is the byte-for-byte
        # shape of backup_daaf.ps1's staging-failure `$StageLog` capture.
        $savedEAP = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        try {
            $captured = (& $script:NativeExe @($script:NativeArgs) 2>&1 | Out-String)
        }
        finally {
            $ErrorActionPreference = $savedEAP
        }

        # The stdout content must survive (the easy leg -- it did not regress).
        $captured | Should -Match ([regex]::Escape($script:OutMarker))

        # The stderr content must ALSO survive. THIS is the leg that dropped in
        # the field on PS 5.1: if this assertion fails, the merged-capture idiom
        # is losing native stderr again and the backup diagnostic block would go
        # silent for the user.
        $captured | Should -Match ([regex]::Escape($script:ErrMarker))
    }

    It "backup_daaf.ps1 still uses the guarded (2>&1 | Out-String) capture for the staging log" {
        # Anchor the behavioral test to the real call site: if the backup script
        # ever stops using the `2>&1 | Out-String` capture (e.g. someone
        # "simplifies" it to a bare assignment), this structural check flags that
        # the behavioral guard above no longer covers the production idiom.
        $content = Get-Content "$RepoRoot/scripts/host/backup_daaf.ps1" -Raw
        $content | Should -Match 'docker logs \$StageCid 2>&1 \| Out-String'
        $content | Should -Match 'docker logs \$ClaudeStageCid 2>&1 \| Out-String'
    }
}
