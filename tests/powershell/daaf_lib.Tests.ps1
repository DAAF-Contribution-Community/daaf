# ============================================================================
# Unit tests for Resolve-DaafDataVolumeName (daaf_lib.ps1)
# ============================================================================
# Resolve-DaafDataVolumeName is the PowerShell twin of daaf_lib.sh
# resolve_data_volume_name. It returns the Docker volume name that holds the DAAF
# research workspace (/daaf), honoring the optional DAAF_DATA_VOLUME_NAME full-name
# override. This battery mirrors the four bash cases in tests/bash/daaf_lib.bats
# (the "Data-volume name resolver" section), asserting the same precedence:
#   1. no override, no project name        => "daaf_daaf-data" (legacy hardcoded)
#   2. only DAAF_PROJECT_NAME=daaf2         => "daaf2_daaf-data" (Compose prefix)
#   3. DAAF_DATA_VOLUME_NAME set            => used verbatim (project prefix ignored)
#   4. DAAF_DATA_VOLUME_NAME set-but-empty  => derived default (empty == unset)
# Precedence: DAAF_DATA_VOLUME_NAME (verbatim) > "<project>_daaf-data" default.
# An unset override reproduces the historical hardcoded derivation byte-for-byte.
#
# A second Describe pins Import-DaafSettingsFile's read-failure contract (the twin
# of daaf_lib.bats "load_daaf_settings returns non-zero on an unreadable file"):
# an existing but unreadable file throws even when the caller's
# $ErrorActionPreference is 'Continue', and adopts nothing.
# ============================================================================

Describe "daaf_lib.ps1 Resolve-DaafDataVolumeName" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        # Dot-source the library so the function is defined in this scope.
        . "$RepoRoot/scripts/host/daaf_lib.ps1"
    }

    BeforeEach {
        # Snapshot the two env vars the resolver reads, then start each test from a
        # clean slate so the ambient process env cannot skew the assertions. AfterEach
        # restores the caller's exact prior state (clearing a var only when it was
        # genuinely unset), so the suite leaves no environment residue.
        $script:SavedVolName = $env:DAAF_DATA_VOLUME_NAME
        $script:SavedProject = $env:DAAF_PROJECT_NAME
        Remove-Item Env:DAAF_DATA_VOLUME_NAME -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue
    }

    AfterEach {
        if ($null -ne $script:SavedVolName) { $env:DAAF_DATA_VOLUME_NAME = $script:SavedVolName } else { Remove-Item Env:DAAF_DATA_VOLUME_NAME -ErrorAction SilentlyContinue }
        if ($null -ne $script:SavedProject) { $env:DAAF_PROJECT_NAME = $script:SavedProject } else { Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue }
    }

    It "derives the default when no override and no project name" {
        # Unset override + unset project name => the legacy hardcoded name, unchanged.
        Resolve-DaafDataVolumeName | Should -Be "daaf_daaf-data"
    }

    It "applies the project prefix when only DAAF_PROJECT_NAME is set" {
        # A second instance owns "<project>_daaf-data" without touching the override.
        $env:DAAF_PROJECT_NAME = "daaf2"
        Resolve-DaafDataVolumeName | Should -Be "daaf2_daaf-data"
    }

    It "uses DAAF_DATA_VOLUME_NAME verbatim when set (ignores project prefix)" {
        # Set override wins verbatim -- no project prefix is added (shared-workspace hatch).
        $env:DAAF_DATA_VOLUME_NAME = "shared_workspace_vol"
        $env:DAAF_PROJECT_NAME = "daaf2"
        Resolve-DaafDataVolumeName | Should -Be "shared_workspace_vol"
    }

    It "treats a set-but-empty override as unset (derived default)" {
        # An empty string is falsy in PowerShell, so the guard treats empty and unset
        # alike, matching the bash `:-` semantics -- it falls through to the derived
        # default rather than returning an empty volume name.
        $env:DAAF_DATA_VOLUME_NAME = ""
        Resolve-DaafDataVolumeName | Should -Be "daaf_daaf-data"
    }
}

Describe "daaf_lib.ps1 Import-DaafSettingsFile read failure" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        . "$RepoRoot/scripts/host/daaf_lib.ps1"
    }

    BeforeEach {
        $script:SavedVscode = $env:DAAF_PORT_VSCODE
        Remove-Item Env:DAAF_PORT_VSCODE -ErrorAction SilentlyContinue
        $script:DaafKeysFromFile = @()
        $script:LockedFile = Join-Path $TestDrive ("environment_settings-" + [guid]::NewGuid().ToString('N') + ".txt")
        Set-Content -LiteralPath $script:LockedFile -Value "DAAF_PORT_VSCODE=3555"
    }

    AfterEach {
        if (Test-Path -LiteralPath $script:LockedFile) { & chmod 644 $script:LockedFile }
        if ($null -ne $script:SavedVscode) { $env:DAAF_PORT_VSCODE = $script:SavedVscode } else { Remove-Item Env:DAAF_PORT_VSCODE -ErrorAction SilentlyContinue }
    }

    It "throws on an unreadable file even under ErrorActionPreference Continue, adopting nothing" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows -or ((& id -u) -eq '0')) {
        # chmod 000 stages a real read failure; skipped where it cannot (Windows,
        # root). Without -ErrorAction Stop on the read, 'Continue' would turn the
        # failure into a non-terminating error and the load would silently adopt
        # nothing while appearing to succeed.
        & chmod 000 $script:LockedFile
        $threw = $false
        $savedEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            Import-DaafSettingsFile -SettingsFile $script:LockedFile 2>$null
        } catch {
            $threw = $true
        } finally {
            $ErrorActionPreference = $savedEap
        }
        $threw | Should -BeTrue
        $env:DAAF_PORT_VSCODE | Should -BeNullOrEmpty
        @($script:DaafKeysFromFile).Count | Should -Be 0
    }

    It "stays a silent no-op for an ABSENT file under ErrorActionPreference Stop" {
        # Assigned inside the It block, so the preference is local to this test.
        $absent = Join-Path $TestDrive "no-such-environment_settings.txt"
        $ErrorActionPreference = 'Stop'
        { Import-DaafSettingsFile -SettingsFile $absent } | Should -Not -Throw
        $env:DAAF_PORT_VSCODE | Should -BeNullOrEmpty
    }
}
