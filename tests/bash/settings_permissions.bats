#!/usr/bin/env bats
# ============================================================================
# Static contract tests for checked-in Claude Code permission rules.
#
# This suite validates the checked-in configuration contract in
# .claude/settings.json. It does NOT dynamically prove Claude Code permission-
# matcher semantics; runtime matcher behavior remains the responsibility of the
# installed Claude Code version and its authoritative documentation.
# ============================================================================

load 'test_helper'

setup() { common_setup; }
teardown() { common_teardown; }

SETTINGS_FILE="${REPO_ROOT}/.claude/settings.json"
EXPECTED_RULES_JSON='[
  "Edit(/.claude/logs/**)",
  "Write(/.claude/logs/**)",
  "Edit(//home/appuser/.claude/**/*.jsonl)",
  "Write(//home/appuser/.claude/**/*.jsonl)",
  "Edit(/research/*/logs/**)",
  "Write(/research/*/logs/**)"
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

@test "settings permissions: all six approved deny rules are present" {
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

@test "settings permissions: protected log and transcript subset is exactly six rules" {
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

@test "settings permissions: every approved path has exact Edit and Write variants" {
    local path
    for path in "${EXPECTED_PATHS[@]}"; do
        run jq -e --arg path "${path}" '
            ["Edit(" + $path + ")", "Write(" + $path + ")"] as $expected
            | [.permissions.deny[] | select(. == $expected[0] or . == $expected[1])] | sort
            == ($expected | sort)
        ' "${SETTINGS_FILE}"
        assert_success
    done
}

@test "settings permissions: existing tmp Edit and Write deny rules remain present" {
    run jq -e '
        . as $settings
        | ["Edit(//tmp/**)", "Write(//tmp/**)"]
        | all(. as $rule | $settings.permissions.deny | index($rule) != null)
    ' "${SETTINGS_FILE}"
    assert_success
}
