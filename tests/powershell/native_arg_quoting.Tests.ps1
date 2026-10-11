# ============================================================================
# Pester tests for ConvertTo-DaafNativeArg and the host-script child-launch idioms
# ============================================================================
# Start-Process -ArgumentList does NOT quote array elements: it joins them with
# bare spaces and the child re-splits the string with the Windows argv rules
# (Microsoft Start-Process docs; PowerShell#5576). A child path or backup path
# containing a space therefore arrived as several arguments. The fix is ONE
# pre-joined string built from ConvertTo-DaafNativeArg (canonical in
# daaf_lib.ps1; INLINE COPIES in the standalone backup_daaf.ps1 and
# test_migration.ps1). This file pins:
#   1. the helper's quoting rules (table-driven),
#   2. an exact argv round-trip through REAL child processes whose script lives
#      in a directory containing a space,
#   3. byte-identity of every inline copy with the canonical definition
#      (plus a self-test proving the comparison can fail),
#   4. AST-based structural guards over scripts/host/*.ps1 (comments can never
#      satisfy them): every Start-Process / saps / start call binds analysably
#      (no splatting, no positional -ArgumentList, no unresolvable parameter),
#      its -ArgumentList is one string built with ConvertTo-DaafNativeArg, the
#      call-site inventory is pinned, every -PassThru result caches .Handle
#      before any other use (on Windows -- Windows PowerShell 5.1 and PowerShell
#      6.0-7.4.0, with -NoNewWindow / -RedirectStandard* -- ExitCode reads $null
#      otherwise: PowerShell#5421, #20400, fixed in 7.4.1), and daaf.ps1 never
#      coerces $ec with a truthiness idiom -- each guard with a self-test that
#      proves it rejects the known-bad shapes,
#   5. $null script arguments are dropped by the test_migration.ps1 launchers
#      (daaf.ps1's delegates are covered in daaf.Tests.ps1).
# ============================================================================

