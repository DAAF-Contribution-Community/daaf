# ============================================================================
# Pester tests: no host script keeps a docker stderr capture that Windows
# PowerShell 5.1 empties (AST-based structural guard)
# ============================================================================
# THE GOTCHA (shell-scripting skill > gotchas.md, "Windows PowerShell 5.1 Drops
# Native stderr Under `SilentlyContinue`, Even With `2>&1`")
# ---------------------------------------------------------------------------
# On Windows PowerShell 5.1, $ErrorActionPreference still applies to each native
# stderr line that a redirection operator captures, so under 'SilentlyContinue'
# the line never reaches a `2>&1` capture (field-observed 2026-10-05 on
# 5.1.26100: SILENT_LINES=1, CONTINUE_LINES=2). From PowerShell 7.2 the
# preference no longer applies to redirected native stderr (sourced:
# about_Preference_Variables), so pwsh 7 -- this container and every Pester run
# in CI -- keeps the line, and no behavioral test on pwsh 7 can see the drop.
# A `2>>` FILE redirect is emptied the same way: observed by the
# validate-ps-windows CI job's "Probe native stderr capture" step (CI - Scripts
# run 38316686493, 5.1.26100.33438, 2026-10-12: `file_lines=0` under
# 'SilentlyContinue'), which now asserts it; a plain `2>` is inference. Under
# 'Continue' the same run's file held PowerShell's formatted 7-line error record
# (`cmd.exe : PROBE_ERR`, CategoryInfo, ...), not the raw line, which is why
# stderr read back for display is kept in memory rather than in a file.
#
# WHAT THIS GUARD CHECKS
# ----------------------
# Over every scripts/host/*.ps1 (parsed, never read as text, so a comment can
# neither trip nor satisfy it), it flags a call site that meets ALL of:
#   1. it runs docker: a `docker` / `docker.exe` CommandAst, or a call to an
#      in-file WRAPPER (a function whose body runs docker, or another wrapper,
#      with stderr NOT redirected, so the stderr flows out to the caller);
#   2. its effective $ErrorActionPreference is NOT an explicit literal
#      'Continue': the last `$ErrorActionPreference = <literal>` assignment
#      before it, in source order, in the same function body (or the script
#      body). 'SilentlyContinue' and 'Ignore' drop the line on 5.1; 'Stop'
#      makes it a terminating error there (inference, from the documented 5.1
#      behaviour). "Inherited" -- no assignment yet in this scope, or a
#      non-literal one (`= $savedEAP`, the bracket's restore) -- is whatever the
#      caller had, which a parse cannot know, so it is flagged too: a function
#      with no bracket of its own, called from a SilentlyContinue caller, drops
#      the line. Inside a wrapper, a non-'Continue' literal set by the wrapper
#      itself wins over the caller's;
#   3. its stderr is kept somewhere: merged into output (`2>&1`, `*>&1`) or
#      redirected to a file (`2> f`, `2>> f`, `*> f`). `2>$null` discards it;
#   4. what it kept is used: for a merge, the output is assigned, returned,
#      emitted, piped onward, or read in a condition -- NOT `$null = ...`,
#      `[void](...)`, `| Out-Null` or `> $null`. A file redirect always counts
#      (the file is where the lines are kept).
#
# FIX CHOOSER (printed with every violation). The two fixes are NOT
# interchangeable (scoping audit 05, the "inverted polarity" finding):
#   - The capture is only tested for emptiness, or parsed for stdout (an ID, a
#     marker): use `2>$null` and keep 'SilentlyContinue'. 'Continue' would be
#     WRONG here: it lets a stderr-only warning make the capture non-empty, which
#     is exactly the pwsh 7 misread the 5.1 drop was hiding.
#   - Its text is shown to the user: use 'Continue' in the bracket. A file
#     redirect read back for display: keep the lines in memory under 'Continue'
#     (the install / rebuild / update readiness loops).
#   - It reads only stdout markers and never shows stderr: an allowlist entry
#     below, with the reason.
#
# KNOWN LIMITS (inference): source order is not control flow (a bracket opened
# in one branch and restored in another is read in source order; the audit's
# lexical scan found every bracket paired); a redirection on an enclosing
# `& { docker ... }` is not attributed to the docker call; `& $exe` with a
# computed name is not recognised as docker; `docker ... 2>&1 | Tee-Object
# -Variable t | Out-Null` reads as discarded (the trailing Out-Null), though $t
# keeps the lines; `Set-Variable -Name ErrorActionPreference -Value ...` is not
# seen as an assignment, so it is missed when it follows a literal 'Continue' in
# the same scope (with no literal before it, the site reads "inherited" and is
# flagged anyway). A wrapper that sets its own 'Continue' does not clear a
# caller's SilentlyContinue: which scope's preference governs stderr redirected
# at the caller is not verified on 5.1, so the guard keeps the stricter reading.
#
# Modelled on native_arg_quoting.Tests.ps1 (Start-Process guards): AST walk
# over the host scripts, plus SELF-TESTS on snippets and on in-memory reverts of
# the dispatch #63 fixes, because a guard that cannot fail is worthless.
# ============================================================================

