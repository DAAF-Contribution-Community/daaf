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