Describe "ConvertTo-DaafNativeArg (canonical, daaf_lib.ps1)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        . "$RepoRoot/scripts/host/daaf_lib.ps1"
    }

    Context "Quoting rules (table-driven)" {
        # Encoded forms follow the inverse of the Windows argv parser: bare when
        # there is no whitespace and no double quote; otherwise quoted, with every
        # backslash run before an embedded quote doubled plus the quote escaped,
        # and a trailing backslash run doubled so it cannot escape the closing quote.
        It "encodes <Name>" -ForEach @(
            @{ Name = 'empty string';            Value = '';                                     Expected = '""' }
            @{ Name = 'plain token';             Value = 'plain';                                Expected = 'plain' }
            @{ Name = 'flag token';              Value = '-NoProfile';                           Expected = '-NoProfile' }
            @{ Name = 'embedded space';          Value = 'with space';                           Expected = '"with space"' }
            @{ Name = 'embedded quote';          Value = 'q"z';                                  Expected = '"q\"z"' }
            @{ Name = 'backslash before quote';  Value = 'back\"slash';                          Expected = '"back\\\"slash"' }
            @{ Name = 'bare trailing backslash'; Value = 'trail\';                               Expected = 'trail\' }
            @{ Name = 'spaced trailing backslash'; Value = 'C:\Users\John Smith\OneDrive - Org\'; Expected = '"C:\Users\John Smith\OneDrive - Org\\"' }
            @{ Name = 'embedded tab';            Value = "tab`there";                            Expected = "`"tab`there`"" }
            # Backslashes that are NOT at the end: a '$' anchor would also match
            # before the final LF and wrongly double them; '\z' does not.
            @{ Name = 'backslash then trailing LF'; Value = "trail\`n";                          Expected = "`"trail\`n`"" }
        ) {
            ConvertTo-DaafNativeArg $Value | Should -BeExactly $Expected
        }
    }

    Context "argv round-trip through a real child process (script in a spaced directory)" {
        BeforeAll {
            # The repro-D value set from the 2026-09-29 host sweep plus the two
            # shapes the host scripts actually pass (a flag and a spaced path).
            $script:RoundTripValues = @(
                '',
                'plain',
                'with space',
                'q"z',
                'back\"slash',
                'trail\',
                'C:\Users\John Smith\OneDrive - Org\'
            )
            $script:SpacedDir = Join-Path $TestDrive 'dir with space'
            $null = New-Item -ItemType Directory -Force -Path $script:SpacedDir
            $script:PsExe = (Get-Process -Id $PID).Path
        }

        It "a PowerShell child launched with -File and a spaced script path receives every value exactly" {
            # Mirrors the daaf.ps1 / test_migration.ps1 launch shape: host exe +
            # -NoProfile -File <child path under a spaced folder> + script args.
            $child = Join-Path $script:SpacedDir 'argv echo.ps1'
            Set-Content -LiteralPath $child -Value 'foreach ($a in $args) { [Console]::Out.WriteLine("<" + $a + ">") }'
            $outFile = Join-Path $TestDrive 'ps-argv.out'
            $parts = @('-NoProfile', '-NonInteractive', '-File', $child) + $script:RoundTripValues
            $argString = (@($parts) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '
            $p = Start-Process -FilePath $script:PsExe -ArgumentList $argString -NoNewWindow -PassThru -RedirectStandardOutput $outFile
            $null = $p.Handle
            $p.WaitForExit()
            $p.ExitCode | Should -Be 0
            $got = @(Get-Content -LiteralPath $outFile)
            $want = @($script:RoundTripValues | ForEach-Object { "<$_>" })
            ($got -join "`n") | Should -BeExactly ($want -join "`n")
        }

        It "a native child (sh) launched with a spaced script path receives every value exactly" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
            # Mirrors the backup_daaf.ps1 `docker cp` shape: a native exe whose
            # argv is split from the single joined string by .NET's Windows rules.
            $child = Join-Path $script:SpacedDir 'argv echo.sh'
            [System.IO.File]::WriteAllText($child, "printf '<%s>\n' `"`$@`"`n")
            $outFile = Join-Path $TestDrive 'sh-argv.out'
            $parts = @($child) + $script:RoundTripValues
            $argString = (@($parts) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join ' '
            $p = Start-Process -FilePath 'sh' -ArgumentList $argString -NoNewWindow -PassThru -RedirectStandardOutput $outFile
            $null = $p.Handle
            $p.WaitForExit()
            $p.ExitCode | Should -Be 0
            $got = @(Get-Content -LiteralPath $outFile)
            $want = @($script:RoundTripValues | ForEach-Object { "<$_>" })
            ($got -join "`n") | Should -BeExactly ($want -join "`n")
        }

        It "CONTROL: the old array form splits the spaced script path (proves the harness detects the bug)" -Skip:(($PSVersionTable.PSVersion.Major -lt 6) -or $IsWindows) {
            # Executable evidence that the round-trip harness can fail: the pre-fix
            # array -ArgumentList hands sh a split path, so the script is not found.
            $child = Join-Path $script:SpacedDir 'argv echo.sh'
            [System.IO.File]::WriteAllText($child, "printf '<%s>\n' `"`$@`"`n")
            $errFile = Join-Path $TestDrive 'sh-control.err'
            $p = Start-Process -FilePath 'sh' -ArgumentList @($child, 'x') -NoNewWindow -PassThru -RedirectStandardError $errFile
            $null = $p.Handle
            $p.WaitForExit()
            $p.ExitCode | Should -Not -Be 0
        }
    }
}

Describe "ConvertTo-DaafNativeArg inline-copy parity" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"

        # Return the exact source text of every `function <Name>` definition in a
        # file (CRLF normalized to LF so a checkout's line endings cannot matter).
        function Get-FunctionDefinitionText([string]$Source, [string]$Name) {
            $tokens = $null; $errors = $null
            $ast = [System.Management.Automation.Language.Parser]::ParseInput($Source, [ref]$tokens, [ref]$errors)
            @($ast.FindAll({
                param($n)
                $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $Name
            }, $true) | ForEach-Object { $_.Extent.Text -replace "`r", "" })
        }

        $script:HostDir = Join-Path $RepoRoot 'scripts/host'
        $script:Canonical = @(Get-FunctionDefinitionText (Get-Content -Raw -LiteralPath (Join-Path $script:HostDir 'daaf_lib.ps1')) 'ConvertTo-DaafNativeArg')
        # The standalone scripts that carry an inline copy (they do not dot-source
        # daaf_lib.ps1). Adding a new consumer means adding it here -- the
        # "every consumer is wired" test below fails until you do.
        $script:InlineCopyFiles = @('backup_daaf.ps1', 'test_migration.ps1')
    }

    It "daaf_lib.ps1 defines the canonical helper exactly once" {
        $script:Canonical.Count | Should -Be 1
    }

    It "<File> carries exactly one inline copy, byte-identical to daaf_lib.ps1" -ForEach @(
        @{ File = 'backup_daaf.ps1' }
        @{ File = 'test_migration.ps1' }
    ) {
        $copies = @(Get-FunctionDefinitionText (Get-Content -Raw -LiteralPath (Join-Path $script:HostDir $File)) 'ConvertTo-DaafNativeArg')
        $copies.Count | Should -Be 1
        $copies[0] | Should -BeExactly $script:Canonical[0]
    }

    It "every host script that calls the helper dot-sources daaf_lib.ps1 or carries a pinned inline copy" {
        $unwired = @()
        foreach ($f in @(Get-ChildItem -LiteralPath $script:HostDir -Filter '*.ps1' -File)) {
            if ($f.Name -eq 'daaf_lib.ps1') { continue }
            $src = Get-Content -Raw -LiteralPath $f.FullName
            if ($src -notmatch 'ConvertTo-DaafNativeArg') { continue }
            $dotSources = $src -match '(?m)^\s*\.\s+\(Join-Path\s+\$\w+\s+"daaf_lib\.ps1"\)'
            $pinned = $script:InlineCopyFiles -contains $f.Name
            if (-not ($dotSources -or $pinned)) { $unwired += $f.Name }
        }
        $unwired | Should -BeNullOrEmpty
    }

    It "SELF-TEST: a one-character perturbation of an inline copy trips the comparison" {
        # A parity test that cannot fail is worthless: perturb the backup copy in
        # memory (drop the trailing-backslash doubling) and show it now differs.
        $src = Get-Content -Raw -LiteralPath (Join-Path $script:HostDir 'backup_daaf.ps1')
        $perturbed = $src.Replace('-replace ''(\\+)\z'', ''$1$1''', '-replace ''(\\+)\z'', ''$1''')
        $perturbed | Should -Not -BeExactly $src
        $copy = @(Get-FunctionDefinitionText $perturbed 'ConvertTo-DaafNativeArg')
        $copy.Count | Should -Be 1
        $copy[0] | Should -Not -BeExactly $script:Canonical[0]
    }
}