Describe "Host-script native stderr capture guard (Windows PowerShell 5.1 drops stderr under SilentlyContinue)" {
    BeforeAll {
        . "$PSScriptRoot/TestHelper.ps1"
        $script:HostDir = Join-Path $RepoRoot 'scripts/host'
        $script:DockerNames = @('docker', 'docker.exe')

        # Merged or file-redirected stderr without an explicit 'Continue' (all
        # four under SilentlyContinue) that is kept on purpose. Each entry is
        # <file, assigned variable> plus the reason; the guard fails if an
        # entry no longer matches exactly one site (stale).
        # Why an allowlist and not a flip to 'Continue' (audit 05 section 6 item 7):
        # the flip would mean editing four host scripts for no user-visible gain
        # (these reads never show stderr), and it is out of this guard's scope.
        # Each parser below matches anchored stdout-only shapes, so a merged
        # stderr record can never be mistaken for a marker -- and if one were
        # dropped on 5.1, nothing the user sees would change.
        $script:Allowlist = @(
            @{ File = 'backup_daaf.ps1'; Target = 'StageDoneLog'
               Reason = 'staging log read only for STAGED_* / STAGE_* stdout markers (Get-DaafCountMarker anchors ^NAME=digits$; Write-DaafNameReport takes only fixed-prefix TAB lines); the program echoes them to stdout' }
            @{ File = 'backup_daaf.ps1'; Target = 'HostCountOutput'
               Reason = 'backup-folder count read only for the BACKUP_* stdout markers via Get-DaafCountMarker; the decision is the exit code plus BACKUP_SENTINEL=1' }
            @{ File = 'backup_daaf.ps1'; Target = 'ClaudeStageDoneLog'
               Reason = 'Claude staging log read only for STAGED_FILES / STAGE_* stdout markers (same parsers as StageDoneLog)' }
            @{ File = 'migrate_daaf.ps1'; Target = 'SearchResultRaw'
               Reason = 'commit search parses only ^(EXACT|BEST): stdout lines; its stderr (the "Searching commit N/M" progress printf, plus any docker exec or git error text) is never shown' }
        )

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

        # The nearest enclosing function definition, or the script root.
        function Get-EnclosingScope($Node) {
            $scope = $Node.Parent
            while ($null -ne $scope -and -not ($scope -is [System.Management.Automation.Language.FunctionDefinitionAst]) -and $null -ne $scope.Parent) {
                $scope = $scope.Parent
            }
            return $scope
        }

        function Test-IsNullVariable($Node) {
            ($Node -is [System.Management.Automation.Language.VariableExpressionAst]) -and $Node.VariablePath.UserPath -eq 'null'
        }

        # `$ErrorActionPreference = ...`, also scope-qualified ($script:, $global:).
        function Test-IsPreferenceAssignment($Node) {
            ($Node -is [System.Management.Automation.Language.AssignmentStatementAst]) -and
            ($Node.Left -is [System.Management.Automation.Language.VariableExpressionAst]) -and
            ($Node.Left.VariablePath.UserPath -replace '^(?:global|script|local|private):', '') -eq 'ErrorActionPreference'
        }

        # The literal a preference assignment sets ('SilentlyContinue', "Continue",
        # [ActionPreference]::Stop), or 'inherited' for anything computed (the
        # bracket's `= $savedEAP` restore).
        function Get-PreferenceLiteral($Assignment) {
            $x = $Assignment.Right
            if ($x -is [System.Management.Automation.Language.CommandExpressionAst]) { $x = $x.Expression }
            if ($x -is [System.Management.Automation.Language.StringConstantExpressionAst]) { return $x.Value }
            if ($x -is [System.Management.Automation.Language.ExpandableStringExpressionAst] -and $x.NestedExpressions.Count -eq 0) { return $x.Value }
            if ($x -is [System.Management.Automation.Language.MemberExpressionAst] -and $x.Static -and
                $x.Member -is [System.Management.Automation.Language.StringConstantExpressionAst]) { return $x.Member.Value }
            return 'inherited'
        }

        # Effective preference at a node: the last preference assignment that ends
        # before it, in source order, in the same function body (or script body).
        # The per-scope assignment lists are cached (AST nodes compare by
        # reference), which keeps the walk over the host call sites (265 on
        # 2026-10-12) to a few seconds.
        $script:PreferenceAssignmentCache = New-Object 'System.Collections.Generic.Dictionary[object,object]'
        function Get-EffectivePreference($Node) {
            $scope = Get-EnclosingScope $Node
            if (-not $script:PreferenceAssignmentCache.ContainsKey($scope)) {
                $script:PreferenceAssignmentCache[$scope] = @($scope.FindAll({ param($n) Test-IsPreferenceAssignment $n }, $true) |
                    Where-Object { [object]::ReferenceEquals((Get-EnclosingScope $_), $scope) } |
                    Sort-Object { $_.Extent.StartOffset })
            }
            $offset = $Node.Extent.StartOffset
            $before = @($script:PreferenceAssignmentCache[$scope] | Where-Object { $_.Extent.EndOffset -le $offset })
            if ($before.Count -eq 0) { return 'inherited' }
            return (Get-PreferenceLiteral $before[-1])
        }

        # The only preference under which a kept stderr capture is safe on 5.1
        # (case-insensitive, as PowerShell compares it).
        function Test-IsExplicitContinue([string]$Value) {
            $Value -eq 'Continue'
        }

        # 'merged' (2>&1, *>&1), 'file' (2> f, 2>> f, *> f), 'discarded' (2>$null)
        # or 'none' (stderr not redirected at this call).
        function Get-StderrDisposition($Command) {
            $disposition = 'none'
            foreach ($r in $Command.Redirections) {
                $from = "$($r.FromStream)"
                if ($from -ne 'Error' -and $from -ne 'All') { continue }
                if ($r -is [System.Management.Automation.Language.MergingRedirectionAst]) {
                    if ("$($r.ToStream)" -eq 'Output') { $disposition = 'merged' }
                } elseif ($r -is [System.Management.Automation.Language.FileRedirectionAst]) {
                    if (Test-IsNullVariable $r.Location) { $disposition = 'discarded' } else { $disposition = 'file' }
                }
            }
            return $disposition
        }

        # Walk up from the call to the first node that decides what happens to its
        # output: discarded ($null =, [void], | Out-Null, > $null) or retained
        # (assigned -- with the variable name as Target --, returned, function or
        # script output). Anything in between (@(), (), $(), a script block fed
        # to ForEach-Object, an if condition) passes the output on.
        function Get-OutputDisposition($Command) {
            foreach ($r in $Command.Redirections) {
                $from = "$($r.FromStream)"
                if ($r -is [System.Management.Automation.Language.FileRedirectionAst] -and
                    ($from -eq 'Output' -or $from -eq 'All') -and (Test-IsNullVariable $r.Location)) {
                    return [pscustomobject]@{ Kept = $false; How = '> $null'; Target = '' }
                }
            }
            $child = $Command
            $node = $Command.Parent
            while ($null -ne $node) {
                if ($node -is [System.Management.Automation.Language.PipelineAst]) {
                    $after = $false
                    foreach ($element in $node.PipelineElements) {
                        if ($after -and $element -is [System.Management.Automation.Language.CommandAst] -and $element.GetCommandName() -eq 'Out-Null') {
                            return [pscustomobject]@{ Kept = $false; How = '| Out-Null'; Target = '' }
                        }
                        if ([object]::ReferenceEquals($element, $child)) { $after = $true }
                    }
                } elseif ($node -is [System.Management.Automation.Language.AssignmentStatementAst]) {
                    if (Test-IsNullVariable $node.Left) { return [pscustomobject]@{ Kept = $false; How = '$null ='; Target = '' } }
                    $target = $node.Left.Extent.Text
                    if ($node.Left -is [System.Management.Automation.Language.VariableExpressionAst]) { $target = $node.Left.VariablePath.UserPath }
                    return [pscustomobject]@{ Kept = $true; How = 'assigned'; Target = $target }
                } elseif ($node -is [System.Management.Automation.Language.ConvertExpressionAst] -and $node.Type.TypeName.Name -eq 'void') {
                    return [pscustomobject]@{ Kept = $false; How = '[void]'; Target = '' }
                } elseif ($node -is [System.Management.Automation.Language.ReturnStatementAst]) {
                    return [pscustomobject]@{ Kept = $true; How = 'returned'; Target = '' }
                } elseif ($node -is [System.Management.Automation.Language.FunctionDefinitionAst]) {
                    return [pscustomobject]@{ Kept = $true; How = 'function output'; Target = '' }
                }
                $child = $node
                $node = $node.Parent
            }
            return [pscustomobject]@{ Kept = $true; How = 'script output'; Target = '' }
        }

        function Test-IsDockerOrWrapperCall($Node, [hashtable]$Wrappers) {
            if (-not ($Node -is [System.Management.Automation.Language.CommandAst])) { return $false }
            $name = $Node.GetCommandName()
            if ($null -eq $name) { return $false }
            (@($script:DockerNames | Where-Object { $_ -eq $name }).Count -gt 0) -or $Wrappers.ContainsKey($name)
        }

        # In-file wrappers: functions whose body runs docker (or another wrapper)
        # with stderr NOT redirected, so the stderr reaches the caller's
        # redirection. Value = a non-'Continue' literal the wrapper sets around
        # that call itself, or 'inherited' (the caller's preference applies; a
        # wrapper's own 'Continue' is not trusted to clear the caller's, see
        # KNOWN LIMITS). Iterated to a fixpoint so a wrapper of a wrapper is found.
        function Get-DockerWrapper($Ast) {
            $wrappers = @{}
            $functions = @($Ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true))
            $changed = $true
            while ($changed) {
                $changed = $false
                foreach ($fn in $functions) {
                    if ($wrappers.ContainsKey($fn.Name)) { continue }
                    $inner = @($fn.Body.FindAll({ param($n) Test-IsDockerOrWrapperCall $n $wrappers }, $true) |
                        Where-Object { (Get-StderrDisposition $_) -eq 'none' })
                    if ($inner.Count -eq 0) { continue }
                    $preference = 'inherited'
                    foreach ($call in $inner) {
                        $p = Get-EffectivePreference $call
                        if ($wrappers.ContainsKey("$($call.GetCommandName())") -and $p -eq 'inherited') { $p = $wrappers["$($call.GetCommandName())"] }
                        if ($p -ne 'inherited' -and -not (Test-IsExplicitContinue $p)) { $preference = $p }
                    }
                    $wrappers[$fn.Name] = $preference
                    $changed = $true
                }
            }
            return $wrappers
        }

        # One record per docker / wrapper call site, with everything the rule needs.
        function Get-NativeStderrSite($Parsed, [string]$Label) {
            $wrappers = Get-DockerWrapper $Parsed.Ast
            foreach ($call in @($Parsed.Ast.FindAll({ param($n) Test-IsDockerOrWrapperCall $n $wrappers }, $true))) {
                $name = $call.GetCommandName()
                $preference = Get-EffectivePreference $call
                if ($wrappers.ContainsKey($name) -and $wrappers[$name] -ne 'inherited') { $preference = "$($wrappers[$name]) (inside $name)" }
                $stderr = Get-StderrDisposition $call
                $output = Get-OutputDisposition $call
                $explicitContinue = (Test-IsExplicitContinue ($preference -replace ' \(inside .*\)$', ''))
                $violation = (-not $explicitContinue) -and (($stderr -eq 'file') -or ($stderr -eq 'merged' -and $output.Kept))
                [pscustomobject]@{
                    File       = $Label
                    Line       = $call.Extent.StartLineNumber
                    Command    = (($call.Extent.Text -split "`r?`n")[0]).Trim()
                    Wrapper    = $wrappers.ContainsKey($name)
                    Preference = $preference
                    Stderr     = $stderr
                    Output     = $output.How
                    Target     = $output.Target
                    Violation  = $violation
                }
            }
        }

        function Test-IsAllowlisted($Site) {
            @($script:Allowlist | Where-Object { $_.File -eq $Site.File -and $_.Target -eq $Site.Target }).Count -gt 0
        }

        # The failure text: where, what, why, and which fix (see FIX CHOOSER above).
        function Format-NativeStderrViolation($Site) {
            $kept = 'merged into the output (2>&1 or *>&1) and the output is kept'
            if ($Site.Stderr -eq 'file') { $kept = 'redirected to a file' }
            $what = $Site.Output
            if ($Site.Target) { $what = '$' + $Site.Target }
            "$($Site.File):$($Site.Line) [$what] '$($Site.Command)': stderr $kept under '$($Site.Preference)', not an explicit 'Continue' in this scope; " +
            "Windows PowerShell 5.1 drops those lines under SilentlyContinue or Ignore (including one inherited from a caller), and under Stop a stderr line becomes a terminating error (inference). FIX: emptiness test or stdout-only parse -> 2>`$null (keep SilentlyContinue); " +
            "text shown to the user -> 'Continue' in the bracket (a file read back for display: keep the lines in memory under 'Continue'); " +
            "stdout-marker-only read -> allowlist entry with a reason (shell-scripting gotchas.md)."
        }

        # Parse errors plus every non-allowlisted violation in one parsed source.
        function Get-SourceViolation($Parsed, [string]$Label, [switch]$IgnoreAllowlist) {
            foreach ($err in $Parsed.Errors) { "${Label}:$($err.Extent.StartLineNumber) parse error: $($err.Message)" }
            foreach ($site in @(Get-NativeStderrSite $Parsed $Label)) {
                if (-not $site.Violation) { continue }
                if (-not $IgnoreAllowlist -and (Test-IsAllowlisted $site)) { continue }
                Format-NativeStderrViolation $site
            }
        }

        $script:HostSources = @(Get-ChildItem -LiteralPath $script:HostDir -Filter '*.ps1' -File | Sort-Object Name | ForEach-Object {
            [pscustomobject]@{ Name = $_.Name; Parsed = (Get-ParsedSource -Path $_.FullName) }
        })
        $script:HostSites = @($script:HostSources | ForEach-Object { Get-NativeStderrSite $_.Parsed $_.Name })
    }

    It "finds the host scripts and every one of them parses" {
        $script:HostSources.Count | Should -BeGreaterOrEqual 14
        $parseErrors = @($script:HostSources | ForEach-Object {
            $name = $_.Name
            $_.Parsed.Errors | ForEach-Object { "${name}:$($_.Extent.StartLineNumber) $($_.Message)" }
        })
        $parseErrors | Should -BeNullOrEmpty
    }

    It "no host script keeps a merged or file-redirected docker stderr capture without an explicit 'Continue' (outside the allowlist)" {
        $violations = @($script:HostSites | Where-Object { $_.Violation -and -not (Test-IsAllowlisted $_) } |
            ForEach-Object { Format-NativeStderrViolation $_ })
        $violations | Should -BeNullOrEmpty
    }

    It "every allowlist entry still matches exactly one flagged site (no stale entries)" {
        foreach ($entry in $script:Allowlist) {
            $hits = @($script:HostSites | Where-Object { $_.Violation -and $_.File -eq $entry.File -and $_.Target -eq $entry.Target })
            "$($entry.File) `$$($entry.Target) hits=$($hits.Count)" | Should -BeExactly "$($entry.File) `$$($entry.Target) hits=1"
            $entry.Reason | Should -Not -BeNullOrEmpty
        }
    }

    It "is not vacuous: it sees the SilentlyContinue brackets and the 'Continue' captures in the host scripts" {
        # If preference tracking broke (every site read as "inherited"), the guard
        # above would pass on anything. Floors measured 2026-10-12 (dispatch #64):
        # 167 docker/wrapper sites under SilentlyContinue, 22 'Continue' merged
        # captures that are kept.
        $silent = @($script:HostSites | Where-Object { $_.Preference -eq 'SilentlyContinue' })
        $silent.Count | Should -BeGreaterOrEqual 150
        $continueKept = @($script:HostSites | Where-Object { $_.Preference -eq 'Continue' -and $_.Stderr -eq 'merged' -and $_.Output -eq 'assigned' })
        $continueKept.Count | Should -BeGreaterOrEqual 20
        @($script:HostSites | Where-Object { $_.Stderr -eq 'discarded' }).Count | Should -BeGreaterOrEqual 40
    }

    It "finds the in-file docker wrappers it is meant to follow (<File>: <Function>)" -ForEach @(
        @{ File = 'update_daaf.ps1';  Function = 'Invoke-ComposeExec' }
        @{ File = 'update_daaf.ps1';  Function = 'Invoke-ComposeGitVerbose' }
        @{ File = 'migrate_daaf.ps1'; Function = 'Invoke-ContainerExec' }
        @{ File = 'migrate_daaf.ps1'; Function = 'Invoke-ContainerGitVerbose' }
    ) {
        $source = @($script:HostSources | Where-Object { $_.Name -eq $File })[0]
        (Get-DockerWrapper $source.Parsed.Ast).ContainsKey($Function) | Should -BeTrue
    }

    Context "SELF-TEST: the guard rejects the known-bad shapes (a guard that cannot fail is worthless)" {
        # Snippets use <NL> for a line break. Each must yield at least one violation.
        It "rejects: <Name>" -ForEach @(
            @{ Name = 'merged capture assigned';                   Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$x = docker logs $c 2>&1' }
            @{ Name = 'one-line bracket, @() and ForEach-Object';  Code = '$s = $ErrorActionPreference; $ErrorActionPreference = "SilentlyContinue"<NL>$x = @(docker compose exec -T d true 2>&1 | ForEach-Object { "$_" })<NL>$ErrorActionPreference = $s' }
            @{ Name = 'G1 shape: (... 2>&1 | Out-String)';         Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$x = (docker logs $c 2>&1 | Out-String)' }
            @{ Name = 'G2 shape: 2>> file';                        Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>docker compose exec -T d true 2>> $readyLog' }
            @{ Name = '2> file with the output discarded';         Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$null = docker info 2> $log' }
            @{ Name = 'G3 shape: ps -q emptiness test';            Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$cid = docker compose ps -q d 2>&1<NL>if ([string]::IsNullOrWhiteSpace($cid)) { }' }
            @{ Name = 'returned from a function';                  Code = 'function F {<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>return (docker info 2>&1)<NL>}' }
            @{ Name = 'implicit function output';                  Code = 'function F {<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>docker info 2>&1<NL>}' }
            @{ Name = 'piped onward to Write-Host';                Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>docker info 2>&1 | Select-Object -Last 5 | Write-Host' }
            @{ Name = '*>&1';                                      Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$x = docker info *>&1' }
            @{ Name = 'Ignore preference';                         Code = '$ErrorActionPreference = ''Ignore''<NL>$x = docker info 2>&1' }
            @{ Name = 'enum literal';                              Code = '$ErrorActionPreference = [System.Management.Automation.ActionPreference]::SilentlyContinue<NL>$x = docker info 2>&1' }
            @{ Name = 'lower-case literal';                        Code = '$ErrorActionPreference = ''silentlycontinue''<NL>$x = docker info 2>&1' }
            @{ Name = 'scope-qualified preference';                Code = '$script:ErrorActionPreference = ''SilentlyContinue''<NL>$x = docker info 2>&1' }
            @{ Name = 'try/finally bracket';                       Code = '$s = $ErrorActionPreference<NL>try {<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>$x = docker info 2>&1<NL>} finally { $ErrorActionPreference = $s }' }
            @{ Name = 'in-file wrapper';                           Code = 'function Invoke-D { docker @args }<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>$x = Invoke-D info 2>&1' }
            @{ Name = 'wrapper of a wrapper';                      Code = 'function A { docker @args }<NL>function B { A @args }<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>$x = B info 2>&1' }
            @{ Name = 'wrapper that sets SilentlyContinue itself'; Code = 'function W {<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>docker @args<NL>}<NL>$ErrorActionPreference = ''Continue''<NL>$x = W info 2>&1' }
            @{ Name = 'docker.exe';                                Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$x = docker.exe info 2>&1' }
            @{ Name = 'inside a ForEach-Object script block';      Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$x = @(1, 2 | ForEach-Object { docker logs $_ 2>&1 })' }
            @{ Name = 'read in a condition';                       Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>if ((docker info 2>&1) -match ''x'') { }' }
            @{ Name = 'function with no bracket of its own, called from a SilentlyContinue caller'
               Code = 'function Get-DockerLog { param($c) docker logs $c 2>&1 }<NL>$s = $ErrorActionPreference; $ErrorActionPreference = ''SilentlyContinue''<NL>$t = Get-DockerLog x<NL>$ErrorActionPreference = $s' }
            @{ Name = 'nested function under an outer SilentlyContinue'
               Code = 'function Outer {<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>function Inner {<NL>$x = docker info 2>&1<NL>$x<NL>}<NL>Inner<NL>}' }
            @{ Name = 'kept merge after the bracket is restored (inherited)'; Code = '$s = $ErrorActionPreference; $ErrorActionPreference = ''SilentlyContinue''<NL>$null = docker info 2>&1<NL>$ErrorActionPreference = $s<NL>$x = docker logs $c 2>&1' }
            @{ Name = 'explicit Stop';                             Code = '$ErrorActionPreference = ''Stop''<NL>$x = docker info 2>&1' }
            @{ Name = 'unparseable source';                        Code = '$x = (docker info 2>&1' }
        ) {
            $parsed = Get-ParsedSource -Code ($Code -replace '<NL>', "`n")
            @(Get-SourceViolation $parsed 'snippet').Count | Should -BeGreaterThan 0
        }

        It "accepts: <Name>" -ForEach @(
            @{ Name = 'Continue bracket around a kept merge';      Code = '$s = $ErrorActionPreference; $ErrorActionPreference = ''Continue''<NL>$x = docker logs $c 2>&1<NL>$ErrorActionPreference = $s' }
            @{ Name = 'SilentlyContinue with 2>$null';             Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$cid = docker compose ps -q d 2>$null' }
            @{ Name = '$null = discard';                           Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$null = docker rm -f $c 2>&1' }
            @{ Name = '| Out-Null discard';                        Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>docker network rm n 2>&1 | Out-Null' }
            @{ Name = '[void] discard';                            Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>[void](docker info 2>&1)' }
            @{ Name = '> $null 2>&1';                              Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>docker info > $null 2>&1' }
            @{ Name = 'stderr not redirected (console)';           Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>$x = docker info' }
            @{ Name = 'Continue bracket after a SilentlyContinue one'; Code = '$s = $ErrorActionPreference; $ErrorActionPreference = ''SilentlyContinue''<NL>$null = docker info 2>&1<NL>$ErrorActionPreference = $s<NL>$s = $ErrorActionPreference; $ErrorActionPreference = ''Continue''<NL>$x = docker logs $c 2>&1<NL>$ErrorActionPreference = $s' }
            @{ Name = 'function sets its own Continue';            Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>function F {<NL>$ErrorActionPreference = ''Continue''<NL>$x = docker info 2>&1<NL>$x<NL>}' }
            @{ Name = 'wrapper that discards its own stderr';      Code = 'function Invoke-D { docker @args 2>$null }<NL>$ErrorActionPreference = ''SilentlyContinue''<NL>$x = Invoke-D info 2>&1' }
            @{ Name = 'mention in a comment';                      Code = '$ErrorActionPreference = ''SilentlyContinue''<NL># $x = docker info 2>&1' }
            @{ Name = 'mention in a string';                       Code = '$ErrorActionPreference = ''SilentlyContinue''<NL>Write-Host "run: docker info 2>&1"' }
        ) {
            $parsed = Get-ParsedSource -Code ($Code -replace '<NL>', "`n")
            @(Get-SourceViolation $parsed 'snippet') | Should -BeNullOrEmpty
        }

        It "a violation message names the site and carries the fix chooser" {
            $parsed = Get-ParsedSource -Code ('$ErrorActionPreference = ''SilentlyContinue''' + "`n" + '$cid = docker compose ps -q d 2>&1')
            $message = @(Get-SourceViolation $parsed 'snippet.ps1')
            $message.Count | Should -Be 1
            $message[0] | Should -Match ([regex]::Escape('snippet.ps1:2 [$cid]'))
            $message[0] | Should -Match ([regex]::Escape('emptiness test or stdout-only parse -> 2>$null'))
            $message[0] | Should -Match ([regex]::Escape("text shown to the user -> 'Continue'"))
        }
    }

    Context "SELF-TEST: reverting a dispatch #63 fix in memory is flagged" {
        # Each case takes the CURRENT host script, undoes one fix with a targeted
        # replacement (the replacement must apply -- if the code is reshaped, update
        # the pattern here with it), and requires a violation at that site.
        It "flags <Name>" -ForEach @(
            @{ Name = 'G1: backup_daaf.ps1 $StageLog bracket back to SilentlyContinue'
               File = 'backup_daaf.ps1'; Target = 'StageLog'; Stderr = 'merged'
               Pattern = '(\$ErrorActionPreference = )"Continue"(\r?\n[ \t]*\$StageLog = \(docker logs )'
               Replacement = '$1"SilentlyContinue"$2' }
            @{ Name = 'G2: install.ps1 readiness $readyOut bracket back to SilentlyContinue'
               File = 'install.ps1'; Target = 'readyOut'; Stderr = 'merged'
               Pattern = '(\$ErrorActionPreference = )"Continue"(\r?\n[ \t]*\$readyOut = @\(docker compose )'
               Replacement = '$1"SilentlyContinue"$2' }
            @{ Name = 'G2: rebuild_daaf.ps1 readiness back to the SilentlyContinue + 2>> $readyLog form'
               File = 'rebuild_daaf.ps1'; Target = ''; Stderr = 'file'
               Pattern = '(\$ErrorActionPreference = )"Continue"(\r?\n[ \t]*)\$readyOut = @\((docker compose exec -T daaf-docker true) 2>&1\)'
               Replacement = '$1"SilentlyContinue"$2$3 2>> $readyLog' }
            @{ Name = 'G3: run_daaf.ps1 $CidOutput back to 2>&1'
               File = 'run_daaf.ps1'; Target = 'CidOutput'; Stderr = 'merged'
               Pattern = '(\$CidOutput = docker compose ps -q daaf-docker )2>\$null'
               Replacement = '${1}2>&1' }
        ) {
            $source = Get-Content -Raw -LiteralPath (Join-Path $script:HostDir $File)
            $reverted = [regex]::Replace($source, $Pattern, $Replacement)
            ([regex]::Matches($source, $Pattern)).Count | Should -Be 1 -Because "the revert pattern must match exactly one site in $File (update it if the code was reshaped)"
            $before = @(Get-NativeStderrSite (Get-ParsedSource -Code $source) $File | Where-Object { $_.Violation -and -not (Test-IsAllowlisted $_) })
            $before | Should -BeNullOrEmpty
            $after = @(Get-NativeStderrSite (Get-ParsedSource -Code $reverted) $File | Where-Object { $_.Violation -and -not (Test-IsAllowlisted $_) })
            $after.Count | Should -Be 1
            $after[0].Target | Should -BeExactly $Target
            $after[0].Stderr | Should -BeExactly $Stderr
        }
    }
}
