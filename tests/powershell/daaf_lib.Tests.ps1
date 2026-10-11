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
#
# A third Describe (at the end) pins Resolve-DaafProjectName: the Compose
# project-name normalization, its byte-identical inline copies in the standalone
# scripts, and install.ps1's inline expression, all on one fixed input set.
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

# ============================================================================
# Compose project-name normalization (Resolve-DaafProjectName) and its copies
# ============================================================================
# Twin of the daaf_lib.bats section of the same name. Docker Compose normalizes the
# project name (compose-go NormalizeProjectName: lowercase, keep [a-z0-9_-], trim
# leading '_'/'-'), so `Work` in the settings file makes the volume
# "work_daaf-data". Every host script that derives a Docker name from the project
# must use that same name. The helper lives in daaf_lib.ps1; the standalone scripts
# (backup_daaf.ps1, restore_from_backup.ps1, update_daaf.ps1, and the maintainer
# harness test_migration.ps1) carry a byte-identical copy, and install.ps1 carries
# its own inline expression. These tests pin all of
# them to one fixed input set (the same inputs and expectations as the bats table).
# Non-ASCII inputs are built with [char] so this file stays ASCII: U+00C4 (A-umlaut),
# U+212A (the Kelvin sign, which ToLowerInvariant would turn into an ASCII 'k' if it
# ran first; review 45q NIT-1) and U+0130 (dotted capital I). An empty expectation
# means the name is refused.

BeforeDiscovery {
    $script:ProjectNameCases = @(
        @{ In = 'Work'; Want = 'work' }
        @{ In = 'work '; Want = 'work' }
        @{ In = 'x # mine'; Want = 'xmine' }
        @{ In = '"x'; Want = 'x' }
        @{ In = '_x'; Want = 'x' }
        @{ In = '-x'; Want = 'x' }
        @{ In = '-_x'; Want = 'x' }
        @{ In = 'x.y'; Want = 'xy' }
        @{ In = ([string][char]0x00C4) + 'BC'; Want = 'bc' }
        @{ In = ([string][char]0x212A) + 'x'; Want = 'x' }
        @{ In = ([string][char]0x0130) + 'x'; Want = 'x' }
        @{ In = '___'; Want = '' }
        @{ In = '@@'; Want = '' }
        @{ In = 'daaf'; Want = 'daaf' }
        @{ In = 'daaf2'; Want = 'daaf2' }
        @{ In = 'My_Proj-1'; Want = 'my_proj-1' }
        @{ In = '--a-b_'; Want = 'a-b_' }
    )
}