Describe "Host-script Start-Process structural guards" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:HostFiles = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot 'scripts/host') -Filter '*.ps1' -File)

        # Every guard below works on the parsed AST, never on raw text, so a comment
        # that merely mentions ConvertTo-DaafNativeArg or .Handle cannot satisfy it.
        #
        # Start-Process parameter metadata (names, aliases, switch-ness) is read from
        # the running host so prefix and alias resolution mirrors PowerShell's own
        # binder: -Arg / -Argument / -Args all resolve to ArgumentList, -Pass to
        # PassThru; an ambiguous or unknown name is reported, not guessed.
        $script:SpParams = @((Get-Command Start-Process).Parameters.Values)
        # The cmdlet plus its built-in aliases (matched case-insensitively; a
        # module-qualified Microsoft.PowerShell.Management\Start-Process too).
        $script:SpNames = @('Start-Process', 'saps', 'start')

        function Resolve-SpParameter([string]$Name) {
            $exact = @($script:SpParams | Where-Object { $_.Name -eq $Name -or $_.Aliases -contains $Name })
            if ($exact.Count -eq 1) { return $exact[0] }
            $prefixed = @($script:SpParams | Where-Object {
                $meta = $_
                $meta.Name.StartsWith($Name, [System.StringComparison]::OrdinalIgnoreCase) -or
                @($meta.Aliases | Where-Object { $_.StartsWith($Name, [System.StringComparison]::OrdinalIgnoreCase) }).Count -gt 0
            })
            if ($prefixed.Count -eq 1) { return $prefixed[0] }
            return $null
        }

        # Parse a file or a snippet; parse errors are returned so callers FAIL on
        # them (an unparseable file must never be silently skipped).
        function Get-ParsedSource([string]$Path, [string]$Code) {
            $tokens = $null; $errors = $null
            if ($Path) {
                $ast = [System.Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors)
            } else {
                $ast = [System.Management.Automation.Language.Parser]::ParseInput($Code, [ref]$tokens, [ref]$errors)
            }
            [pscustomobject]@{ Ast = $ast; Errors = @($errors) }
        }

        # The nearest enclosing function body, or the script root.
        function Get-EnclosingScope($Node) {
            $scope = $Node.Parent
            while ($null -ne $scope -and -not ($scope -is [System.Management.Automation.Language.FunctionDefinitionAst]) -and $null -ne $scope.Parent) {
                $scope = $scope.Parent
            }
            return $scope
        }

        function Test-HasHelperCall($Node) {
            $null -ne $Node.Find({
                param($n)
                $n -is [System.Management.Automation.Language.CommandAst] -and $n.GetCommandName() -eq 'ConvertTo-DaafNativeArg'
            }, $true)
        }

        # One record per Start-Process / saps / start call under $Root: where it is,
        # what FilePath / ArgumentList bound to (the way PowerShell binds them:
        # named, colon-attached, or positional -- FilePath is Position 0 and
        # ArgumentList Position 1), whether -PassThru is present, and the binding
        # violations. Splatting and any positional value beyond FilePath are
        # violations outright: the guard cannot see what they bind.
        function Get-StartProcessSite($Root, [string]$Label) {
            $calls = @($Root.FindAll({
                param($n)
                if (-not ($n -is [System.Management.Automation.Language.CommandAst])) { return $false }
                $cmd = $n.GetCommandName()
                if ($null -eq $cmd) { return $false }
                $script:SpNames -contains ($cmd -replace '^Microsoft\.PowerShell\.Management\\', '')
            }, $true))
            foreach ($call in $calls) {
                $where = "${Label}:$($call.Extent.StartLineNumber)"
                $violations = @()
                $named = @{}
                $positional = @()
                $els = $call.CommandElements
                for ($i = 1; $i -lt $els.Count; $i++) {
                    $e = $els[$i]
                    if ($e -is [System.Management.Automation.Language.VariableExpressionAst] -and $e.Splatted) {
                        $violations += "$where splatted @$($e.VariablePath.UserPath) (its bindings cannot be checked)"
                        continue
                    }
                    if ($e -is [System.Management.Automation.Language.CommandParameterAst]) {
                        $meta = Resolve-SpParameter $e.ParameterName
                        if ($null -eq $meta) { $violations += "$where unresolvable parameter -$($e.ParameterName)"; continue }
                        if ($null -ne $e.Argument) { $named[$meta.Name] = $e.Argument; continue }
                        if ($meta.SwitchParameter) { $named[$meta.Name] = $e; continue }
                        if ($i + 1 -ge $els.Count) { $violations += "$where -$($meta.Name) has no value"; continue }
                        $i++
                        $value = $els[$i]
                        if ($value -is [System.Management.Automation.Language.VariableExpressionAst] -and $value.Splatted) {
                            $violations += "$where splatted @$($value.VariablePath.UserPath) (its bindings cannot be checked)"
                        }
                        $named[$meta.Name] = $value
                        continue
                    }
                    $positional += $e
                }
                $filePathAst = $null
                if ($named.ContainsKey('FilePath')) {
                    $filePathAst = $named['FilePath']
                    if ($positional.Count -gt 0) {
                        $violations += "$where positional value $($positional[0].Extent.Text) binds to -ArgumentList"
                    }
                } else {
                    if ($positional.Count -ge 1) { $filePathAst = $positional[0] }
                    if ($positional.Count -gt 1) {
                        $violations += "$where positional value $($positional[1].Extent.Text) binds to -ArgumentList"
                    }
                }
                $filePathText = $null
                if ($null -ne $filePathAst) { $filePathText = $filePathAst.Extent.Text }
                $argumentList = $null
                if ($named.ContainsKey('ArgumentList')) { $argumentList = $named['ArgumentList'] }
                [pscustomobject]@{
                    Where        = $where
                    Label        = $Label
                    Call         = $call
                    FilePathText = $filePathText
                    ArgumentList = $argumentList
                    PassThru     = $named.ContainsKey('PassThru')
                    Violations   = $violations
                }
            }
        }

        # Rule: the -ArgumentList value is ONE pre-joined string built through
        # ConvertTo-DaafNativeArg. An array (`@(...)` or `a, b`) is rejected
        # outright; a variable is accepted only if EVERY assignment to it in the
        # enclosing function (or script) contains a ConvertTo-DaafNativeArg call.
        function Get-ArgumentListViolation($Site) {
            $argAst = $Site.ArgumentList
            if ($null -eq $argAst) { return }
            $where = $Site.Where
            if ($argAst -is [System.Management.Automation.Language.ArrayExpressionAst] -or
                $argAst -is [System.Management.Automation.Language.ArrayLiteralAst]) {
                "$where array-form -ArgumentList"
                return
            }
            if ($argAst -is [System.Management.Automation.Language.VariableExpressionAst]) {
                $varName = $argAst.VariablePath.UserPath
                $assigns = @((Get-EnclosingScope $Site.Call).FindAll({
                    param($n)
                    $n -is [System.Management.Automation.Language.AssignmentStatementAst] -and
                    $n.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
                    $n.Left.VariablePath.UserPath -eq $varName
                }, $true))
                if ($assigns.Count -eq 0) { "$where `$$varName is never assigned in scope"; return }
                foreach ($a in $assigns) {
                    if (-not (Test-HasHelperCall $a.Right)) {
                        "$where `$$varName assigned without ConvertTo-DaafNativeArg (line $($a.Extent.StartLineNumber))"
                    }
                }
                return
            }
            if (-not (Test-HasHelperCall $argAst)) {
                "$where -ArgumentList value not built with ConvertTo-DaafNativeArg"
            }
        }

        # Rule: a -PassThru result is assigned to a variable, and the FIRST use of
        # that variable after the launch is a `.Handle` property read (bare or in a
        # try block) -- before any WaitForExit / HasExited / ExitCode access lets the
        # child's exit go unobserved.
        function Get-HandleCacheViolation($Site) {
            if (-not $Site.PassThru) { return }
            $where = $Site.Where
            $pipe = $Site.Call.Parent
            $assign = $null
            if ($null -ne $pipe) { $assign = $pipe.Parent }
            if (-not ($pipe -is [System.Management.Automation.Language.PipelineAst] -and
                      $pipe.PipelineElements.Count -eq 1 -and
                      $assign -is [System.Management.Automation.Language.AssignmentStatementAst] -and
                      $assign.Left -is [System.Management.Automation.Language.VariableExpressionAst] -and
                      $assign.Left.VariablePath.UserPath -ne 'null')) {
                "$where Start-Process -PassThru result is not assigned to a variable, so its .Handle is never cached"
                return
            }
            $varName = $assign.Left.VariablePath.UserPath
            $after = $assign.Extent.EndOffset
            $refs = @((Get-EnclosingScope $assign).FindAll({
                param($n)
                $n -is [System.Management.Automation.Language.VariableExpressionAst] -and
                $n.VariablePath.UserPath -eq $varName -and $n.Extent.StartOffset -ge $after
            }, $true) | Sort-Object { $_.Extent.StartOffset })
            if ($refs.Count -eq 0) { "$where `$$varName is never used after Start-Process -PassThru"; return }
            $first = $refs[0]
            $member = $first.Parent
            $isHandle = ($member -is [System.Management.Automation.Language.MemberExpressionAst]) -and
                -not ($member -is [System.Management.Automation.Language.InvokeMemberExpressionAst]) -and
                [object]::ReferenceEquals($member.Expression, $first) -and
                ($member.Member -is [System.Management.Automation.Language.StringConstantExpressionAst]) -and
                $member.Member.Value -eq 'Handle'
            if (-not $isHandle) {
                "$where first use of `$$varName after Start-Process -PassThru is '$($member.Extent.Text)', not a .Handle cache"
            }
        }

        # All structural violations for one parsed source (parse errors included);
        # -SkipHandle leaves the .Handle rule to its own test.
        function Get-SourceViolation($Parsed, [string]$Label, [switch]$SkipHandle) {
            foreach ($err in $Parsed.Errors) { "${Label}:$($err.Extent.StartLineNumber) parse error: $($err.Message)" }
            foreach ($site in @(Get-StartProcessSite $Parsed.Ast $Label)) {
                $site.Violations
                Get-ArgumentListViolation $site
                if (-not $SkipHandle) { Get-HandleCacheViolation $site }
            }
        }

        # Strip parentheses and single-expression pipelines: ((($ec))) -> $ec.
        function Get-UnwrappedExpression($Node) {
            $x = $Node
            while ($true) {
                if ($x -is [System.Management.Automation.Language.ParenExpressionAst]) { $x = $x.Pipeline; continue }
                if ($x -is [System.Management.Automation.Language.PipelineAst] -and $x.PipelineElements.Count -eq 1 -and
                    $x.PipelineElements[0] -is [System.Management.Automation.Language.CommandExpressionAst]) {
                    $x = $x.PipelineElements[0].Expression
                    continue
                }
                return $x
            }
        }

        function Test-IsVariable($Node, [string]$Name) {
            if ($null -eq $Node) { return $false }
            $u = Get-UnwrappedExpression $Node
            ($u -is [System.Management.Automation.Language.VariableExpressionAst]) -and $u.VariablePath.UserPath -eq $Name
        }

        # Truthiness / coercion uses of an exit-code variable: `!$v`, `-not $v`,
        # `$v -and/-or/-xor ...` (either side), a bare `if ($v)` / loop condition,
        # and any cast (`[int]$v`, `[bool]$v`). Each reads $null (UNKNOWN) as 0 or
        # as "no error".
        function Get-TruthinessViolation($Root, [string]$VarName) {
            $kind = [System.Management.Automation.Language.TokenKind]
            # Every node: the predicate ignores its argument, so it declares none.
            foreach ($n in @($Root.FindAll({ $true }, $true))) {
                $line = $n.Extent.StartLineNumber
                if ($n -is [System.Management.Automation.Language.UnaryExpressionAst] -and
                    ($n.TokenKind -eq $kind::Not -or $n.TokenKind -eq $kind::Exclaim) -and (Test-IsVariable $n.Child $VarName)) {
                    "line ${line}: negation of `$$VarName ($($n.Extent.Text))"
                }
                elseif ($n -is [System.Management.Automation.Language.BinaryExpressionAst] -and
                    ($n.Operator -eq $kind::And -or $n.Operator -eq $kind::Or -or $n.Operator -eq $kind::Xor) -and
                    ((Test-IsVariable $n.Left $VarName) -or (Test-IsVariable $n.Right $VarName))) {
                    "line ${line}: logical operator on `$$VarName ($($n.Extent.Text))"
                }
                elseif ($n -is [System.Management.Automation.Language.ConvertExpressionAst] -and (Test-IsVariable $n.Child $VarName)) {
                    "line ${line}: cast of `$$VarName ($($n.Extent.Text))"
                }
                elseif ($n -is [System.Management.Automation.Language.IfStatementAst]) {
                    foreach ($clause in $n.Clauses) {
                        if (Test-IsVariable $clause.Item1 $VarName) { "line $($clause.Item1.Extent.StartLineNumber): bare condition on `$$VarName" }
                    }
                }
                elseif ($n -is [System.Management.Automation.Language.LoopStatementAst] -and (Test-IsVariable $n.Condition $VarName)) {
                    "line ${line}: bare loop condition on `$$VarName"
                }
            }
        }

        $script:HostSources = @($script:HostFiles | ForEach-Object {
            [pscustomobject]@{ Name = $_.Name; Parsed = (Get-ParsedSource -Path $_.FullName) }
        })
        $script:HostSites = @($script:HostSources | ForEach-Object { Get-StartProcessSite $_.Parsed.Ast $_.Name })
    }

    It "every Start-Process / saps / start call in scripts/host parses, binds analysably, and quotes -ArgumentList through the helper" {
        $violations = @($script:HostSources | ForEach-Object { Get-SourceViolation $_.Parsed $_.Name -SkipHandle })
        $violations | Should -BeNullOrEmpty
    }

    It "pins the Start-Process call-site inventory (5 -ArgumentList sites + 2 FilePath-only opens)" {
        # A new or removed launch site must be a deliberate, reviewed change: update
        # these pins together with the code. The two FilePath-only calls open a URL
        # / an HTML file with the default handler (no argv, ExitCode never read).
        $withArgs = @($script:HostSites | Where-Object { $null -ne $_.ArgumentList } |
            Group-Object Label | Sort-Object Name | ForEach-Object { "$($_.Name)=$($_.Count)" })
        ($withArgs -join ', ') | Should -BeExactly 'backup_daaf.ps1=1, daaf.ps1=2, test_migration.ps1=2'
        $fileOnly = @($script:HostSites | Where-Object { $null -eq $_.ArgumentList } |
            ForEach-Object { "$($_.Label) $($_.FilePathText)" } | Sort-Object)
        ($fileOnly -join ', ') | Should -BeExactly 'daaf_lib.ps1 $Url, view_quarto.ps1 $AbsHtml'
        $script:HostSites.Count | Should -Be 7
    }

    It "every Start-Process -PassThru in scripts/host caches .Handle before any other use of the result" {
        # On Windows (Windows PowerShell 5.1 and PowerShell 6.0-7.4.0, with
        # -NoNewWindow and/or -RedirectStandard*) a -PassThru Process object holds
        # no OS handle; if nothing opens one before the child exits, ExitCode reads
        # $null (PowerShell#5421, #20400; fixed in 7.4.1). Reading .Handle right
        # after the launch keeps the exit status readable.
        $passThru = @($script:HostSites | Where-Object { $_.PassThru })
        $passThru.Count | Should -Be 5
        $violations = @($passThru | ForEach-Object { Get-HandleCacheViolation $_ })
        $violations | Should -BeNullOrEmpty
    }

    It "daaf.ps1 never coerces `$ec with a truthiness idiom (!, -not, -and/-or, bare if, cast)" {
        # `-not $ec` / `!$ec` / `if ($ec)` read $null (unknown) as success; `$ec -and
        # ...` reads it as "no error"; `[int]$ec` makes it 0. All hid a failed or
        # unreadable child exit. AST-based, so the explanatory comments that quote
        # the retired idioms do not count.
        $daaf = @($script:HostSources | Where-Object { $_.Name -eq 'daaf.ps1' })[0].Parsed.Ast
        @(Get-TruthinessViolation $daaf 'ec') | Should -BeNullOrEmpty
        $kind = [System.Management.Automation.Language.TokenKind]
        $nullChecks = @($daaf.FindAll({
            param($n)
            $n -is [System.Management.Automation.Language.BinaryExpressionAst] -and $n.Operator -eq $kind::Ieq -and
            (Test-IsVariable $n.Left 'null') -and (Test-IsVariable $n.Right 'ec')
        }, $true))
        $nullChecks.Count | Should -BeGreaterOrEqual 2
    }

    Context "SELF-TEST: the guards reject the known-bad shapes (a guard that cannot fail is worthless)" {
        # Snippets use <NL> for a line break. Each BAD snippet must yield at least
        # one violation; each GOOD snippet none.
        It "Start-Process guard rejects: <Name>" -ForEach @(
            @{ Name = 'positional array ArgumentList';           Code = 'Start-Process docker @(''cp'', $x)' }
            @{ Name = 'positional string after named FilePath';  Code = 'Start-Process -FilePath docker ''cp a b''' }
            @{ Name = 'splatted invocation';                     Code = '$p = @{ FilePath = ''docker''; ArgumentList = @(''cp'', $x) }<NL>Start-Process @p' }
            @{ Name = 'saps alias with array';                   Code = 'saps -FilePath docker -ArgumentList @(''cp'', $x)' }
            @{ Name = 'start alias with -Args alias';            Code = 'start -FilePath docker -Args @(''cp'', $x)' }
            @{ Name = '-Arg prefix';                             Code = 'Start-Process -FilePath docker -Arg @(''cp'', $x)' }
            @{ Name = '-Argument prefix, bare comma list';       Code = 'Start-Process -FilePath docker -Argument ''cp'', $x' }
            @{ Name = 'upper-case names';                        Code = 'START-PROCESS -FILEPATH docker -ARGUMENTLIST @(''cp'', $x)' }
            @{ Name = 'module-qualified cmdlet';                 Code = 'Microsoft.PowerShell.Management\Start-Process -FilePath docker -ArgumentList @(''cp'', $x)' }
            @{ Name = 'colon-attached array';                    Code = 'Start-Process -FilePath docker -ArgumentList:@(''cp'', $x)' }
            @{ Name = 'helper named only in a trailing comment'; Code = '$a = ''cp '' + $x # ConvertTo-DaafNativeArg<NL>Start-Process -FilePath docker -ArgumentList $a' }
            @{ Name = 'helper named only in an inline comment';  Code = 'Start-Process -FilePath docker -ArgumentList (''cp '' + $x <# ConvertTo-DaafNativeArg #>)' }
            @{ Name = 'variable never assigned';                 Code = 'Start-Process -FilePath docker -ArgumentList $a' }
            @{ Name = 'unresolvable parameter';                  Code = 'Start-Process -FilePath docker -Bogus 1 -ArgumentList (ConvertTo-DaafNativeArg $x)' }
            @{ Name = 'unparseable source';                      Code = 'Start-Process -FilePath docker -ArgumentList (' }
            @{ Name = '.Handle only in a comment';               Code = '$p = Start-Process -FilePath docker -ArgumentList (ConvertTo-DaafNativeArg $x) -PassThru<NL># $null = $p.Handle<NL>$p.WaitForExit()' }
            @{ Name = '.Handle read after the wait';             Code = '$p = Start-Process -FilePath docker -ArgumentList (ConvertTo-DaafNativeArg $x) -PassThru<NL>$p.WaitForExit()<NL>$null = $p.Handle' }
            @{ Name = '-PassThru result discarded';              Code = 'Start-Process -FilePath docker -ArgumentList (ConvertTo-DaafNativeArg $x) -PassThru' }
            @{ Name = '-Pass prefix without a .Handle cache';    Code = '$p = Start-Process -FilePath docker -ArgumentList (ConvertTo-DaafNativeArg $x) -Pass<NL>$p.WaitForExit()' }
        ) {
            $parsed = Get-ParsedSource -Code ($Code -replace '<NL>', "`n")
            @(Get-SourceViolation $parsed 'snippet').Count | Should -BeGreaterThan 0
        }

        It "Start-Process guard accepts: <Name>" -ForEach @(
            @{ Name = 'canonical idiom';            Code = '$s = (@(''cp'', $x) | ForEach-Object { ConvertTo-DaafNativeArg $_ }) -join '' ''<NL>$p = Start-Process -FilePath docker -ArgumentList $s -NoNewWindow -PassThru<NL>try { $null = $p.Handle } catch { }<NL>$p.WaitForExit()' }
            @{ Name = 'FilePath-only default open'; Code = 'Start-Process $Url' }
            @{ Name = 'alias with inline helper';   Code = 'saps -FilePath docker -Args (ConvertTo-DaafNativeArg $x)' }
        ) {
            $parsed = Get-ParsedSource -Code ($Code -replace '<NL>', "`n")
            @(Get-SourceViolation $parsed 'snippet') | Should -BeNullOrEmpty
        }

        It "truthiness guard rejects: <Code>" -ForEach @(
            @{ Code = 'if (!$ec) { }' }
            @{ Code = 'if (-not $ec) { }' }
            @{ Code = 'if ($ec) { }' }
            @{ Code = 'if ($ec -and $ec -ne 0) { }' }
            @{ Code = 'if (-not $ec -or $ec -eq 0) { }' }
            @{ Code = 'if ($ok -or ($ec)) { }' }
            @{ Code = '$n = [int]$ec' }
            @{ Code = 'while ($ec) { break }' }
        ) {
            $parsed = Get-ParsedSource -Code $Code
            @(Get-TruthinessViolation $parsed.Ast 'ec').Count | Should -BeGreaterThan 0
        }

        It "truthiness guard accepts the explicit three-outcome form" {
            $parsed = Get-ParsedSource -Code 'if ($null -eq $ec) { } elseif ($ec -ne 0) { } else { "code $ec" }'
            @(Get-TruthinessViolation $parsed.Ast 'ec') | Should -BeNullOrEmpty
        }
    }
}

