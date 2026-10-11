#!/usr/bin/env bats
# ============================================================================
# Static contract tests for checked-in Claude Code permission rules.
#
# This suite validates the checked-in configuration contract in
# .claude/settings.json. It does NOT dynamically prove Claude Code permission-
# matcher semantics; runtime matcher behavior remains the responsibility of the
# installed Claude Code version and its authoritative documentation.
#
# Edit-only rule form (Claude Code >= 2.1.261, observed 2026-09-05): startup
# stderr reports that a `Write(path)` deny rule "is not matched by file
# permission checks -- only Edit(path) rules are. Use Edit(...) instead (Edit
# rules cover all file-editing tools)." A live probe confirmed the Write tool
# targeting /tmp is denied by `Edit(//tmp/**)` alone. The formerly paired
# `Write(...)` deny rules were therefore inert and were removed; this suite now
# asserts Edit-rule coverage AND the absence of the redundant Write twins so a
# future re-add is caught.
# ============================================================================

load 'test_helper'

setup() { common_setup; }
teardown() { common_teardown; }

SETTINGS_FILE="${REPO_ROOT}/.claude/settings.json"
EXPECTED_RULES_JSON='[
  "Edit(/.claude/logs/**)",
  "Edit(//home/appuser/.claude/**/*.jsonl)",
  "Edit(/research/*/logs/**)"
]'
# The Write twins that used to accompany each Edit rule. Inert under CC
# >= 2.1.261 (see header); asserted ABSENT rather than present.
REMOVED_WRITE_RULES_JSON='[
  "Write(/.claude/logs/**)",
  "Write(//home/appuser/.claude/**/*.jsonl)",
  "Write(/research/*/logs/**)",
  "Write(//tmp/**)",
  "Write(.env)",
  "Write(.env.*)",
  "Write(environment_settings.txt)",
  "Write(.claude/hooks/*)"
]'
EXPECTED_PATHS=(
    '/.claude/logs/**'
    '//home/appuser/.claude/**/*.jsonl'
    '/research/*/logs/**'
)
NEAR_RULES_JSON='[
  "Read(/.claude/logs/**)",
  "Read(//home/appuser/.claude/**/*.jsonl)",
  "Edit(.claude/logs/**)",
  "Write(research/*/logs/**)",
  "Edit(/.claude/./logs/**)",
  "Write(//home/appuser//.claude/**/*.jsonl)",
  "Edit(/research/*/./logs/**)",
  "Read(/.claude/././logs/**)",
  "Write(//home/appuser/././.claude/**/*.jsonl)",
  "Edit(/research/*/././logs/**)"
]'
# Environment-disclosure Bash deny rules, added by the user on 2026-09-26
# (SafetyHookHardening session). They are the tool-permission layer for
# shell commands that print environment values; the in-script layer is the
# run_with_capture.sh environment-secret print scan. Pinned as exact strings:
# a reworded or broadened rule should surface here as a failing test to
# review, not pass silently.
ENV_DISCLOSURE_RULES_JSON='[
  "Bash(env)",
  "Bash(printenv*)",
  "Bash(export -p*)",
  "Bash(set)",
  "Bash(cat /proc/*)"
]'
NON_MEMBER_RULES_JSON='[
  "Read(/archive/.claude/logs/**)",
  "Read(/archive/home/appuser/.claude/**/*.jsonl)",
  "Read(/archive/research/project/logs/**)",
  "Read(//home/appuser/.claude/cache/example.jsonl.bak)",
  "Read(/ordinary/path/**)"
]'

# Select any permission rule targeting one of the three protected path families.
# Structural segment normalization removes every repeated slash and /./ segment
# while preserving whether the original path had zero, one, or two leading
# slashes. Direct anchors exclude unrelated archive/lookalike paths; exact set
# equality below then rejects every selected variant except the six approved
# strings.
PROTECTED_FAMILY_FILTER='def normalized_path:
    (if startswith("//") then "//" elif startswith("/") then "/" else "" end) as $anchor
    | (if startswith("//") then .[2:] elif startswith("/") then .[1:] else . end) as $rest
    | ($rest | split("/") | map(select(. != "" and . != ".")) | join("/")) as $body
    | $anchor + $body;
  [.permissions.deny[]
   | (capture("^(?<tool>[^()]+)\\((?<path>.*)\\)$")?) as $rule
   | select($rule != null)
   | ($rule.path | normalized_path) as $path
   | select(
       ($path | test("^(//|/)?\\.claude/logs(/|$)"))
       or (($path | test("^(//|/)?home/appuser/\\.claude(/|$)")) and ($path | test("\\.jsonl$")))
       or ($path | test("^(//|/)?research/[^/]+/logs(/|$)"))
     )
   | .] | sort'

