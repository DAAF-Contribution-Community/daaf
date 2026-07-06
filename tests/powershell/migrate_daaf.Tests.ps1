# ============================================================================
# Pester tests for migrate_daaf.ps1 -- DAAF Migration Script (Windows)
# ============================================================================

Describe "migrate_daaf.ps1" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    Context "Syntax validation" {
        It "parses without errors" {
            $errors = Test-ScriptSyntax -Path "$RepoRoot/scripts/host/migrate_daaf.ps1"
            $errors | Should -BeNullOrEmpty
        }
    }

    Context "Script structure" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "sets ErrorActionPreference to Stop" {
            $Content | Should -Match '\$ErrorActionPreference\s*=\s*[''"]Stop[''"]'
        }

        It "enables Set-StrictMode -Version 3.0" {
            $Content | Should -Match 'Set-StrictMode\s+-Version\s+3\.0'
        }

        It "places Set-StrictMode after the test-mode guard" {
            # Strict mode is dynamically scoped: placing it before the guard would
            # leak into Pester's dot-sourced test session. It must come after.
            $guardIdx = $Content.IndexOf('$env:DAAF_TEST_MODE -eq "1"')
            $strictIdx = $Content.IndexOf('Set-StrictMode -Version 3.0')
            $guardIdx | Should -BeGreaterThan -1
            $strictIdx | Should -BeGreaterThan $guardIdx
        }

        It "defines Wait-ForUser function" {
            $Content | Should -Match 'function Wait-ForUser'
        }

        It "checks DAAF_NESTED in Wait-ForUser" {
            $Content | Should -Match 'DAAF_NESTED'
        }

        It "defines Read-UserChoice helper function" {
            $Content | Should -Match 'function Read-UserChoice'
        }

        It "defines Invoke-ContainerGit helper function" {
            $Content | Should -Match 'function Invoke-ContainerGit\b'
        }

        It "defines Invoke-ContainerGitVerbose helper function" {
            $Content | Should -Match 'function Invoke-ContainerGitVerbose'
        }

        It "defines Invoke-ContainerExec helper function" {
            $Content | Should -Match 'function Invoke-ContainerExec'
        }

        It "defines Invoke-ContainerShell helper function" {
            $Content | Should -Match 'function Invoke-ContainerShell\b'
        }

        It "defines Invoke-ContainerShellVerbose helper function" {
            $Content | Should -Match 'function Invoke-ContainerShellVerbose'
        }

        It "has a trap handler for unexpected failures" {
            $Content | Should -Match 'trap \{'
        }

        It "checks for Docker with Get-Command" {
            $Content | Should -Match 'Get-Command docker'
        }

        It "checks Docker daemon with docker info" {
            $Content | Should -Match 'docker info'
        }

        It "checks volume exists" {
            $Content | Should -Match 'docker volume inspect'
        }

        It "supports DAAF_BRANCH environment variable" {
            $Content | Should -Match 'DAAF_BRANCH'
        }

        It "detects non-interactive mode" {
            $Content | Should -Match 'NonInteractive'
        }

        It "detects Era 1 (clone-based) installations" {
            $Content | Should -Match 'clone-based installation'
        }

        It "detects Era 2 (ZIP-based) installations" {
            $Content | Should -Match 'ZIP-based installation'
        }

        It "performs a backup before migration" {
            $Content | Should -Match 'backup_daaf\.ps1'
        }

        It "handles fork detection" {
            $Content | Should -Match 'IsFork'
        }

        It "performs graft for ERA 2 installations" {
            $Content | Should -Match 'replace --graft'
        }

        It "fixes file permissions for ZIP downloads" {
            $Content | Should -Match 'Fixing file permissions'
        }

        It "sets upstream tracking branch" {
            $Content | Should -Match 'set-upstream-to=origin/main'
        }

        It "offers to run update after migration" {
            $Content | Should -Match 'Run update'
        }

        It "sets TLS 1.2 for GitHub downloads" {
            $Content | Should -Match 'Tls12'
        }

        It "claims idempotency in its header" {
            $Content | Should -Match 'idempotent'
        }
    }
}

# ============================================================================
# Behavioral tests -- dot-source the script and call functions directly
# ============================================================================