Describe "daaf_lib.ps1 Resolve-DaafProjectName" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        . "$RepoRoot/scripts/host/daaf_lib.ps1"
        # The function definition as written in a file: from the column-0
        # `function Resolve-DaafProjectName {` line to the first column-0 `}`.
        function Get-ProjectNameFunctionText {
            param([string]$Path)
            $text = [System.IO.File]::ReadAllText($Path)
            $m = [regex]::Match($text, '(?ms)^function Resolve-DaafProjectName \{\n.*?^\}')
            if (-not $m.Success) { return '' }
            return $m.Value
        }
        # Run a definition (function text) for one DAAF_PROJECT_NAME value in a child
        # scope, so each copy is exercised on its own.
        function Invoke-ProjectNameCopy {
            param([string]$Definition, [string]$Value)
            $saved = $env:DAAF_PROJECT_NAME
            try {
                if ([string]::IsNullOrEmpty($Value)) { Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue } else { $env:DAAF_PROJECT_NAME = $Value }
                return (& ([scriptblock]::Create($Definition + "`nResolve-DaafProjectName")))
            } finally {
                if ($null -ne $saved) { $env:DAAF_PROJECT_NAME = $saved } else { Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue }
            }
        }
        $script:Copies = @('backup_daaf.ps1', 'restore_from_backup.ps1', 'update_daaf.ps1', 'test_migration.ps1')
    }

    BeforeEach {
        $script:SavedVolName = $env:DAAF_DATA_VOLUME_NAME
        $script:SavedProject = $env:DAAF_PROJECT_NAME
        Remove-Item Env:DAAF_DATA_VOLUME_NAME -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue
    }

    AfterEach {
        if ($null -ne $script:SavedVolName) { $env:DAAF_DATA_VOLUME_NAME = $script:SavedVolName } else { Remove-Item Env:DAAF_DATA_VOLUME_NAME -ErrorAction SilentlyContinue }
        if ($null -ne $script:SavedProject) { $env:DAAF_PROJECT_NAME = $script:SavedProject } else { Remove-Item Env:DAAF_PROJECT_NAME -ErrorAction SilentlyContinue }
    }

    It "returns the default 'daaf' when DAAF_PROJECT_NAME is unset" {
        Resolve-DaafProjectName | Should -BeExactly 'daaf'
    }

    It "normalizes <In> to '<Want>' as Docker Compose does" -ForEach $script:ProjectNameCases {
        $env:DAAF_PROJECT_NAME = $In
        Resolve-DaafProjectName | Should -BeExactly $Want
    }

    It "Resolve-DaafDataVolumeName uses the normalized project name (-Work.1 -> work1_daaf-data)" {
        $env:DAAF_PROJECT_NAME = '-Work.1'
        Resolve-DaafDataVolumeName | Should -BeExactly 'work1_daaf-data'
    }

    It "Resolve-DaafDataVolumeName never normalizes the DAAF_DATA_VOLUME_NAME override" {
        $env:DAAF_DATA_VOLUME_NAME = 'My.Shared_Vol'
        $env:DAAF_PROJECT_NAME = 'Work'
        Resolve-DaafDataVolumeName | Should -BeExactly 'My.Shared_Vol'
    }

    It "Resolve-DaafDataVolumeName returns an empty string when the project name normalizes to nothing" {
        $env:DAAF_PROJECT_NAME = '___'
        Resolve-DaafDataVolumeName | Should -BeExactly ''
    }

    It "the inline copies in backup/restore/update/test_migration are byte-identical to daaf_lib.ps1" {
        $lib = Get-ProjectNameFunctionText "$RepoRoot/scripts/host/daaf_lib.ps1"
        # Guard against an empty or wrong extraction making every copy "equal".
        $lib | Should -Match ([regex]::Escape("-creplace '[^A-Za-z0-9_-]', ''"))
        foreach ($f in $script:Copies) {
            $copy = Get-ProjectNameFunctionText "$RepoRoot/scripts/host/$f"
            $copy | Should -BeExactly $lib -Because "$f must carry the library function byte for byte"
        }
    }

    It "each inline copy and install.ps1 give the library's result for <In>" -ForEach $script:ProjectNameCases {
        # (PowerShell variable names are case-insensitive: $libResult, not $want,
        # so the case's own $Want is not overwritten.)
        $env:DAAF_PROJECT_NAME = $In
        $libResult = Resolve-DaafProjectName
        $libResult | Should -BeExactly $Want
        foreach ($f in $script:Copies) {
            $def = Get-ProjectNameFunctionText "$RepoRoot/scripts/host/$f"
            Invoke-ProjectNameCopy -Definition $def -Value $In | Should -BeExactly $libResult -Because "$f copy"
        }
        # install.ps1 runs standalone (irm | iex) and keeps its own one-line
        # expression; it must occur exactly once. Wrap it as a Resolve-DaafProjectName
        # so it runs through the same harness.
        $lines = @(Get-Content -LiteralPath "$RepoRoot/scripts/host/install.ps1" | Where-Object { $_ -like '$InstallTargetProject = if (*' })
        $lines.Count | Should -Be 1
        $installDef = "function Resolve-DaafProjectName {`n" + $lines[0] + "`nreturn `$InstallTargetProject`n}"
        Invoke-ProjectNameCopy -Definition $installDef -Value $In | Should -BeExactly $libResult -Because "install.ps1"
    }

    It "each inline copy and install.ps1 return 'daaf' when DAAF_PROJECT_NAME is unset" {
        foreach ($f in $script:Copies) {
            $def = Get-ProjectNameFunctionText "$RepoRoot/scripts/host/$f"
            Invoke-ProjectNameCopy -Definition $def -Value '' | Should -BeExactly 'daaf' -Because "$f copy"
        }
        $line = @(Get-Content -LiteralPath "$RepoRoot/scripts/host/install.ps1" | Where-Object { $_ -like '$InstallTargetProject = if (*' })[0]
        Invoke-ProjectNameCopy -Definition ("function Resolve-DaafProjectName {`n" + $line + "`nreturn `$InstallTargetProject`n}") -Value '' | Should -BeExactly 'daaf'
    }

    It "no host script derives a Docker name from the RAW DAAF_PROJECT_NAME" {
        # Twin of the daaf_lib.bats pin. The copies are only useful if the scripts call
        # them: no code line may still read the raw value for a name (the old
        # `if ($env:DAAF_PROJECT_NAME) { $env:DAAF_PROJECT_NAME } else { ... }` form),
        # and each script takes its project from Resolve-DaafProjectName.
        $raw = '\$env:DAAF_PROJECT_NAME\s*\}\s*else'
        foreach ($f in @('daaf_lib.ps1') + $script:Copies) {
            $code = @(Get-Content -LiteralPath "$RepoRoot/scripts/host/$f" | Where-Object { $_ -notmatch '^\s*#' })
            @($code | Where-Object { $_ -match $raw }).Count | Should -Be 0 -Because "$f must not read the raw DAAF_PROJECT_NAME for a name"
        }
        foreach ($f in @('backup_daaf.ps1', 'restore_from_backup.ps1')) {
            @(Get-Content -LiteralPath "$RepoRoot/scripts/host/$f" | Where-Object { $_ -ceq '$projectName = Resolve-DaafProjectName' }).Count | Should -Be 1 -Because "$f takes its project from the helper"
        }
        $tm = @(Get-Content -LiteralPath "$RepoRoot/scripts/host/test_migration.ps1")
        @($tm | Where-Object { $_ -ceq '$ProjectName = Resolve-DaafProjectName' }).Count | Should -Be 1
        @($tm | Where-Object { $_ -cmatch '^\$(VolumeName|ClaudeVolumeName|ContainerMain|ContainerInit|ImageName) = "\$\{ProjectName\}[-_]' }).Count | Should -Be 5
        # update_daaf.ps1: every printed `docker cp <project>-daaf-docker-1:` hint uses
        # $daafProj, and every $daafProj comes from the helper.
        $up = @(Get-Content -LiteralPath "$RepoRoot/scripts/host/update_daaf.ps1")
        $hints = @($up | Where-Object { $_ -match 'Write-Host .*docker cp .*-daaf-docker-1:' })
        $hints.Count | Should -Be 7
        @($hints | Where-Object { $_ -notlike '*docker cp ${daafProj}-daaf-docker-1:*' }).Count | Should -Be 0
        $assigns = @($up | Where-Object { $_ -match '^\s*\$daafProj\s*=' })
        $assigns.Count | Should -Be 4
        @($assigns | Where-Object { $_.Trim() -cne '$daafProj = Resolve-DaafProjectName' }).Count | Should -Be 0
        # daaf_lib.ps1's own data-volume resolver calls the helper.
        $lib = [System.IO.File]::ReadAllText("$RepoRoot/scripts/host/daaf_lib.ps1")
        $m = [regex]::Match($lib, '(?ms)^function Resolve-DaafDataVolumeName \{\n.*?^\}')
        $m.Success | Should -BeTrue
        $m.Value | Should -Match ([regex]::Escape('$projectName = Resolve-DaafProjectName'))
    }

    It "test_migration.ps1 refuses a project name that normalizes to nothing, before any identifier is built" {
        # Static: the harness needs Docker and a network to run.
        $tm = @(Get-Content -LiteralPath "$RepoRoot/scripts/host/test_migration.ps1")
        $derive = [array]::IndexOf($tm, '$ProjectName = Resolve-DaafProjectName')
        $refuse = [array]::IndexOf($tm, 'if ([string]::IsNullOrEmpty($ProjectName)) {')
        $firstUse = [array]::IndexOf($tm, '$VolumeName = "${ProjectName}_daaf-data"')
        $derive | Should -BeGreaterThan -1
        $refuse | Should -BeGreaterThan $derive
        $firstUse | Should -BeGreaterThan $refuse
        ($tm[$refuse..($refuse + 5)] -join "`n") | Should -Match 'cannot be used as a Docker Compose project name'
        ($tm[$refuse..($refuse + 5)] -join "`n") | Should -Match '(?m)^\s*exit 1\s*$'
    }
}