@test "settings permissions: checked-in settings JSON parses" {
    run jq empty "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: all three approved Edit deny rules are present" {
    run jq -e --argjson expected "${EXPECTED_RULES_JSON}" '
        . as $settings
        | all($expected[]; . as $rule | $settings.permissions.deny | index($rule) != null)
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: obsolete non-recursive log rules are absent" {
    run jq -e '
        [.permissions.deny[]
         | select(. == "Edit(.claude/logs/*)" or . == "Write(.claude/logs/*)")]
        | length == 0
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: protected log and transcript subset is exactly three rules" {
    run jq -e \
        --argjson expected "${EXPECTED_RULES_JSON}" \
        "${PROTECTED_FAMILY_FILTER} == (\$expected | sort)" \
        "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: classifier includes near-rules and excludes lookalikes" {
    run jq -n -e \
        --argjson expected "${EXPECTED_RULES_JSON}" \
        --argjson extras "${NEAR_RULES_JSON}" \
        --argjson nonmembers "${NON_MEMBER_RULES_JSON}" \
        "{permissions: {deny: (\$expected + \$extras + \$nonmembers)}}
         | ${PROTECTED_FAMILY_FILTER} as \$observed
         | (all(\$extras[]; . as \$rule | \$observed | index(\$rule) != null))
           and (all(\$nonmembers[]; . as \$rule | \$observed | index(\$rule) == null))
           and (\$observed != (\$expected | sort))"
    assert_success
}

@test "settings permissions: every approved path has an exact Edit variant and no Write twin" {
    # Edit(path) is the only form the 2.1.261+ file-permission matcher honors,
    # and it covers all file-editing tools (Write included). The exact-set
    # equality below therefore requires the Edit rule AND rejects a re-added
    # Write twin for the same path.
    local path
    for path in "${EXPECTED_PATHS[@]}"; do
        run jq -e --arg path "${path}" '
            ["Edit(" + $path + ")"] as $expected
            | [.permissions.deny[]
               | select(. == "Edit(" + $path + ")" or . == "Write(" + $path + ")")]
            == $expected
        ' "${SETTINGS_FILE}"
        assert_success
    done
}

@test "settings permissions: tmp deny is the Edit rule only (Write twin removed)" {
    run jq -e '
        [.permissions.deny[]
         | select(. == "Edit(//tmp/**)" or . == "Write(//tmp/**)")]
        == ["Edit(//tmp/**)"]
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: inert Write(...) deny twins are absent" {
    # Under CC >= 2.1.261 these are ignored by the file-permission matcher and
    # emit a startup warning; their Edit(...) counterparts carry the protection.
    run jq -e --argjson removed "${REMOVED_WRITE_RULES_JSON}" '
        . as $settings
        | all($removed[]; . as $rule | $settings.permissions.deny | index($rule) == null)
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: credential and hook surfaces keep Edit deny coverage" {
    # The Edit twins that must survive the Write-rule removal.
    run jq -e '
        . as $settings
        | ["Edit(.env)", "Edit(.env.*)", "Edit(environment_settings.txt)",
           "Edit(.claude/hooks/*)"]
        | all(. as $rule | $settings.permissions.deny | index($rule) != null)
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: no Write(...) deny rule of any form remains" {
    # Broad backstop: the matcher ignores every Write(path) deny rule, so any
    # occurrence is dead configuration that reads as protection.
    run jq -e '
        [.permissions.deny[] | select(startswith("Write("))] | length == 0
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: environment-disclosure Bash deny rules are present" {
    # Static contract only (see header): this proves the five checked-in
    # strings exist in the deny list, not how Claude Code's matcher applies
    # them. CLAUDE.md § Credential & Secret Protection states the policy these
    # rules back (scripts never print environment or credential values).
    run jq -e --argjson expected "${ENV_DISCLOSURE_RULES_JSON}" '
        . as $settings
        | all($expected[]; . as $rule | $settings.permissions.deny | index($rule) != null)
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: environment-disclosure rules are deny-only, never allow-listed" {
    # An identical string in the allow list would contradict the deny entry
    # and make the intended policy ambiguous to a reader of the file.
    run jq -e --argjson expected "${ENV_DISCLOSURE_RULES_JSON}" '
        . as $settings
        | all($expected[]; . as $rule | ($settings.permissions.allow // []) | index($rule) == null)
    ' "${SETTINGS_FILE}"
    assert_success
}

@test "settings permissions: attribution is never the boolean form" {
    # Claude Code 2.1.281 added "attribution": false, but older CLIs (including
    # the rollback target) skip a settings file that holds the boolean form,
    # silently dropping every hook registration and deny rule. Keep the object
    # form. Absent key reads as null and passes. See FRAMEWORK_INTEGRATION_CHECKLIST.md CC9.
    run jq -e '(.attribution | type) != "boolean"' "${SETTINGS_FILE}"
    assert_success
}