Describe "migrate_daaf.ps1 behavioral tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        $env:DAAF_TEST_MODE = "1"
        . "$RepoRoot/scripts/host/migrate_daaf.ps1"

        # Declare a docker function so Pester can mock it
        function docker {}
    }

    AfterAll {
        Remove-Item Env:DAAF_TEST_MODE -ErrorAction SilentlyContinue
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerGit
    # -----------------------------------------------------------------
    Context "Invoke-ContainerGit" {
        It "executes git command in container" {
            Mock docker { return "mock-sha-output" }
            $null = Invoke-ContainerGit rev-parse HEAD
            Should -Invoke docker -Times 1
        }

        It "strips carriage returns from output" {
            Mock docker { return "abc123`r`ndef456`r`n" }
            $result = Invoke-ContainerGit log --oneline
            $result | Should -Not -Match "`r"
        }

        It "returns trimmed output" {
            Mock docker { return "  abc123  " }
            $result = Invoke-ContainerGit rev-parse HEAD
            $result | Should -Not -Match '^\s'
            $result | Should -Not -Match '\s$'
        }
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerGitVerbose
    # -----------------------------------------------------------------
    Context "Invoke-ContainerGitVerbose" {
        It "preserves output content" {
            Mock docker { return "verbose-fetch-progress" }
            $result = Invoke-ContainerGitVerbose fetch origin
            $result | Should -BeLike "*verbose-fetch*"
        }
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerExec
    # -----------------------------------------------------------------
    Context "Invoke-ContainerExec" {
        It "runs arbitrary command in container" {
            Mock docker { $global:LASTEXITCODE = 0 }
            Invoke-ContainerExec test -f /daaf/CLAUDE.md
            Should -Invoke docker -Times 1
            $LASTEXITCODE | Should -Be 0
        }
    }

    # -----------------------------------------------------------------
    # Invoke-ContainerShell / Invoke-ContainerShellVerbose
    # -----------------------------------------------------------------
    Context "Invoke-ContainerShell" {
        It "runs shell command and returns string" {
            Mock docker { return "shell-output-here" }
            $result = Invoke-ContainerShell "echo hello"
            $result | Should -BeLike "*shell-output*"
        }

        It "strips carriage returns" {
            Mock docker { return "line1`r`nline2`r`n" }
            $result = Invoke-ContainerShell "ls /daaf"
            $result | Should -Not -Match "`r"
        }
    }

    Context "Invoke-ContainerShellVerbose" {
        It "returns output including stderr content" {
            Mock docker { return "verbose-shell-output" }
            $result = Invoke-ContainerShellVerbose "ls -la /daaf"
            $result | Should -BeLike "*verbose-shell*"
        }
    }

    # -----------------------------------------------------------------
    # Read-UserChoice
    # -----------------------------------------------------------------
    Context "Read-UserChoice" {
        # On CI runners, [Environment]::UserInteractive is false, which
        # triggers the non-interactive auto-select path before Read-Host
        # is called. To test the interactive read path, we define a
        # test-only version that skips the interactivity check.
        BeforeAll {
            function Read-UserChoiceInteractive {
                param([string]$PromptText, [string[]]$ValidChoices)
                while ($true) {
                    $choice = (Read-Host $PromptText).Trim().ToLower()
                    if ($ValidChoices -contains $choice) { return $choice }
                    Write-Host "  Please enter one of: $($ValidChoices -join ', ')" -ForegroundColor Yellow
                }
            }
        }

        It "returns valid selection" {
            Mock Read-Host { return "y" }
            $result = Read-UserChoiceInteractive "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }

        It "normalizes input to lowercase" {
            Mock Read-Host { return "Y" }
            $result = Read-UserChoiceInteractive "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }

        It "trims whitespace from input" {
            Mock Read-Host { return "  n  " }
            $result = Read-UserChoiceInteractive "Choose [y/n]" @("y", "n")
            $result | Should -Be "n"
        }

        It "auto-selects first choice in non-interactive mode" {
            $result = Read-UserChoice "Choose [y/n]" @("y", "n")
            $result | Should -Be "y"
        }
    }

    # -----------------------------------------------------------------
    # Era detection patterns (verified via source analysis)
    # -----------------------------------------------------------------
    Context "Era detection patterns" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "no remote indicates Era 2 (ZIP-based)" {
            # When origin URL is empty/whitespace, DetectedEra should be "2"
            $Content | Should -Match 'IsNullOrWhiteSpace\(\$OriginUrl\)'
            $Content | Should -Match '\$DetectedEra = "2"'
        }

        It "remote with upstream repo URL indicates Era 1" {
            $Content | Should -Match '\$OriginUrl -match \$Repo'
            $Content | Should -Match '\$DetectedEra = "1"'
        }

        It "idempotency: graft already in place skips graft step" {
            $Content | Should -Match 'History graft already in place'
            $Content | Should -Match '\$InitialParentCount -gt 0'
        }
    }

    # -----------------------------------------------------------------
    # Era-specific file markers and output patterns
    # -----------------------------------------------------------------
    # These verify the migration script has distinct detection strings
    # and code paths for each era. Complements the integration tests
    # in ci-integration.yml which test against real Docker containers.
    Context "Era-specific marker patterns" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "emits 'clone-based installation' for Era 1 detection" {
            $Content | Should -Match 'clone-based installation'
        }

        It "emits 'ZIP-based installation' for Era 2 detection" {
            $Content | Should -Match 'ZIP-based installation'
        }

        It "has distinct code paths for Era 1 and Era 2" {
            # Era 1 path
            $Content | Should -Match '\$DetectedEra -eq "1"'
            # Era 2 path uses graft
            $Content | Should -Match 'replace --graft'
        }

        It "Era 2 path includes graft operation" {
            # The graft is the critical Era 2 operation that connects
            # local ZIP history to upstream timeline
            $graftPos = $Content.IndexOf('replace --graft')
            $graftPos | Should -BeGreaterThan -1
        }

        It "Era 1 and Era 2 detection strings are distinct" {
            # Both detection strings must exist and be different
            $era1Pos = $Content.IndexOf('clone-based installation')
            $era2Pos = $Content.IndexOf('ZIP-based installation')
            $era1Pos | Should -BeGreaterThan -1
            $era2Pos | Should -BeGreaterThan -1
            $era1Pos | Should -Not -Be $era2Pos
        }
    }

    # -----------------------------------------------------------------
    # Safety mechanisms
    # -----------------------------------------------------------------
    Context "Safety mechanisms" {
        BeforeAll {
            $script:Content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        }

        It "uses System.Threading.Mutex for locking" {
            $Content | Should -Match 'System\.Threading\.Mutex'
            $Content | Should -Not -Match 'flock'
        }

        It "mutex uses Global scope for cross-process visibility" {
            $Content | Should -Match 'Global\\DAAFMigrate'
        }

        It "backup call precedes destructive operations" {
            # backup_daaf.ps1 is called in section 3, before era detection/graft in sections 5-6
            $backupPos = $Content.IndexOf('backup_daaf.ps1')
            $graftPos = $Content.IndexOf('replace --graft')
            $backupPos | Should -BeLessThan $graftPos
        }

        It "trap handler releases mutex on failure" {
            $Content | Should -Match 'trap \{'
            $Content | Should -Match 'Mutex\.ReleaseMutex'
        }
    }
}

# ============================================================================
# Dry-run mode
# ============================================================================

Describe "migrate_daaf.ps1 dry-run mode" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:OrigDryRun = $env:DAAF_DRY_RUN
        $script:OrigNested = $env:DAAF_NESTED
        # Run inside a throwaway temp dir. migrate_daaf.ps1 treats the current
        # directory as an existing install when it finds a docker-compose.yml
        # there, and writes stub scripts + a docker-compose.yml.pre-migrate into
        # it. Without this isolation the repo root (which has a docker-compose.yml)
        # would be clobbered. Push in BeforeAll and Pop in a crash-proof AfterAll.
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-migrate-dry-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
        Set-Content -Path (Join-Path $script:TestDir "backup_daaf.ps1") -Value "exit 0"
    }

    AfterAll {
        $env:DAAF_DRY_RUN = $script:OrigDryRun
        $env:DAAF_NESTED = $script:OrigNested
        # Pop unconditionally so a mid-block failure cannot leave CWD at the repo
        # root for the next Describe block.
        if ((Get-Location).Path -eq $script:TestDir.FullName) { Pop-Location }
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
    }

    It "completes successfully with DAAF_DRY_RUN=1" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $null = & "$RepoRoot/scripts/host/migrate_daaf.ps1" *>&1
        $LASTEXITCODE | Should -BeIn @(0, $null)
    }

    It "completes full migration flow" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/migrate_daaf.ps1" *>&1
        ($output | Out-String) | Should -BeLike "*Migration complete*"
    }

    It "dry-run output includes era detection string" {
        $env:DAAF_DRY_RUN = "1"
        $env:DAAF_NESTED = "1"
        $output = & "$RepoRoot/scripts/host/migrate_daaf.ps1" *>&1
        # Dry-run simulates Era 1 (clone-based) -- verify detection output
        ($output | Out-String) | Should -BeLike "*clone-based installation*"
    }
}