Describe "test_migration.ps1 launchers drop `$null script arguments" {
    # A $null $ScriptArgs binds to [string[]] as ONE $null element; unfiltered, the
    # helper turned it into an explicit "" argument for the child. The launchers
    # sit below test_migration.ps1's DAAF_TEST_MODE guard, so their definitions
    # (plus the inline helper) are extracted from the AST and defined here, with
    # Start-Process mocked to capture the argument string.
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $tokens = $null; $errors = $null
        $ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $RepoRoot 'scripts/host/test_migration.ps1'), [ref]$tokens, [ref]$errors)
        foreach ($fn in @('ConvertTo-DaafNativeArg', 'Invoke-HardenedScript', 'Invoke-HardenedScriptAuto')) {
            $def = @($ast.FindAll({
                param($n)
                $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $fn
            }, $true))
            $def.Count | Should -Be 1
            . ([scriptblock]::Create($def[0].Extent.Text))
        }
        $script:ChildPath = Join-Path $TestDrive 'harness copy.ps1'
        $null = New-Item -ItemType File -Force -Path $script:ChildPath
        $script:Expected = '-NoProfile -ExecutionPolicy Bypass -File ' + (ConvertTo-DaafNativeArg $script:ChildPath)
    }
    BeforeEach {
        $script:CapturedArgumentList = $null
        Mock Start-Process {
            $script:CapturedArgumentList = $ArgumentList
            [pscustomobject]@{ ExitCode = 0; Handle = [IntPtr]::Zero } |
                Add-Member -MemberType ScriptMethod -Name WaitForExit -Value { } -PassThru
        }
    }

    It "Invoke-HardenedScript: a `$null ScriptArgs adds no trailing empty argument" {
        $null = Invoke-HardenedScript -Path $script:ChildPath -ScriptArgs $null
        @($script:CapturedArgumentList).Count | Should -Be 1
        @($script:CapturedArgumentList)[0] | Should -BeExactly $script:Expected
    }

    # No element-level case here: these launchers are [CmdletBinding()] advanced
    # functions, whose binder already converts a $null ELEMENT of a [string[]]
    # argument to '' before the body runs (observed: @('-Auto', $null, 'x y')
    # arrives as -Auto "" "x y"), so only a wholly-$null ScriptArgs is droppable.
    It "Invoke-HardenedScript: real arguments follow the quoted -File path" {
        $null = Invoke-HardenedScript -Path $script:ChildPath -ScriptArgs @('-Auto', 'x y')
        @($script:CapturedArgumentList)[0] | Should -BeExactly ($script:Expected + ' -Auto "x y"')
    }

    It "Invoke-HardenedScriptAuto: a `$null ScriptArgs adds no trailing empty argument" {
        $capture = Join-Path $TestDrive 'auto capture.txt'
        $null = Invoke-HardenedScriptAuto -Path $script:ChildPath -CaptureFile $capture -ScriptArgs $null 6>&1
        @($script:CapturedArgumentList).Count | Should -Be 1
        @($script:CapturedArgumentList)[0] | Should -BeExactly $script:Expected
    }
}
