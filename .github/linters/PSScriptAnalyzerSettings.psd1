# PSScriptAnalyzer Settings for DAAF
#
# Configuration for PSScriptAnalyzer linting of all .ps1 scripts.
# Used by CI (ci-scripts.yml) and local development.
#
# Run locally:
#   Install-Module -Name PSScriptAnalyzer -Force -Scope CurrentUser
#   Invoke-ScriptAnalyzer -Path . -Recurse -Settings ./PSScriptAnalyzerSettings.psd1
#
# Severity levels included: Error, Warning
# Information-level rules are excluded — too noisy for CI gating.

@{
    Severity = @('Error', 'Warning')

    ExcludeRules = @(
        # All DAAF scripts are CLI tools that intentionally use Write-Host
        # for user-facing output (colored progress messages, status indicators).
        # Write-Host is the correct choice for these scripts — they are not
        # library functions where output stream purity matters.
        'PSAvoidUsingWriteHost'
    )
}