# ============================================================================
# Integrated state-machine tests
# ============================================================================
# These test the MAIN ORCHESTRATION flow by running the full script with
# custom docker mock functions to simulate specific scenarios.

Describe "migrate_daaf.ps1 integrated state-machine tests" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    BeforeEach {
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-migrate-int-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
        # Create stub backup_daaf.ps1 that exits cleanly
        Set-Content -Path (Join-Path $script:TestDir "backup_daaf.ps1") -Value "exit 0"
    }

    AfterEach {
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
    }

    It "Era 1 path (clone-based) completes successfully" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { Write-Output "daaf-test-1" }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { return }
        "*exec*git -C /daaf remote get-url*upstream*" { $global:LASTEXITCODE = 1; return }
        "*exec*git -C /daaf remote get-url*origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*exec*git -C /daaf fetch*" { return }
        "*exec*git -C /daaf branch --set-upstream*" { return }
        "*exec*git*" { return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -BeIn @(0, $null)
        $outputStr | Should -BeLike "*clone-based installation*"
        $outputStr | Should -BeLike "*Migration complete*"
    }

    It "Era 2 path (ZIP-based) detects and reports correctly" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { Write-Output "daaf-test-1" }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { return }
        "*exec*git -C /daaf remote get-url*" { $global:LASTEXITCODE = 1; return }
        "*exec*git -C /daaf fetch*" { return }
        "*exec*git -C /daaf rev-list --max-parents=0*" { Write-Output "aaa111root" }
        "*exec*git -C /daaf cat-file*" {
            Write-Output "tree abc123"
            Write-Output "parent def456"
            Write-Output "author Test"
        }
        "*exec*git -C /daaf branch --set-upstream*" { return }
        "*exec*git -C /daaf remote add*" { return }
        "*exec*git*" { return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -BeIn @(0, $null)
        $outputStr | Should -BeLike "*ZIP-based installation*"
        $outputStr | Should -BeLike "*Migration complete*"
    }

    It "already migrated (idempotency) skips graft step" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { Write-Output "daaf-test-1" }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { return }
        "*exec*git -C /daaf remote get-url*" { $global:LASTEXITCODE = 1; return }
        "*exec*git -C /daaf fetch*" { return }
        "*exec*git -C /daaf rev-list --max-parents=0*" { Write-Output "aaa111root" }
        "*exec*git -C /daaf cat-file*" {
            Write-Output "tree abc123"
            Write-Output "parent def456"
            Write-Output "author Test"
        }
        "*exec*git -C /daaf branch --set-upstream*" { return }
        "*exec*git -C /daaf remote add*" { return }
        "*exec*git*" { return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -BeIn @(0, $null)
        $outputStr | Should -BeLike "*graft already in place*"
    }
}

