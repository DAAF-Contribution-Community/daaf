# ============================================================================
# Unit tests for Set-DaafSettingsKey (daaf_lib.ps1)
# ============================================================================
# Set-DaafSettingsKey is the WRITE counterpart to Import-DaafSettingsFile and the
# PowerShell twin of daaf_lib.sh upsert_settings_key. It inserts or updates a
# single KEY=value line in a dotenv-style settings file, preserving comments, key
# order, and layout. This battery mirrors tests/bash/upsert_settings_key.bats
# (append / activate-commented-example / replace / if-absent / value edge cases /
# dry-run / one-time backup) and adds two PowerShell-specific encoding checks the
# Bash writer gets for free: NO UTF-8 BOM and LF-only line endings (Windows
# PowerShell 5.1's default writers emit both a BOM and CRLF, which corrupt the
# strict bash/Compose parser -- so the function uses a hand-rolled writer that
# these tests must protect).
# ============================================================================

Describe "daaf_lib.ps1 Set-DaafSettingsKey" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        # Dot-source the library so the function is defined in this scope.
        . "$RepoRoot/scripts/host/daaf_lib.ps1"

        # Write a settings file with deterministic LF endings and no BOM, so the
        # tests control the exact input bytes (the function strips CR on read, so
        # CRLF input is tolerated, but LF input keeps the assertions unambiguous).
        function Write-LfFile {
            param([string]$Path, [string]$Text)
            [System.IO.File]::WriteAllText($Path, $Text, (New-Object System.Text.UTF8Encoding($false)))
        }
    }

    BeforeEach {
        $script:TmpDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-upsert-test-$(Get-Random)")
        $script:S = Join-Path $script:TmpDir "s.txt"
        Remove-Item Env:DAAF_DRY_RUN -ErrorAction SilentlyContinue
    }

    AfterEach {
        Remove-Item -Recurse -Force $script:TmpDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_DRY_RUN -ErrorAction SilentlyContinue
    }

    # ---------------------------------------------------------------------
    # Placement rule 3 -- append under a dated provenance comment
    # ---------------------------------------------------------------------
    It "appends a fresh key under a dated provenance comment" {
        Write-LfFile $script:S "DAAF_PORT_MARIMO=2718`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value main 6>$null
        $lines = @(Get-Content -LiteralPath $script:S)
        $lines | Should -Contain 'DAAF_BRANCH=main'
        @($lines -match '^# Added by DAAF on \d{4}-\d{2}-\d{2}$').Count | Should -BeGreaterThan 0
        # The provenance comment sits directly above the new key.
        $idx = [array]::IndexOf($lines, 'DAAF_BRANCH=main')
        $lines[$idx - 1] | Should -Match '^# Added by DAAF on '
    }

    # ---------------------------------------------------------------------
    # Placement rule 2 -- insert directly below a commented example
    # ---------------------------------------------------------------------
    It "inserts a new active line directly below a commented example (adjacency)" {
        Write-LfFile $script:S "FOO=bar`n#DAAF_BRANCH=`nBAZ=qux`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value dev 6>$null
        $lines = @(Get-Content -LiteralPath $script:S)
        $ci = [array]::IndexOf($lines, '#DAAF_BRANCH=')
        $ai = [array]::IndexOf($lines, 'DAAF_BRANCH=dev')
        $ai | Should -Be ($ci + 1)
        $lines | Should -Contain 'BAZ=qux'
    }

    It "activates a '# KEY=' commented example with a leading space too" {
        Write-LfFile $script:S "# DAAF_BRANCH=example`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value dev 6>$null
        $lines = @(Get-Content -LiteralPath $script:S)
        $ci = [array]::IndexOf($lines, '# DAAF_BRANCH=example')
        $ai = [array]::IndexOf($lines, 'DAAF_BRANCH=dev')
        $ai | Should -Be ($ci + 1)
    }

    # ---------------------------------------------------------------------
    # if-absent guard -- active key present, file left byte-identical
    # ---------------------------------------------------------------------
    It "if-absent skips when an active key already exists (file byte-identical)" {
        Write-LfFile $script:S "DAAF_BRANCH=main`nFOO=bar`n"
        $before = [System.IO.File]::ReadAllBytes($script:S)
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value other 6>$null
        $after = [System.IO.File]::ReadAllBytes($script:S)
        ($after -join ',') | Should -Be ($before -join ',')
    }

    # ---------------------------------------------------------------------
    # Placement rule 1 (replace) -- rewrite value in place, preserve position
    # ---------------------------------------------------------------------
    It "replace mode rewrites the value in place, preserving position" {
        Write-LfFile $script:S "A=1`nDAAF_BRANCH=old`nB=2`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value new -Mode replace 6>$null
        $lines = @(Get-Content -LiteralPath $script:S)
        $lines[0] | Should -Be 'A=1'
        $lines[1] | Should -Be 'DAAF_BRANCH=new'
        $lines[2] | Should -Be 'B=2'
        ($lines -join "`n") | Should -Not -Match 'DAAF_BRANCH=old'
    }

    It "replace on an unchanged value is a no-op (file byte-identical)" {
        Write-LfFile $script:S "DAAF_BRANCH=main`n"
        $before = [System.IO.File]::ReadAllBytes($script:S)
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value main -Mode replace 6>$null
        $after = [System.IO.File]::ReadAllBytes($script:S)
        ($after -join ',') | Should -Be ($before -join ',')
    }

    # ---------------------------------------------------------------------
    # Documented limitation -- duplicate active keys (replace hits the FIRST)
    # ---------------------------------------------------------------------
    It "replace updates the FIRST active occurrence when a key is duplicated (single-occurrence assumption)" {
        # A settings file should never contain two active lines for the same key,
        # but if one was hand-created, replace mode updates the FIRST occurrence and
        # leaves later ones stale. Locks the documented behavior (Compose env_file is
        # last-wins, DAAF's loader is first-wins -- neither reconciles a duplicate).
        Write-LfFile $script:S "DAAF_BRANCH=first`nFOO=bar`nDAAF_BRANCH=second`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value new -Mode replace 6>$null
        $lines = @(Get-Content -LiteralPath $script:S)
        # First occurrence rewritten in place...
        $lines[0] | Should -Be 'DAAF_BRANCH=new'
        # ...the later duplicate is left untouched (stale).
        $lines[2] | Should -Be 'DAAF_BRANCH=second'
    }

    # ---------------------------------------------------------------------
    # Value edge cases -- spaces, quotes, and '=' inside the value
    # ---------------------------------------------------------------------
    It "preserves a value with spaces, quotes, and = signs" {
        Write-LfFile $script:S "DAAF_BRANCH=main`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_PROJECT_NAME -Value 'a b="c=d"' 6>$null
        $lines = @(Get-Content -LiteralPath $script:S)
        $lines | Should -Contain 'DAAF_PROJECT_NAME=a b="c=d"'
    }

    # ---------------------------------------------------------------------
    # Dry-run -- describes the write, touches nothing on disk
    # ---------------------------------------------------------------------
    It "dry-run describes the write but touches nothing on disk" {
        Write-LfFile $script:S "FOO=bar`n"
        $before = [System.IO.File]::ReadAllBytes($script:S)
        $env:DAAF_DRY_RUN = '1'
        try {
            $out = (Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value main 6>&1 | Out-String)
        }
        finally {
            Remove-Item Env:DAAF_DRY_RUN -ErrorAction SilentlyContinue
        }
        $out | Should -Match '\[DRY-RUN\]'
        $out | Should -Match 'DAAF_BRANCH=main'
        $after = [System.IO.File]::ReadAllBytes($script:S)
        ($after -join ',') | Should -Be ($before -join ',')
    }

    # ---------------------------------------------------------------------
    # Backup -- one-time creation, never overwritten on a later call
    # ---------------------------------------------------------------------
    It "backup suffix creates a one-time backup, not overwritten on 2nd call" {
        Write-LfFile $script:S "DAAF_BRANCH=v1`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value v2 -Mode replace -BackupSuffix '.bak' 6>$null
        $bak = $script:S + '.bak'
        Test-Path -LiteralPath $bak | Should -BeTrue
        @(Get-Content -LiteralPath $bak) | Should -Contain 'DAAF_BRANCH=v1'
        # Second replace with the same suffix -> backup must STILL hold v1, not v2.
        Set-DaafSettingsKey -File $script:S -Key DAAF_BRANCH -Value v3 -Mode replace -BackupSuffix '.bak' 6>$null
        @(Get-Content -LiteralPath $bak) | Should -Contain 'DAAF_BRANCH=v1'
        @(Get-Content -LiteralPath $bak) | Should -Not -Contain 'DAAF_BRANCH=v2'
        @(Get-Content -LiteralPath $script:S) | Should -Contain 'DAAF_BRANCH=v3'
    }

    # ---------------------------------------------------------------------
    # PowerShell-specific: no BOM, LF-only line endings
    # ---------------------------------------------------------------------
    It "writes UTF-8 without a BOM and with LF-only line endings" {
        Write-LfFile $script:S "DAAF_BRANCH=main`n"
        Set-DaafSettingsKey -File $script:S -Key DAAF_PORT_VSCODE -Value 2720 6>$null
        $bytes = [System.IO.File]::ReadAllBytes($script:S)
        # No BOM: the first three bytes must not be EF BB BF.
        ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) | Should -BeFalse
        # LF-only: the raw file text must contain no carriage return.
        $raw = [System.IO.File]::ReadAllText($script:S)
        $raw | Should -Not -Match "`r"
    }

    # ---------------------------------------------------------------------
    # Error path -- missing file
    # ---------------------------------------------------------------------
    It "errors when the target file does not exist" {
        $missing = Join-Path $script:TmpDir "nonexistent.txt"
        { Set-DaafSettingsKey -File $missing -Key DAAF_BRANCH -Value main -ErrorAction Stop } | Should -Throw
    }
}