# ============================================================================
# Error path tests
# ============================================================================

Describe "migrate_daaf.ps1 error paths" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    BeforeEach {
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-migrate-err-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
        Set-Content -Path (Join-Path $script:TestDir "backup_daaf.ps1") -Value "exit 0"
    }

    AfterEach {
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
    }

    It "fetch from origin fails exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { Write-Output "daaf-test-1" }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { return }
        "*exec*git -C /daaf remote get-url*upstream*" { $global:LASTEXITCODE = 1; return }
        "*exec*git -C /daaf remote get-url*origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*exec*git -C /daaf fetch*" { $global:LASTEXITCODE = 1; return }
        "*exec*git*" { return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*Failed to fetch*"
    }

    It "DAAF not installed (CLAUDE.md missing) exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { Write-Output "daaf-test-1" }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { $global:LASTEXITCODE = 1; return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*DAAF does not appear to be installed*"
    }

    It "container not running and start fails exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { return }
        "*compose up*" { $global:LASTEXITCODE = 1; return }
        "*start*" { $global:LASTEXITCODE = 1; return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*Failed to start*"
    }

    It "volume not found exits with error" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { $global:LASTEXITCODE = 1; return }
        default { return }
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -Be 1
        $outputStr | Should -BeLike "*not found*"
    }
}

# ============================================================================
# Edge cases
# ============================================================================

Describe "migrate_daaf.ps1 edge cases" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
    }

    BeforeEach {
        $script:TestDir = New-Item -ItemType Directory -Path (Join-Path ([System.IO.Path]::GetTempPath()) "daaf-migrate-edge-$(Get-Random)")
        Push-Location $script:TestDir
        New-FakeComposeFile
        Set-Content -Path (Join-Path $script:TestDir "backup_daaf.ps1") -Value "exit 0"
    }

    AfterEach {
        Pop-Location
        Remove-Item -Recurse -Force $script:TestDir -ErrorAction SilentlyContinue
        Remove-Item Env:DAAF_NESTED -ErrorAction SilentlyContinue
    }

    It "fork detection adds upstream remote" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" { Write-Output "daaf-test-1" }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { return }
        "*exec*git -C /daaf remote get-url*upstream*" { $global:LASTEXITCODE = 1; return }
        "*exec*git -C /daaf remote get-url*origin*" {
            Write-Output "https://github.com/user/daaf-fork.git"
        }
        "*exec*git -C /daaf remote add*upstream*" { return }
        "*exec*git -C /daaf fetch*" { return }
        "*exec*git -C /daaf branch --set-upstream*" { return }
        "*exec*git*" { return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -BeIn @(0, $null)
        $outputStr | Should -BeLike "*clone-based installation*"
        $outputStr | Should -BeLike "*fork*"
        $outputStr | Should -BeLike "*Migration complete*"
    }

    It "multi-container on same volume shows warning" {
        $env:DAAF_NESTED = "1"
        $wrapperScript = Join-Path $script:TestDir "test_wrapper.ps1"
        Set-Content -Path $wrapperScript -Value @'
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
function docker {
    $argStr = $args -join ' '
    $global:LASTEXITCODE = 0
    switch -Wildcard ($argStr) {
        "*info*" { return }
        "*volume inspect*" { return }
        "*ps -a*--filter*volume=*--format*" {
            Write-Output "daaf-test-1"
            Write-Output "daaf-test-2"
        }
        "*inspect*--format*Status*" { Write-Output "running" }
        "*exec*true*" { return }
        "*exec*test -f*CLAUDE.md*" { return }
        "*exec*git -C /daaf remote get-url*upstream*" { $global:LASTEXITCODE = 1; return }
        "*exec*git -C /daaf remote get-url*origin*" {
            Write-Output "https://github.com/DAAF-Contribution-Community/daaf.git"
        }
        "*exec*git -C /daaf fetch*" { return }
        "*exec*git -C /daaf branch --set-upstream*" { return }
        "*exec*git*" { return }
        "*exec*" { return }
        "*start*" { return }
        default { return }
    }
}
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    $null = $UseBasicParsing, $Uri
    if ($OutFile) {
        $parentDir = Split-Path $OutFile -Parent
        if ($parentDir -and -not (Test-Path $parentDir)) {
            New-Item -ItemType Directory -Path $parentDir -Force | Out-Null
        }
        Set-Content -Path $OutFile -Value "exit 0"
    }
}
$NonInteractive = $true
'@
        Add-Content -Path $wrapperScript -Value ". '$RepoRoot/scripts/host/migrate_daaf.ps1'"
        $output = & pwsh -NoProfile -File $wrapperScript *>&1
        $outputStr = $output | Out-String
        $LASTEXITCODE | Should -BeIn @(0, $null)
        $outputStr | Should -BeLike "*Multiple containers*"
        $outputStr | Should -BeLike "*Migration complete*"
    }

    It "concurrent execution guard uses mutex" {
        $content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        $content | Should -Match 'Global\\DAAFMigrate'
        $content | Should -Match 'Mutex\.WaitOne'
    }

    It "mutex released in trap handler on failure" {
        $content = Get-Content "$RepoRoot/scripts/host/migrate_daaf.ps1" -Raw
        $content | Should -Match 'trap \{'
        $content | Should -Match 'Mutex\.ReleaseMutex'
    }
}
